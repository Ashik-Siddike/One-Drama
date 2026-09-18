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


_NVENC_CHECKED = None


def _has_nvenc_support() -> bool:
    """Check if NVIDIA NVENC hardware encoder is usable."""
    global _NVENC_CHECKED
    if _NVENC_CHECKED is not None:
        return _NVENC_CHECKED
    try:
        ffmpeg = require_binary("ffmpeg")
        res = run_command(
            [
                ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-f",
                "lavfi",
                "-i",
                "nullsrc=s=256x256:d=0.04",
                "-c:v",
                "h264_nvenc",
                "-f",
                "null",
                "-",
            ],
            desc="test-nvenc",
            capture=True,
            check=False,
        )
        _NVENC_CHECKED = res.returncode == 0
    except Exception:
        _NVENC_CHECKED = False
    return _NVENC_CHECKED


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


def generate_feathered_mask(
    width: int,
    height: int,
    radius: int = 16,
    feather_sigma: float = 6.5,
    output_path: str | None = None,
) -> str:
    """Generate an alpha-channel mask PNG with Gaussian-feathered edges and rounded corners.

    The center is white (255), while borders and corners smoothly fade to black (0),
    providing a seamless, organic frosted glass blur without harsh box edges.
    """
    from PIL import Image, ImageDraw, ImageFilter

    w = max(24, int(width))
    h = max(16, int(height))
    mask = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(mask)

    pad_x = max(6, int(w * 0.03))
    pad_y = max(3, int(h * 0.08))
    r = max(4, min(int(radius), int(h * 0.38)))

    draw.rounded_rectangle(
        [pad_x, pad_y, w - pad_x, h - pad_y],
        radius=r,
        fill=255,
    )
    feathered = mask.filter(ImageFilter.GaussianBlur(radius=feather_sigma))
    if not output_path:
        out_fd, output_path = tempfile.mkstemp(prefix="sub_feather_mask_", suffix=".png")
        os.close(out_fd)
    feathered.save(output_path, "PNG")
    return output_path


def build_video_filter(
    config: dict | None,
    width: int = 1280,
    height: int = 720,
    watermark_profile: dict | None = None,
    speech_segments: Sequence[dict] | None = None,
    work_dir: str | None = None,
) -> str:
    """Return the video filter chain string derived from ``visual_filters`` and ``watermark_profile``."""
    zoom = float(_cfg(config, "visual_filters", "zoom_percent", 1.03))
    crop_bottom = int(_cfg(config, "visual_filters", "crop_bottom", 80))
    crop_top = int(_cfg(config, "visual_filters", "crop_top", 0))
    contrast = float(_cfg(config, "visual_filters", "contrast", 1.04))
    saturation = float(_cfg(config, "visual_filters", "saturation", 1.06))
    brightness = float(_cfg(config, "visual_filters", "brightness", 0.0))
    gamma = float(_cfg(config, "visual_filters", "gamma", 1.01))
    remove_watermark = bool(_cfg(config, "visual_filters", "remove_watermark", True))
    remove_disclaimer = bool(_cfg(config, "visual_filters", "remove_right_disclaimer", True))
    bottom_treatment = str(_cfg(config, "visual_filters", "bottom_subtitle_treatment", "feathered_gaussian")).lower()
    side_action = str(_cfg(config, "visual_filters", "side_watermark_action", "auto_crop")).lower()
    visual_hash_breaker = bool(_cfg(config, "visual_filters", "visual_hash_breaker", True))
    noise_strength = int(_cfg(config, "visual_filters", "noise_strength", 2))

    wp = watermark_profile or {}
    has_right_wm = wp.get("has_right_watermark", remove_disclaimer)
    right_crop_px = int(wp.get("right_crop_pixels", 0))
    if has_right_wm and right_crop_px <= 0:
        right_crop_px = int(_cfg(config, "visual_filters", "side_watermark_crop_px", 80))

    has_top_l = wp.get("has_top_left_logo", remove_watermark)
    has_top_r = wp.get("has_top_right_logo", False)

    zoom = max(1.0, min(1.5, zoom))
    crop_bottom = max(0, crop_bottom)
    crop_top = max(0, crop_top)

    stages: list[str] = []

    # 1. Smart Side-Crop for Right-edge Watermark / Disclaimer
    if has_right_wm and right_crop_px > 0:
        if side_action == "auto_crop":
            # Crop off the right-edge strip and scale back smoothly to preserve aspect ratio
            stages.append(f"crop=w=iw-{right_crop_px}:h=ih:x=0:y=0")
            stages.append(f"scale={width}:{height}:flags=lanczos")
        else:
            # Fallback delogo on right edge
            rx = max(0, int(width - right_crop_px))
            ry = max(0, int(height * 0.10))
            rw = min(right_crop_px, int(width * 0.08))
            rh = max(100, int(height * 0.80))
            stages.append(f"delogo=x={rx}:y={ry}:w={rw}:h={rh}:show=0")

    # 2. Corner Logo Inpainting (Delogo)
    if has_top_l:
        w_top = max(100, int(width * 0.18))
        h_top = max(40, int(height * 0.09))
        stages.append(f"delogo=x=10:y=10:w={w_top}:h={h_top}:show=0")

    if has_top_r:
        w_top = max(100, int(width * 0.18))
        h_top = max(40, int(height * 0.09))
        stages.append(f"delogo=x=iw-{w_top}-10:y=10:w={w_top}:h={h_top}:show=0")

    # 3. Subtitle Treatment: Feathered Gaussian Frosted Blur Mask vs Legacy Hard Crop
    # NOTE: Subtitle blur MUST execute on source coordinates BEFORE any micro-zoom,
    # ensuring the frosted plate aligns with 100% pixel accuracy over the Chinese text.
    has_sub = wp.get("has_bottom_subtitles", True) if wp else True
    if has_sub and bottom_treatment in ("feathered_gaussian", "glassmorphism", "frosted_glass", "blur"):
        if wp and wp.get("subtitle_y_start"):
            raw_sy = int(wp["subtitle_y_start"])
            raw_h = int(wp.get("subtitle_height") or round(height * 0.08))
            # Add generous padding so blur plate comfortably covers the text
            sub_y = max(0, raw_sy - 8)
            box_h = max(int(round(height * 0.08)), raw_h + 16)
            sub_x = max(0, int(wp.get("subtitle_x_start") or round(width * 0.06)) - 10)
            box_w = min(width - sub_x, int(wp.get("subtitle_width") or round(width * 0.88)) + 20)
        elif height > width:
            # Fallback for 9:16 vertical video
            sub_y = int(round(height * 0.72))
            box_h = int(round(height * 0.085))
            sub_x = int(round(width * 0.06))
            box_w = int(round(width * 0.88))
        else:
            sub_y = int(round(height * 0.82))
            box_h = int(round(height * 0.09))
            sub_x = int(round(width * 0.08))
            box_w = int(round(width * 0.84))

        # Clamp boundaries safely inside the video frame and ensure even dimensions for YUV420p
        sub_x = max(0, min(width - 40, sub_x))
        sub_y = max(0, min(height - 30, sub_y))
        box_w = min(width - sub_x, max(60, box_w))
        box_h = min(height - sub_y, max(30, box_h))

        sub_x = (sub_x // 2) * 2
        sub_y = (sub_y // 2) * 2
        box_w = (box_w // 2) * 2
        box_h = (box_h // 2) * 2

        glass_color = str(_cfg(config, "visual_filters", "glassmorphism_color", "white")).lower()
        if glass_color not in ("white", "black"):
            glass_color = "white"
        opacity = float(_cfg(config, "visual_filters", "glassmorphism_opacity", 0.50))
        opacity = max(0.15, min(0.95, opacity))
        blur_sigma = int(_cfg(config, "visual_filters", "glassmorphism_blur", 16))
        blur_sigma = max(8, min(32, blur_sigma))

        # Dynamic overlay enable: blur plate appears ONLY during speech dialogue timestamps
        overlay_filter = f"overlay={sub_x}:{sub_y}"
        dynamic_plate = bool(_cfg(config, "visual_filters", "dynamic_subtitle_plate", True))
        if dynamic_plate and speech_segments:
            enable_parts = []
            for seg in speech_segments:
                txt = str(seg.get("recap_text") or seg.get("original_text") or "").strip()
                if txt and float(seg.get("end", 0.0)) > float(seg.get("start", 0.0)):
                    s = max(0.0, float(seg["start"]) - 0.05)
                    e = float(seg["end"]) + 0.10
                    enable_parts.append(f"between(t\\,{s:.2f}\\,{e:.2f})")
            if enable_parts:
                enable_expr = "+".join(enable_parts)
                overlay_filter += f":enable='{enable_expr}'"

        # Generate feathered alpha mask PNG
        mask_dest = os.path.join(work_dir, "sub_feather_mask.png") if work_dir else None
        mask_path = generate_feathered_mask(
            width=box_w,
            height=box_h,
            radius=16,
            feather_sigma=6.5,
            output_path=mask_dest,
        )
        escaped_mask = mask_path.replace("\\", "/").replace(":", "\\:")

        # Blend via alphamerge and overlay at the detected subtitle position
        stages.append(
            f"split=2[main][crop_src];"
            f"movie='{escaped_mask}',scale={box_w}:{box_h}[mask];"
            f"[crop_src]crop={box_w}:{box_h}:{sub_x}:{sub_y},scale={box_w}:{box_h},"
            f"gblur=sigma={blur_sigma},"
            f"drawbox=x=0:y=0:w=iw:h=ih:color={glass_color}@{opacity:.2f}:t=fill[blurred];"
            f"[blurred][mask]alphamerge[plate];"
            f"[main][plate]{overlay_filter}"
        )
    elif bottom_treatment == "crop" and (crop_top > 0 or crop_bottom > 0):
        # Legacy hard crop only if user explicitly chose crop mode
        ch = f"max(2\\,ih-{crop_bottom + crop_top})"
        stages.append(f"crop=w=iw:h={ch}:x=0:y={crop_top}")

    # 4. Anti-Fingerprint Visual Micro-Zoom (applied evenly with centered crop)
    if zoom > 1.0:
        stages.append(f"scale=max({width}\\,trunc(iw*{zoom:.4f}/2)*2):max({height}\\,trunc(ih*{zoom:.4f}/2)*2):flags=lanczos,crop={width}:{height}")

    # 5. Visual Hash Breaking: Imperceptible Film Grain Noise
    if visual_hash_breaker and noise_strength > 0:
        stages.append(f"noise=alls={noise_strength}:allf=t")

    # 6. Color Grading & Output Normalization
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
    ducking: bool = True,
    ducking_threshold: float = 0.03,
    ducking_ratio: float = 8.0,
    ducking_attack: float = 20.0,
    ducking_release: float = 400.0,
) -> str:
    """Blend the instrumental bed with the narration bed using dynamic sidechain ducking & broadcast voice EQ."""
    ffmpeg = require_binary("ffmpeg")
    if ducking:
        chain = (
            f"[0:a]aresample={SAMPLE_RATE},aformat=channel_layouts=stereo,volume={bgm_volume:.4f}[bgm_raw];"
            f"[1:a]aresample={SAMPLE_RATE},aformat=channel_layouts=stereo,highpass=f=80,treble=g=2.5:f=3500[voice_eq];"
            f"[voice_eq]asplit=2[sc][voice_clean];"
            f"[bgm_raw][sc]sidechaincompress=threshold={ducking_threshold}:ratio={ducking_ratio}:attack={ducking_attack}:release={ducking_release}[ducked_bgm];"
            f"[ducked_bgm][voice_clean]amix=inputs=2:duration=longest:normalize=0:dropout_transition=0[mixed];"
        )
    else:
        chain = (
            f"[0:a]aresample={SAMPLE_RATE},aformat=channel_layouts=stereo,volume={bgm_volume:.4f}[bgm];"
            f"[1:a]aresample={SAMPLE_RATE},aformat=channel_layouts=stereo,highpass=f=80,treble=g=2.5:f=3500[voice];"
            f"[bgm][voice]amix=inputs=2:duration=longest:normalize=0:dropout_transition=0[mixed];"
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
    speech_segments: Sequence[dict] | None = None,
    work_dir: str | None = None,
    keep_work_dir: bool = False,
    filler_trim_plan: dict[str, Any] | None = None,
    watermark_profile: dict[str, Any] | None = None,
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

    bgm_volume = float(_cfg(config, "audio_mixing", "bgm_volume", 0.75))
    voice_volume = float(_cfg(config, "audio_mixing", "voice_volume", 1.05))
    loudnorm = bool(_cfg(config, "audio_mixing", "loudnorm", True))
    ducking = bool(_cfg(config, "audio_mixing", "ducking", True))
    ducking_threshold = float(_cfg(config, "audio_mixing", "ducking_threshold", 0.03))
    ducking_ratio = float(_cfg(config, "audio_mixing", "ducking_ratio", 8.0))
    ducking_attack = float(_cfg(config, "audio_mixing", "ducking_attack", 20.0))
    ducking_release = float(_cfg(config, "audio_mixing", "ducking_release", 400.0))

    req_codec = str(_cfg(config, "encoding", "video_codec", "auto")).lower()
    has_nvenc = _has_nvenc_support()

    if req_codec in ("auto", "h264_nvenc", "nvenc") and has_nvenc:
        video_codec = "h264_nvenc"
        preset = str(_cfg(config, "encoding", "preset", "p4"))
        cq = int(_cfg(config, "encoding", "cq", _cfg(config, "encoding", "crf", 20)))
    else:
        video_codec = "libx264"
        preset = str(_cfg(config, "encoding", "preset", "veryfast"))
        cq = int(_cfg(config, "encoding", "crf", 20))

    audio_codec = str(_cfg(config, "encoding", "audio_codec", "aac"))
    audio_bitrate = str(_cfg(config, "encoding", "audio_bitrate", "192k"))
    fps = _cfg(config, "encoding", "fps", None)

    try:
        video_duration = ffprobe_duration(video_path)
        if video_duration <= 0:
            raise PipelineError(f"Could not read a duration from {video_path}")

        active_duration = video_duration
        active_no_vocals = no_vocals_path

        log.info("[%s] building narration bed (%.1fs timeline)...", stem, active_duration)
        voice_bed = build_voice_bed(
            synced_tracks,
            active_duration,
            work_dir,
            voice_volume=voice_volume,
        )

        log.info(
            "[%s] mixing instrumental at %.0f%% with dynamic sidechain ducking under narration...", stem, bgm_volume * 100
        )
        mixed_audio = _mix_final_audio(
            active_no_vocals,
            voice_bed,
            os.path.join(work_dir, "final_mix.wav"),
            active_duration,
            bgm_volume=bgm_volume,
            loudnorm=loudnorm,
            ducking=ducking,
            ducking_threshold=ducking_threshold,
            ducking_ratio=ducking_ratio,
            ducking_attack=ducking_attack,
            ducking_release=ducking_release,
        )

        vw, vh = probe_video_dimensions(video_path)
        if watermark_profile is None:
            try:
                from . import watermark_detector
                watermark_profile = watermark_detector.inspect_video_watermarks(
                    video_path, config, work_dir=work_dir
                )
            except Exception as w_exc:
                log.warning("[%s] Watermark inspection failed (%s); using heuristic.", stem, w_exc)
                watermark_profile = None

        video_filter = build_video_filter(
            config,
            width=vw,
            height=vh,
            watermark_profile=watermark_profile,
            speech_segments=speech_segments,
            work_dir=work_dir,
        )

        if subtitle_path and os.path.isfile(subtitle_path):
            escaped = subtitle_path.replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
            if subtitle_path.endswith(".ass"):
                video_filter += f",subtitles='{escaped}'"
            else:
                bottom_treatment = str(_cfg(config, "visual_filters", "bottom_subtitle_treatment", "feathered_gaussian")).lower()
                if bottom_treatment in ("feathered_gaussian", "glassmorphism", "frosted_glass", "blur"):
                    if vh > vw:
                        raw_sy = int(watermark_profile.get("subtitle_y_start") or int(round(vh * 0.665))) if watermark_profile else int(round(vh * 0.665))
                        raw_h = int(watermark_profile.get("subtitle_height") or int(round(vh * 0.078))) if watermark_profile else int(round(vh * 0.078))
                        box_h = max(int(round(vh * 0.078)), raw_h)
                        sub_y = min(raw_sy, int(round(vh * 0.668)))
                    else:
                        sub_y = int(watermark_profile.get("subtitle_y_start") or int(round(vh * 0.82))) if watermark_profile else int(round(vh * 0.82))
                        box_h = int(watermark_profile.get("subtitle_height") or int(round(vh * 0.09))) if watermark_profile else int(round(vh * 0.09))
                    margin_v = max(16, int(vh - (sub_y + box_h) + max(4, (box_h - 26) // 2)))
                else:
                    sub_h = int(watermark_profile.get("bottom_subtitle_height", 85)) if watermark_profile else 85
                    margin_v = max(14, int(sub_h * 0.18))
                video_filter += (
                    f",subtitles='{escaped}':force_style="
                    f"'FontSize=24,Bold=1,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,Outline=2,MarginV={margin_v},Alignment=2'"
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
        ]
        if video_codec == "h264_nvenc":
            argv += ["-cq", str(cq)]
        else:
            argv += ["-crf", str(cq)]
        argv += [
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

        log.info(
            "[%s] encoding final video on %s (%s / %s, preset=%s)...",
            stem,
            "NVIDIA NVENC Hardware Accelerator" if video_codec == "h264_nvenc" else "CPU libx264",
            video_codec,
            audio_codec,
            preset,
        )
        try:
            run_command(argv, desc="ffmpeg(render)", capture=True, check=True)
        except Exception as exc:
            if video_codec == "h264_nvenc":
                log.warning("[%s] NVENC hardware encode failed (%s). Falling back to CPU libx264...", stem, exc)
                fb_argv = [
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
                    "libx264",
                    "-preset",
                    "veryfast",
                    "-crf",
                    "20",
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
                    fb_argv += ["-r", str(fps)]
                fb_argv.append(output_path)
                run_command(fb_argv, desc="ffmpeg(render-fallback)", capture=True, check=True)
            else:
                raise

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
