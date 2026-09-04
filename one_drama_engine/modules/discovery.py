"""Discovery & smart recommendation stage.

Provides automated search and trend discovery for Chinese dynamic manhua (动态漫画)
with an active **Anti-Copyright Shield** that filters out globally claimed tier-1
mega-franchises (e.g. Soul Land, Battle Through the Heavens) and prioritizes domestic
indie/web-novel dynamic comics with high engagement and minimal international copyright risk.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from typing import Any, Sequence

from . import PipelineError, ensure_dir, human_time, log, read_json, write_json

# --------------------------------------------------------------------------- #
# Anti-Copyright Shield: Curated Blocklists
# --------------------------------------------------------------------------- #

# High-risk Mega Donghua & Worldwide Franchises (Strict YouTube Content-ID & international distribution)
BLOCKED_FRANCHISES: frozenset[str] = frozenset(
    {
        "斗罗大陆",
        "斗破苍穹",
        "完美世界",
        "吞噬星空",
        "一念永恒",
        "遮天",
        "凡人修仙传",
        "仙逆",
        "武动乾坤",
        "神印王座",
        "全职法师",
        "狐妖小红娘",
        "一人之下",
        "魔道祖师",
        "天官赐福",
        "大王饶命",
        "灵笼",
        "百炼成神",
        "沧元图",
        "不良人",
        "画江湖",
        "剑来",
        "武庚纪",
        "西行纪",
        "镇魂街",
        "soul land",
        "battle through the heavens",
        "perfect world",
        "swallowed star",
        "a will eternal",
        "renegade immortal",
        "scumbag system",
        "link click",
        "fog hill",
        "solo leveling",
    }
)

# High-risk global broadcasting studios / official labels
BLOCKED_STUDIOS: frozenset[str] = frozenset(
    {
        "腾讯视频动漫",
        "bilibili international",
        "bilibili animation",
        "玄机科技",
        "sparkly key",
        "福煦影视",
        "foch film",
        "中影年年",
        "若森数字",
        "wetv",
        "iqiyi animation",
        "youku animation",
    }
)

# --------------------------------------------------------------------------- #
# Curated High-Retention Dynamic Manhua Genres
# --------------------------------------------------------------------------- #
TRENDING_GENRES: dict[str, dict[str, Any]] = {
    "urban": {
        "name": "Urban Rebirth & Revenge (都市重生 / 逆袭)",
        "queries": [
            "都市修仙 动态漫画 纯享",
            "都市重生 动态漫画",
            "神医下山 动态漫画 官方",
            "赘婿逆袭 动态漫画",
            "战神归来 动态漫 纯享",
        ],
    },
    "cultivation": {
        "name": "Cultivation & Xianxia (修仙 / 玄幻 / 修真)",
        "queries": [
            "开局无敌 动态漫画 纯享",
            "玄幻修仙 动态漫画 官方",
            "万界仙王 动态漫画",
            "绝世丹神 动态漫 纯享",
            "退婚流 动态漫画",
        ],
    },
    "system": {
        "name": "Overpowered System & Leveling (无敌系统 / 签到)",
        "queries": [
            "签到系统 动态漫画 纯享",
            "神级系统 动态漫画",
            "无敌升级系统 动态漫 官方",
            "我有一座藏经阁 动态漫",
            "满级大佬 动态漫画 纯享",
        ],
    },
    "isekai": {
        "name": "Isekai & Fantasy Reincarnation (穿越 / 异界)",
        "queries": [
            "异界重生 动态漫画 纯享",
            "穿越异世 动态漫画 官方",
            "大理寺日志 动态漫",
            "转生异界 动态漫画",
            "开局签到 动态漫画 纯享",
        ],
    },
}


# --------------------------------------------------------------------------- #
# Safety Filter
# --------------------------------------------------------------------------- #
def is_copyright_safe(
    title: str, uploader: str = "", custom_blocklist: Sequence[str] | None = None
) -> tuple[bool, str]:
    """Evaluate whether a series is safe from global copyright takedowns.

    Returns:
        (is_safe: bool, reason: str)
    """
    title_clean = (title or "").lower()
    uploader_clean = (uploader or "").lower()

    # Check custom user-defined blocklist
    if custom_blocklist:
        for blocked in custom_blocklist:
            if blocked.lower() in title_clean:
                return False, f"Matches user blocklist franchise '{blocked}'"

    # Check mega franchise titles
    for franchise in BLOCKED_FRANCHISES:
        if franchise in title_clean:
            return False, f"High-risk tier-1 mega franchise '{franchise}'"

    # Check corporate broadcast channels
    for studio in BLOCKED_STUDIOS:
        if studio in uploader_clean or studio in title_clean:
            return False, f"Official broadcast studio '{studio}'"

    return True, "Safe domestic dynamic manhua"


# --------------------------------------------------------------------------- #
# Search & Discovery Core
# --------------------------------------------------------------------------- #
def _yt_dlp_cmd() -> list[str]:
    """Get the python command list to invoke yt-dlp."""
    return [sys.executable, "-m", "yt_dlp"]


_BILIBILI_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
_BILIBILI_REFERER = "https://www.bilibili.com/"


def _probe_entry_details(url: str, timeout: float = 15.0) -> dict[str, Any] | None:
    """Fetch rich metadata for a single Bilibili URL via yt-dlp."""
    cmd = _yt_dlp_cmd() + [
        "--ignore-config",
        "--no-warnings",
        "--referer",
        _BILIBILI_REFERER,
        "--user-agent",
        _BILIBILI_UA,
        "-j",
        "--playlist-items",
        "1",
        url,
    ]
    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        if proc.returncode != 0 or not proc.stdout.strip():
            return None
        data = json.loads(proc.stdout.strip().splitlines()[0])
        return data
    except Exception as exc:
        log.debug("Error probing %s: %s", url, exc)
        return None


def search_manhua_series(
    query: str,
    max_results: int = 10,
    custom_blocklist: Sequence[str] | None = None,
    timeout: float = 25.0,
) -> list[dict[str, Any]]:
    """Search Bilibili for matching dynamic manhua series.

    Returns candidate objects sorted by relevance and episode completeness.
    """
    if not query or not query.strip():
        return []

    # Ensure dynamic manhua keywords are present for precision
    search_term = query.strip()
    if not any(k in search_term for k in ("动态漫画", "动态漫", "manhua", "comic")):
        search_query = f"bilisearch{max_results}:{search_term} 动态漫画"
    else:
        search_query = f"bilisearch{max_results}:{search_term}"

    log.info("Searching Bilibili for: %s", search_query)
    cmd = _yt_dlp_cmd() + [
        "--ignore-config",
        "--no-warnings",
        "--referer",
        _BILIBILI_REFERER,
        "--user-agent",
        _BILIBILI_UA,
        "--dump-json",
        "--flat-playlist",
        search_query,
    ]

    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except Exception as exc:
        log.error("Search failed: %s", exc)
        return []

    raw_items = []
    for line in proc.stdout.strip().splitlines():
        if not line:
            continue
        try:
            raw_items.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    from concurrent.futures import ThreadPoolExecutor

    unique_items: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    for item in raw_items:
        url = item.get("url") or item.get("webpage_url") or f"https://www.bilibili.com/video/{item.get('id')}"
        if url not in seen_urls:
            seen_urls.add(url)
            unique_items.append(item)

    def _fetch_candidate(item: dict[str, Any]) -> dict[str, Any] | None:
        url = item.get("url") or item.get("webpage_url") or f"https://www.bilibili.com/video/{item.get('id')}"
        details = _probe_entry_details(url)
        if not details:
            return None
        title = details.get("title") or item.get("title") or "Unknown Manhua"
        uploader = details.get("uploader") or item.get("uploader") or ""
        view_count = details.get("view_count") or 0
        n_entries = details.get("n_entries") or 1
        duration = details.get("duration") or 0.0

        is_safe, safety_reason = is_copyright_safe(title, uploader, custom_blocklist)
        return {
            "id": details.get("id") or item.get("id"),
            "title": title,
            "uploader": uploader,
            "url": url,
            "episodes": n_entries,
            "duration_seconds": duration,
            "runtime_estimate": human_time(duration * max(1, n_entries)),
            "view_count": view_count,
            "is_safe": is_safe,
            "safety_reason": safety_reason,
        }

    candidates: list[dict[str, Any]] = []
    if unique_items:
        with ThreadPoolExecutor(max_workers=min(6, len(unique_items))) as executor:
            for cand in executor.map(_fetch_candidate, unique_items):
                if cand:
                    candidates.append(cand)

    # Sort: safe first, then by episode count and views
    candidates.sort(
        key=lambda c: (
            1 if c["is_safe"] else 0,
            c["episodes"] if c["episodes"] > 1 else 0,
            c["view_count"],
        ),
        reverse=True,
    )
    return candidates


def discover_trending_gems(
    genre: str | None = None,
    limit: int = 8,
    custom_blocklist: Sequence[str] | None = None,
) -> list[dict[str, Any]]:
    """Discover domestic trending dynamic manhua sweet-spot recommendations."""
    selected_genres = [genre.lower()] if genre and genre.lower() in TRENDING_GENRES else list(TRENDING_GENRES.keys())

    all_recommendations: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for g_key in selected_genres:
        g_info = TRENDING_GENRES[g_key]
        query = g_info["queries"][0]
        results = search_manhua_series(query, max_results=6, custom_blocklist=custom_blocklist)

        for item in results:
            if not item["is_safe"]:
                continue
            if item["id"] in seen_ids:
                continue
            seen_ids.add(item["id"])
            item["genre"] = g_info["name"]
            all_recommendations.append(item)
            if len(all_recommendations) >= limit:
                break
        if len(all_recommendations) >= limit:
            break

    return all_recommendations


# --------------------------------------------------------------------------- #
# Presentation & Formatting
# --------------------------------------------------------------------------- #
def format_catalogue_table(candidates: Sequence[dict[str, Any]]) -> str:
    """Format candidate series into a clean terminal report."""
    if not candidates:
        return "No matching manhua series found."

    lines: list[str] = [
        "=" * 82,
        f"{'#':<3} {'STATUS':<8} {'EPS':<5} {'EST. RUNTIME':<12} {'SERIES TITLE & URL'}",
        "=" * 82,
    ]

    for idx, c in enumerate(candidates, start=1):
        status = "[SAFE]" if c["is_safe"] else "[RISK]"
        eps = f"{c['episodes']} eps"
        runtime = c["runtime_estimate"]
        title_snippet = c["title"][:50]
        lines.append(f"{idx:<3} {status:<8} {eps:<5} {runtime:<12} {title_snippet}")
        lines.append(f"    URL: {c['url']} | Author: {c['uploader']} | Views: {c['view_count']}")
        if not c["is_safe"]:
            lines.append(f"    [!] Note: {c['safety_reason']}")
        lines.append("-" * 82)

    return "\n".join(lines)
