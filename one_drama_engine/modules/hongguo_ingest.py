"""Hongguo Drama Ingestion Module for OneDrama.

Bridges downloaded dramas from Hongguo Downloader into OneDrama's raw_episodes workspace.
Uses zero-cost NTFS hardlinks so staging is instantaneous and consumes 0 additional disk space.
"""

from __future__ import annotations

import glob
import json
import os
import re
import shutil
from typing import Any

from . import ensure_dir, log

DEFAULT_HONGGUO_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "storage", "hongguo_downloads")
)
DEFAULT_RAW_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "storage", "raw_episodes")
)


def _natural_sort_key(s: str) -> list[int | str]:
    """Natural sort key helper so '第002集' comes before '第010集' and '2' before '10'."""
    parts = re.split(r"(\d+)", s)
    return [int(p) if p.isdigit() else p.lower() for p in parts]


def list_hongguo_dramas(hongguo_dir: str = DEFAULT_HONGGUO_DIR) -> list[dict[str, Any]]:
    """Scan the Hongguo downloads folder and return available series with metadata."""
    if not os.path.isdir(hongguo_dir):
        return []

    entries = []
    for item in os.listdir(hongguo_dir):
        full_path = os.path.join(hongguo_dir, item)
        if not os.path.isdir(full_path):
            continue

        mp4_files = [
            f
            for f in os.listdir(full_path)
            if f.lower().endswith(".mp4") and os.path.isfile(os.path.join(full_path, f))
        ]
        if not mp4_files:
            continue

        meta_file = os.path.join(full_path, ".series.json")
        meta: dict[str, Any] = {}
        if os.path.isfile(meta_file):
            try:
                with open(meta_file, "r", encoding="utf-8") as fp:
                    meta = json.load(fp)
            except Exception:
                pass

        title = meta.get("title") or item
        mtime = os.path.getmtime(full_path)

        entries.append(
            {
                "title": title,
                "dir_name": item,
                "full_path": full_path,
                "episodes_count": len(mp4_files),
                "total_expected": meta.get("total", len(mp4_files)),
                "score": meta.get("score", "N/A"),
                "series_id": meta.get("series_id", ""),
                "cover": meta.get("cover", ""),
                "mtime": mtime,
            }
        )

    # Sort by newest downloaded first
    entries.sort(key=lambda x: x["mtime"], reverse=True)
    for idx, e in enumerate(entries, start=1):
        e["index"] = idx

    return entries


def stage_hongguo_drama(
    selector: str | int = "latest",
    raw_dir: str = DEFAULT_RAW_DIR,
    hongguo_dir: str = DEFAULT_HONGGUO_DIR,
    clean_raw_first: bool = True,
) -> dict[str, Any]:
    """Stage a downloaded Hongguo drama into storage/raw_episodes with standard names (ep_001.mp4...).

    Uses NTFS hardlinks for zero disk usage and instant operation.
    """
    dramas = list_hongguo_dramas(hongguo_dir)
    if not dramas:
        raise RuntimeError(f"No downloaded dramas found in {hongguo_dir}")

    target_drama = None

    if selector in ("latest", None, ""):
        target_drama = dramas[0]
    elif isinstance(selector, int) or (isinstance(selector, str) and selector.isdigit()):
        idx = int(selector)
        if 1 <= idx <= len(dramas):
            target_drama = dramas[idx - 1]
        else:
            raise ValueError(f"Invalid drama index {idx}. Available: 1 to {len(dramas)}")
    else:
        # Match by title or dir_name substring
        q = str(selector).strip().lower()
        for d in dramas:
            if q in d["title"].lower() or q in d["dir_name"].lower():
                target_drama = d
                break
        if not target_drama:
            raise ValueError(
                f"No drama matching '{selector}' found. Available: {[d['title'] for d in dramas]}"
            )

    ensure_dir(raw_dir)

    # Clean existing raw_episodes if requested
    if clean_raw_first:
        for f in os.listdir(raw_dir):
            if f.startswith("."):
                continue
            fp = os.path.join(raw_dir, f)
            if os.path.isfile(fp):
                os.remove(fp)

    # Find and sort all episodes
    drama_path = target_drama["full_path"]
    ep_files = [
        f
        for f in os.listdir(drama_path)
        if f.lower().endswith(".mp4") and os.path.isfile(os.path.join(drama_path, f))
    ]
    ep_files.sort(key=_natural_sort_key)

    staged_episodes = []
    for idx, filename in enumerate(ep_files, start=1):
        src_fp = os.path.join(drama_path, filename)
        target_name = f"ep_{idx:03d}.mp4"
        dest_fp = os.path.join(raw_dir, target_name)

        # Remove dest if exists
        if os.path.exists(dest_fp):
            os.remove(dest_fp)

        # Try hardlink (instantaneous, zero disk copy)
        try:
            os.link(src_fp, dest_fp)
        except Exception:
            shutil.copy2(src_fp, dest_fp)

        staged_episodes.append(
            {
                "standard_name": target_name,
                "original_name": filename,
                "path": dest_fp,
                "size_mb": round(os.path.getsize(dest_fp) / (1024 * 1024), 2),
            }
        )

    # Write series info
    info_path = os.path.join(raw_dir, "series_info.json")
    with open(info_path, "w", encoding="utf-8") as fp:
        json.dump(
            {
                "title": target_drama["title"],
                "series_id": target_drama["series_id"],
                "total_staged": len(staged_episodes),
                "source_dir": drama_path,
                "score": target_drama["score"],
                "cover": target_drama["cover"],
            },
            fp,
            indent=2,
            ensure_ascii=False,
        )

    log.info(
        "Successfully staged drama '%s' (%d episodes) into %s",
        target_drama["title"],
        len(staged_episodes),
        raw_dir,
    )

    return {
        "title": target_drama["title"],
        "series_id": target_drama["series_id"],
        "total_staged": len(staged_episodes),
        "source_dir": drama_path,
        "episodes": staged_episodes,
    }
