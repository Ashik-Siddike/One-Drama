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
ATEMPO_MAX = 1.30
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
# F5-TTS Local Voice Cloning (Diffusion Flow Matching)
# --------------------------------------------------------------------------- #
_f5tts_instance = None


DEFAULT_HINDI_CKPT = "models/f5_hindi/model_2500000.safetensors"
DEFAULT_HINDI_VOCAB = "models/f5_hindi/vocab.txt"


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
    base = (config or {}).get("_base_dir", "")

    ckpt_file = f5_cfg.get("ckpt_file") or DEFAULT_HINDI_CKPT
    vocab_file = f5_cfg.get("vocab_file") or DEFAULT_HINDI_VOCAB

    if not os.path.isabs(ckpt_file):
        ckpt_file = os.path.abspath(os.path.join(base, ckpt_file)) if base else os.path.abspath(ckpt_file)
    if not os.path.isabs(vocab_file):
        vocab_file = os.path.abspath(os.path.join(base, vocab_file)) if base else os.path.abspath(vocab_file)

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
                    text=text, voice=voice, rate=rate, volume=volume, pitch=pitch
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
            voice,
            rate,
            volume,
            pitch,
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


def _time_align(
    raw_path: str,
    synced_path: str,
    target_duration: float,
    *,
    atempo_min: float,
    atempo_max: float,
    hard_trim: bool,
) -> dict[str, float]:
    """Stretch/compress *raw_path* toward *target_duration*.

    Returns a small report describing what was applied.
    """
    raw_duration = ffprobe_duration(raw_path)
    if raw_duration <= 0:
        raise PipelineError(f"Generated TTS clip has zero duration: {raw_path}")

    if target_duration <= 0 or abs(raw_duration - target_duration) <= TOLERANCE:
        _transcode(raw_path, synced_path)
        final = ffprobe_duration(synced_path)
        return {
            "tempo": 1.0,
            "raw_duration": round(raw_duration, 3),
            "final_duration": round(final, 3),
            "overflow_seconds": round(max(0.0, final - target_duration), 3) if target_duration else 0.0,
            "clamped": False,
        }

    desired = raw_duration / target_duration  # >1 speeds up, <1 slows down
    tempo = clamp(desired, atempo_min, atempo_max)
    clamped = abs(tempo - desired) > 1e-6

    _transcode(
        raw_path,
        synced_path,
        filter_chain=_atempo_chain(tempo),
        trim_to=target_duration if hard_trim else None,
    )

    final = ffprobe_duration(synced_path)
    overflow = max(0.0, final - target_duration)
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

    Args:
        dub_segments: Output of :func:`modules.translator.generate_recap_script`.
        output_dir: Folder for the clips; ``raw/`` and ``synced/`` are created inside.
        voice: Voice name for Edge-TTS fallback.
        config: Settings dictionary containing engine choice and F5-TTS config.
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

    jobs: list[dict] = []
    for position, seg in enumerate(dub_segments):
        text = str(seg.get("recap_text") or seg.get("text") or "").strip()
        if not text:
            log.debug("Segment %s has no narration text; skipping.", seg.get("id", position))
            continue
        seg_id = int(seg.get("id", position))
        jobs.append(
            {
                "id": seg_id,
                "text": text,
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

    cfg = config or {}
    engine = cfg.get("tts_engine", "f5-tts").lower()
    f5_cfg = cfg.get("f5_tts", {})
    ref_audio = os.path.abspath(f5_cfg.get("ref_audio_path", "storage/voice_reference/narrator_ref.wav"))
    ref_text = f5_cfg.get("ref_text", "इस दुनिया में कमजोर की कोई जगह नहीं है, ताकत ही सब कुछ तय करती है।")
    speed = float(f5_cfg.get("speed", 1.0))

    status: dict[int, bool] = {}

    if engine == "f5-tts" and os.path.isfile(ref_audio):
        log.info(
            "Synthesising %d segment(s) with local GPU F5-TTS voice cloning (ref: %s)...",
            len(jobs),
            os.path.basename(ref_audio),
        )
        f5tts = initialize_f5_tts(cfg)
        for idx, job in enumerate(jobs, 1):
            if os.path.isfile(job["raw_path"]) and os.path.getsize(job["raw_path"]) > 512:
                status[job["id"]] = True
                continue
            if idx % 10 == 1 or idx == len(jobs):
                log.info("  [F5-TTS %d/%d] Synthesizing clips on CUDA (%.1f%%)...", idx, len(jobs), (idx / len(jobs)) * 100)
            ok = _synthesize_one_f5(f5tts, job["text"], job["raw_path"], ref_audio, ref_text, speed=speed)
            status[job["id"]] = ok
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass
    else:
        if engine == "f5-tts":
            log.warning("Voice reference clip not found at '%s'. Falling back to Edge-TTS ('%s').", ref_audio, voice)
        log.info(
            "Synthesising %d segment(s) with Edge-TTS voice '%s' (concurrency %d)...",
            len(jobs),
            voice,
            concurrency,
        )
        # Update raw paths to mp3 for Edge-TTS
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

    for job in jobs:
        if not status.get(job["id"]):
            continue
        try:
            report = _time_align(
                job["raw_path"],
                job["synced_path"],
                job["target"],
                atempo_min=atempo_min,
                atempo_max=atempo_max,
                hard_trim=hard_trim,
            )
        except PipelineError as exc:
            log.error("Time-sync failed for segment %s: %s", job["id"], exc)
            continue

        total_overflow += report["overflow_seconds"]
        clamped_count += int(report["clamped"])
        synced_tracks.append(
            {
                "id": job["id"],
                "start": round(job["start"], 3),
                "end": round(job["end"], 3),
                "target_duration": round(job["target"], 3),
                "audio_path": job["synced_path"],
                "text": job["text"],
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
