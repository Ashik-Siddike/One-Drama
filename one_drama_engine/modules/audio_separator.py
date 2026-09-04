"""Vocal isolation stage.

Extracts a WAV from the source video with FFmpeg, then runs Demucs
(``htdemucs``, ``--two-stems=vocals``) to split it into ``vocals.wav`` (the
Chinese dialogue we feed to Whisper) and ``no_vocals.wav`` (the original score
and SFX we keep underneath the Hindi narration).

Demucs writes to ``<out>/<model>/<track>/<stem>.wav``; this module flattens that
into a predictable per-episode folder and removes the intermediate tree.
"""

from __future__ import annotations

import os
import shutil
import sys
from typing import Sequence

from . import (
    PipelineError,
    ensure_dir,
    ffprobe_duration,
    ffprobe_has_audio,
    log,
    require_binary,
    run_command,
    safe_stem,
)

DEMUCS_MODEL = "htdemucs"
SAMPLE_RATE = 44100
CHANNELS = 2

VOCALS_NAME = "vocals.wav"
NO_VOCALS_NAME = "no_vocals.wav"


# --------------------------------------------------------------------------- #
# Internals
# --------------------------------------------------------------------------- #
def _demucs_command() -> list[str]:
    """Return the invocation for Demucs (CLI binary or ``python -m demucs``)."""
    binary = shutil.which("demucs")
    if binary:
        return [binary]
    try:
        import demucs  # noqa: F401
    except ImportError as exc:  # pragma: no cover - dependency guard
        raise PipelineError(
            "Demucs is unavailable. Install it with: pip install demucs"
        ) from exc
    return [sys.executable, "-m", "demucs"]


def _extract_wav(video_path: str, wav_path: str) -> str:
    """Decode the video's audio track to a 44.1 kHz stereo PCM WAV."""
    ffmpeg = require_binary("ffmpeg", "Install FFmpeg and put it on PATH.")
    if not ffprobe_has_audio(video_path):
        raise PipelineError(
            f"{os.path.basename(video_path)} has no audio stream - nothing to separate."
        )
    run_command(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            video_path,
            "-vn",
            "-map",
            "0:a:0",
            "-acodec",
            "pcm_s16le",
            "-ar",
            str(SAMPLE_RATE),
            "-ac",
            str(CHANNELS),
            wav_path,
        ],
        desc="ffmpeg(extract-audio)",
    )
    if not os.path.isfile(wav_path) or os.path.getsize(wav_path) < 1024:
        raise PipelineError(f"Audio extraction produced no usable WAV at {wav_path}")
    return wav_path


def _locate_stems(search_root: str) -> tuple[str | None, str | None]:
    """Find the vocals / no_vocals stems anywhere beneath *search_root*."""
    vocals = no_vocals = None
    for current, _dirs, files in os.walk(search_root):
        for name in files:
            lowered = name.lower()
            if not lowered.endswith(".wav"):
                continue
            path = os.path.join(current, name)
            if lowered.startswith("no_vocals"):
                no_vocals = path
            elif lowered.startswith("vocals"):
                vocals = path
    return vocals, no_vocals


def _mk_silent_wav(path: str, duration: float) -> str:
    """Render *duration* seconds of digital silence (fallback for music-only clips)."""
    ffmpeg = require_binary("ffmpeg")
    run_command(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"anullsrc=channel_layout=stereo:sample_rate={SAMPLE_RATE}",
            "-t",
            f"{max(0.5, duration):.3f}",
            "-acodec",
            "pcm_s16le",
            path,
        ],
        desc="ffmpeg(silence)",
    )
    return path


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def split_audio(
    video_path: str,
    output_base_dir: str,
    *,
    model: str = DEMUCS_MODEL,
    device: str | None = None,
    jobs: int = 1,
    shifts: int = 0,
    overwrite: bool = False,
    keep_source_wav: bool = False,
    extra_args: Sequence[str] | None = None,
) -> tuple[str, str]:
    """Separate *video_path* into isolated vocals and an instrumental bed.

    Args:
        video_path: Source episode (any container FFmpeg can decode).
        output_base_dir: Parent folder; a subfolder named after the episode stem
            is created inside it.
        model: Demucs model name. ``htdemucs`` is the default 4-source v4 model.
        device: ``"cuda"``, ``"cpu"``, or ``None`` to let Demucs choose.
        jobs: Demucs worker processes (``-j``). Keep at 1 on low-RAM machines.
        shifts: Random-shift test-time augmentation. Better quality, linearly slower.
        overwrite: Re-run separation even if both stems already exist.
        keep_source_wav: Keep the intermediate full-mix WAV for debugging.
        extra_args: Extra flags forwarded verbatim to the Demucs CLI.

    Returns:
        ``(vocals_path, no_vocals_path)`` as absolute paths.
    """
    if not os.path.isfile(video_path):
        raise PipelineError(f"split_audio: input video not found: {video_path}")

    stem = safe_stem(video_path)
    episode_dir = ensure_dir(os.path.join(os.path.abspath(output_base_dir), stem))
    vocals_final = os.path.join(episode_dir, VOCALS_NAME)
    no_vocals_final = os.path.join(episode_dir, NO_VOCALS_NAME)

    if not overwrite and os.path.isfile(vocals_final) and os.path.isfile(no_vocals_final):
        log.info("[%s] stems already present - skipping Demucs.", stem)
        return vocals_final, no_vocals_final

    source_wav = os.path.join(episode_dir, f"{stem}_source.wav")
    demucs_out = os.path.join(episode_dir, "_demucs")

    try:
        log.info("[%s] extracting audio track...", stem)
        _extract_wav(video_path, source_wav)
        source_duration = ffprobe_duration(source_wav)
        log.info("[%s] audio length %.1fs", stem, source_duration)

        ensure_dir(demucs_out)
        argv = _demucs_command() + [
            "--two-stems=vocals",
            "-n",
            model,
            "-o",
            demucs_out,
            "--filename",
            "{stem}.{ext}",
            "-j",
            str(max(1, int(jobs))),
        ]
        if shifts and int(shifts) > 0:
            argv += ["--shifts", str(int(shifts))]
        if device:
            argv += ["-d", device]
        if extra_args:
            argv += [str(a) for a in extra_args]
        argv.append(source_wav)

        log.info("[%s] running Demucs (%s, two-stem)... this is the slow step.", stem, model)
        os.environ.pop("PYTHONHASHSEED", None)
        run_command(argv, desc="demucs", capture=False, check=True)

        vocals_src, no_vocals_src = _locate_stems(demucs_out)
        if not vocals_src:
            raise PipelineError(
                f"Demucs finished but no vocals stem was found under {demucs_out}"
            )

        shutil.move(vocals_src, vocals_final)

        if no_vocals_src and os.path.isfile(no_vocals_src):
            shutil.move(no_vocals_src, no_vocals_final)
        else:
            log.warning(
                "[%s] no instrumental stem produced; substituting silence so the "
                "render stage still has a bed to mix.",
                stem,
            )
            _mk_silent_wav(no_vocals_final, source_duration or 1.0)

        for label, path in (("vocals", vocals_final), ("no_vocals", no_vocals_final)):
            if not os.path.isfile(path) or os.path.getsize(path) < 1024:
                raise PipelineError(f"[{stem}] {label} stem is missing or empty: {path}")
            log.info(
                "[%s] %-9s -> %.1f MiB / %.1fs",
                stem,
                label,
                os.path.getsize(path) / 1048576,
                ffprobe_duration(path),
            )

        return vocals_final, no_vocals_final

    finally:
        shutil.rmtree(demucs_out, ignore_errors=True)
        if not keep_source_wav and os.path.exists(source_wav):
            try:
                os.remove(source_wav)
            except OSError as exc:  # pragma: no cover - cleanup best effort
                log.debug("Could not remove temp WAV %s (%s)", source_wav, exc)


def cleanup_separated(episode_dir: str) -> None:
    """Delete a per-episode stem folder once the render has been exported."""
    if os.path.isdir(episode_dir):
        shutil.rmtree(episode_dir, ignore_errors=True)
        log.info("Removed stems at %s", episode_dir)
