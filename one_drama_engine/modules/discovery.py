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
import time
from typing import Any, Sequence

from . import PipelineError, ensure_dir, human_time, log, read_json, write_json

_SEARCH_CACHE: dict[str, tuple[float, list[dict[str, Any]]]] = {}
_SEARCH_CACHE_TTL_SEC = 900.0  # 15 minutes cache

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
# Curated High-Retention Dynamic Manhua Genres (Short-Episode Series: 1.5 - 3.5m)
# --------------------------------------------------------------------------- #
TRENDING_GENRES: dict[str, dict[str, Any]] = {
    "3d_urban": {
        "name": "3D Urban Rebirth & Revenge (3D 都市重生 / 漫剧)",
        "queries": [
            "都市仙尊 3D 漫剧 分P",
            "都市重生 3D 漫剧 选集",
            "神医下山 3D 动态漫 分P",
            "首富继承人 3D 漫剧 连载",
        ],
    },
    "3d_cultivation": {
        "name": "3D Xianxia & Cultivation (3D 玄幻修仙 / 漫剧)",
        "queries": [
            "3D 玄幻 漫剧 分P",
            "开局无敌 3D 漫剧 选集",
            "弃徒觉醒神体 3D 漫剧 连载",
            "万界仙王 3D 动态漫 分P",
        ],
    },
    "3d_apocalypse": {
        "name": "3D Apocalypse & SSS System (3D 末日觉醒 / 漫剧)",
        "queries": [
            "末日死灵法师 3D 漫剧 选集",
            "末日觉醒 3D 漫剧 分P",
            "末世无敌系统 3D 动态漫画 连载",
        ],
    },
    "3d_all": {
        "name": "3D Dynamic Manhua Collection (3D 漫剧 / 动态漫 选集)",
        "queries": [
            "3D 动态漫画 选集",
            "3D 漫剧 连载",
            "3D 漫剧 爽文 分P",
            "AI 3D 动态漫 选集",
        ],
    },
    "urban": {
        "name": "Urban Rebirth & Revenge (都市重生 / 逆袭)",
        "queries": [
            "都市修仙 动态漫画 分P",
            "都市重生 动态漫 选集",
            "神医下山 动态漫画 连载",
            "赘婿逆袭 动态漫画 分P",
            "战神归来 动态漫 选集",
        ],
    },
    "cultivation": {
        "name": "Cultivation & Xianxia (修仙 / 玄幻 / 修真)",
        "queries": [
            "开局无敌 动态漫画 分P",
            "玄幻修仙 动态漫画 选集",
            "万界仙王 动态漫画 连载",
            "绝世丹神 动态漫 分P",
            "退婚流 动态漫画 选集",
        ],
    },
    "system": {
        "name": "Overpowered System & Leveling (无敌系统 / 签到)",
        "queries": [
            "签到系统 动态漫画 分P",
            "神级系统 动态漫画 选集",
            "无敌升级系统 动态漫 连载",
            "我有一座藏经阁 动态漫 分P",
            "满级大佬 动态漫画 选集",
        ],
    },
    "isekai": {
        "name": "Isekai & Fantasy Reincarnation (穿越 / 异界)",
        "queries": [
            "异界重生 动态漫画 分P",
            "穿越异世 动态漫画 选集",
            "大理寺日志 动态漫 连载",
            "转生异界 动态漫画 分P",
            "开局签到 动态漫画 选集",
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
        "--extractor-args",
        "bilibili:player_client=android",
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
    timeout: float = 60.0,
) -> list[dict[str, Any]]:
    """Search Bilibili for matching dynamic manhua series.

    Returns candidate objects sorted by relevance and episode completeness.
    Uses resilient fallback and candidate preservation so searches never drop valid results.
    """
    if not query or not query.strip():
        return []

    search_term = query.strip()
    cache_key = f"{search_term.lower()}_{max_results}"
    if cache_key in _SEARCH_CACHE:
        cache_time, cached_data = _SEARCH_CACHE[cache_key]
        if time.time() - cache_time < _SEARCH_CACHE_TTL_SEC:
            log.info("Returning %d cached search results for '%s'", len(cached_data), search_term)
            return cached_data

    # Check if query is in DAILY_3D_TROPES with a verified direct URL
    for t in DAILY_3D_TROPES:
        t_query = (t.get("query") or "").strip()
        t_title = (t.get("title") or "").strip()
        t_chinese = (t.get("chinese_title") or "").strip()
        t_bengali = (t.get("bengali_title") or "").strip()
        aliases = t.get("aliases") or []
        alias_match = any(a in search_term or a.lower() in search_term.lower() for a in aliases if len(a) >= 2)
        if t.get("url"):
            term_clean = search_term.lower().replace(" ", "")
            if (
                alias_match
                or (t_query and (t_query in search_term or search_term in t_query or t_query.replace(" ", "") in term_clean))
                or (t_chinese and (t_chinese in search_term or search_term in t_chinese or t_chinese.replace(" ", "") in term_clean))
                or (t_title and t_title.lower() in search_term.lower())
                or (t_bengali and t_bengali in search_term)
            ):
                log.info("Direct verified URL match found for trope '%s': %s", t.get("title"), t["url"])
                eps = int(t.get("episodes_count") or 25)
                dur = float(t.get("duration_seconds") or 7200.0)
                return [{
                    "id": t.get("id", "trope"),
                    "title": t.get("chinese_title", t.get("title", search_term)),
                    "uploader": "Verified Producer",
                    "url": t["url"],
                    "episodes": eps,
                    "duration_seconds": dur,
                    "runtime_estimate": human_time(dur),
                    "view_count": 500000,
                    "is_safe": True,
                    "safety_reason": "Verified Indie Studio",
                }]

    # Ensure dynamic manhua keywords are present for precision
    if not any(k in search_term for k in ("动态漫画", "动态漫", "manhua", "comic")):
        search_query = f"bilisearch{max_results}:{search_term} 动态漫画"
    else:
        search_query = f"bilisearch{max_results}:{search_term}"

    def _execute_yt_dlp_search(sq: str) -> list[dict[str, Any]]:
        log.info("Searching Bilibili for: %s", sq)
        cmd = _yt_dlp_cmd() + [
            "--ignore-config",
            "--no-warnings",
            "--referer",
            _BILIBILI_REFERER,
            "--user-agent",
            _BILIBILI_UA,
            "--extractor-args",
            "bilibili:player_client=android",
            "--dump-json",
            "--flat-playlist",
            sq,
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
            items = []
            for line in proc.stdout.strip().splitlines():
                if line.strip():
                    try:
                        items.append(json.loads(line.strip()))
                    except json.JSONDecodeError:
                        pass
            return items
        except Exception as exc:
            log.warning("yt-dlp search attempt failed (%s): %s", sq, exc)
            return []

    raw_items = _execute_yt_dlp_search(search_query)

    # If 0 results, relax query by removing noise qualifiers (e.g. 纯享, 4K, 3D)
    if not raw_items:
        relaxed_term = re.sub(r"(纯享|1-Click|4K|3D|漫剧|高清|完整版)", "", search_term).strip()
        if relaxed_term and relaxed_term != search_term:
            relaxed_query = f"bilisearch{max_results}:{relaxed_term} 动态漫"
            log.info("Initial query yielded 0 results; retrying with relaxed keywords: '%s'", relaxed_query)
            raw_items = _execute_yt_dlp_search(relaxed_query)

    if not raw_items:
        log.warning("No Bilibili search candidates found for '%s'", search_term)
        return []

    from concurrent.futures import ThreadPoolExecutor

    unique_items: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    for item in raw_items:
        raw_id = item.get("id") or item.get("url", "")
        url = item.get("url") or item.get("webpage_url") or f"https://www.bilibili.com/video/{raw_id}"
        if url not in seen_urls:
            seen_urls.add(url)
            unique_items.append(item)

    # Limit items to probe to keep search responsive (<10s)
    to_process = unique_items[:max(2, min(max_results, 4))]

    def _fetch_candidate(item: dict[str, Any]) -> dict[str, Any]:
        raw_id = str(item.get("id") or "")
        url = item.get("url") or item.get("webpage_url") or f"https://www.bilibili.com/video/{raw_id}"
        title = item.get("title")
        uploader = item.get("uploader") or ""
        view_count = item.get("view_count") or 0
        n_entries = item.get("n_entries") or 1
        duration = item.get("duration") or 0.0

        # Try fast entry probe with safe timeout
        try:
            details = _probe_entry_details(url, timeout=12.0)
            if details:
                title = details.get("title") or title
                uploader = details.get("uploader") or uploader
                view_count = details.get("view_count") or view_count
                n_entries = details.get("n_entries") or n_entries
                duration = details.get("duration") or duration
        except Exception as exc:
            log.debug("Detail probe skipped for %s: %s", url, exc)

        if not title:
            clean_q = re.sub(r"(纯享|1-Click|4K|3D)", "", search_term).strip()
            title = f"{clean_q} 动态漫画 ({raw_id})"

        is_safe, safety_reason = is_copyright_safe(title, uploader, custom_blocklist)
        is_teaser = bool(n_entries <= 1 and 0 < duration < 180.0)
        return {
            "id": raw_id,
            "title": title,
            "uploader": uploader or "UP Creator",
            "url": url,
            "episodes": n_entries,
            "duration_seconds": duration,
            "runtime_estimate": human_time(duration * max(1, n_entries)) if duration > 0 else "১.৫ ঘণ্টা",
            "view_count": view_count,
            "is_safe": is_safe and not is_teaser,
            "safety_reason": "Short teaser/PV clip (<3m)" if is_teaser else safety_reason,
            "is_teaser": is_teaser,
        }

    candidates: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=min(3, len(to_process))) as executor:
        for cand in executor.map(_fetch_candidate, to_process):
            if cand:
                candidates.append(cand)

    # Filter out short teasers unless no other candidates exist
    full_candidates = [c for c in candidates if not c.get("is_teaser")]
    if full_candidates:
        candidates = full_candidates

    # Sort: safe first, then prioritize multi-episode / long compilations, then views
    candidates.sort(
        key=lambda c: (
            1 if c["is_safe"] else 0,
            c["episodes"] if c["episodes"] > 1 else (1 if c.get("duration_seconds", 0) >= 1800 else 0),
            c.get("duration_seconds", 0),
            c["view_count"],
        ),
        reverse=True,
    )
    _SEARCH_CACHE[cache_key] = (time.time(), candidates)
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
        "bengali_title": "নগরীর অমর সম্রাট: আধুনিক পৃথিবীতে দেবমানব",
        "chinese_title": "都市仙尊归来 (3D 漫剧)",
        "query": "都市仙尊 3D 漫剧 分P",
        "url": "http://www.bilibili.com/video/av117177915015785",
        "thumbnail": "http://i2.hdslb.com/bfs/archive/4e0fa0e77a596ef5cc223fd8bee52bd176b03d47.jpg",
        "genre": "3d_urban",
        "hook": "Betrayed in his past life, the supreme celestial emperor reincarnates into his 18-year-old self to protect his mother and take brutal revenge.",
        "bengali_hook": "পূর্বজন্মে বিশ্বাসঘাতকতায় নিহত হয়ে মহাশক্তিধর অমর সম্রাট ১৮ বছর বয়সে বীরের রূপ নিয়ে ফিরে আসে। মা ও পরিবারকে রক্ষা করে চরম প্রতিশোধ নেয়ার রোমহর্ষক গল্প!",
        "category": "3D Urban Rebirth",
        "episodes_est": "৫৫ পর্ব • প্রতিটি ৩ মিনিট",
        "episodes_count": 55,
        "duration_seconds": 180.0,
        "target_audience": "হাই-রিটেনশন রিভেঞ্জ অ্যাকশন",
        "icon": "⚡",
        "is_short_series": True,
    },
    {
        "id": "apocalypse_necromancer",
        "title": "SSS-Rank Necromancer in the Global Cataclysm",
        "bengali_title": "মৃত্যুঞ্জয়ী শ্যাডো লর্ড: অ্যাপোক্যালিপ্স নেক্রোম্যান্সার",
        "chinese_title": "末日死灵法师 (3D 漫剧)",
        "query": "末日死灵法师 3D 漫剧 选集",
        "url": "http://www.bilibili.com/video/av117161305705311",
        "thumbnail": "http://i1.hdslb.com/bfs/archive/6c8e74b06fc72ec17edadd3dcb25fe28288c6b9b.jpg",
        "genre": "3d_apocalypse",
        "hook": "When the world transforms into a bloodthirsty dungeon, he awakens an infinite shadow army to conquer all monarchs.",
        "bengali_hook": "হঠাৎ পুরো পৃথিবী যখন দানবের নরকে পরিণত হয়, তখন বীর জাগিয়ে তোলে অপরাজিত ছায়া সেনাবাহিনী! একাই সমস্ত রাজাদের পরাজিত করে বিশ্বজয়ী হওয়ার গল্প।",
        "category": "3D Apocalypse & System",
        "episodes_est": "৪৯ পর্ব • প্রতিটি ৩.২ মিনিট",
        "episodes_count": 49,
        "duration_seconds": 196.0,
        "target_audience": "ডার্ক ফ্যান্টাসি ও সোলো লেভেলিং ফ্যানস",
        "icon": "🔥",
        "is_short_series": True,
    },
    {
        "id": "sect_outcast_godbody",
        "title": "Sect Outcast Unlocks the Ancient God Body",
        "bengali_title": "দেবদেহের উত্তরাধিকারী: প্রাচীন ঈশ্বরের ক্ষমতা",
        "chinese_title": "弃徒觉醒太古神体 (3D 漫剧)",
        "query": "弃徒觉醒神体 3D 漫剧 连载",
        "url": "http://www.bilibili.com/video/av117136424961608",
        "thumbnail": "http://i2.hdslb.com/bfs/archive/5b2dfa13cac73a128f1c014ce63fc8bbd8eb0d57.jpg",
        "genre": "3d_cultivation",
        "hook": "His dantian was destroyed and his fiancee betrayed him. But deep in the abyss, he absorbs the heart of an ancient god.",
        "bengali_hook": "ক্ল্যান থেকে অপমানিত হয়ে বিতাড়িত এবং বাগদত্তার বিশ্বাসঘাতকতায় নিঃস্ব বীর গভীর গিরিখাতে প্রাচীন ঈশ্বরের হৃদয় লাভ করে ফিরে আসে সবার মুখে চড় মারতে!",
        "category": "3D Xianxia / Cultivation",
        "episodes_est": "৪৩ পর্ব • প্রতিটি ৩.২ মিনিট",
        "episodes_count": 43,
        "duration_seconds": 194.0,
        "target_audience": "মার্শাল আর্টস ও কুংফু অ্যাকশন",
        "icon": "⚔️",
        "is_short_series": True,
    },
    {
        "id": "overpowered_signin_system",
        "title": "Starting with an Undefeated Sign-In System",
        "bengali_title": "অপরাজেয় সাইন-ইন সিস্টেম: ১ম দিনেই ঈশ্বর-তলোয়ার",
        "chinese_title": "开局签到无敌系统 (3D 漫剧)",
        "query": "开局签到无敌系统 3D 漫剧 分P",
        "url": "http://www.bilibili.com/video/av117095991872768",
        "thumbnail": "http://i1.hdslb.com/bfs/archive/634c1d75bef86f01a062deb108dcd2bf06ff1dfe.jpg",
        "genre": "3d_system",
        "hook": "Given a daily sign-in system in a terrifying immortal world: Day 1: God-Grade Sword, Day 30: Immortal Physique!",
        "bengali_hook": "ভয়ংকর এক অমর জগতে প্রতিদিনের সাইন-ইন রিওয়ার্ড সিস্টেম: ১ম দিনেই ঈশ্বর-তলোয়ার, ৩০তম দিনেই অমর শরীর! একদম সুপারহিরো এনার্জি।",
        "category": "3D OP System",
        "episodes_est": "৩১ পর্ব • প্রতিটি ৩.৩ মিনিট",
        "episodes_count": 31,
        "duration_seconds": 196.0,
        "target_audience": "পাওয়ার ফ্যান্টাসি ও ফাস্ট পেসিং",
        "icon": "👑",
        "is_short_series": True,
    },
    {
        "id": "billionaire_hidden_heir",
        "title": "The Trillion-Dollar Heir: Billionaire Revenge",
        "bengali_title": "গোপন ট্রিলিয়নিয়ার উত্তরাধিকারী: শত বিলিয়ন ডলারের ব্ল্যাক কার্ড",
        "chinese_title": "首富继承人归来 (3D 漫剧)",
        "query": "首富继承人 3D 漫剧 选集",
        "aliases": ["首富", "继承人", "开局万亿", "亿万", "billionaire"],
        "url": "http://www.bilibili.com/video/av117200094498300",
        "thumbnail": "http://i0.hdslb.com/bfs/archive/5025942c612c0b65997b6163cf10c446c811423c.jpg",
        "genre": "3d_billionaire",
        "hook": "Looked down upon as a useless son-in-law, his grandfather's black card finally unfreezes 100 billion dollars.",
        "bengali_hook": "সবাই তাকে গরিব ও অপদার্থ ভেবে উপহাস করতো, কিন্তু হঠাৎ তার শত বিলিয়ন ডলারের ব্যাঙ্ক অ্যাকাউন্ট আনলক হতেই বদলে যায় সবার আসল রূপ!",
        "category": "3D Modern Drama",
        "episodes_est": "৬০ পর্ব • প্রতিটি ৩ মিনিট",
        "episodes_count": 60,
        "duration_seconds": 183.0,
        "target_audience": "ভাইরাল শর্ট-ড্রামা ও স্যাটিসফ্যাকশন",
        "icon": "💎",
        "is_short_series": True,
    },
    {
        "id": "cybernetic_cultivator",
        "title": "Cybernetic Cultivator: AI & Flying Swords",
        "bengali_title": "সাইবার অমর যোদ্ধা: ৩০০০ সালের রোবোটিক যুদ্ধ",
        "chinese_title": "赛博修真：三千年后 (3D 漫剧)",
        "query": "赛博修真 3D 漫剧 连载",
        "aliases": ["赛博", "修真", "大佬画风不对", "cyber"],
        "url": "http://www.bilibili.com/video/av117188753099652",
        "thumbnail": "http://i2.hdslb.com/bfs/archive/658af34ba5d8e635c1aaaffc30d082271db38f69.jpg",
        "genre": "3d_scifi",
        "hook": "Qi cultivation meets neon cyberware: mechanical flying swords, AI alchemy, and digital transcendence.",
        "bengali_hook": "ভবিষ্যতের ৩০০০ সালের রোবোটিক সায়েন্স-ফিকশন আর মার্শাল আর্টসের মিশ্রণ: যান্ত্রিক উড়ন্ত তলোয়ার আর ডিজিটাল অ্যালকেমির শ্বাসরুদ্ধকর যুদ্ধ।",
        "category": "3D Sci-Fi Cultivation",
        "episodes_est": "৪৮ পর্ব • প্রতিটি ২.৫ মিনিট",
        "episodes_count": 48,
        "duration_seconds": 150.0,
        "target_audience": "সাই-ফাই ও ফিউচারিস্টিক অ্যাকশন",
        "icon": "🧬",
        "is_short_series": True,
    },
    {
        "id": "dragon_king_son_in_law",
        "title": "Return of the Dragon King: Son-In-Law Revenge",
        "bengali_title": "ড্রাগন কিং-এর প্রত্যাবর্তন: ঘরজামাই থেকে সেনাপতি",
        "chinese_title": "龙王赘婿逆袭 (3D 漫剧)",
        "query": "龙王赘婿 3D 漫剧 分P",
        "aliases": ["龙王", "赘婿", "战神", "dragon"],
        "url": "http://www.bilibili.com/video/av117127717653649",
        "thumbnail": "http://i1.hdslb.com/bfs/archive/c8c6b33ca7fa072ac495c73715390dfad137498b.jpg",
        "genre": "3d_billionaire",
        "hook": "Looked down upon as a live-in son-in-law, his supreme commander identity finally reveals with 1 million armored soldiers.",
        "bengali_hook": "শ্বশুরবাড়ির চরম অপমান আর তাচ্ছিল্যের পর যখন দশ লাখ সৈন্যের প্রধান সেনাপতির আসল পরিচয় উন্মোচিত হয়!",
        "category": "3D Revenge Drama",
        "episodes_est": "৫০ পর্ব • প্রতিটি ৩ মিনিট",
        "episodes_count": 50,
        "duration_seconds": 180.0,
        "target_audience": "রিভেঞ্জ ও স্যাটিসফ্যাকশন",
        "icon": "🐉",
        "is_short_series": True,
    },
    {
        "id": "seven_immortal_fairies",
        "title": "My Sect Masters Are All Peerless Fairies",
        "bengali_title": "আমার সাত দেবী গুরু: রূপবতী অপ্সরাদের আশীর্বাদ",
        "chinese_title": "反派：我的师尊都是绝色仙子 (3D 漫剧)",
        "query": "反派 我的师尊都是绝色仙子 3D 漫剧 分P",
        "url": "http://www.bilibili.com/video/av117121610878679",
        "thumbnail": "http://i1.hdslb.com/bfs/archive/918bd8a6cd68b222dd3bb51779e59aab4593f1fa.jpg",
        "genre": "3d_comedy",
        "hook": "Born into a demonic family, seven beautiful goddess masters protect and pamper him while waging war on all realms.",
        "bengali_hook": "ভিলেন বংশে জন্মালেও সাত সুন্দরী অমর দেবী গুরু বীরকে রক্ষা করতে সারা বিশ্ব কাঁপিয়ে যুদ্ধ ঘোষণা করে!",
        "category": "3D Comedy & Romance",
        "episodes_est": "৪২ পর্ব • প্রতিটি ২.৮ মিনিট",
        "episodes_count": 42,
        "duration_seconds": 168.0,
        "target_audience": "কমেডি ও ফ্যামিলি ড্রামা",
        "icon": "🌸",
        "is_short_series": True,
    },
]


def load_custom_series() -> list[dict[str, Any]]:
    """Load user-added custom series from storage/custom_series.json."""
    custom_path = os.path.join(os.path.dirname(__file__), "..", "..", "storage", "custom_series.json")
    if os.path.isfile(custom_path):
        try:
            with open(custom_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def save_custom_series(series_list: list[dict[str, Any]]) -> None:
    """Save user-added custom series to storage/custom_series.json."""
    storage_dir = os.path.join(os.path.dirname(__file__), "..", "..", "storage")
    os.makedirs(storage_dir, exist_ok=True)
    custom_path = os.path.join(storage_dir, "custom_series.json")
    with open(custom_path, "w", encoding="utf-8") as f:
        json.dump(series_list, f, ensure_ascii=False, indent=2)


def generate_daily_3d_suggestions(
    genre: str | None = None,
    refresh: bool = False,
    count: int = 6,
) -> list[dict[str, Any]]:
    """Return curated 3D Màn jù suggested themes with search metadata and poster images."""
    import random
    custom = load_custom_series()
    all_pool = list(custom) + list(DAILY_3D_TROPES)

    if genre and genre != "all":
        filtered = [item for item in all_pool if item.get("genre") == genre]
        if not filtered:
            filtered = all_pool
    else:
        filtered = all_pool

    if refresh:
        shuffled = list(filtered)
        random.shuffle(shuffled)
        return shuffled[:count]

    return filtered[:count]


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

        # 4. Clean 3D Keyword Factor (Bonus for serialized short episodes, penalty for giant merged movies)
        title = cand.get("title", "")
        bonus = 0.0
        if "3D" in title or "3d" in title:
            bonus += 5.0
        if "漫剧" in title or "动态漫" in title:
            bonus += 5.0
        if any(k in title for k in ("分P", "选集", "连载", "第", "集")):
            bonus += 10.0
        # Heavily penalize pre-merged full movies that violate episodic short-video architecture
        if any(k in title for k in ("纯享", "一口气", "大合集", "完整版", "合集")):
            bonus -= 30.0

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


def auto_scan_short_3d_manhua_series(
    genre: str | None = None,
    count: int = 6,
    custom_blocklist: Sequence[str] | None = None,
) -> list[dict[str, Any]]:
    """Scan Bilibili for genuine serialized short-episode 3D manhua series (1.5 - 3.5 min/ep).

    Rejects pre-merged full movies (一口气看完, 纯享) and promotional trailers (< 50s).
    Enforces episodic short-video standards and returns cards localized for 1-click AutoPilot.
    """
    import random

    # Determine targeted search queries for episodic short 3D manhua
    search_queries = [
        "3D 漫剧 分P",
        "3D 动态漫画 选集",
        "3D 漫剧 连载",
        "3D 动态漫 第一集",
    ]
    if genre and genre in TRENDING_GENRES:
        search_queries = TRENDING_GENRES[genre]["queries"] + search_queries

    scanned_candidates: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    # Fast probe of search queries
    for q in search_queries[:3]:
        results = search_manhua_series(q, max_results=6, custom_blocklist=custom_blocklist)
        for r in results:
            url = r.get("url", "")
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            title = r.get("title", "")
            # Strictly reject any merged full movies, audiobooks, or novels
            if any(k in title for k in ("一口气", "纯享", "完整版", "大合集", "合集", "有声书", "小说", "小时")):
                continue
            if not r.get("is_safe", True):
                continue

            eps = int(r.get("episodes") or 1)
            dur = float(r.get("duration_seconds") or 180.0)

            # Strictly enforce episodic short-video standard (45s <= dur <= 300s, ~1.5 to 3.5 mins)
            # NEVER allow long merged videos (> 360s) or micro-trailers (< 45s) into the queue!
            if not (45.0 <= dur <= 300.0):
                continue

            est_min = round(dur / 60.0, 1)
            scanned_candidates.append({
                "id": f"scanned_{abs(hash(url)) % 1000000}",
                "title": title,
                "chinese_title": title,
                "bengali_title": f"৩ডি শর্ট ড্রামা: {title[:25]}",
                "query": title,
                "url": url,
                "thumbnail": r.get("thumbnail") or "http://i2.hdslb.com/bfs/archive/4e0fa0e77a596ef5cc223fd8bee52bd176b03d47.jpg",
                "genre": genre or "3d_all",
                "category": "৩ডি শর্ট ড্রামা সিরিজ",
                "hook": f"A fast-paced serialized 3D comic drama with intense short episodes.",
                "bengali_hook": f"রোমহর্ষক ৩ডি শর্ট ড্রামা সিরিজ — টানটান উত্তেজনা ও অ্যাকশন সমৃদ্ধ ২-৩ মিনিটের পর্ব!",
                "episodes_est": f"{max(eps, 30)} পর্ব • প্রতিটি {est_min if est_min > 0.5 else 2.5:.1f} মিনিট",
                "episodes_count": max(eps, 30),
                "duration_seconds": dur,
                "target_audience": "শর্ট ড্রামা ও ফাস্ট পেসিং",
                "icon": "⚡",
                "is_short_series": True,
            })
            if len(scanned_candidates) >= count:
                break
        if len(scanned_candidates) >= count:
            break

    # If scanner collected candidates, combine with curated pool for variety
    curated_pool = list(DAILY_3D_TROPES)
    if genre and genre != "all":
        curated_pool = [t for t in curated_pool if t.get("genre") == genre] or curated_pool

    combined = scanned_candidates + [t for t in curated_pool if t.get("url") not in seen_urls]
    random.shuffle(combined)
    return combined[:count]


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

