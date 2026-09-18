"""Automated High-CTR YouTube Shorts Generator.

Scans the dramatic narrative for peak emotional/tension moments and carves
a 55-second vertical 9:16 teaser video complete with hook text badges and
pinned-comment Call-to-Action banners directing viewers to the full-length movie.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from typing import Any, Sequence

from . import ensure_dir, ffprobe_duration, log, require_binary, run_command

TENSION_KEYWORDS = [
    "किस", "चूम", "गले", "धोखा", "पुनर्जन्म", "ट्रक", "हैरान", "चीख",
    "मार", "खून", "भगवान", "ताकत", "बदला", "अहंकार", "अपमान",
    "बिजली", "स्वर्ग", "मौत", "ज़िंदा", "मर", "ड्रैगन", "शहंशाह", "जादू", "ताक़त",
    "kiss", "hug", "reborn", "betrayal", "god", "revenge", "shock", "lightning", "dragon",
    "thunder", "emperor", "kill", "die", "power", "immortal",
]


def _get_system_font() -> str | None:
    """Find a reliable system TrueType font for drawtext."""
    candidates = [
        r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\segoeui.ttf",
        r"C:\Windows\Fonts\calibri.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    for c in candidates:
        if os.path.isfile(c):
            # Format path for FFmpeg filtergraph: escape colons and backslashes
            return c.replace("\\", "/").replace(":", "\\:")
    return None


def find_highest_tension_window(
    recap_script_path: str,
    target_duration: float = 54.0,
    safe_intro_offset: float = 3.5,
    safe_outro_offset: float = 5.0,
) -> tuple[float, float, str]:
    """Find the start timestamp of the highest-drama 50-58s window, strictly avoiding intro/outro bumpers."""
    default_start = safe_intro_offset
    default_end = default_start + target_duration
    default_hook = "WAIT TILL THE END TO SEE WHAT HAPPENS!"

    if not os.path.isfile(recap_script_path):
        return default_start, default_end, default_hook

    try:
        with open(recap_script_path, "r", encoding="utf-8") as f:
            segments = json.load(f)
    except Exception:
        return default_start, default_end, default_hook

    if not isinstance(segments, list) or not segments:
        return default_start, default_end, default_hook

    best_score = -1
    best_start = safe_intro_offset
    best_text = ""

    # Chinese Outro CTA filter keywords to strictly avoid selecting closing cards
    CTA_EXCLUSION = ["关注", "点赞", "三连", "下集更精彩", "未完待续", "下集再见"]

    for seg in segments:
        text = seg.get("recap_text", "")
        orig_text = seg.get("original_text", "")
        start = float(seg.get("start", 0.0))

        # Skip segments that touch the intro bumper zone or contain creator outro CTA
        if start < safe_intro_offset:
            continue
        if any(cta in orig_text for cta in CTA_EXCLUSION):
            continue

        score = sum(text.count(kw) for kw in TENSION_KEYWORDS)

        # Extra weight for exclamation marks and dramatic punctuation
        score += text.count("!") * 2
        score += text.count("?") * 1

        if score > best_score:
            best_score = score
            best_start = start
            best_text = text

    if not best_text and segments:
        for seg in segments:
            if float(seg.get("start", 0.0)) >= safe_intro_offset and seg.get("recap_text"):
                best_text = seg["recap_text"]
                best_start = float(seg.get("start", safe_intro_offset))
                break

    hook_clean = default_hook
    if best_text:
        first_sentence = best_text.split("।")[0].split("!")[0].strip()
        if 10 < len(first_sentence) < 60:
            hook_clean = first_sentence

    return best_start, best_start + target_duration, hook_clean


def render_vertical_short(
    input_video_path: str,
    output_short_path: str,
    start_sec: float = 0.0,
    duration_sec: float = 55.0,
    top_hook_text: str = "WAIT TILL THE END TO SEE WHAT HAPPENS!",
    bottom_cta_text: str = "WATCH FULL 2-HR MOVIE IN PINNED COMMENT",
) -> str | None:
    """Carve a 9:16 vertical YouTube Short from an input master video (supports both 16:9 and native 9:16)."""
    ffmpeg = require_binary("ffmpeg")
    ensure_dir(os.path.dirname(os.path.abspath(output_short_path)))

    total_dur = ffprobe_duration(input_video_path)
    if start_sec + duration_sec > total_dur:
        start_sec = max(0.0, total_dur - duration_sec)

    log.info(
        "Rendering 9:16 YouTube Short (start: %.1fs, duration: %.1fs) -> %s",
        start_sec, duration_sec, os.path.basename(output_short_path),
    )

    from modules.video_processor import probe_video_dimensions
    vw, vh = probe_video_dimensions(input_video_path)

    font_path = _get_system_font()
    font_arg = f":fontfile='{font_path}'" if font_path else ""

    # Sanitize text quotes
    clean_top = top_hook_text.replace("'", "").replace(":", "-").replace('"', "")
    clean_bot = bottom_cta_text.replace("'", "").replace(":", "-").replace('"', "")

    if vh > vw:
        # Source video is ALREADY vertical 9:16 (e.g. 720x1280 or 1080x1920)
        # Directly scale to 1080x1920 canvas without squashing or letterboxing!
        filter_complex = (
            f"[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920[scaled];"
            f"[scaled]drawtext=text='{clean_top}'{font_arg}:fontcolor=yellow:fontsize=44:x=(w-text_w)/2:y=120:box=1:boxcolor=black@0.75:boxborderw=10,"
            f"drawtext=text='{clean_bot}'{font_arg}:fontcolor=white:fontsize=34:x=(w-text_w)/2:y=1760:box=1:boxcolor=red@0.85:boxborderw=8[v]"
        )
    else:
        # Source video is horizontal 16:9
        # Canvas: 1080x1920 with blurred background and centered 16:9 foreground
        filter_complex = (
            "[0:v]split=2[bg_src][fg_src];"
            "[bg_src]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=25:5[bg];"
            "[fg_src]scale=1080:608:flags=lanczos[fg];"
            "[bg][fg]overlay=0:656[comp];"
            f"[comp]drawtext=text='{clean_top}'{font_arg}:fontcolor=yellow:fontsize=46:x=(w-text_w)/2:y=400:box=1:boxcolor=black@0.75:boxborderw=10,"
            f"drawtext=text='{clean_bot}'{font_arg}:fontcolor=white:fontsize=36:x=(w-text_w)/2:y=1380:box=1:boxcolor=red@0.85:boxborderw=8[v]"
        )

    from modules.video_processor import _has_nvenc_support

    use_nvenc = _has_nvenc_support()
    encoder = "h264_nvenc" if use_nvenc else "libx264"
    preset = "p4" if use_nvenc else "veryfast"
    quality_flag = ["-cq", "20"] if use_nvenc else ["-crf", "20"]

    cmd = [
        ffmpeg,
        "-hide_banner",
        "-loglevel", "error",
        "-y",
        "-ss", f"{start_sec:.2f}",
        "-t", f"{duration_sec:.2f}",
        "-i", input_video_path,
        "-filter_complex", filter_complex,
        "-map", "[v]",
        "-map", "0:a:0?",
        "-c:v", encoder,
        "-preset", preset,
        *quality_flag,
        "-c:a", "aac",
        "-b:a", "192k",
        "-ar", "44100",
        output_short_path,
    ]

    try:
        log.info("Rendering YouTube Short on %s (%s)...", "NVIDIA NVENC" if use_nvenc else "CPU libx264", encoder)
        run_command(cmd, desc="ffmpeg(render_short)")
        if os.path.isfile(output_short_path) and os.path.getsize(output_short_path) > 1024:
            log.info("YouTube Short successfully rendered: %s", output_short_path)
            return output_short_path
    except Exception as exc:
        if use_nvenc:
            log.warning("NVENC failed for short (%s). Retrying with CPU libx264...", exc)
            cmd[cmd.index("h264_nvenc")] = "libx264"
            cmd[cmd.index("p4")] = "veryfast"
            cmd[cmd.index("-cq")] = "-crf"
            try:
                run_command(cmd, desc="ffmpeg(render_short_fallback)")
                if os.path.isfile(output_short_path) and os.path.getsize(output_short_path) > 1024:
                    return output_short_path
            except Exception as fb_exc:
                log.error("Failed to render vertical short with fallback: %s", fb_exc)
        else:
            log.error("Failed to render vertical short: %s", exc)

    return None
