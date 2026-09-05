"""Ultra-low-bandwidth remote keyframe sniffing & static watermark detector.

Enables zero-waste acquisition for 3D AI Dynamic Manhua / Màn jù by fetching
only a tiny 2-second stream segment (~250 KB) and auditing corner zones for
baked-in creator logos and watermarks before committing to full downloads.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from typing import Any, Sequence

import numpy as np
from PIL import Image

from . import ensure_dir, log, require_binary

_BILIBILI_REFERER = "https://www.bilibili.com/"


def _yt_dlp_cmd() -> list[str]:
    venv_yt = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".venv", "Scripts", "yt-dlp.exe"))
    if os.path.isfile(venv_yt):
        return [venv_yt]
    import shutil
    yt = shutil.which("yt-dlp")
    if yt:
        return [yt]
    return ["yt-dlp"]


def sniff_remote_sample_clip(
    video_url: str,
    start_sec: float = 25.0,
    duration_sec: float = 2.0,
    output_path: str | None = None,
    timeout: float = 25.0,
) -> str | None:
    """Download a tiny ~250 KB snippet using yt-dlp section slicing."""
    if not output_path:
        scratch_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scratch"))
        ensure_dir(scratch_dir)
        output_path = os.path.join(scratch_dir, f"sniff_{int(time.time()*1000)}.mp4")

    ensure_dir(os.path.dirname(os.path.abspath(output_path)))
    if os.path.exists(output_path):
        try:
            os.remove(output_path)
        except OSError:
            pass

    end_sec = start_sec + duration_sec
    section_arg = f"*{start_sec:.1f}-{end_sec:.1f}"

    cmd = _yt_dlp_cmd() + [
        "--no-warnings",
        "--quiet",
        "--download-sections", section_arg,
        "--force-keyframes-at-cuts",
        "--referer", _BILIBILI_REFERER,
        "--extractor-args", "bilibili:player_client=android",
        "-f", "bestvideo[height<=480]/best",
        "-o", output_path,
        video_url,
    ]

    try:
        subprocess.run(cmd, capture_output=True, timeout=timeout)
        if os.path.isfile(output_path) and os.path.getsize(output_path) > 1024:
            return output_path
        base_no_ext = os.path.splitext(output_path)[0]
        for ext in (".mp4", ".mkv", ".webm"):
            candidate = f"{base_no_ext}{ext}"
            if os.path.isfile(candidate) and os.path.getsize(candidate) > 1024:
                return candidate
    except Exception as exc:
        log.debug("Remote snippet sniff failed for %s: %s", video_url, exc)

    return None


def extract_frames_from_clip(clip_path: str, output_dir: str) -> list[str]:
    """Extract up to 2 frames from the sniffed snippet for temporal analysis."""
    ensure_dir(output_dir)
    ffmpeg = require_binary("ffmpeg")
    base = os.path.splitext(os.path.basename(clip_path))[0]

    frame_paths = [
        os.path.join(output_dir, f"{base}_f1.jpg"),
        os.path.join(output_dir, f"{base}_f2.jpg"),
    ]

    # Frame 1 at start
    subprocess.run([
        ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
        "-ss", "0.2",
        "-i", clip_path,
        "-vframes", "1",
        "-q:v", "2",
        frame_paths[0],
    ], capture_output=True)

    # Frame 2 near end
    subprocess.run([
        ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
        "-ss", "1.6",
        "-i", clip_path,
        "-vframes", "1",
        "-q:v", "2",
        frame_paths[1],
    ], capture_output=True)

    return [f for f in frame_paths if os.path.isfile(f) and os.path.getsize(f) > 512]


def detect_static_corner_watermark(frame_paths: list[str]) -> dict[str, Any]:
    """Analyze corner zones across frames for static watermark/logo persistence."""
    if not frame_paths:
        return {"has_watermark": False, "confidence": 0.0, "zone": None, "is_clean": True}

    imgs = []
    for fp in frame_paths:
        try:
            with Image.open(fp) as im:
                imgs.append(np.array(im.convert("L"), dtype=np.float32))
        except Exception:
            continue

    if not imgs:
        return {"has_watermark": False, "confidence": 0.0, "zone": None, "is_clean": True}

    detected_zone = None
    max_confidence = 0.0
    zone_details = {}

    for idx, arr in enumerate(imgs):
        h, w = arr.shape
        zones = {
            "top_right": arr[0:int(h * 0.15), int(w * 0.70):w],
            "top_left": arr[0:int(h * 0.15), 0:int(w * 0.30)],
            "bottom_right": arr[int(h * 0.85):h, int(w * 0.70):w],
            "bottom_left": arr[int(h * 0.85):h, 0:int(w * 0.30)],
        }

        for z_name, z_arr in zones.items():
            gx = np.abs(np.diff(z_arr, axis=1))
            gy = np.abs(np.diff(z_arr, axis=0))
            sharp_edges = (gx[:-1, :] > 25) | (gy[:, :-1] > 25)
            edge_pct = float(np.mean(sharp_edges) * 100.0)

            white_text = (z_arr[:-1, :-1] > 180) & sharp_edges
            white_text_pct = float(np.mean(white_text) * 100.0)

            # High density of sharp white characters (watermark / logo glyphs)
            if white_text_pct > 2.0 or (edge_pct > 12.0 and "top" in z_name):
                conf = min(0.99, (white_text_pct / 3.5) * 0.9 + 0.1)
                if conf > max_confidence:
                    max_confidence = conf
                    detected_zone = z_name
                zone_details[z_name] = {
                    "edge_pct": round(edge_pct, 2),
                    "white_text_pct": round(white_text_pct, 2),
                }

    has_wm = detected_zone is not None and max_confidence >= 0.60
    return {
        "has_watermark": has_wm,
        "confidence": round(float(max_confidence), 2),
        "zone": detected_zone if has_wm else None,
        "is_clean": not has_wm,
        "zone_details": zone_details,
    }


def screen_candidate_series(
    video_url: str,
    preview_dir: str | None = None,
    keep_preview_image: bool = True,
) -> dict[str, Any]:
    """End-to-end zero-waste pre-screening for a candidate series URL.

    Fetches ~250 KB snippet, audits corners, produces preview image, and cleans up snippet.
    """
    t0 = time.time()
    if not preview_dir:
        preview_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "storage", "previews"))
    ensure_dir(preview_dir)

    clip_path = sniff_remote_sample_clip(video_url, start_sec=20.0, duration_sec=2.0)
    if not clip_path:
        return {
            "url": video_url,
            "has_watermark": False,
            "is_clean": True,
            "error": "Could not sniff remote keyframe",
            "latency_seconds": round(time.time() - t0, 2),
        }

    scratch_frames_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scratch", "frames"))
    frames = extract_frames_from_clip(clip_path, scratch_frames_dir)

    result = detect_static_corner_watermark(frames)
    result["url"] = video_url
    result["latency_seconds"] = round(time.time() - t0, 2)

    # Save a permanent preview image for dashboard display
    if frames and keep_preview_image:
        import hashlib
        h = hashlib.md5(video_url.encode("utf-8")).hexdigest()[:10]
        preview_dest = os.path.join(preview_dir, f"preview_{h}.jpg")
        try:
            shutil.copyfile(frames[0], preview_dest)
            result["preview_image"] = os.path.relpath(preview_dest, os.path.join(os.path.dirname(__file__), ".."))
        except Exception:
            pass

    # Cleanup temporary sniff snippet
    try:
        if os.path.isfile(clip_path):
            os.remove(clip_path)
        for f in frames:
            if os.path.isfile(f):
                os.remove(f)
    except OSError:
        pass

    return result
