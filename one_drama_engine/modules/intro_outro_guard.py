"""Smart Intro & Outro Guard Module for OneDrama Engine.

Detects and eliminates raw Chinese creator bumpers, title stingers, and outro
Call-To-Actions (like & follow screens, Bilibili QR codes, '关注不迷路') from short
videos and episodes, ensuring high viewer retention and clean copyright-safe storytelling.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from typing import Any, Sequence

from . import ensure_dir, ffprobe_duration, get_logger, read_json, require_binary, run_command, write_json

log = get_logger("intro_outro_guard")

# Common Chinese Outro CTA phrases used by Bilibili creators
OUTRO_CTA_PATTERNS = [
    r"关注",
    r"点赞",
    r"三连",
    r"迷路",
    r"投币",
    r"收藏",
    r"下集",
    r"未完待续",
    r"敬请期待",
    r"喜欢.*小伙伴",
    r"别忘了",
    r"老铁",
    r"弹幕",
    r"主页",
    r"粉丝",
    r"加个关注",
    r"拜托",
    r"动态",
]

# Common Chinese Intro bumper patterns
INTRO_BUMPER_PATTERNS = [
    r"前情提要",
    r"回顾",
    r"出品",
    r"制作",
    r"第[一二三四五六七八九十0-9]+[集话回]",
    r"重温",
]


def detect_intro_outro_boundaries(
    video_path: str,
    recap_script_path: str | None = None,
    transcript_path: str | None = None,
    *,
    default_intro_cushion: float = 0.25,
    default_outro_cushion: float = 0.40,
    min_intro_cut: float = 2.0,
    max_intro_cut: float = 5.0,
    min_outro_cut: float = 3.5,
) -> dict[str, Any]:
    """Analyze ASR cues, transcript text, and video length to find clean boundaries.

    Returns:
        A dict with:
        - total_duration: float
        - clean_start_sec: float (where actual story starts)
        - clean_end_sec: float (where story finishes, before creator outro CTA)
        - intro_cut_duration: float
        - outro_cut_duration: float
        - cta_detected: list of matched outro phrases
        - confidence: float (0.0 to 1.0)
    """
    total_dur = ffprobe_duration(video_path) if os.path.isfile(video_path) else 0.0
    if total_dur <= 0.0:
        total_dur = 180.0

    # 1. Load segments from recap_script or transcript
    segments: list[dict[str, Any]] = []
    if recap_script_path and os.path.isfile(recap_script_path):
        segments = read_json(recap_script_path, default=[])
    elif transcript_path and os.path.isfile(transcript_path):
        segments = read_json(transcript_path, default=[])

    clean_start = 0.0
    clean_end = total_dur
    cta_detected: list[str] = []
    intro_detected: list[str] = []

    if segments and isinstance(segments, list):
        # --- Analyze Head (Intro) ---
        first_seg = segments[0]
        first_start = float(first_seg.get("start", 0.0))
        first_text = first_seg.get("original_text", "")

        # Check if first segment contains title / bumper announcements
        for pat in INTRO_BUMPER_PATTERNS:
            if re.search(pat, first_text):
                intro_detected.append(pat)

        if first_start > 0.8:
            # There is lead-in dead air or bumper music before speech
            clean_start = max(0.0, first_start - default_intro_cushion)
        elif intro_detected:
            clean_start = min(max_intro_cut, first_start + 2.0)
        else:
            # Default soft bumper protection (e.g. 1.5s - 2.5s) if user has fast stingers
            clean_start = min(min_intro_cut, first_start)

        # --- Analyze Tail (Outro) ---
        last_seg = segments[-1]
        last_end = float(last_seg.get("end", total_dur))
        last_text = last_seg.get("original_text", "")

        # Check for Chinese Outro CTA phrases
        for pat in OUTRO_CTA_PATTERNS:
            if re.search(pat, last_text):
                cta_detected.append(pat)

        if cta_detected:
            # If the last segment is a CTA, cut before the CTA or at end of previous story segment
            if len(segments) > 1:
                prev_seg = segments[-2]
                clean_end = float(prev_seg.get("end", last_end)) + default_outro_cushion
            else:
                clean_end = max(clean_start + 10.0, last_end - min_outro_cut)
        else:
            # If no explicit CTA speech, cut trailing dead air after last dialogue
            if total_dur - last_end > 2.0:
                clean_end = last_end + default_outro_cushion
            else:
                clean_end = total_dur

    else:
        # Fallback heuristic: 2.5s intro cut, 4.0s outro cut
        clean_start = min(min_intro_cut, 2.5)
        clean_end = max(clean_start + 15.0, total_dur - min_outro_cut)

    # Sanity bounds
    clean_start = round(max(0.0, min(clean_start, total_dur - 10.0)), 2)
    clean_end = round(max(clean_start + 5.0, min(clean_end, total_dur)), 2)

    intro_cut_duration = round(clean_start, 2)
    outro_cut_duration = round(total_dur - clean_end, 2)

    confidence = 0.95 if cta_detected or intro_detected else 0.80

    return {
        "total_duration": round(total_dur, 2),
        "clean_start_sec": clean_start,
        "clean_end_sec": clean_end,
        "clean_duration_sec": round(clean_end - clean_start, 2),
        "intro_cut_duration": intro_cut_duration,
        "outro_cut_duration": outro_cut_duration,
        "cta_detected": cta_detected,
        "intro_detected": intro_detected,
        "has_chinese_cta": len(cta_detected) > 0,
        "confidence": confidence,
    }


def trim_intro_outro(
    input_video_path: str,
    output_video_path: str,
    clean_start_sec: float,
    clean_end_sec: float,
    reencode: bool = True,
) -> str | None:
    """Trim video losslessly or re-encode to exact boundaries."""
    if not os.path.isfile(input_video_path):
        log.error("Input video not found: %s", input_video_path)
        return None

    ffmpeg = require_binary("ffmpeg")
    ensure_dir(os.path.dirname(os.path.abspath(output_video_path)))
    duration = clean_end_sec - clean_start_sec
    if duration <= 0:
        log.error("Invalid duration for trim: %.2f - %.2f", clean_start_sec, clean_end_sec)
        return None

    if reencode:
        cmd = [
            ffmpeg,
            "-hide_banner",
            "-loglevel", "error",
            "-y",
            "-ss", f"{clean_start_sec:.2f}",
            "-i", input_video_path,
            "-t", f"{duration:.2f}",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "19",
            "-c:a", "aac",
            "-b:a", "192k",
            "-avoid_negative_ts", "make_zero",
            output_video_path,
        ]
    else:
        cmd = [
            ffmpeg,
            "-hide_banner",
            "-loglevel", "error",
            "-y",
            "-ss", f"{clean_start_sec:.2f}",
            "-to", f"{clean_end_sec:.2f}",
            "-i", input_video_path,
            "-c", "copy",
            "-avoid_negative_ts", "make_zero",
            output_video_path,
        ]

    try:
        run_command(cmd)
        if os.path.isfile(output_video_path) and os.path.getsize(output_video_path) > 1000:
            log.info("Successfully trimmed intro/outro: %s (%.2fs -> %.2fs)", output_video_path, clean_start_sec, clean_end_sec)
            return output_video_path
    except Exception as exc:
        log.error("FFmpeg trim failed: %s", exc)
    return None


def get_safe_shorts_candidate(
    recap_script_path: str,
    video_duration: float,
    target_short_duration: float = 54.0,
    safe_intro_offset: float = 3.5,
    safe_outro_offset: float = 5.0,
) -> tuple[float, float, str]:
    """Find peak drama window strictly avoiding the first 3-5s intro and last 4-6s outro.

    Returns:
        (start_sec, end_sec, hook_text)
    """
    safe_min = safe_intro_offset
    safe_max = max(safe_min + target_short_duration, video_duration - safe_outro_offset)

    from .shorts_generator import find_highest_tension_window

    raw_start, raw_end, hook = find_highest_tension_window(
        recap_script_path,
        target_duration=target_short_duration,
    )

    # Clamp within safe zones
    clamped_start = max(safe_min, min(raw_start, safe_max - target_short_duration))
    clamped_end = min(video_duration - safe_outro_offset, clamped_start + target_short_duration)

    return round(clamped_start, 2), round(clamped_end, 2), hook
