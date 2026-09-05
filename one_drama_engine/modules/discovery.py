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
    "3d_urban": {
        "name": "3D Urban Rebirth & Revenge (3D 都市重生 / 漫剧)",
        "queries": [
            "都市仙尊 3D 动态漫画 纯享",
            "都市重生 3D 漫剧",
            "神医下山 3D 动态漫 官方",
            "首富继承人 3D 漫剧",
        ],
    },
    "3d_cultivation": {
        "name": "3D Xianxia & Cultivation (3D 玄幻修仙 / 漫剧)",
        "queries": [
            "3D 玄幻 动态漫画 纯享",
            "开局无敌 3D 漫剧",
            "弃徒觉醒神体 3D 动态漫画 纯享",
            "万界仙王 3D 动态漫",
        ],
    },
    "3d_apocalypse": {
        "name": "3D Apocalypse & SSS System (3D 末日觉醒 / 漫剧)",
        "queries": [
            "末日死灵法师 3D 动态漫 纯享",
            "末日觉醒 3D 漫剧 纯享",
            "末世无敌系统 3D 动态漫画",
        ],
    },
    "3d_all": {
        "name": "3D Dynamic Manhua Collection (3D 漫剧 / 3D 动画纯享)",
        "queries": [
            "3D 动态漫画 纯享",
            "3D 漫剧 爽文",
            "AI 3D 动态漫 纯享",
        ],
    },
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
    """Get the command list to invoke yt-dlp, preferring project venv."""
    venv_yt = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", ".venv", "Scripts", "yt-dlp.exe")
    )
    if os.path.isfile(venv_yt):
        return [venv_yt]
    import shutil
    yt = shutil.which("yt-dlp")
    if yt:
        return [yt]
    return [sys.executable, "-m", "yt_dlp"]


_BILIBILI_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
_BILIBILI_REFERER = "https://www.bilibili.com/"


def _probe_entry_details(url: str, timeout: float = 25.0) -> dict[str, Any] | None:
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


# --------------------------------------------------------------------------- #
# Daily 3D Màn jù Curated Tropes & Hooks
# --------------------------------------------------------------------------- #
DAILY_3D_TROPES: list[dict[str, Any]] = [
    {
        "id": "urban_immortal",
        "title": "Urban Immortal Emperor Reborn",
        "chinese_title": "都市仙尊归来 (3D 漫剧)",
        "query": "都市仙尊 3D 动态漫画 纯享",
        "hook": "Betrayed in his past life, the supreme celestial emperor reincarnates into his 18-year-old self to protect his mother and take brutal revenge.",
        "category": "3D Urban Rebirth",
        "target_audience": "High-CTR Revenge Fantasy (Male 18-35)",
        "icon": "⚡",
    },
    {
        "id": "apocalypse_necromancer",
        "title": "SSS-Rank Necromancer in the Global Cataclysm",
        "chinese_title": "末日死灵法师 (3D 漫剧)",
        "query": "末日死灵法师 3D 动态漫 纯享",
        "hook": "When the world transforms into a bloodthirsty dungeon, he awakens an infinite shadow army to conquer all monarchs.",
        "category": "3D Apocalypse & System",
        "target_audience": "Action & Dark Fantasy (Solo Leveling Fans)",
        "icon": "🔥",
    },
    {
        "id": "sect_outcast_godbody",
        "title": "Sect Outcast Unlocks the Ancient God Body",
        "chinese_title": "弃徒觉醒太古神体 (3D 漫剧)",
        "query": "弃徒觉醒神体 3D 动态漫画 纯享",
        "hook": "His dantian was destroyed and his fiancee betrayed him. But deep in the abyss, he absorbs the heart of an ancient god.",
        "category": "3D Xianxia / Cultivation",
        "target_audience": "High-Tension Xianxia, Face-Slapping Tropes",
        "icon": "⚔",
    },
    {
        "id": "overpowered_signin_system",
        "title": "Starting with an Undefeated Sign-In System",
        "chinese_title": "开局签到无敌系统 (3D 漫剧)",
        "query": "开局签到无敌系统 3D 动态漫",
        "hook": "Given a daily sign-in system in a terrifying immortal world: Day 1: God-Grade Sword, Day 30: Immortal Physique!",
        "category": "3D OP System",
        "target_audience": "Power Fantasy, Fast Pacing",
        "icon": "👑",
    },
    {
        "id": "billionaire_hidden_heir",
        "title": "The Trillion-Dollar Heir Pretends to Be a Beggar",
        "chinese_title": "首富继承人装穷逆袭 (3D 漫剧)",
        "query": "首富继承人 3D 漫剧 动态漫画",
        "hook": "Looked down upon as a useless son-in-law, his grandfather's black card finally unfreezes 100 billion dollars.",
        "category": "3D Modern Drama",
        "target_audience": "Viral Short-Drama Hook, Maximum Satisfaction",
        "icon": "💎",
    },
    {
        "id": "cybernetic_cultivator",
        "title": "Cybernetic Cultivation in Year 3000",
        "chinese_title": "赛博修仙传 (3D 漫剧)",
        "query": "赛博修真 3D 动态漫画",
        "hook": "Qi cultivation meets neon cyberware: mechanical flying swords, AI alchemy, and digital transcendence.",
        "category": "3D Sci-Fi / Cyber Cultivation",
        "target_audience": "Futuristic Donghua, High Aesthetic Appeal",
        "icon": "🧬",
    },
]


def generate_daily_3d_suggestions() -> list[dict[str, Any]]:
    """Return today's curated 3D Màn jù suggested themes with search metadata."""
    return list(DAILY_3D_TROPES)


def rank_candidates_efs(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Compute the Engagement & Feasibility Score (EFS 0-100) and rank candidates.

    Considers view count, multi-part compilation fit, estimated runtime, and clean keywords.
    """
    import math

    for cand in candidates:
        if not cand.get("is_safe", True):
            cand["efs_score"] = 0.0
            cand["grade"] = "BLOCKED"
            continue

        views = max(0, int(cand.get("view_count") or 0))
        episodes = max(1, int(cand.get("episodes") or 1))
        duration = max(0.0, float(cand.get("duration_seconds") or 0.0))
        total_duration = duration * episodes

        # 1. View Factor (0 - 35 pts): 10K views = ~20pts, 100K views = ~28pts, 1M+ views = 35pts
        view_score = min(35.0, (math.log10(views + 1) / 6.0) * 35.0)

        # 2. Episode / Multi-part Factor (0 - 25 pts)
        if episodes >= 8:
            ep_score = 25.0
        elif episodes >= 4:
            ep_score = 20.0
        elif episodes >= 2:
            ep_score = 15.0
        else:
            ep_score = 8.0

        # 3. Duration Fit Factor (0 - 25 pts): Target 1.5 - 4 hours
        if 5400 <= total_duration <= 18000:
            dur_score = 25.0
        elif 2400 <= total_duration:
            dur_score = 18.0
        else:
            dur_score = 10.0

        # 4. Clean 3D Keyword Bonus (0 - 15 pts)
        title = cand.get("title", "")
        bonus = 0.0
        if "3D" in title or "3d" in title:
            bonus += 5.0
        if "漫剧" in title or "动态漫" in title:
            bonus += 5.0
        if "纯享" in title or "一口气" in title:
            bonus += 5.0

        total_efs = round(view_score + ep_score + dur_score + bonus, 1)
        cand["efs_score"] = total_efs

        if total_efs >= 80:
            cand["grade"] = "S-TIER VIRAL"
        elif total_efs >= 65:
            cand["grade"] = "A-TIER HIT"
        elif total_efs >= 50:
            cand["grade"] = "B-TIER GOOD"
        else:
            cand["grade"] = "C-TIER FAIR"

    candidates.sort(key=lambda c: c.get("efs_score", 0.0), reverse=True)
    return candidates


def search_and_screen_3d_manhua(
    query: str,
    max_candidates: int = 5,
    screen_watermarks: bool = True,
    custom_blocklist: Sequence[str] | None = None,
) -> list[dict[str, Any]]:
    """Full end-to-end workflow: Search 3D manhua -> EFS Rank -> Remote Watermark Audit."""
    from . import watermark_detector

    raw_candidates = search_manhua_series(query, max_results=max_candidates * 2, custom_blocklist=custom_blocklist)
    ranked = rank_candidates_efs(raw_candidates)

    top_candidates = [c for c in ranked if c.get("is_safe", True)][:max_candidates]

    if screen_watermarks:
        for cand in top_candidates:
            audit = watermark_detector.screen_candidate_series(cand["url"])
            cand["watermark_audit"] = audit
            cand["has_watermark"] = audit.get("has_watermark", False)
            cand["watermark_zone"] = audit.get("zone")
            cand["is_clean"] = audit.get("is_clean", True)
            cand["preview_image"] = audit.get("preview_image")

    return top_candidates
