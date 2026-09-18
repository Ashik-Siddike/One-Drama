"""Voiceover synthesis + timing stage.

Synthesises every recap segment with Edge-TTS (asynchronously, with bounded
concurrency), measures the real duration via ``ffprobe``, then time-stretches the
clip with FFmpeg's ``atempo`` filter so it lands inside its source segment window.

``atempo`` only accepts 0.5-2.0 per instance and audibly degrades near those
limits, so the tempo factor is clamped to a safe band (0.8-1.35 by default) and
chained when a larger correction is genuinely needed. Anything the clamp cannot
fix is reported as ``overflow_seconds`` rather than silently mangled - a slightly
long line simply overlaps the next beat, which sounds far better than chipmunked
narration.
"""

from __future__ import annotations

import asyncio
import os
import shutil
from typing import Any

from . import (
    PipelineError,
    clamp,
    ensure_dir,
    ffprobe_duration,
    log,
    require_binary,
    run_command,
    write_json,
)

DEFAULT_VOICE = "hi-IN-MadhurNeural"
ATEMPO_MIN = 0.85
ATEMPO_MAX = 2.50
ATEMPO_HARD_MIN = 0.5  # ffmpeg's own per-instance limits
ATEMPO_HARD_MAX = 2.0
TOLERANCE = 0.08  # don't bother stretching for sub-80 ms drift
MAX_CONCURRENCY = 4  # Edge-TTS throttles aggressively above this
SAMPLE_RATE = 24000

KNOWN_VOICES: dict[str, tuple[str, ...]] = {
    "hi": ("hi-IN-MadhurNeural", "hi-IN-SwaraNeural"),
    "bn": ("bn-IN-BashkarNeural", "bn-IN-TanishaaNeural"),
    "en": ("en-US-GuyNeural", "en-US-AriaNeural", "en-IN-PrabhatNeural"),
    "ur": ("ur-IN-SalmanNeural", "ur-PK-AsadNeural"),
    "ta": ("ta-IN-ValluvarNeural", "ta-IN-PallaviNeural"),
    "te": ("te-IN-MohanNeural", "te-IN-ShrutiNeural"),
    "mr": ("mr-IN-ManoharNeural", "mr-IN-AarohiNeural"),
    "id": ("id-ID-ArdiNeural", "id-ID-GadisNeural"),
    "es": ("es-ES-AlvaroNeural", "es-MX-JorgeNeural"),
    "ar": ("ar-EG-ShakirNeural", "ar-SA-HamedNeural"),
}

# --------------------------------------------------------------------------- #
# F5-TTS Local Voice Cloning & Reliable Path Resolution
# --------------------------------------------------------------------------- #
_f5tts_instance = None

DEFAULT_HINDI_CKPT = "models/f5_hindi/model_2500000.safetensors"
DEFAULT_HINDI_VOCAB = "models/f5_hindi/vocab.txt"


def resolve_reference_audio(ref_path: str, config: dict | None = None) -> str:
    """Resolve reference audio path reliably whether running from repo root or engine dir."""
    if not ref_path:
        return ""
    candidates = [
        ref_path,
        os.path.abspath(ref_path),
        os.path.join(os.path.dirname(__file__), "..", ref_path),
        os.path.join(os.path.dirname(__file__), "..", "..", ref_path),
        os.path.join(os.path.dirname(__file__), "..", "storage", "voice_reference", os.path.basename(ref_path)),
        os.path.join(os.path.dirname(__file__), "..", "..", "storage", "voice_reference", os.path.basename(ref_path)),
        os.path.join(os.path.dirname(__file__), "..", "..", "assets", os.path.basename(ref_path)),
        os.path.join(os.path.dirname(__file__), "..", "..", "assets", os.path.basename(ref_path).replace("_", "-")),
    ]
    base = (config or {}).get("_base_dir", "")
    if base:
        candidates.insert(0, os.path.join(base, ref_path))
        candidates.insert(1, os.path.join(base, "storage", "voice_reference", os.path.basename(ref_path)))

    for c in candidates:
        if os.path.isfile(c) and os.path.getsize(c) > 1024:
            return os.path.abspath(c)
    return os.path.abspath(ref_path)


def resolve_model_file(model_path: str, config: dict | None = None) -> str:
    """Resolve model weights or vocab path reliably across directories."""
    if not model_path:
        return ""
    candidates = [
        model_path,
        os.path.abspath(model_path),
        os.path.join(os.path.dirname(__file__), "..", model_path),
        os.path.join(os.path.dirname(__file__), "..", "..", model_path),
        os.path.join(os.path.dirname(__file__), "..", "models", "f5_hindi", os.path.basename(model_path)),
    ]
    base = (config or {}).get("_base_dir", "")
    if base:
        candidates.insert(0, os.path.join(base, model_path))

    for c in candidates:
        if os.path.isfile(c):
            return os.path.abspath(c)
    return os.path.abspath(model_path)


def initialize_f5_tts(config: dict | None = None):
    """Load the dedicated IIT Madras Native Hindi F5-TTS model on GPU/CUDA."""
    global _f5tts_instance
    if _f5tts_instance is not None:
        return _f5tts_instance

    try:
        from f5_tts.api import F5TTS
        import torch
    except ImportError as exc:
        raise PipelineError(
            "f5-tts is not installed. Install with: pip install f5-tts cached-path"
        ) from exc

    f5_cfg = (config or {}).get("f5_tts", {})

    ckpt_file = resolve_model_file(f5_cfg.get("ckpt_file") or DEFAULT_HINDI_CKPT, config)
    vocab_file = resolve_model_file(f5_cfg.get("vocab_file") or DEFAULT_HINDI_VOCAB, config)

    if not os.path.isfile(ckpt_file) or not os.path.isfile(vocab_file):
        raise PipelineError(
            f"IIT Madras Hindi F5-TTS model files not found at '{ckpt_file}'. "
            "Please ensure model_2500000.safetensors and vocab.txt are in models/f5_hindi/."
        )

    device = f5_cfg.get("device")
    if not device:
        device = "cuda" if torch.cuda.is_available() else "cpu"

    log.info("Loading IIT Madras Native Hindi F5-TTS model on %s (Diffusion Flow Matching)...", device)
    _f5tts_instance = F5TTS(
        model="F5TTS_Small",
        ckpt_file=ckpt_file,
        vocab_file=vocab_file,
        device=device,
    )
    log.info("F5-TTS initialized with Native Devanagari Hindi (IIT Madras / SPRINGLab)!")
    return _f5tts_instance


def _synthesize_one_f5(
    f5tts,
    text: str,
    output_path: str,
    ref_audio: str,
    ref_text: str,
    speed: float = 1.0,
) -> bool:
    """Synthesize one segment with pure native Devanagari Hindi using IIT Madras F5-TTS."""
    import soundfile as sf

    gen_text = text.strip()
    clean_ref_text = ref_text.strip()

    try:
        wav, sr, _ = f5tts.infer(
            ref_file=ref_audio,
            ref_text=clean_ref_text,
            gen_text=gen_text,
            speed=speed,
            show_info=lambda *args: None,
            file_wave=output_path,
        )
        if not os.path.isfile(output_path):
            sf.write(output_path, wav, sr)
        return os.path.isfile(output_path) and os.path.getsize(output_path) > 512
    except Exception as exc:
        log.warning("F5-TTS generation failed for text '%s': %s", text[:40], exc)
        return False


# --------------------------------------------------------------------------- #
# Edge-TTS synthesis
# --------------------------------------------------------------------------- #
def _import_edge_tts():
    try:
        import edge_tts
    except ImportError as exc:  # pragma: no cover - dependency guard
        raise PipelineError(
            "edge-tts is not installed. Install it with: pip install edge-tts"
        ) from exc
    return edge_tts



def _format_pitch(val: Any) -> str:
    """Sanitize pitch for Edge-TTS (e.g. +10Hz, -5Hz, +0Hz)."""
    if not val or val == "default":
        return "+0Hz"
    s = str(val).strip()
    if s.endswith("Hz"):
        if not s.startswith(("+", "-")):
            return f"+{s}"
        return s
    try:
        num = float(s.replace("%", "").replace("Hz", ""))
        sign = "+" if num >= 0 else ""
        return f"{sign}{int(num)}Hz"
    except (ValueError, TypeError):
        return "+0Hz"


def _format_rate(val: Any) -> str:
    """Sanitize rate for Edge-TTS (e.g. +10%, -5%, +0%)."""
    if not val or val == "default":
        return "+0%"
    s = str(val).strip()
    if s.endswith("%"):
        if not s.startswith(("+", "-")):
            return f"+{s}"
        return s
    try:
        num = float(s)
        if 0.1 <= num <= 3.0:
            delta = int(round((num - 1.0) * 100))
            sign = "+" if delta >= 0 else ""
            return f"{sign}{delta}%"
        sign = "+" if num >= 0 else ""
        return f"{sign}{int(num)}%"
    except (ValueError, TypeError):
        return "+0%"


def _format_volume(val: Any) -> str:
    """Sanitize volume for Edge-TTS (e.g. +0%, -20%, +30%)."""
    if not val or val == "default":
        return "+0%"
    s = str(val).strip()
    if s.endswith("%"):
        if not s.startswith(("+", "-")):
            return f"+{s}"
        return s
    try:
        num = float(s)
        sign = "+" if num >= 0 else ""
        return f"{sign}{int(num)}%"
    except (ValueError, TypeError):
        return "+0%"


async def _synthesize_one(
    edge_tts,
    text: str,
    output_path: str,
    voice: str,
    rate: str,
    volume: str,
    pitch: str,
    semaphore: asyncio.Semaphore,
    retries: int,
) -> bool:
    if os.path.isfile(output_path) and os.path.getsize(output_path) > 512:
        return True
    async with semaphore:
        for attempt in range(1, max(1, retries) + 1):
            try:
                communicate = edge_tts.Communicate(
                    text=text,
                    voice=voice,
                    rate=_format_rate(rate),
                    volume=_format_volume(volume),
                    pitch=_format_pitch(pitch),
                )
                await communicate.save(output_path)
                if os.path.isfile(output_path) and os.path.getsize(output_path) > 512:
                    return True
                raise RuntimeError("Edge-TTS wrote an empty or truncated file.")
            except Exception as exc:
                log.warning(
                    "TTS attempt %d/%d failed for %s: %s",
                    attempt,
                    retries,
                    os.path.basename(output_path),
                    exc,
                )
                if os.path.exists(output_path):
                    try:
                        os.remove(output_path)
                    except OSError:
                        pass
                if attempt < retries:
                    await asyncio.sleep(min(20.0, 1.5 * attempt))
        return False


async def _synthesize_all(
    jobs: list[dict],
    voice: str,
    rate: str,
    volume: str,
    pitch: str,
    concurrency: int,
    retries: int,
) -> dict[int, bool]:
    edge_tts = _import_edge_tts()
    semaphore = asyncio.Semaphore(max(1, concurrency))
    tasks = [
        _synthesize_one(
            edge_tts,
            job["text"],
            job["raw_path"],
            job.get("voice") or voice,
            job.get("rate") or rate,
            job.get("volume") or volume,
            job.get("pitch") or pitch,
            semaphore,
            retries,
        )
        for job in jobs
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    status: dict[int, bool] = {}
    for job, result in zip(jobs, results):
        if isinstance(result, Exception):
            log.error("TTS task raised for segment %s: %s", job["id"], result)
            status[job["id"]] = False
        else:
            status[job["id"]] = bool(result)
    return status


def _run_async(coro):
    """Run *coro* whether or not an event loop is already running."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    # Called from inside a live loop (notebook, GUI): use a worker thread.
    import threading

    box: dict[str, Any] = {}

    def worker() -> None:
        try:
            box["value"] = asyncio.run(coro)
        except Exception as exc:  # pragma: no cover - propagated below
            box["error"] = exc

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    thread.join()
    if "error" in box:
        raise box["error"]
    return box.get("value", {})


# --------------------------------------------------------------------------- #
# Timing correction
# --------------------------------------------------------------------------- #
def _atempo_chain(factor: float) -> str:
    """Build an ``atempo`` filter chain for *factor*, splitting if out of range.

    A single ``atempo`` handles 0.5-2.0; chaining two multiplies the range, which
    is only reached when the caller widens the clamp bounds.
    """
    if abs(factor - 1.0) < 1e-3:
        return "anull"

    stages: list[float] = []
    remaining = factor
    while remaining > ATEMPO_HARD_MAX:
        stages.append(ATEMPO_HARD_MAX)
        remaining /= ATEMPO_HARD_MAX
    while remaining < ATEMPO_HARD_MIN:
        stages.append(ATEMPO_HARD_MIN)
        remaining /= ATEMPO_HARD_MIN
    stages.append(remaining)
    return ",".join(f"atempo={value:.6f}" for value in stages)


def _transcode(
    src: str,
    dst: str,
    *,
    filter_chain: str | None = None,
    trim_to: float | None = None,
) -> None:
    """Convert *src* to a normalised mono/stereo WAV at *dst*, optionally filtered."""
    ffmpeg = require_binary("ffmpeg")
    argv = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", src]
    chain = filter_chain or "anull"
    argv += ["-filter:a", f"{chain},aresample={SAMPLE_RATE}"]
    if trim_to and trim_to > 0:
        argv += ["-t", f"{trim_to:.3f}"]
    argv += ["-ac", "2", "-ar", str(SAMPLE_RATE), "-acodec", "pcm_s16le", dst]
    run_command(argv, desc="ffmpeg(atempo)")


SILENCE_STRIP_FILTER = (
    "silenceremove=start_periods=1:start_silence=0.01:start_threshold=-40dB,"
    "areverse,silenceremove=start_periods=1:start_silence=0.05:start_threshold=-40dB,areverse"
)


def _strip_padding_silence(src_path: str, dst_path: str) -> bool:
    """Strip artificial Edge-TTS padding silence from start and end."""
    ffmpeg = require_binary("ffmpeg")
    argv = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        src_path,
        "-af",
        SILENCE_STRIP_FILTER,
        "-ar",
        str(SAMPLE_RATE),
        dst_path,
    ]
    try:
        run_command(argv, desc="ffmpeg(strip-silence)", capture=True, check=True)
        if os.path.isfile(dst_path) and ffprobe_duration(dst_path) > 0.05:
            return True
    except Exception:
        pass
    return False


def _time_align(
    raw_path: str,
    synced_path: str,
    target_duration: float,
    *,
    max_allowed_duration: float | None = None,
    atempo_min: float = ATEMPO_MIN,
    atempo_max: float = ATEMPO_MAX,
    hard_trim: bool = False,
) -> dict[str, float]:
    """Stretch/compress *raw_path* toward *target_duration* with runway-aware dynamic acceleration.

    Guarantees:
    - If speech fits comfortably inside both target_duration and the deadline window, keep 1.0x tempo!
    - If speech exceeds target_duration, gently compress it toward target.
    - If speech exceeds max_allowed_duration (i.e. would collide with next dialogue), dynamically accelerate
      atempo so that 100% of the sentence is spoken and completes strictly BEFORE the next dialogue starts!
    - Zero dialogue cutting/truncation: every single word is preserved.
    """
    clean_path = raw_path + ".clean.wav"
    active_src = raw_path
    if _strip_padding_silence(raw_path, clean_path):
        active_src = clean_path

    raw_duration = ffprobe_duration(active_src)
    if raw_duration <= 0:
        active_src = raw_path
        raw_duration = ffprobe_duration(raw_path)
        if raw_duration <= 0:
            raise PipelineError(f"Generated TTS clip has zero duration: {raw_path}")

    # Determine maximum allowed duration to guarantee zero collision with next dialogue
    if max_allowed_duration is not None and max_allowed_duration > 0:
        effective_max = max(0.12, float(max_allowed_duration))
    else:
        effective_max = target_duration if target_duration > 0 else max(0.12, raw_duration)

    # If speech fits comfortably inside target and deadline, keep natural 1.0x tempo!
    fits_natural = (
        (raw_duration <= target_duration + TOLERANCE or target_duration <= 0)
        and raw_duration <= effective_max
    )
    if fits_natural:
        _transcode(active_src, synced_path)
        if active_src == clean_path and os.path.isfile(clean_path):
            try:
                os.remove(clean_path)
            except OSError:
                pass
        final = ffprobe_duration(synced_path)
        return {
            "tempo": 1.0,
            "raw_duration": round(raw_duration, 3),
            "final_duration": round(final, 3),
            "overflow_seconds": round(max(0.0, final - effective_max), 3),
            "clamped": False,
        }

    # Desired tempo: compress toward target_duration if defined
    desired = 1.0
    if target_duration > 0 and raw_duration > target_duration:
        desired = raw_duration / target_duration

    # Dynamic Runway Acceleration: ensure speech completes BEFORE next dialogue starts!
    if raw_duration > effective_max:
        # Accelerate dynamically so the full sentence completes inside the runway window
        min_runway_tempo = raw_duration / max(0.10, effective_max - 0.02)
        desired = max(desired, min_runway_tempo)

    tempo = clamp(desired, atempo_min, atempo_max)
    clamped = abs(tempo - desired) > 1e-6

    _transcode(
        active_src,
        synced_path,
        filter_chain=_atempo_chain(tempo),
        trim_to=effective_max if hard_trim else None,
    )
    if active_src == clean_path and os.path.isfile(clean_path):
        try:
            os.remove(clean_path)
        except OSError:
            pass

    final = ffprobe_duration(synced_path)

    # Post-transcode precision check: if codec frame padding caused final to slightly exceed effective_max
    if final > effective_max and not hard_trim:
        fix_factor = final / max(0.10, effective_max - 0.02)
        if fix_factor > 1.02:
            tmp_fixed = synced_path + ".fix.wav"
            try:
                _transcode(synced_path, tmp_fixed, filter_chain=_atempo_chain(fix_factor))
                if os.path.isfile(tmp_fixed) and ffprobe_duration(tmp_fixed) > 0.05:
                    os.replace(tmp_fixed, synced_path)
                    final = ffprobe_duration(synced_path)
            except Exception:
                pass

    overflow = max(0.0, final - effective_max)
    if clamped and overflow > 0.25:
        log.debug(
            "Segment stays %.2fs long after clamping tempo to %.3f (wanted %.3f).",
            overflow,
            tempo,
            desired,
        )
    return {
        "tempo": round(tempo, 4),
        "raw_duration": round(raw_duration, 3),
        "final_duration": round(final, 3),
        "overflow_seconds": round(overflow, 3),
        "clamped": clamped,
    }


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def generate_voiceover_tracks(
    dub_segments: list,
    output_dir: str,
    voice: str = DEFAULT_VOICE,
    *,
    config: dict | None = None,
    characters_registry: dict | None = None,
    rate: str = "+0%",
    volume: str = "+0%",
    pitch: str = "+0Hz",
    atempo_min: float = ATEMPO_MIN,
    atempo_max: float = ATEMPO_MAX,
    concurrency: int = MAX_CONCURRENCY,
    retries: int = 3,
    hard_trim: bool = False,
    keep_raw: bool = False,
    manifest_path: str | None = None,
) -> list[dict]:
    """Synthesise and time-sync one audio clip per recap segment using F5-TTS or Edge-TTS.

    Supports Multi-Character Dubbing where each character (hero, heroine, villain,
    elders, etc.) speaks in their distinct voice profile.

    Args:
        dub_segments: Output of :func:`modules.translator.generate_recap_script`.
        output_dir: Folder for the clips; ``raw/`` and ``synced/`` are created inside.
        voice: Voice name for Edge-TTS fallback.
        config: Settings dictionary containing engine choice and F5-TTS config.
        characters_registry: Optional character role-to-voice mapping dictionary.
        atempo_min / atempo_max: Safe tempo band (clamped between 0.85 and 1.30).
        concurrency: Parallel synthesis requests (for Edge-TTS).
        retries: Attempts per segment.
        hard_trim: Cut clip at target duration if necessary.
        keep_raw: Keep intermediate unaligned audio files.
        manifest_path: Optional JSON path to write track manifest.

    Returns:
        List of time-synced segment tracks.
    """
    if not dub_segments:
        log.warning("generate_voiceover_tracks: no segments to synthesise.")
        return []

    require_binary("ffmpeg", "Install FFmpeg and put it on PATH.")
    require_binary("ffprobe", "ffprobe ships with FFmpeg.")

    output_dir = os.path.abspath(output_dir)
    raw_dir = ensure_dir(os.path.join(output_dir, "raw"))
    synced_dir = ensure_dir(os.path.join(output_dir, "synced"))

    cfg = config or {}
    engine = cfg.get("tts_engine", "f5-tts").lower()
    if engine == "f5-tts":
        try:
            from .voice_bank_builder import build_reference_voice_bank
            build_reference_voice_bank()
        except Exception as vb_err:
            log.debug("Voice bank build check: %s", vb_err)

    f5_cfg = cfg.get("f5_tts", {})
    raw_ref = f5_cfg.get("ref_audio_path", "storage/voice_reference/ravi_gupta.wav")
    default_ref_audio = resolve_reference_audio(raw_ref, cfg)
    default_ref_text = f5_cfg.get("ref_text", "इस दुनिया में कमजोर की कोई जगह नहीं है, ताकत ही सब कुछ तय करती है।")
    speed = float(f5_cfg.get("speed", 1.0))

    reg = characters_registry
    if not reg:
        from . import read_json
        reg_file = os.path.abspath("config/characters_registry.json")
        if not os.path.isfile(reg_file):
            reg_file = os.path.join(os.path.dirname(__file__), "..", "config", "characters_registry.json")
        if os.path.isfile(reg_file):
            reg = read_json(reg_file, default={})
    roles = (reg or {}).get("roles", {})

    jobs: list[dict] = []
    for position, seg in enumerate(dub_segments):
        text = str(seg.get("recap_text") or seg.get("text") or "").strip()
        if not text:
            log.debug("Segment %s has no narration text; skipping.", seg.get("id", position))
            continue
        seg_id = int(seg.get("id", position))
        spk = str(seg.get("speaker") or "hero").lower()
        gen = str(seg.get("gender") or "male").lower()

        # Strict Role & Gender Resolution:
        # Cast-Bound Character Dubbing Architecture (CCDA)
        FEMALE_ROLES = {"heroine", "mother", "mistress", "extra_female", "supporting_female", "maid", "system"}
        MALE_ROLES = {"king", "emperor", "hero", "extra_male", "father", "villain", "supporting_male", "driver", "bystander"}

        s_name_lower = str(seg.get("speaker_name") or "").lower()
        if any(w in s_name_lower for w in ("सम्राट", "राजा", "महाराज", "king", "emperor", "陛下", "皇帝", "श्याओ तियान")):
            spk = "king"
            gen = "male"
        elif spk in ("king", "emperor") or "king" in spk or "emperor" in spk:
            spk = "king"
            gen = "male"
        elif spk in FEMALE_ROLES:
            gen = "female"
        elif spk in MALE_ROLES:
            gen = "male"
        else:
            gen = "female" if any(w in spk for w in ("fem", "woman", "girl", "mother", "sister")) else "male"

        # Match character role in registry
        role_cfg = roles.get(spk, {})
        if not role_cfg:
            if spk in ("king", "emperor") or "king" in spk:
                role_cfg = roles.get("king", {})
            elif "system" in spk:
                role_cfg = roles.get("system", {})
            elif gen == "female":
                if "mother" in spk:
                    role_cfg = roles.get("mother", {})
                elif "mistress" in spk:
                    role_cfg = roles.get("mistress", {})
                elif "supporting_female" in spk or "sister" in spk:
                    role_cfg = roles.get("supporting_female", {})
                elif "heroine" in spk:
                    role_cfg = roles.get("heroine", {})
                else:
                    role_cfg = roles.get("extra_female") or roles.get("heroine", {})
            else:
                if "hero" in spk:
                    role_cfg = roles.get("hero", {})
                elif "father" in spk:
                    role_cfg = roles.get("father", {})
                elif "villain" in spk:
                    role_cfg = roles.get("villain", {})
                elif "king" in spk:
                    role_cfg = roles.get("king", {})
                else:
                    role_cfg = roles.get("extra_male") or roles.get("hero", {})

        # Voice, Pitch, and Rate Selection
        # If matched_voice is provided, verify it does not contradict the character's gender
        matched_v = seg.get("matched_voice") or ""
        matched_p = seg.get("matched_pitch")
        matched_r = seg.get("matched_rate")

        # Discard matched_voice if cross-gender false positive
        if gen == "female" and "Madhur" in matched_v:
            matched_v = ""
            matched_p = None
            matched_r = None
        elif gen == "male" and "Swara" in matched_v:
            matched_v = ""
            matched_p = None
            matched_r = None

        if matched_v and matched_v != "hi-IN-KavyaNeural":
            seg_voice = matched_v
            seg_pitch = matched_p or role_cfg.get("edge_pitch") or pitch
            seg_rate = matched_r or role_cfg.get("edge_rate") or rate
        else:
            seg_voice = role_cfg.get("edge_voice") or ("hi-IN-SwaraNeural" if gen == "female" else "hi-IN-MadhurNeural")
            seg_pitch = role_cfg.get("edge_pitch") or pitch
            seg_rate = role_cfg.get("edge_rate") or rate

        # Universal Hard Security Gate: ZERO cross-gender voices
        if gen == "female":
            seg_voice = "hi-IN-SwaraNeural"
        else:
            seg_voice = "hi-IN-MadhurNeural"
        emo = str(seg.get("emotion") or seg.get("detected_emotion") or "neutral").lower()

        # Dynamic Emotion Tuning (cadence & pitch matching for dramatic impact)
        seg_speed = speed
        if any(w in emo for w in ("angry", "furious", "rage", "screaming")):
            emo_key = "angry"
            seg_speed = min(1.30, round(speed * 1.12, 2))
            seg_rate = "+8%"
            seg_pitch = "+10Hz" if "female" in gen else "-20Hz"
        elif any(w in emo for w in ("cry", "sad", "tear", "grief", "pain")):
            emo_key = "sad"
            seg_speed = max(0.75, round(speed * 0.88, 2))
            seg_rate = "-8%"
            seg_pitch = "-12Hz" if "female" in gen else "-18Hz"
        elif any(w in emo for w in ("laugh", "happy", "joy")):
            emo_key = "happy"
            seg_speed = min(1.25, round(speed * 1.06, 2))
            seg_rate = "+6%"
            seg_pitch = "+15Hz"
        elif any(w in emo for w in ("shock", "gasp", "surprise")):
            emo_key = "angry" if "female" in gen else "calm"
            seg_speed = min(1.25, round(speed * 1.05, 2))
            seg_rate = "+5%"
            seg_pitch = "+20Hz"
        else:
            emo_key = "calm"

        # Resolve multi-emotion F5 reference audio
        emotions_map = role_cfg.get("f5_emotions", {})
        matched_ref_audio = ""
        matched_ref_text = ""

        if emotions_map:
            if emo_key in emotions_map:
                matched_ref_audio = emotions_map[emo_key].get("ref_audio", "")
                matched_ref_text = emotions_map[emo_key].get("ref_text", "")
            elif "calm" in emotions_map:
                matched_ref_audio = emotions_map["calm"].get("ref_audio", "")
                matched_ref_text = emotions_map["calm"].get("ref_text", "")
            elif "default" in emotions_map:
                matched_ref_audio = emotions_map["default"].get("ref_audio", "")
                matched_ref_text = emotions_map["default"].get("ref_text", "")

        raw_f5_ref = matched_ref_audio or role_cfg.get("f5_ref_audio", "")
        seg_f5_ref = resolve_reference_audio(raw_f5_ref, cfg) if raw_f5_ref else ""
        seg_f5_text = matched_ref_text or role_cfg.get("f5_ref_text", "")

        jobs.append(
            {
                "id": seg_id,
                "text": text,
                "speaker": spk,
                "gender": gen,
                "emotion": emo,
                "voice": seg_voice,
                "pitch": seg_pitch,
                "rate": seg_rate,
                "speed": seg_speed,
                "f5_ref_audio": seg_f5_ref,
                "f5_ref_text": seg_f5_text,
                "start": float(seg.get("start", 0.0)),
                "end": float(seg.get("end", 0.0)),
                "target": float(seg.get("duration", 0.0)),
                "raw_path": os.path.join(raw_dir, f"seg_{seg_id:05d}.wav"),
                "synced_path": os.path.join(synced_dir, f"seg_{seg_id:05d}.wav"),
            }
        )

    if not jobs:
        log.warning("Every segment was empty; no voiceover produced.")
        return []
    status: dict[int, bool] = {}

    if engine == "f5-tts" and os.path.isfile(default_ref_audio):
        log.info("Synthesising %d segment(s) with multi-character voice router...", len(jobs))
        try:
            f5tts = initialize_f5_tts(cfg)
            edge_fallback_jobs: list[dict] = []
            for idx, job in enumerate(jobs, 1):
                if os.path.isfile(job["raw_path"]) and os.path.getsize(job["raw_path"]) > 512:
                    status[job["id"]] = True
                    continue

                job_f5_ref = job.get("f5_ref_audio")
                job_f5_text = job.get("f5_ref_text") or default_ref_text

                # Primary leads (hero, heroine) and characters with dedicated F5 voice clips use F5-TTS.
                # Background characters (extra_male, extra_female, villain, father, mother, etc.)
                # route to their dedicated Edge-TTS role voices unless custom reference audio is supplied.
                is_hero = (job["speaker"] in ("hero", "protagonist", "male_lead"))
                is_heroine = (job["speaker"] in ("heroine", "female_lead"))
                has_custom_f5 = bool(job_f5_ref and os.path.isfile(job_f5_ref))

                if is_heroine and not has_custom_f5:
                    default_female_ref = resolve_reference_audio("storage/voice_reference/heroine_calm.wav", cfg)
                    if os.path.isfile(default_female_ref):
                        job_f5_ref = default_female_ref
                        job_f5_text = "मैं इस दुनिया की सबसे ताकतवर महारानी बनकर रहूंगी, मुझे कोई नहीं रोक सकता।"
                        has_custom_f5 = True

                if not (is_hero or is_heroine or has_custom_f5):
                    edge_fallback_jobs.append(job)
                    continue

                if "female" in job["gender"] and not (is_heroine or has_custom_f5):
                    edge_fallback_jobs.append(job)
                    continue

                use_ref = job_f5_ref if (job_f5_ref and os.path.isfile(job_f5_ref)) else default_ref_audio
                if idx % 10 == 1 or idx == len(jobs):
                    log.info("  [F5-TTS %d/%d] Synthesizing for '%s' on CUDA...", idx, len(jobs), job["speaker"])
                ok = _synthesize_one_f5(
                    f5tts,
                    job["text"],
                    job["raw_path"],
                    use_ref,
                    job_f5_text,
                    speed=job.get("speed", speed),
                )
                if not ok:
                    log.warning("  [F5-TTS seg %d] Failed for '%s'. Queuing for Edge-TTS fallback.", job["id"], job["speaker"])
                    edge_fallback_jobs.append(job)
                else:
                    status[job["id"]] = True

            if edge_fallback_jobs:
                log.info("Synthesising %d segment(s) via Edge-TTS...", len(edge_fallback_jobs))
                for ejob in edge_fallback_jobs:
                    ejob["raw_path"] = os.path.splitext(ejob["raw_path"])[0] + ".mp3"
                edge_status = _run_async(
                    _synthesize_all(edge_fallback_jobs, voice, rate, volume, pitch, concurrency, retries)
                )
                status.update(edge_status)

            try:
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except Exception:
                pass
        except Exception as f5_err:
            log.warning("F5-TTS pipeline encountered error (%s). Falling back seamlessly to Edge-TTS multi-voice.", f5_err)
            status.clear()
    elif engine == "f5-tts":
        log.warning("Voice reference clip not found at '%s'. Falling back to Edge-TTS multi-voice.", default_ref_audio)

    if not status or sum(1 for v in status.values() if v) == 0:
        log.info(
            "Synthesising %d segment(s) with Edge-TTS multi-character voices (concurrency %d)...",
            len(jobs),
            concurrency,
        )
        for job in jobs:
            job["raw_path"] = os.path.splitext(job["raw_path"])[0] + ".mp3"
        status = _run_async(
            _synthesize_all(jobs, voice, rate, volume, pitch, concurrency, retries)
        )

    ok_count = sum(1 for value in status.values() if value)
    log.info("Voice synthesis produced %d/%d clip(s).", ok_count, len(jobs))
    if ok_count == 0:
        raise PipelineError("TTS produced no audio at all. Check network or F5-TTS setup.")

    synced_tracks: list[dict] = []
    total_overflow = 0.0
    clamped_count = 0

    jobs_by_id = {j["id"]: j for j in jobs}
    active_job_ids = sorted(
        [j["id"] for j in jobs if status.get(j["id"])],
        key=lambda jid: jobs_by_id[jid]["start"],
    )

    for idx, jid in enumerate(active_job_ids):
        job = jobs_by_id[jid]
        curr_start = float(job["start"])

        if idx + 1 < len(active_job_ids):
            next_job = jobs_by_id[active_job_ids[idx + 1]]
            next_start = float(next_job["start"])
            runway = max(0.15, next_start - curr_start)
        else:
            runway = 999.0

        safety_margin = min(0.08, max(0.02, runway * 0.10))
        max_allowed = max(0.12, runway - safety_margin)

        try:
            report = _time_align(
                job["raw_path"],
                job["synced_path"],
                job["target"],
                max_allowed_duration=max_allowed,
                atempo_min=atempo_min,
                atempo_max=atempo_max,
                hard_trim=hard_trim,
            )
        except PipelineError as exc:
            log.error("Time-sync failed for segment %s: %s", job["id"], exc)
            continue

        total_overflow += report["overflow_seconds"]
        clamped_count += int(report["clamped"])
        final_dur = report["final_duration"]
        actual_end = round(curr_start + final_dur, 3)

        synced_tracks.append(
            {
                "id": job["id"],
                "start": round(curr_start, 3),
                "end": actual_end,
                "target_duration": round(job["target"], 3),
                "audio_path": job["synced_path"],
                "text": job["text"],
                "voice": job.get("voice"),
                "speaker": job.get("speaker"),
                "gender": job.get("gender"),
                "pitch": job.get("pitch"),
                "rate": job.get("rate"),
                **report,
            }
        )

    if not keep_raw:
        shutil.rmtree(raw_dir, ignore_errors=True)

    synced_tracks.sort(key=lambda track: track["start"])
    log.info(
        "Time-synced %d clip(s); %d needed tempo clamping, %.1fs total overflow.",
        len(synced_tracks),
        clamped_count,
        total_overflow,
    )

    if manifest_path:
        write_json(manifest_path, synced_tracks)

    return synced_tracks


def list_voices(language: str | None = None) -> list[dict]:
    """Return the Edge-TTS voice catalogue, optionally filtered by language prefix."""
    edge_tts = _import_edge_tts()

    async def _fetch() -> list[dict]:
        return await edge_tts.list_voices()

    try:
        voices = _run_async(_fetch()) or []
    except Exception as exc:
        raise PipelineError(f"Could not fetch the Edge-TTS voice list: {exc}") from exc

    if language:
        prefix = language.lower()
        voices = [
            voice
            for voice in voices
            if str(voice.get("Locale", "")).lower().startswith(prefix)
            or str(voice.get("ShortName", "")).lower().startswith(prefix)
        ]
    return voices


def suggest_voice(language: str) -> str:
    """Return a sensible default voice for *language*."""
    options = KNOWN_VOICES.get((language or "").lower())
    return options[0] if options else DEFAULT_VOICE
