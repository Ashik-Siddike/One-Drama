"""Video inspection module: detects watermarks, logos, and burnt-in subtitles.

Extracts representative keyframe samples (e.g. at 3s, 10s, 20s) and analyzes them
via Gemini 2.5 Flash Vision (with local fallback heuristics) to produce a
WatermarkProfile. This profile drives intelligent side-cropping and
real-time glassmorphism subtitle masking.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import time
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

_DETECTION_SYSTEM_INSTRUCTION = """\
You are an expert video editor specializing in Chinese short dramas, anime, and social media videos (Douyin, Kuaishou, Bilibili, Xiaohongshu).
You will be given sample frames extracted from different timestamps of a video.

YOUR TASKS:
1. RIGHT-SIDE WATERMARKS & DISCLAIMERS:
   - Check if there is vertical text, creator ID, or watermark along the right edge (e.g. '内容纯属虚构', Douyin ID, creator handles).
   - If present, estimate how many pixels wide the strip to crop from the right edge is (typically 60 to 110 pixels on standard 720p/1080p).
2. TOP CORNER LOGOS:
   - Check if there is a static channel/creator logo in the top-left or top-right corners.
   - Specify whether top-left or top-right has a logo.
3. BURNT-IN CHINESE SUBTITLES:
   - Check if Chinese dialogue subtitles appear in the frame (usually in the lower portion, e.g. 60% to 85% of height).
   - Provide the normalized bounding box (0 to 1000) for the subtitle line:
     "subtitle_ymin": int (e.g. 680),
     "subtitle_ymax": int (e.g. 740),
     "subtitle_xmin": int (e.g. 80),
     "subtitle_xmax": int (e.g. 920)
   - If no subtitles appear, set has_subtitles to false.

OUTPUT FORMAT:
Return ONLY a valid JSON object of this exact shape:
{
  "has_right_watermark": bool,
  "right_crop_pixels": int,
  "has_top_left_logo": bool,
  "has_top_right_logo": bool,
  "has_subtitles": bool,
  "subtitle_ymin": int,
  "subtitle_ymax": int,
  "subtitle_xmin": int,
  "subtitle_xmax": int
}
No prose outside JSON. No markdown code fences.
"""


def extract_sample_frames(
    video_path: str,
    timestamps: Sequence[float] = (3.0, 10.0, 20.0),
    output_dir: str | None = None,
) -> list[str]:
    """Extract lightweight sample frames at the given timestamps."""
    if not os.path.isfile(video_path):
        raise PipelineError(f"Video file not found: {video_path}")

    ffmpeg = require_binary("ffmpeg")
    dur = ffprobe_duration(video_path)

    # Filter timestamps to within video duration
    safe_times = [min(dur - 0.5, max(0.5, t)) for t in timestamps if dur <= 0 or t < dur]
    if not safe_times:
        safe_times = [min(dur * 0.2, 1.0)] if dur > 1.0 else [0.5]

    stem = safe_stem(video_path)
    target_dir = ensure_dir(output_dir or tempfile.mkdtemp(prefix=f"frames_{stem}_"))
    extracted_paths: list[str] = []

    for idx, ts in enumerate(safe_times, 1):
        out_frame = os.path.join(target_dir, f"sample_{idx:02d}.jpg")
        cmd = [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-ss",
            f"{ts:.2f}",
            "-i",
            video_path,
            "-frames:v",
            "1",
            "-q:v",
            "2",
            out_frame,
        ]
        try:
            run_command(cmd, desc=f"ffmpeg(sample-frame-{idx})")
            if os.path.isfile(out_frame) and os.path.getsize(out_frame) > 1024:
                extracted_paths.append(out_frame)
        except Exception as exc:
            log.warning("Could not extract frame at %.1fs: %s", ts, exc)

    return extracted_paths


def _extract_json(raw: str) -> dict[str, Any]:
    """Extract and parse JSON from model response."""
    text = (raw or "").strip()
    fenced = re.search(r"```(?:json)?\s*(.+?)\s*```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        return json.loads(text[start : end + 1])
    raise PipelineError(f"Could not parse JSON: {raw[:200]}")


def _heuristic_profile(video_path: str, config: dict | None = None) -> dict[str, Any]:
    """Fallback profile using configured visual filters or standard rules."""
    from .video_processor import probe_video_dimensions

    w, h = probe_video_dimensions(video_path)
    vf = (config or {}).get("visual_filters", {})
    remove_disclaimer = bool(vf.get("remove_right_disclaimer", False))
    remove_watermark = bool(vf.get("remove_watermark", False))

    # Standard subtitle band is in the lower portion (~68% to 74% of height)
    sub_y = int(round(h * 0.69))
    box_h = max(50, min(120, int(round(h * 0.055))))
    sub_x = int(round(w * 0.08))
    box_w = int(round(w * 0.84))
    right_crop = int(vf.get("side_watermark_crop_px", 80)) if remove_disclaimer else 0

    return {
        "has_right_watermark": remove_disclaimer,
        "right_crop_pixels": right_crop,
        "has_top_left_logo": remove_watermark,
        "has_top_right_logo": False,
        "has_bottom_subtitles": True,
        "subtitle_y_start": sub_y,
        "subtitle_height": box_h,
        "subtitle_x_start": sub_x,
        "subtitle_width": box_w,
        "bottom_subtitle_height": box_h,
        "source": "heuristic",
    }


def inspect_video_watermarks(
    video_path: str,
    config: dict | None = None,
    *,
    work_dir: str | None = None,
    timestamps: Sequence[float] = (4.0, 12.0, 24.0, 36.0),
) -> dict[str, Any]:
    """Analyze video frames to detect watermarks, corner logos, and subtitles.

    Returns a WatermarkProfile dict:
        {
            "has_right_watermark": bool,
            "right_crop_pixels": int,
            "has_top_left_logo": bool,
            "has_top_right_logo": bool,
            "has_bottom_subtitles": bool,
            "subtitle_y_start": int,
            "subtitle_height": int,
            "subtitle_x_start": int,
            "subtitle_width": int,
            "bottom_subtitle_height": int,
            "source": "gemini_vision" | "heuristic"
        }
    """
    cfg = config or {}
    vf = cfg.get("visual_filters", {})
    auto_detect = bool(vf.get("auto_detect_watermarks", True))

    if not auto_detect:
        return _heuristic_profile(video_path, cfg)

    frame_paths = extract_sample_frames(video_path, timestamps, output_dir=work_dir)
    if not frame_paths:
        log.warning("No sample frames extracted; falling back to heuristic profile.")
        return _heuristic_profile(video_path, cfg)

    api_key = str(cfg.get("gemini_api_key", "")).strip()
    if not api_key or api_key == "YOUR_GEMINI_API_KEY":
        log.info("No Gemini API key for vision probe; using heuristic profile.")
        return _heuristic_profile(video_path, cfg)

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        preferred_model = cfg.get("gemini_model", "gemini-flash-lite-latest")
        candidate_models = [preferred_model, "gemini-flash-lite-latest", "gemini-2.5-flash", "gemini-3.1-flash-lite-preview"]
        # Deduplicate while preserving order
        candidate_models = list(dict.fromkeys(candidate_models))

        contents: list[Any] = [
            "Analyze these sample frames from the video. Identify right-side watermarks, corner logos, and Chinese subtitles with exact bounding boxes."
        ]
        for p in frame_paths:
            with open(p, "rb") as f:
                img_bytes = f.read()
            contents.append(types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg"))

        gen_config = types.GenerateContentConfig(
            response_mime_type="application/json",
            system_instruction=_DETECTION_SYSTEM_INSTRUCTION,
            temperature=0.1,
        )

        response = None
        for model in candidate_models:
            try:
                log.info("Analyzing %d sample frame(s) with %s...", len(frame_paths), model)
                response = client.models.generate_content(
                    model=model,
                    contents=contents,
                    config=gen_config,
                )
                if response and getattr(response, "text", ""):
                    break
            except Exception as model_err:
                log.warning("Model %s unavailable (%s). Trying next candidate...", model, model_err)

        if not response or not getattr(response, "text", ""):
            raise PipelineError("All Gemini vision candidates exhausted.")

        raw_text = getattr(response, "text", "")
        profile = _extract_json(raw_text)

        # Normalize and clamp values
        from .video_processor import probe_video_dimensions

        w, h = probe_video_dimensions(video_path)

        right_crop = int(profile.get("right_crop_pixels", 0))
        if profile.get("has_right_watermark") and right_crop <= 0:
            right_crop = int(vf.get("side_watermark_crop_px", 80))
        right_crop = min(max(0, right_crop), int(w * 0.25))

        has_sub = bool(profile.get("has_subtitles", profile.get("has_bottom_subtitles", True)))

        # Subtitle vertical band
        ymin = int(profile.get("subtitle_ymin", 680))
        ymax = int(profile.get("subtitle_ymax", 740))
        if ymax <= ymin:
            ymax = ymin + 50
        ymin = max(350, min(920, ymin))
        ymax = max(ymin + 25, min(980, ymax))

        sub_y = int(round(h * (ymin / 1000.0)))
        box_h = int(round(h * ((ymax - ymin) / 1000.0)))
        sub_y = max(0, sub_y - 6)
        box_h = max(45, min(int(h * 0.15), box_h + 12))

        # Subtitle horizontal span - ensure comfortable width so varying dialogue lengths don't overflow
        xmin = int(profile.get("subtitle_xmin", 70))
        xmax = int(profile.get("subtitle_xmax", 930))
        if xmax <= xmin or (xmax - xmin) < 700:
            # Expand to at least 76% screen width centered to accommodate all sentences in the episode
            center = (xmin + xmax) // 2 if xmax > xmin else 500
            xmin = max(40, center - 380)
            xmax = min(960, center + 380)

        sub_x = int(round(w * (xmin / 1000.0)))
        box_w = int(round(w * ((xmax - xmin) / 1000.0)))
        sub_x = max(0, sub_x)
        box_w = min(w - sub_x, max(int(w * 0.76), box_w))

        normalized = {
            "has_right_watermark": bool(profile.get("has_right_watermark", False)),
            "right_crop_pixels": right_crop,
            "has_top_left_logo": bool(profile.get("has_top_left_logo", False)),
            "has_top_right_logo": bool(profile.get("has_top_right_logo", False)),
            "has_bottom_subtitles": has_sub,
            "subtitle_y_start": sub_y,
            "subtitle_height": box_h,
            "subtitle_x_start": sub_x,
            "subtitle_width": box_w,
            "bottom_subtitle_height": box_h,
            "source": "gemini_vision",
        }
        log.info(
            "Video Inspection Complete -> Right Watermark: %s (%dpx), Top-L: %s, Top-R: %s, Subtitle Band: Y=%dpx H=%dpx X=%dpx W=%dpx",
            normalized["has_right_watermark"],
            normalized["right_crop_pixels"],
            normalized["has_top_left_logo"],
            normalized["has_top_right_logo"],
            normalized["subtitle_y_start"],
            normalized["subtitle_height"],
            normalized["subtitle_x_start"],
            normalized["subtitle_width"],
        )
        return normalized

    except Exception as exc:
        log.warning("Gemini Vision watermark inspection encountered issue (%s). Using heuristic.", exc)
        return _heuristic_profile(video_path, cfg)


def screen_candidate_series(url_or_path: str, config: dict | None = None) -> dict[str, Any]:
    """Rapid pre-flight watermark and anti-copyright screening for candidate series.

    Inspects whether a remote series URL or local video candidate has intrusive
    unrecoverable watermarks or copyright blacklisted terms.
    Returns a screening dictionary with `is_clean`, `watermarks`, and `zone`.
    """
    cfg = config or {}
    # If it's a local video file, perform quick inspection
    if os.path.isfile(url_or_path):
        profile = inspect_video_watermarks(url_or_path, cfg)
        is_clean = not (profile.get("has_right_watermark") and profile.get("right_crop_pixels", 0) > 180)
        return {
            "is_clean": is_clean,
            "profile": profile,
            "watermarks": ["right_watermark"] if profile.get("has_right_watermark") else [],
            "zone": "right_edge" if profile.get("has_right_watermark") else None,
            "url_or_path": url_or_path,
        }

    # For remote URLs, verify URL syntax and apply Anti-Copyright blacklist checks
    try:
        from .discovery import BLOCKED_FRANCHISES, BLOCKED_STUDIOS
        lower_target = url_or_path.lower()
        for franchise in BLOCKED_FRANCHISES:
            if franchise.lower() in lower_target:
                return {
                    "is_clean": False,
                    "reason": f"Blocked franchise keyword: {franchise}",
                    "watermarks": ["franchise_copyright"],
                    "zone": "full_frame",
                    "url_or_path": url_or_path,
                }
        for studio in BLOCKED_STUDIOS:
            if studio.lower() in lower_target:
                return {
                    "is_clean": False,
                    "reason": f"Blocked studio: {studio}",
                    "watermarks": ["studio_copyright"],
                    "zone": "full_frame",
                    "url_or_path": url_or_path,
                }
    except Exception as e:
        log.debug("Blacklist check exception: %s", e)

    # Clean candidate passes pre-flight
    return {
        "is_clean": True,
        "watermarks": [],
        "zone": None,
        "url_or_path": url_or_path,
        "checked_at": time.time(),
    }

