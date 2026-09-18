"""Workspace Manager for OneDrama Studio.

Guarantees clean isolation between different drama series:
- Automatically archives previous runs (raw episodes, stems, scripts, dubs, master movies)
  into storage/archive/{timestamp}_{project_name}/
- Prevents cross-contamination where episodes of Drama A mix with Drama B
- Resets working directories (raw_episodes, audio_separated, tts_output, processed_episodes, master_export)
- Tracks archive manifest history
"""

from __future__ import annotations

import json
import os
import re
import shutil
import time
from typing import Any, Optional

from modules import ensure_dir, log

BASE_STORAGE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "storage"))
ARCHIVE_DIR = os.path.join(BASE_STORAGE, "archive")

WORKING_DIRS = {
    "raw": os.path.join(BASE_STORAGE, "raw_episodes"),
    "separated": os.path.join(BASE_STORAGE, "audio_separated"),
    "tts": os.path.join(BASE_STORAGE, "tts_output"),
    "processed": os.path.join(BASE_STORAGE, "processed_episodes"),
    "master": os.path.join(BASE_STORAGE, "master_export"),
    "characters": os.path.join(BASE_STORAGE, "characters"),
}


def sanitize_filename(name: str) -> str:
    clean = re.sub(r'[\\/*?:"<>|#]+', "_", name).strip()
    clean = re.sub(r"\s+", "_", clean)
    return clean[:40] if clean else "drama_project"


def get_active_workspace_status() -> dict[str, Any]:
    raw_files = []
    if os.path.isdir(WORKING_DIRS["raw"]):
        raw_files = [
            f for f in os.listdir(WORKING_DIRS["raw"])
            if not f.startswith(".") and os.path.isfile(os.path.join(WORKING_DIRS["raw"], f))
        ]

    processed_files = []
    if os.path.isdir(WORKING_DIRS["processed"]):
        processed_files = [
            f for f in os.listdir(WORKING_DIRS["processed"])
            if not f.startswith(".") and os.path.isfile(os.path.join(WORKING_DIRS["processed"], f))
        ]

    master_files = []
    if os.path.isdir(WORKING_DIRS["master"]):
        master_files = [
            f for f in os.listdir(WORKING_DIRS["master"])
            if not f.startswith(".") and f.endswith(".mp4")
        ]

    has_assets = bool(raw_files or processed_files or master_files)
    return {
        "has_active_assets": has_assets,
        "raw_episodes_count": len(raw_files),
        "raw_files": raw_files,
        "processed_episodes_count": len(processed_files),
        "master_movies_count": len(master_files),
    }


def archive_and_reset_workspace(
    project_name: Optional[str] = None,
    reason: str = "new_production",
) -> dict[str, Any]:
    status = get_active_workspace_status()
    if not status["has_active_assets"]:
        log.info("Workspace is already clean; no archiving required.")
        return {
            "archived": False,
            "message": "Workspace is already clean.",
            "archive_path": None,
            "total_files": 0,
        }

    timestamp_str = time.strftime("%Y%m%d_%H%M%S")
    safe_slug = sanitize_filename(project_name or "previous_drama")
    dest_dir = os.path.join(ARCHIVE_DIR, f"{timestamp_str}_{safe_slug}")
    ensure_dir(dest_dir)

    log.info("Archiving active project assets to: %s", dest_dir)
    archived_counts: dict[str, int] = {}
    total_moved = 0

    for key, src_dir in WORKING_DIRS.items():
        if not os.path.isdir(src_dir):
            continue

        target_sub = ensure_dir(os.path.join(dest_dir, os.path.basename(src_dir)))
        count = 0
        for item in os.listdir(src_dir):
            if item.startswith(".gitkeep"):
                continue

            src_item = os.path.join(src_dir, item)
            dst_item = os.path.join(target_sub, item)
            try:
                if os.path.isdir(src_item):
                    if os.path.exists(dst_item):
                        shutil.rmtree(dst_item)
                    shutil.move(src_item, dst_item)
                    count += 1
                elif os.path.isfile(src_item):
                    if os.path.exists(dst_item):
                        os.remove(dst_item)
                    shutil.move(src_item, dst_item)
                    count += 1
            except Exception as exc:
                log.warning("Could not archive %s: %s", src_item, exc)

        archived_counts[key] = count
        total_moved += count

        keep_file = os.path.join(src_dir, ".gitkeep")
        if not os.path.exists(keep_file):
            try:
                with open(keep_file, "w", encoding="utf-8") as f:
                    f.write("")
            except Exception:
                pass

    manifest = {
        "timestamp": time.time(),
        "date_str": time.strftime("%Y-%m-%d %H:%M:%S"),
        "project_name": project_name or "Archived Drama",
        "reason": reason,
        "counts": archived_counts,
        "total_items": total_moved,
    }
    with open(os.path.join(dest_dir, "archive_manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    log.info("Successfully archived %d items to %s", total_moved, dest_dir)
    return {
        "archived": True,
        "archive_path": dest_dir,
        "total_files": total_moved,
        "counts": archived_counts,
        "message": f"Successfully archived previous drama ({total_moved} files) into storage/archive.",
    }


def list_archives() -> list[dict[str, Any]]:
    if not os.path.isdir(ARCHIVE_DIR):
        return []

    results = []
    for item in sorted(os.listdir(ARCHIVE_DIR), reverse=True):
        full_path = os.path.join(ARCHIVE_DIR, item)
        if not os.path.isdir(full_path):
            continue

        manifest_file = os.path.join(full_path, "archive_manifest.json")
        if os.path.isfile(manifest_file):
            try:
                with open(manifest_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    data["folder_name"] = item
                    data["path"] = full_path
                    results.append(data)
                    continue
            except Exception:
                pass

        results.append({
            "folder_name": item,
            "path": full_path,
            "project_name": item,
            "total_items": len(os.listdir(full_path)),
        })

    return results
