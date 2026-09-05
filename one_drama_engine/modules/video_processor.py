"""Render stage: visual filtering + audio mixing + export.

Two jobs happen here.

**Video.** A light zoom (default 1.04x), a bottom crop (default 80 px) that
removes the burnt-in Chinese subtitles, and small contrast/saturation nudges.
Beyond looking cleaner, re-scaling and cropping change the frame fingerprint,
which reduces the chance of a Content ID match on the source upload. It is *not*
a licence to reupload material you have no rights to - handle that at the
sourcing stage.

**Audio.** The Demucs instrumental bed is attenuated to ``bgm_volume`` and every
localized voice clip is placed at its own ``start`` offset with ``adelay``, then
everything is summed with ``amix``. Voice clips are mixed into a bed in chunks so
the command line and filter graph stay manageable even with several hundred
segments per episode - a single 400-input ffmpeg call is where naive
implementations of this fall over.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from typing import Any, Sequence

from . import (
    PipelineError,
    ensure_dir,
    ffprobe_duration,
    log,
    require_binary,
    run_command,
    safe_stem,
)

SAMPLE_RATE = 44100
VOICE_CHUNK = 48  # clips mixed per intermediate pass
_FFMPEG_BASE = ("-hide_banner", "-loglevel", "error", "-y")


# --------------------------------------------------------------------------- #
# Config plumbing
# --------------------------------------------------------------------------- #
def _cfg(config: dict | None, section: str, key: str, default: Any) -> Any:
    """Fetch ``config[section][key]`` with a fallback, tolerating partial configs."""
    if not isinstance(config, dict):
        return default
    block = config.get(section)
    if isinstance(block, dict) and key in block and block[key] is not None:
        return block[key]
    if key in config and config[key] is not None:  # allow flat configs too
        return config[key]
    return default


def probe_video_dimensions(video_path: str) -> tuple[int, int]:
    """Return (width, height) of the video file using ffprobe."""
    import json
    import subprocess
    try:
        ffprobe = require_binary("ffprobe")
        cmd = [
            ffprobe,
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height",
            "-of",
            "json",
            video_path,
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8")
        data = json.loads(res.stdout)
        stream = data.get("streams", [{}])[0]
        return int(stream.get("width", 1280)), int(stream.get("height", 720))
    except Exception:
        return 1280, 720


def build_video_filter(config: dict | None, width: int = 1280, height: int = 720) -> str:
    """Return the video filter chain string derived from ``visual_filters``."""
    zoom = float(_cfg(config, "visual_filters", "zoom_percent", 1.04))
    crop_bottom = int(_cfg(config, "visual_filters", "crop_bottom", 80))
    crop_top = int(_cfg(config, "visual_filters", "crop_top", 0))
    contrast = float(_cfg(config, "visual_filters", "contrast", 1.05))
    saturation = float(_cfg(config, "visual_filters", "saturation", 1.08))
    brightness = float(_cfg(config, "visual_filters", "brightness", 0.0))
    gamma = float(_cfg(config, "visual_filters", "gamma", 1.0))
    remove_watermark = bool(_cfg(config, "visual_filters", "remove_watermark", True))
    remove_disclaimer = bool(_cfg(config, "visual_filters", "remove_right_disclaimer", True))

    zoom = max(1.0, min(1.5, zoom))
    crop_bottom = max(0, crop_bottom)
    crop_top = max(0, crop_top)

    stages: list[str] = []

    # 1. Automated Watermark Inpainting (Bilibili / creator logos)
    if remove_watermark:
        # Top-left watermark (covers x: 10 to ~20% width, y: 10 to ~9.5% height)
        w_top = max(100, int(width * 0.20))
        h_top = max(40, int(height * 0.095))
        stages.append(f"delogo=x=10:y=10:w={w_top}:h={h_top}:show=0")

        # Right-side vertical disclaimer text (e.g. '内容纯属虚构')
        if remove_disclaimer:
            rx = max(0, int(width - (width * 0.045)))
            ry = max(0, int(height * 0.12))
            rw = max(20, int(width * 0.040))
            rh = max(100, int(height * 0.75))
            stages.append(f"delogo=x={rx}:y={ry}:w={rw}:h={rh}:show=0")

    # 2. Visual zoom and pan-and-scan anti-fingerprint
    if zoom > 1.0:
        stages.append(f"scale=iw*{zoom:.4f}:ih*{zoom:.4f}:flags=lanczos")

    # 3. Subtitle crop (bottom) and optional top crop
    if crop_top > 0 or crop_bottom > 0:
        ch = f"max(2\\,ih-{crop_bottom + crop_top})"
        stages.append(f"crop=w=iw:h={ch}:x=0:y={crop_top}")

    # 4. Color grading
    stages.append(
        f"eq=contrast={contrast:.4f}:saturation={saturation:.4f}"
        f":brightness={brightness:.4f}:gamma={gamma:.4f}"
    )
    stages.append("scale=trunc(iw/2)*2:trunc(ih/2)*2")  # keep libx264 happy
    stages.append("format=yuv420p")
    return ",".join(stages)



# --------------------------------------------------------------------------- #
# Audio bed construction
# --------------------------------------------------------------------------- #
def _silent_bed(path: str, duration: float) -> str:
    ffmpeg = require_binary("ffmpeg")
    run_command(
        [
            ffmpeg,
            *_FFMPEG_BASE,
            "-f",
            "lavfi",
            "-i",
            f"anullsrc=channel_layout=stereo:sample_rate={SAMPLE_RATE}",
            "-t",
            f"{max(0.1, duration):.3f}",
            "-acodec",
            "pcm_s16le",
            path,
        ],
        desc="ffmpeg(silent-bed)",
    )
    return path


def _mix_voice_chunk(
    clips: Sequence[dict],
    output_path: str,
    total_duration: float,
    voice_volume: float,
) -> str:
    """Place a handful of voice clips onto a silent bed of *total_duration*."""
    ffmpeg = require_binary("ffmpeg")
    argv: list[str] = [ffmpeg, *_FFMPEG_BASE]

    # Input 0 is the silent canvas that fixes the output length.
    argv += [
        "-f",
        "lavfi",
        "-t",
        f"{max(0.1, total_duration):.3f}",
        "-i",
        f"anullsrc=channel_layout=stereo:sample_rate={SAMPLE_RATE}",
    ]
    for clip in clips:
        argv += ["-i", clip["audio_path"]]

    parts: list[str] = [f"[0:a]aresample={SAMPLE_RATE}[base]"]
    labels: list[str] = ["[base]"]
    for index, clip in enumerate(clips, start=1):
        delay_ms = max(0, int(round(float(clip.get("start", 0.0)) * 1000)))
        label = f"v{index}"
        parts.append(
            f"[{index}:a]aresample={SAMPLE_RATE},aformat=channel_layouts=stereo,"
            f"volume={voice_volume:.4f},adelay={delay_ms}:all=1[{label}]"
        )
        labels.append(f"[{label}]")

    parts.append(
        "".join(labels)
        + f"amix=inputs={len(labels)}:duration=first:normalize=0:dropout_transition=0[out]"
    )
    filter_complex = ";".join(parts)

    argv += [
        "-filter_complex",
        filter_complex,
        "-map",
        "[out]",
        "-t",
        f"{max(0.1, total_duration):.3f}",
        "-ac",
        "2",
        "-ar",
        str(SAMPLE_RATE),
        "-acodec",
        "pcm_s16le",
        output_path,
    ]
    run_command(argv, desc="ffmpeg(voice-chunk)")
    return output_path


def _merge_beds(bed_paths: Sequence[str], output_path: str, total_duration: float) -> str:
    """Sum several equal-length beds into one."""
    if len(bed_paths) == 1:
        shutil.copyfile(bed_paths[0], output_path)
        return output_path

    ffmpeg = require_binary("ffmpeg")
    argv: list[str] = [ffmpeg, *_FFMPEG_BASE]
    for path in bed_paths:
        argv += ["-i", path]
    labels = "".join(f"[{i}:a]" for i in range(len(bed_paths)))
    filter_complex = (
        f"{labels}amix=inputs={len(bed_paths)}:duration=longest:normalize=0"
        f":dropout_transition=0,aresample={SAMPLE_RATE}[out]"
    )
    argv += [
        "-filter_complex",
        filter_complex,
        "-map",
        "[out]",
        "-t",
        f"{max(0.1, total_duration):.3f}",
        "-ac",
        "2",
        "-ar",
        str(SAMPLE_RATE),
        "-acodec",
        "pcm_s16le",
        output_path,
    ]
    run_command(argv, desc="ffmpeg(merge-beds)")
    return output_path


def build_voice_bed(
    synced_tracks: Sequence[dict],
    total_duration: float,
    work_dir: str,
    *,
    voice_volume: float = 1.0,
    chunk_size: int = VOICE_CHUNK,
) -> str:
    """Render all voice clips onto one full-length WAV bed.

    Clips are processed ``chunk_size`` at a time and the partial beds are summed,
    which keeps every individual ffmpeg invocation small regardless of segment count.
    """
    ensure_dir(work_dir)
    usable = [
        track
        for track in synced_tracks
        if track.get("audio_path") and os.path.isfile(track["audio_path"])
    ]
    usable.sort(key=lambda track: float(track.get("start", 0.0)))

    bed_path = os.path.join(work_dir, "voice_bed.wav")
    if not usable:
        log.warning("No usable voice clips; rendering a silent voice bed.")
        return _silent_bed(bed_path, total_duration)

    chunk_size = max(1, int(chunk_size))
    chunks = [usable[i : i + chunk_size] for i in range(0, len(usable), chunk_size)]
    log.info(
        "Building voice bed from %d clip(s) in %d pass(es)...", len(usable), len(chunks)
    )

    partials: list[str] = []
    for index, chunk in enumerate(chunks, start=1):
        partial = os.path.join(work_dir, f"voice_part_{index:03d}.wav")
        _mix_voice_chunk(chunk, partial, total_duration, voice_volume)
        partials.append(partial)
        log.debug("  voice pass %d/%d done (%d clips)", index, len(chunks), len(chunk))

    _merge_beds(partials, bed_path, total_duration)
    for partial in partials:
        try:
            os.remove(partial)
        except OSError:
            pass
    return bed_path


def _mix_final_audio(
    no_vocals_path: str,
    voice_bed_path: str,
    output_path: str,
    total_duration: float,
    *,
    bgm_volume: float,
    loudnorm: bool,
) -> str:
    """Blend the instrumental bed with the narration bed."""
    ffmpeg = require_binary("ffmpeg")
    chain = (
        f"[0:a]aresample={SAMPLE_RATE},aformat=channel_layouts=stereo,"
        f"volume={bgm_volume:.4f}[bgm];"
        f"[1:a]aresample={SAMPLE_RATE},aformat=channel_layouts=stereo[voice];"
        "[bgm][voice]amix=inputs=2:duration=longest:normalize=0:dropout_transition=0[mixed];"
    )
    if loudnorm:
        chain += "[mixed]loudnorm=I=-16:TP=-1.5:LRA=11[out]"
    else:
        chain += "[mixed]alimiter=limit=0.97:level=false[out]"

    run_command(
        [
            ffmpeg,
            *_FFMPEG_BASE,
            "-i",
            no_vocals_path,
            "-i",
            voice_bed_path,
            "-filter_complex",
            chain,
            "-map",
            "[out]",
            "-t",
            f"{max(0.1, total_duration):.3f}",
            "-ac",
            "2",
            "-ar",
            str(SAMPLE_RATE),
            "-acodec",
            "pcm_s16le",
            output_path,
        ],
        desc="ffmpeg(final-mix)",
    )
    return output_path


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def render_dubbed_episode(
    video_path: str,
    no_vocals_path: str,
    synced_tracks: list,
    output_path: str,
    config: dict,
    *,
    subtitle_path: str | None = None,
    work_dir: str | None = None,
    keep_work_dir: bool = False,
    filler_trim_plan: dict[str, Any] | None = None,
) -> str:
    """Render one finished, localized episode.

    Args:
        video_path: Original episode video.
        no_vocals_path: Demucs instrumental stem (music + SFX, no dialogue).
        synced_tracks: Output of :func:`modules.tts_engine.generate_voiceover_tracks`.
        output_path: Destination MP4.
        config: Parsed ``settings.json`` (reads ``visual_filters``, ``audio_mixing``
            and ``encoding``).
        subtitle_path: Optional SRT burned in as hard subs.
        work_dir: Scratch directory; a temp dir is used when omitted.
        keep_work_dir: Keep intermediates for debugging.
        filler_trim_plan: Optional plan from filler_trimmer.plan_smart_trimming.

    Returns:
        The absolute path of the rendered MP4.
    """
    if not os.path.isfile(video_path):
        raise PipelineError(f"render_dubbed_episode: video not found: {video_path}")
    if not os.path.isfile(no_vocals_path):
        raise PipelineError(f"render_dubbed_episode: instrumental stem not found: {no_vocals_path}")

    ffmpeg = require_binary("ffmpeg", "Install FFmpeg and put it on PATH.")
    output_path = os.path.abspath(output_path)
    ensure_dir(os.path.dirname(output_path))

    stem = safe_stem(video_path)
    owns_work_dir = work_dir is None
    work_dir = ensure_dir(work_dir or tempfile.mkdtemp(prefix=f"odrender_{stem}_"))

    bgm_volume = float(_cfg(config, "audio_mixing", "bgm_volume", 0.35))
    voice_volume = float(_cfg(config, "audio_mixing", "voice_volume", 1.0))
    loudnorm = bool(_cfg(config, "audio_mixing", "loudnorm", True))

    video_codec = str(_cfg(config, "encoding", "video_codec", "libx264"))
    audio_codec = str(_cfg(config, "encoding", "audio_codec", "aac"))
    crf = int(_cfg(config, "encoding", "crf", 20))
    preset = str(_cfg(config, "encoding", "preset", "veryfast"))
    audio_bitrate = str(_cfg(config, "encoding", "audio_bitrate", "192k"))
    fps = _cfg(config, "encoding", "fps", None)

    try:
        video_duration = ffprobe_duration(video_path)
        if video_duration <= 0:
            raise PipelineError(f"Could not read a duration from {video_path}")

        active_duration = video_duration
        active_no_vocals = no_vocals_path
        select_prefix = ""

        if filler_trim_plan and filler_trim_plan.get("saved_seconds", 0.0) > 0.5:
            from modules.filler_trimmer import trim_audio_stem, build_ffmpeg_select_filter
            keep_segs = filler_trim_plan.get("keep_segments", [])
            trimmed_dur = filler_trim_plan.get("trimmed_duration", video_duration)
            if keep_segs and trimmed_dur > 0:
                log.info(
                    "[%s] Applying Smart Filler Trimming: %.1fs -> %.1fs (saved %.1fs / %s)",
                    stem, video_duration, trimmed_dur,
                    filler_trim_plan.get("saved_seconds", 0.0),
                    filler_trim_plan.get("saved_percent", "0%"),
                )
                trimmed_wav = os.path.join(work_dir, "no_vocals_trimmed.wav")
                trim_audio_stem(no_vocals_path, keep_segs, trimmed_wav)
                active_no_vocals = trimmed_wav
                active_duration = trimmed_dur
                select_filter = build_ffmpeg_select_filter(keep_segs)
                if select_filter:
                    select_prefix = select_filter + ","

        log.info("[%s] building narration bed (%.1fs timeline)...", stem, active_duration)
        voice_bed = build_voice_bed(
            synced_tracks,
            active_duration,
            work_dir,
            voice_volume=voice_volume,
        )

        log.info(
            "[%s] mixing instrumental at %.0f%% under narration...", stem, bgm_volume * 100
        )
        mixed_audio = _mix_final_audio(
            active_no_vocals,
            voice_bed,
            os.path.join(work_dir, "final_mix.wav"),
            active_duration,
            bgm_volume=bgm_volume,
            loudnorm=loudnorm,
        )

        vw, vh = probe_video_dimensions(video_path)
        video_filter = build_video_filter(config, width=vw, height=vh)
        if select_prefix:
            video_filter = select_prefix + video_filter

        if subtitle_path and os.path.isfile(subtitle_path):
            escaped = subtitle_path.replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
            video_filter += (
                f",subtitles='{escaped}':force_style="
                "'FontSize=20,PrimaryColour=&H00FFFFFF,OutlineColour=&H80000000,BorderStyle=3'"
            )
        log.debug("[%s] video filter: %s", stem, video_filter)

        argv = [
            ffmpeg,
            *_FFMPEG_BASE,
            "-i",
            video_path,
            "-i",
            mixed_audio,
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-filter:v",
            video_filter,
            "-c:v",
            video_codec,
            "-preset",
            preset,
            "-crf",
            str(crf),
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            audio_codec,
            "-b:a",
            audio_bitrate,
            "-ar",
            str(SAMPLE_RATE),
            "-ac",
            "2",
            "-shortest",
            "-movflags",
            "+faststart",
        ]
        if fps:
            argv += ["-r", str(fps)]
        argv.append(output_path)

        log.info("[%s] encoding final video (%s / %s)...", stem, video_codec, audio_codec)
        run_command(argv, desc="ffmpeg(render)", capture=True)

        if not os.path.isfile(output_path) or os.path.getsize(output_path) < 8192:
            raise PipelineError(f"Render produced no usable output at {output_path}")

        log.info(
            "[%s] rendered %s (%.1f MiB, %.1fs)",
            stem,
            os.path.basename(output_path),
            os.path.getsize(output_path) / 1048576,
            ffprobe_duration(output_path),
        )
        return output_path

    finally:
        if owns_work_dir and not keep_work_dir:
            shutil.rmtree(work_dir, ignore_errors=True)


def probe_render(path: str) -> dict[str, Any]:
    """Return a small QC summary (duration, streams) for a rendered file."""
    from . import ffprobe_has_audio

    return {
        "path": path,
        "exists": os.path.isfile(path),
        "size_mib": round(os.path.getsize(path) / 1048576, 2) if os.path.isfile(path) else 0.0,
        "duration": round(ffprobe_duration(path), 2) if os.path.isfile(path) else 0.0,
        "has_audio": ffprobe_has_audio(path) if os.path.isfile(path) else False,
    }
