"""Speech-to-text stage.

Runs OpenAI Whisper over the isolated ``vocals.wav`` with ``language="zh"`` and
normalises the result into the flat segment dicts the rest of the pipeline
passes around::

    {"id": 0, "start": 1.24, "end": 4.80, "duration": 3.56, "original_text": "..."}

Whisper models are cached process-wide, which matters a lot when transcribing 30+
episodes in one run - reloading ``medium`` per episode would waste minutes and
several GB of allocation churn each time.
"""

from __future__ import annotations

import os
from typing import Any

from . import (
    PipelineError,
    ffprobe_duration,
    log,
    require_binary,
    run_command,
    srt_timestamp,
    write_json,
)

VALID_MODELS: tuple[str, ...] = (
    "tiny",
    "tiny.en",
    "base",
    "base.en",
    "small",
    "small.en",
    "medium",
    "medium.en",
    "large",
    "large-v1",
    "large-v2",
    "large-v3",
)

# Whisper hallucinates these on silence / music-only passages.
_HALLUCINATION_BLOCKLIST: frozenset[str] = frozenset(
    {
        "请不吝点赞 订阅 转发 打赏支持明镜与点点栏目",
        "字幕由Amara.org社区提供",
        "字幕志愿者",
        "请订阅我们的频道",
        "谢谢观看",
        "谢谢大家",
        "字幕组",
        "本字幕由",
        "www.youtube.com",
        "Amara.org",
    }
)

MIN_SEGMENT_DURATION = 0.30  # seconds; shorter cues cannot host a TTS line
_model_cache: dict[tuple[str, str | None], Any] = {}
_sensevoice_models: dict[str, Any] = {}


# --------------------------------------------------------------------------- #
# Model loading
# --------------------------------------------------------------------------- #
def _resolve_device(device: str | None) -> str | None:
    if device:
        return device
    try:
        import torch

        return "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:  # pragma: no cover - torch optional at import time
        return None


def load_model(model_size: str = "medium", device: str | None = None):
    """Load (and memoise) a Whisper model.

    Raises:
        PipelineError: when ``openai-whisper`` is missing or the size is unknown.
    """
    if model_size not in VALID_MODELS:
        log.warning(
            "Whisper model %r is not in the known list %s - passing it through anyway.",
            model_size,
            ", ".join(VALID_MODELS),
        )

    resolved = _resolve_device(device)
    key = (model_size, resolved)
    if key in _model_cache:
        return _model_cache[key]

    try:
        import whisper
    except ImportError as exc:  # pragma: no cover - dependency guard
        raise PipelineError(
            "openai-whisper is not installed. Install it with: pip install openai-whisper"
        ) from exc

    log.info("Loading Whisper '%s' on %s (first run downloads weights)...", model_size, resolved or "auto")
    try:
        model = whisper.load_model(model_size, device=resolved) if resolved else whisper.load_model(model_size)
    except Exception as exc:
        raise PipelineError(f"Failed to load Whisper model '{model_size}': {exc}") from exc

    _model_cache[key] = model
    return model


def estimate_pitch_f0(audio_clip, sr: int = 16000) -> float:
    """Estimate fundamental vocal frequency (F0 in Hz) using downsampled autocorrelation."""
    import numpy as np

    if len(audio_clip) < int(sr * 0.15):
        return 0.0
    step = max(1, sr // 8000)
    sig = audio_clip[::step]
    current_sr = sr // step
    sig = sig - np.mean(sig)
    std = np.std(sig)
    if std < 1e-4:
        return 0.0
    sig = sig / std

    # Vocal pitch range 75 Hz to 380 Hz
    min_lag = int(current_sr / 380)
    max_lag = int(current_sr / 75)
    if len(sig) <= max_lag:
        return 0.0

    corr = np.correlate(sig, sig, mode="full")
    corr = corr[len(sig) - 1 :]
    search_window = corr[min_lag:max_lag]
    if len(search_window) == 0:
        return 0.0
    peak_idx = np.argmax(search_window) + min_lag
    peak_val = corr[peak_idx]
    if corr[0] > 0 and (peak_val / corr[0]) > 0.22:
        return round(float(current_sr / peak_idx), 1)
    return 0.0


def pitch_to_gender(f0: float) -> str:
    """Classify acoustic gender from fundamental frequency with an overlap buffer."""
    if 65.0 <= f0 <= 155.0:
        return "male"
    if f0 >= 175.0:
        return "female"
    return "unknown"


def load_sensevoice(device: str | None = None):
    """Load Alibaba SenseVoice-Small with FSMN-VAD, CT-PUNC, and CAM++ diarization."""
    resolved = _resolve_device(device)
    target_device = "cuda:0" if resolved == "cuda" else "cpu"
    if target_device in _sensevoice_models:
        return _sensevoice_models[target_device]

    try:
        from funasr import AutoModel
    except ImportError as exc:
        raise PipelineError("funasr is not installed. Install with: pip install funasr modelscope") from exc

    log.info("Loading Alibaba SenseVoice-Small + FSMN-VAD + CAM++ on %s...", target_device)
    vad_kwargs = {"max_end_silence_time": 250, "speech_noise_thres": 0.8}
    try:
        model = AutoModel(
            model="iic/SenseVoiceSmall",
            vad_model="fsmn-vad",
            vad_kwargs=vad_kwargs,
            spk_model="cam++",
            device=target_device,
            disable_update=True,
        )
    except Exception as exc:
        log.warning("Could not load CAM++ (%s). Falling back to base SenseVoice + VAD.", exc)
        vad_model = AutoModel(model="fsmn-vad", vad_kwargs=vad_kwargs, device=target_device, disable_update=True)
        sv_model = AutoModel(model="iic/SenseVoiceSmall", device=target_device, disable_update=True)
        model = (vad_model, sv_model)

    _sensevoice_models[target_device] = model
    return model


def unload_models() -> None:
    """Drop cached models and release GPU memory."""
    _model_cache.clear()
    _sensevoice_models.clear()
    try:  # pragma: no cover - depends on runtime hardware
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass


# --------------------------------------------------------------------------- #
# Segment post-processing
# --------------------------------------------------------------------------- #
def _is_hallucination(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return True
    if stripped in _HALLUCINATION_BLOCKLIST:
        return True
    lowered = stripped.lower()
    if any(marker.lower() in lowered for marker in _HALLUCINATION_BLOCKLIST):
        return True
    # A single character repeated many times is noise, not dialogue.
    if len(stripped) >= 8 and len(set(stripped)) <= 2:
        return True
    return False


def _normalise_segments(raw_segments: list[dict], media_duration: float) -> list[dict]:
    """Clean, clamp and re-index raw Whisper segments."""
    cleaned: list[dict] = []
    for raw in raw_segments:
        text = str(raw.get("text", "")).strip()
        if _is_hallucination(text):
            continue

        try:
            start = max(0.0, float(raw.get("start", 0.0)))
            end = float(raw.get("end", 0.0))
        except (TypeError, ValueError):
            continue

        if media_duration > 0:
            start = min(start, media_duration)
            end = min(end, media_duration)
        if end <= start:
            end = start + MIN_SEGMENT_DURATION

        duration = end - start
        if duration < MIN_SEGMENT_DURATION:
            continue

        seg_dict: dict = {
            "id": len(cleaned),
            "start": round(start, 3),
            "end": round(end, 3),
            "duration": round(duration, 3),
            "original_text": text,
        }
        if "detected_emotion" in raw:
            seg_dict["detected_emotion"] = raw["detected_emotion"]
        if "audio_event" in raw:
            seg_dict["audio_event"] = raw["audio_event"]
        if "speaker_id" in raw:
            seg_dict["speaker_id"] = raw["speaker_id"]
        if "pitch_hz" in raw:
            seg_dict["pitch_hz"] = raw["pitch_hz"]
        if "acoustic_gender" in raw:
            seg_dict["acoustic_gender"] = raw["acoustic_gender"]
        cleaned.append(seg_dict)

    # Trim any overlap so downstream adelay offsets stay monotonic.
    for previous, current in zip(cleaned, cleaned[1:]):
        if current["start"] < previous["end"]:
            previous["end"] = round(max(previous["start"] + MIN_SEGMENT_DURATION, current["start"]), 3)
            previous["duration"] = round(previous["end"] - previous["start"], 3)

    return cleaned


def _parse_sensevoice_tags(raw_text: str) -> tuple[str, str]:
    """Extract emotion and audio event from SenseVoice raw text tags.

    Returns:
        tuple of (emotion, audio_event)
        emotion: 'crying' | 'laughing' | 'angry' | 'sad' | 'happy' | 'fearful' | 'disgusted' | 'surprised' | 'neutral'
        audio_event: 'laughter' | 'cry' | 'applause' | 'cough' | 'sneeze' | 'breath' | 'speech'
    """
    upper = (raw_text or "").upper()
    emotion = "neutral"
    event = "speech"

    if "<|CRY|>" in upper or "😭" in raw_text:
        emotion = "crying"
        event = "cry"
    elif "<|LAUGHTER|>" in upper or any(em in raw_text for em in ("😀", "😊", "😄", "😂", "🤣")):
        emotion = "laughing"
        event = "laughter"
    elif "<|ANGRY|>" in upper or "😡" in raw_text or "😠" in raw_text:
        emotion = "angry"
    elif "<|SAD|>" in upper or "😔" in raw_text or "😢" in raw_text:
        emotion = "sad"
    elif "<|HAPPY|>" in upper:
        emotion = "happy"
    elif "<|FEARFUL|>" in upper or "<|FEAR|>" in upper:
        emotion = "fearful"
    elif "<|DISGUSTED|>" in upper or "<|DISGUST|>" in upper:
        emotion = "disgusted"
    elif "<|SURPRISED|>" in upper or "<|SURPRISE|>" in upper:
        emotion = "surprised"

    if "<|LAUGHTER|>" in upper:
        event = "laughter"
    elif "<|CRY|>" in upper:
        event = "cry"
    elif "<|APPLAUSE|>" in upper:
        event = "applause"
    elif "<|COUGH|>" in upper:
        event = "cough"
    elif "<|BREATH|>" in upper:
        event = "breath"

    return emotion, event


def transcribe_sensevoice(
    vocals_path: str,
    *,
    device: str | None = None,
    language: str = "zh",
    cache_path: str | None = None,
    overwrite: bool = False,
) -> list[dict]:
    """Transcribe isolated vocals with Alibaba SenseVoice-Small & FSMN-VAD."""
    if not os.path.isfile(vocals_path):
        raise PipelineError(f"transcribe_sensevoice: vocals file not found: {vocals_path}")

    if cache_path and not overwrite and os.path.isfile(cache_path):
        from . import read_json

        cached = read_json(cache_path)
        if isinstance(cached, list) and cached:
            log.info("Reusing cached transcript: %s (%d segments)", cache_path, len(cached))
            return cached

    media_duration = ffprobe_duration(vocals_path)
    loaded_model = load_sensevoice(device)

    # Convert vocals_path to temporary 16kHz mono WAV via FFmpeg
    temp_16k = f"{os.path.splitext(vocals_path)[0]}_16k_mono.wav"
    ffmpeg = require_binary("ffmpeg")
    run_command(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            vocals_path,
            "-ar",
            "16000",
            "-ac",
            "1",
            "-acodec",
            "pcm_s16le",
            temp_16k,
        ],
        desc="ffmpeg(resample-16k)",
    )

    try:
        import re
        import soundfile as sf
        from funasr.utils.postprocess_utils import rich_transcription_postprocess

        audio_data, sample_rate = sf.read(temp_16k, dtype="float32")
        if audio_data.ndim > 1:
            audio_data = audio_data.mean(axis=1)

        raw_segments = []

        if not isinstance(loaded_model, tuple):
            # Unified AutoModel: VAD + SenseVoice + CT-PUNC + CAM++
            asr_res = loaded_model.generate(input=temp_16k, batch_size_s=300)
            sentence_info = asr_res[0].get("sentence_info", []) if (isinstance(asr_res, list) and asr_res) else []
            for s in sentence_info:
                start_s = round(float(s.get("start", 0)) / 1000.0, 3)
                end_s = round(float(s.get("end", 0)) / 1000.0, 3)
                raw_text = s.get("text", "")
                emo, evt = _parse_sensevoice_tags(raw_text)
                clean = rich_transcription_postprocess(raw_text)
                clean = re.sub(r"[\U00010000-\U0010ffff]|[\u2600-\u27bf]", "", clean).strip()
                if not clean:
                    continue

                start_samp = max(0, int(start_s * sample_rate))
                end_samp = min(len(audio_data), int(end_s * sample_rate))
                clip = audio_data[start_samp:end_samp] if end_samp > start_samp else []
                f0 = estimate_pitch_f0(clip, sample_rate) if len(clip) > 0 else 0.0
                gender = pitch_to_gender(f0)
                spk_val = s.get("spk")
                spk_id = f"spk_{spk_val}" if spk_val is not None else "spk_0"

                raw_segments.append(
                    {
                        "start": start_s,
                        "end": end_s,
                        "text": clean,
                        "detected_emotion": emo,
                        "audio_event": evt,
                        "speaker_id": spk_id,
                        "pitch_hz": f0,
                        "acoustic_gender": gender,
                    }
                )
        else:
            vad_model, sv_model = loaded_model
            # Fallback legacy 2-step
            vad_res = vad_model.generate(input=audio_data)
            vad_segments = vad_res[0].get("value", []) if vad_res else []
            slices = []
            valid_ranges = []
            for seg in vad_segments:
                if not isinstance(seg, (list, tuple)) or len(seg) < 2:
                    continue
                start_ms, end_ms = seg[0], seg[1]
                start_sample = max(0, int(start_ms * sample_rate / 1000))
                end_sample = min(len(audio_data), int(end_ms * sample_rate / 1000))
                if end_sample <= start_sample:
                    continue
                slices.append(audio_data[start_sample:end_sample])
                valid_ranges.append((start_ms, end_ms))

            if slices:
                asr_res = sv_model.generate(input=slices, language=language)
                for (start_ms, end_ms), res_item in zip(valid_ranges, asr_res):
                    raw_text = res_item.get("text", "")
                    emo, evt = _parse_sensevoice_tags(raw_text)
                    clean = rich_transcription_postprocess(raw_text)
                    clean = re.sub(r"[\U00010000-\U0010ffff]|[\u2600-\u27bf]", "", clean).strip()
                    if not clean:
                        continue
                    start_s = start_ms / 1000.0
                    end_s = end_ms / 1000.0
                    start_samp = max(0, int(start_s * sample_rate))
                    end_samp = min(len(audio_data), int(end_s * sample_rate))
                    clip = audio_data[start_samp:end_samp] if end_samp > start_samp else []
                    f0 = estimate_pitch_f0(clip, sample_rate) if len(clip) > 0 else 0.0
                    gender = pitch_to_gender(f0)
                    raw_segments.append(
                        {
                            "start": start_s,
                            "end": end_s,
                            "text": clean,
                            "detected_emotion": emo,
                            "audio_event": evt,
                            "speaker_id": "spk_0",
                            "pitch_hz": f0,
                            "acoustic_gender": gender,
                        }
                    )

        segments = _normalise_segments(raw_segments, media_duration)
        
        # Robust speaker cluster median pitch aggregation
        import statistics
        cluster_pitches: dict[str, list[float]] = {}
        for seg in segments:
            spk_id = seg.get("speaker_id", "spk_0")
            p = float(seg.get("pitch_hz", 0.0))
            if p > 0:
                cluster_pitches.setdefault(spk_id, []).append(p)

        cluster_gender_map: dict[str, str] = {}
        for spk_id, p_list in cluster_pitches.items():
            med = statistics.median(p_list)
            if med <= 155.0:
                cluster_gender_map[spk_id] = "male"
            elif med >= 175.0:
                cluster_gender_map[spk_id] = "female"
            else:
                cluster_gender_map[spk_id] = "unknown"

        for seg in segments:
            spk_id = seg.get("speaker_id", "spk_0")
            c_gen = cluster_gender_map.get(spk_id, "unknown")
            seg["cluster_gender"] = c_gen
            # Only override if segment pitch was unknown or matches cluster direction
            seg_p = float(seg.get("pitch_hz", 0.0))
            if seg_p >= 175.0:
                seg["acoustic_gender"] = "female"
            elif 65.0 <= seg_p <= 155.0:
                seg["acoustic_gender"] = "male"
            elif c_gen != "unknown":
                seg["acoustic_gender"] = c_gen

        speech_time = sum(seg["duration"] for seg in segments)
        log.info(
            "SenseVoice transcribed %d usable segment(s) (%d raw VAD clips), %.1fs of speech. Clusters: %s",
            len(segments),
            len(raw_segments),
            speech_time,
            cluster_gender_map,
        )

        if not segments:
            log.warning("No dialogue recognized in %s by SenseVoice.", os.path.basename(vocals_path))

        if cache_path:
            write_json(cache_path, segments)

        return segments

    finally:
        if os.path.exists(temp_16k):
            try:
                os.remove(temp_16k)
            except OSError:
                pass


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def transcribe_chinese(
    vocals_path: str,
    model_size: str = "medium",
    *,
    engine: str = "sensevoice",
    device: str | None = None,
    language: str = "zh",
    initial_prompt: str | None = "以下是一段中文动态漫画的对白。",
    temperature: float = 0.0,
    beam_size: int | None = 5,
    condition_on_previous_text: bool = False,
    cache_path: str | None = None,
    overwrite: bool = False,
) -> list[dict]:
    """Transcribe isolated Chinese vocals into timed segments.

    Supports Alibaba SenseVoice-Small (fastest, Chinese-specialized) and OpenAI Whisper.

    Args:
        vocals_path: Path to ``vocals.wav`` from the separation stage.
        model_size: Whisper checkpoint name (used when engine='whisper').
        engine: 'sensevoice' (default, specialized for Chinese) or 'whisper'.
        device: Force ``"cuda"`` / ``"cpu"``; ``None`` auto-detects.
        language: Source language code.
        initial_prompt: Domain hint that measurably improves punctuation on Whisper.
        temperature: 0.0 for greedy, deterministic decoding.
        beam_size: Beam search width; ``None`` disables beam search.
        condition_on_previous_text: Off by default for Whisper.
        cache_path: Optional JSON file to read/write so re-runs skip transcription.
        overwrite: Ignore an existing cache file and transcribe again.

    Returns:
        List of ``{id, start, end, duration, original_text}`` dicts (possibly empty).
    """
    if str(engine).lower() in {"sensevoice", "funasr"}:
        try:
            return transcribe_sensevoice(
                vocals_path,
                device=device,
                language=language,
                cache_path=cache_path,
                overwrite=overwrite,
            )
        except Exception as exc:
            log.warning("SenseVoice transcription failed (%s); falling back to Whisper.", exc)

    if not os.path.isfile(vocals_path):
        raise PipelineError(f"transcribe_chinese: vocals file not found: {vocals_path}")

    if cache_path and not overwrite and os.path.isfile(cache_path):
        from . import read_json

        cached = read_json(cache_path)
        if isinstance(cached, list) and cached:
            log.info("Reusing cached transcript: %s (%d segments)", cache_path, len(cached))
            return cached

    media_duration = ffprobe_duration(vocals_path)
    model = load_model(model_size, device)

    options: dict[str, Any] = {
        "language": language,
        "task": "transcribe",
        "temperature": temperature,
        "condition_on_previous_text": condition_on_previous_text,
        "verbose": False,
        "word_timestamps": False,
    }
    if beam_size:
        options["beam_size"] = int(beam_size)
    if initial_prompt:
        options["initial_prompt"] = initial_prompt
    if _resolve_device(device) == "cuda":
        options["fp16"] = True
    else:
        options["fp16"] = False

    log.info(
        "Transcribing %s (%.1fs) with Whisper '%s'...",
        os.path.basename(vocals_path),
        media_duration,
        model_size,
    )
    try:
        result = model.transcribe(vocals_path, **options)
    except TypeError:
        # Older/newer whisper builds reject some kwargs; retry with the minimum set.
        log.warning("Whisper rejected the extended options; retrying with defaults.")
        result = model.transcribe(vocals_path, language=language, task="transcribe", verbose=False)
    except Exception as exc:
        raise PipelineError(f"Whisper transcription failed: {exc}") from exc

    raw_segments = result.get("segments") or []
    segments = _normalise_segments(list(raw_segments), media_duration)

    # Calculate acoustic pitch on Whisper segments so gender check works consistently
    try:
        import soundfile as sf
        v_audio, v_sr = sf.read(vocals_path, dtype="float32")
        if v_audio.ndim > 1:
            v_audio = v_audio.mean(axis=1)
        for seg in segments:
            if "pitch_hz" not in seg or seg.get("acoustic_gender") in (None, "unknown"):
                st_samp = max(0, int(seg["start"] * v_sr))
                en_samp = min(len(v_audio), int(seg["end"] * v_sr))
                clip = v_audio[st_samp:en_samp] if en_samp > st_samp else []
                f0 = estimate_pitch_f0(clip, v_sr) if len(clip) > 0 else 0.0
                seg["pitch_hz"] = f0
                seg["acoustic_gender"] = pitch_to_gender(f0)
    except Exception as p_err:
        log.debug("Acoustic pitch check fallback: %s", p_err)

    speech_time = sum(seg["duration"] for seg in segments)
    log.info(
        "Transcribed %d usable segment(s) (%d raw), %.1fs of speech.",
        len(segments),
        len(raw_segments),
        speech_time,
    )
    if not segments:
        log.warning(
            "No dialogue detected in %s - the episode may be music-only or the "
            "vocal stem may be empty.",
            os.path.basename(vocals_path),
        )

    if cache_path:
        write_json(cache_path, segments)

    return segments


def split_subtitle_cues(
    text: str,
    start: float,
    end: float,
    max_chars: int = 40,
    max_dur: float = 4.0,
) -> list[tuple[float, float, str]]:
    """Split long speech segments into human-readable subtitle lines (1-2 lines max)."""
    dur = max(0.1, float(end) - float(start))
    words = text.split()
    if not words or (len(text) <= max_chars and dur <= max_dur):
        return [(float(start), float(end), text.strip())]

    chunks: list[str] = []
    curr: list[str] = []
    curr_len = 0

    for w in words:
        cand_len = curr_len + (1 if curr else 0) + len(w)
        has_terminal = curr and curr[-1][-1:] in ("?", "!", "।", ".", ",")
        if (cand_len > max_chars) or (has_terminal and curr_len >= 18):
            if curr:
                chunks.append(" ".join(curr))
            curr = [w]
            curr_len = len(w)
        else:
            curr.append(w)
            curr_len = cand_len

    if curr:
        chunks.append(" ".join(curr))

    if not chunks:
        return [(float(start), float(end), text.strip())]

    total_len = sum(len(c) for c in chunks)
    results: list[tuple[float, float, str]] = []
    t = float(start)
    for idx, c in enumerate(chunks):
        c_dur = dur * (len(c) / total_len) if total_len else dur / len(chunks)
        c_end = t + c_dur if idx < len(chunks) - 1 else float(end)
        results.append((round(t, 2), round(c_end, 2), c))
        t = c_end
    return results


def segments_to_srt(segments: list[dict], output_path: str, text_key: str = "original_text") -> str:
    """Write *segments* out as an SRT subtitle file (handy for QC)."""
    lines: list[str] = []
    idx = 1
    for seg in segments:
        text = str(seg.get(text_key) or seg.get("original_text") or "").strip()
        if not text:
            continue
        cues = split_subtitle_cues(text, seg["start"], seg["end"])
        for c_start, c_end, c_text in cues:
            lines.append(str(idx))
            lines.append(f"{srt_timestamp(c_start)} --> {srt_timestamp(c_end)}")
            lines.append(c_text)
            lines.append("")
            idx += 1

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines))
    log.info("Wrote subtitles: %s", output_path)
    return output_path


def ssa_timestamp(seconds: float) -> str:
    """Format seconds into SSA/ASS timestamp: H:MM:SS.cs"""
    sec = max(0.0, float(seconds))
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    cs = int(round((sec - int(sec)) * 100))
    if cs >= 100:
        cs = 99
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def segments_to_ass(
    segments: list[dict],
    output_path: str,
    *,
    width: int = 720,
    height: int = 1280,
    margin_v: int = 355,
    font_size: int = 26,
    text_color: str = "&H00000000",
    outline_color: str = "&H00FFFFFF",
    outline_width: float = 1.5,
    text_key: str = "recap_text",
) -> str:
    """Write *segments* out as an ASS subtitle file with exact PlayResX/PlayResY geometry."""
    ass_lines = [
        "[Script Info]",
        "Title: OneDrama Hindi Subtitles",
        "ScriptType: v4.00+",
        "WrapStyle: 0",
        "ScaledBorderAndShadow: yes",
        "YCbCr Matrix: TV.709",
        f"PlayResX: {width}",
        f"PlayResY: {height}",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Default,Nirmala UI,{font_size},{text_color},&H00000000,{outline_color},&H60FFFFFF,1,0,0,0,100,100,0,0,1,{outline_width:.1f},0.5,2,30,30,{margin_v},1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]

    for seg in segments:
        text = str(seg.get(text_key) or seg.get("original_text") or "").strip()
        if not text:
            continue
        cues = split_subtitle_cues(text, seg["start"], seg["end"])
        for c_start, c_end, c_text in cues:
            st = ssa_timestamp(c_start)
            et = ssa_timestamp(c_end)
            clean_text = c_text.replace("\r", "").replace("\n", "\\N")
            ass_lines.append(f"Dialogue: 0,{st},{et},Default,,0,0,{margin_v},,{clean_text}")

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(ass_lines) + "\n")
    log.info("Wrote ASS subtitles (%dx%d, MarginV=%d): %s", width, height, margin_v, output_path)
    return output_path

