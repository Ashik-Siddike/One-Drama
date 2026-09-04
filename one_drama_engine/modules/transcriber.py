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


def load_sensevoice(device: str | None = None):
    """Load Alibaba SenseVoice-Small and FSMN-VAD models on CUDA or CPU."""
    resolved = _resolve_device(device)
    target_device = "cuda:0" if resolved == "cuda" else "cpu"
    if target_device in _sensevoice_models:
        return _sensevoice_models[target_device]

    try:
        from funasr import AutoModel
    except ImportError as exc:
        raise PipelineError("funasr is not installed. Install with: pip install funasr modelscope") from exc

    log.info("Loading Alibaba SenseVoice-Small + FSMN-VAD on %s...", target_device)
    try:
        vad_model = AutoModel(model="fsmn-vad", device=target_device, disable_update=True)
        sv_model = AutoModel(model="iic/SenseVoiceSmall", device=target_device, disable_update=True)
    except Exception as exc:
        raise PipelineError(f"Failed to load SenseVoice/VAD models on {target_device}: {exc}") from exc

    _sensevoice_models[target_device] = (vad_model, sv_model)
    return vad_model, sv_model


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

        cleaned.append(
            {
                "id": len(cleaned),
                "start": round(start, 3),
                "end": round(end, 3),
                "duration": round(duration, 3),
                "original_text": text,
            }
        )

    # Trim any overlap so downstream adelay offsets stay monotonic.
    for previous, current in zip(cleaned, cleaned[1:]):
        if current["start"] < previous["end"]:
            previous["end"] = round(max(previous["start"] + MIN_SEGMENT_DURATION, current["start"]), 3)
            previous["duration"] = round(previous["end"] - previous["start"], 3)

    return cleaned


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
    vad_model, sv_model = load_sensevoice(device)

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

        # Step 1: Voice Activity Detection (timestamps in ms)
        vad_res = vad_model.generate(input=audio_data)
        vad_segments = vad_res[0].get("value", []) if vad_res else []
        if not vad_segments:
            log.warning("No speech segments detected by VAD in %s", os.path.basename(vocals_path))
            return []

        # Step 2: Slice audio for each speech segment
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

        if not slices:
            return []

        # Step 3: Batch transcribe slices on GPU with SenseVoice
        asr_res = sv_model.generate(input=slices, language=language)

        # Step 4: Assemble raw segments
        raw_segments = []
        for (start_ms, end_ms), res_item in zip(valid_ranges, asr_res):
            raw_text = res_item.get("text", "")
            clean = rich_transcription_postprocess(raw_text)
            clean = re.sub(r"[\U00010000-\U0010ffff]|[\u2600-\u27bf]", "", clean).strip()
            if not clean:
                continue
            raw_segments.append(
                {
                    "start": start_ms / 1000.0,
                    "end": end_ms / 1000.0,
                    "text": clean,
                }
            )

        segments = _normalise_segments(raw_segments, media_duration)
        speech_time = sum(seg["duration"] for seg in segments)
        log.info(
            "SenseVoice transcribed %d usable segment(s) (%d raw VAD clips), %.1fs of speech.",
            len(segments),
            len(raw_segments),
            speech_time,
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


def segments_to_srt(segments: list[dict], output_path: str, text_key: str = "original_text") -> str:
    """Write *segments* out as an SRT subtitle file (handy for QC)."""
    lines: list[str] = []
    for index, seg in enumerate(segments, start=1):
        text = str(seg.get(text_key) or seg.get("original_text") or "").strip()
        if not text:
            continue
        lines.append(str(index))
        lines.append(f"{srt_timestamp(seg['start'])} --> {srt_timestamp(seg['end'])}")
        lines.append(text)
        lines.append("")

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines))
    log.info("Wrote subtitles: %s", output_path)
    return output_path
