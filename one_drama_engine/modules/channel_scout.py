"""Autonomous Safe Creators Brain & Production History Ledger.

Manages verified clean 3D dynamic manhua creators, deduplicates previously
processed series, and enforces a mandatory last-mile pre-flight watermark audit
even on whitelisted safe channels.
"""

from __future__ import annotations

import datetime
import json
import os
import subprocess
import time
from typing import Any, Sequence

from . import ensure_dir, log, read_json, write_json
from .watermark_detector import screen_candidate_series

DEFAULT_SAFE_CREATORS_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "storage", "safe_creators.json")
)
DEFAULT_HISTORY_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "storage", "production_history.json")
)

_BILIBILI_REFERER = "https://www.bilibili.com/"
_BILIBILI_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


def _yt_dlp_cmd() -> list[str]:
    venv_yt = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", ".venv", "Scripts", "yt-dlp.exe")
    )
    if os.path.isfile(venv_yt):
        return [venv_yt]
    import shutil
    yt = shutil.which("yt-dlp")
    if yt:
        return [yt]
    return ["yt-dlp"]


# --------------------------------------------------------------------------- #
# 1. Production History Ledger (Deduplication Guard)
# --------------------------------------------------------------------------- #
class ProductionHistory:
    """Tracks all series that have been processed, downloaded, or rejected."""

    def __init__(self, filepath: str = DEFAULT_HISTORY_PATH):
        self.filepath = filepath
        ensure_dir(os.path.dirname(self.filepath))
        self.data: dict[str, Any] = read_json(self.filepath, default={"processed_series": {}})
        if "processed_series" not in self.data:
            self.data["processed_series"] = {}

    def is_known(self, series_id_or_url: str) -> bool:
        """Check if a series ID or URL has already been processed or rejected."""
        key = self._extract_key(series_id_or_url)
        return key in self.data["processed_series"]

    def get_status(self, series_id_or_url: str) -> str | None:
        key = self._extract_key(series_id_or_url)
        entry = self.data["processed_series"].get(key)
        return entry.get("status") if entry else None

    def record_series(
        self,
        series_id_or_url: str,
        title: str = "",
        status: str = "completed",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Record a series in the permanent ledger."""
        key = self._extract_key(series_id_or_url)
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.data["processed_series"][key] = {
            "series_id": key,
            "title": title,
            "url": series_id_or_url if "http" in series_id_or_url else f"https://www.bilibili.com/video/{key}",
            "status": status,
            "recorded_at": now_str,
            "metadata": metadata or {},
        }
        write_json(self.filepath, self.data)
        log.debug("ProductionHistory: Recorded %s with status '%s'", key, status)

    @staticmethod
    def _extract_key(val: str) -> str:
        """Extract clean BV id or unique identifier."""
        import re
        match = re.search(r"(BV[0-9a-zA-Z]{10})", val)
        if match:
            return match.group(1)
        return val.strip().rstrip("/").split("/")[-1]


# --------------------------------------------------------------------------- #
# 2. Safe Creators Registry (Verified Whitelist Brain)
# --------------------------------------------------------------------------- #
class SafeCreatorsRegistry:
    """Maintains a database of vetted, high-integrity Bilibili creators."""

    def __init__(self, filepath: str = DEFAULT_SAFE_CREATORS_PATH):
        self.filepath = filepath
        ensure_dir(os.path.dirname(self.filepath))
        self.data: dict[str, Any] = read_json(
            self.filepath, default={"creators": {}, "metadata": {"last_updated": None}}
        )
        if "creators" not in self.data:
            self.data["creators"] = {}

    def list_verified_creators(self) -> list[dict[str, Any]]:
        """Return list of creators sorted by clean ratio and reliability."""
        verified = [
            c for c in self.data["creators"].values()
            if c.get("is_verified_safe", False) and c.get("clean_ratio", 0.0) >= 0.75
        ]
        verified.sort(key=lambda x: (x.get("clean_ratio", 0.0), x.get("total_audited", 0)), reverse=True)
        return verified

    def get_creator(self, creator_mid_or_name: str) -> dict[str, Any] | None:
        key = str(creator_mid_or_name).strip()
        return self.data["creators"].get(key)

    def register_or_update_creator(
        self,
        creator_id: str,
        name: str,
        space_url: str = "",
        clean_count: int = 0,
        total_audited: int = 0,
        recent_series: list[str] | None = None,
    ) -> dict[str, Any]:
        """Save or update a creator's audit scorecard."""
        key = str(creator_id).strip()
        ratio = round(clean_count / max(1, total_audited), 2)
        is_safe = ratio >= 0.75 and total_audited >= 3

        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        record = {
            "creator_id": key,
            "name": name,
            "space_url": space_url or f"https://space.bilibili.com/{key}",
            "clean_count": clean_count,
            "total_audited": total_audited,
            "clean_ratio": ratio,
            "is_verified_safe": is_safe,
            "last_audited": now_str,
            "known_series": recent_series or [],
        }
        self.data["creators"][key] = record
        self.data["metadata"]["last_updated"] = now_str
        write_json(self.filepath, self.data)
        log.info(
            "SafeCreators: Updated '%s' (clean: %d/%d, ratio: %.2f, safe: %s)",
            name, clean_count, total_audited, ratio, is_safe,
        )
        return record


# --------------------------------------------------------------------------- #
# 3. Autonomous Channel Scout & Multi-Video Auditor
# --------------------------------------------------------------------------- #
def audit_creator_channel(
    channel_url_or_mid: str,
    max_videos_to_audit: int = 5,
    registry: SafeCreatorsRegistry | None = None,
) -> dict[str, Any]:
    """Inspect up to 5 recent uploads from a creator space and audit watermarks."""
    reg = registry or SafeCreatorsRegistry()
    mid = str(channel_url_or_mid).strip()
    if "space.bilibili.com" in mid:
        import re
        m = re.search(r"space\.bilibili\.com/(\d+)", mid)
        if m:
            mid = m.group(1)

    space_url = f"https://space.bilibili.com/{mid}/video" if mid.isdigit() else channel_url_or_mid

    log.info("Auditing creator channel: %s (sampling up to %d videos)...", space_url, max_videos_to_audit)
    cmd = _yt_dlp_cmd() + [
        "--ignore-config",
        "--no-warnings",
        "--dump-json",
        "--flat-playlist",
        "--playlist-items", f"1-{max_videos_to_audit}",
        "--referer", _BILIBILI_REFERER,
        "--user-agent", _BILIBILI_UA,
        space_url,
    ]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
    except Exception as exc:
        log.error("Failed to query creator space: %s", exc)
        return {"error": str(exc), "is_safe": False}

    videos = []
    creator_name = f"UP_{mid}"
    for line in proc.stdout.strip().splitlines():
        if not line:
            continue
        try:
            item = json.loads(line)
            videos.append(item)
            if item.get("uploader"):
                creator_name = item.get("uploader")
        except json.JSONDecodeError:
            continue

    if not videos:
        log.warning("No videos retrieved from creator space %s", space_url)
        return {"creator_id": mid, "name": creator_name, "is_safe": False, "audited": 0}

    clean_count = 0
    total_audited = 0
    series_ids = []

    for vid in videos:
        url = vid.get("url") or vid.get("webpage_url") or f"https://www.bilibili.com/video/{vid.get('id')}"
        vid_id = vid.get("id") or url
        series_ids.append(vid_id)

        # Run ultra-fast 250 KB snippet watermark screen
        log.debug("  Sniffing video %s from creator %s...", vid_id, creator_name)
        result = screen_candidate_series(url)
        total_audited += 1
        if result.get("is_clean", False):
            clean_count += 1

    return reg.register_or_update_creator(
        creator_id=mid,
        name=creator_name,
        space_url=space_url,
        clean_count=clean_count,
        total_audited=total_audited,
        recent_series=series_ids,
    )


# --------------------------------------------------------------------------- #
# 4. Smart Sourcing Dispatcher (Dual-Track with Mandatory Pre-Flight Gate)
# --------------------------------------------------------------------------- #
def get_next_clean_candidate(
    priority: str = "micro",
    history: ProductionHistory | None = None,
    registry: SafeCreatorsRegistry | None = None,
) -> dict[str, Any] | None:
    """Find the next 100% clean, unworked 3D dynamic manhua series.

    Follows user's strict rules:
    1. Skip any series already processed in ProductionHistory.
    2. Check Verified Safe Creators pool first (Track 1).
    3. MANDATORY PRE-FLIGHT SCAN: Even for safe creators, verify that specific
       candidate has zero watermarks before approving!
    4. Fallback to general discovery if no clean candidate in pool (Track 2).
    """
    hist = history or ProductionHistory()
    reg = registry or SafeCreatorsRegistry()

    # Track 1: Query verified safe creators
    safe_creators = reg.list_verified_creators()
    if safe_creators:
        log.info("Track 1: Checking %d verified safe creator(s) for fresh series...", len(safe_creators))
        for creator in safe_creators:
            # Query creator's recent series
            space_url = creator.get("space_url") or f"https://space.bilibili.com/{creator['creator_id']}/video"
            cmd = _yt_dlp_cmd() + [
                "--ignore-config",
                "--no-warnings",
                "--dump-json",
                "--flat-playlist",
                "--playlist-items", "1-10",
                "--referer", _BILIBILI_REFERER,
                "--user-agent", _BILIBILI_UA,
                space_url,
            ]
            try:
                proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=25)
                for line in proc.stdout.strip().splitlines():
                    if not line:
                        continue
                    item = json.loads(line)
                    url = item.get("url") or item.get("webpage_url") or f"https://www.bilibili.com/video/{item.get('id')}"
                    title = item.get("title", "")

                    # Step 1: Deduplication check
                    if hist.is_known(url):
                        log.debug("Skipping already processed series: %s", title)
                        continue

                    # Step 2: MANDATORY PRE-FLIGHT WATERMARK SCAN
                    log.info("Running mandatory pre-flight watermark scan on candidate from safe creator '%s': %s", creator["name"], title)
                    screen_res = screen_candidate_series(url)
                    if screen_res.get("is_clean", True):
                        log.info("PASSED Pre-Flight Scan! Approved clean candidate: %s", title)
                        return {
                            "source_track": "safe_creators_brain",
                            "creator_name": creator["name"],
                            "creator_id": creator["creator_id"],
                            "title": title,
                            "url": url,
                            "episodes": item.get("n_entries") or 1,
                            "watermark_screen": screen_res,
                        }
                    else:
                        log.warning(
                            "REJECTED: Creator '%s' uploaded a series with watermark (%s): %s",
                            creator["name"], screen_res.get("zone"), title
                        )
                        hist.record_series(url, title, status="rejected_watermarked")
            except Exception as exc:
                log.debug("Track 1 query failed for creator %s: %s", creator.get("name"), exc)

    # Track 2: Fallback to General 3D Micro-Series Discovery
    log.info("Track 2: Scouting general 3D Micro-Series radar for fresh candidates...")
    from .discovery import search_and_screen_3d_manhua

    general_results = search_and_screen_3d_manhua("3D 动态漫画 重生", max_candidates=6, screen_watermarks=True)
    for cand in general_results:
        url = cand.get("url", "")
        title = cand.get("title", "")
        if hist.is_known(url):
            continue

        if cand.get("is_clean", False):
            # Candidate is clean! Check if we should audit its creator for our brain
            uploader = cand.get("uploader", "")
            log.info("Found clean candidate from new creator '%s': %s", uploader, title)
            return {
                "source_track": "general_scout",
                "creator_name": uploader,
                "title": title,
                "url": url,
                "episodes": cand.get("episodes", 1),
                "watermark_screen": cand.get("watermark_screening", {}),
            }
        else:
            hist.record_series(url, title, status="rejected_watermarked")

    return None
