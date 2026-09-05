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
    "kiss", "hug", "reborn", "betrayal", "god", "revenge", "shock",
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
    default_hook = "SHE KISSED HIM IN FRONT OF EVERYONE?!"

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
    top_hook_text: str = "SHE KISSED HIM IN CLASS?! PART 1",
    bottom_cta_text: str = "WATCH FULL 2-HR MOVIE IN PINNED COMMENT",
) -> str | None:
    """Carve a 9:16 vertical YouTube Short from a 16:9 master video."""
    ffmpeg = require_binary("ffmpeg")
    ensure_dir(os.path.dirname(os.path.abspath(output_short_path)))

    total_dur = ffprobe_duration(input_video_path)
    if start_sec + duration_sec > total_dur:
        start_sec = max(0.0, total_dur - duration_sec)

    log.info(
        "Rendering 9:16 YouTube Short (start: %.1fs, duration: %.1fs) -> %s",
        start_sec, duration_sec, os.path.basename(output_short_path),
    )

    # 9:16 canvas: 1080x1920
    # Background: scaled and blurred to fill canvas
    # Foreground: 1080x608 original video centered vertically at y=656
    font_path = _get_system_font()
    font_arg = f":fontfile='{font_path}'" if font_path else ""

    # Sanitize text quotes
    clean_top = top_hook_text.replace("'", "").replace(":", "-")
    clean_bot = bottom_cta_text.replace("'", "").replace(":", "-")

    filter_complex = (
        "[0:v]split=2[bg_src][fg_src];"
        "[bg_src]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=25:5[bg];"
        "[fg_src]scale=1080:608:flags=lanczos[fg];"
        "[bg][fg]overlay=0:656[comp];"
        f"[comp]drawtext=text='{clean_top}'{font_arg}:fontcolor=yellow:fontsize=46:x=(w-text_w)/2:y=400:box=1:boxcolor=black@0.75:boxborderw=10,"
        f"drawtext=text='{clean_bot}'{font_arg}:fontcolor=white:fontsize=36:x=(w-text_w)/2:y=1380:box=1:boxcolor=red@0.85:boxborderw=8[v]"
    )

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
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "20",
        "-c:a", "aac",
        "-b:a", "192k",
        "-ar", "44100",
        output_short_path,
    ]

    try:
        run_command(cmd, desc="ffmpeg(render_short)")
        if os.path.isfile(output_short_path) and os.path.getsize(output_short_path) > 1024:
            log.info("YouTube Short successfully rendered: %s", output_short_path)
            return output_short_path
    except Exception as exc:
        log.error("Failed to render vertical short: %s", exc)

    return None
