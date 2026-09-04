"""Episode acquisition stage.

Two entry points:

* :func:`download_bilibili_playlist` - wraps ``yt-dlp`` to pull an entire
  playlist sequentially and rename the results to ``ep_001.mp4``, ``ep_002.mp4``
  and so on, which is the ordering the rest of the pipeline relies on.
* :func:`download_douyin_no_watermark` - resolves a Douyin share link through
  the mobile JSON endpoint and rewrites the returned ``playwm`` play address to
  ``play``, which serves the un-watermarked master file.

Only download material you own or are licensed to use. The rename scheme is
deliberately zero-padded so that lexicographic sort equals episode order all the
way through concatenation.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import time
from typing import Any, Iterable, Sequence

import requests

from . import (
    PipelineError,
    ensure_dir,
    ffprobe_duration,
    log,
    require_binary,
    run_command,
)

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #
VIDEO_EXTENSIONS: tuple[str, ...] = (
    ".mp4",
    ".mkv",
    ".webm",
    ".flv",
    ".mov",
    ".m4v",
    ".ts",
)

EPISODE_PATTERN = re.compile(r"^ep_(\d{3,})$", re.IGNORECASE)

_MOBILE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"
)
_DESKTOP_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

_DOUYIN_DETAIL_ENDPOINTS: tuple[str, ...] = (
    "https://www.iesdouyin.com/web/api/v2/aweme/iteminfo/?item_ids={aweme_id}",
    "https://www.douyin.com/aweme/v1/web/aweme/detail/?aweme_id={aweme_id}",
)

_AWEME_ID_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"/video/(\d{6,})"),
    re.compile(r"/note/(\d{6,})"),
    re.compile(r"[?&]modal_id=(\d{6,})"),
    re.compile(r"[?&]aweme_id=(\d{6,})"),
)

_SHARE_URL_PATTERN = re.compile(r"https?://[^\s,;\"'）)】]+")

_CHUNK_BYTES = 1 << 18  # 256 KiB


# --------------------------------------------------------------------------- #
# Shared helpers
# --------------------------------------------------------------------------- #
def _is_video(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in VIDEO_EXTENSIONS


def list_episodes(directory: str) -> list[str]:
    """Return video files in *directory*, sorted so ``ep_001`` precedes ``ep_010``.

    Files matching ``ep_<digits>`` sort numerically; anything else falls back to
    a case-insensitive name sort and is placed after the numbered episodes.
    """
    if not os.path.isdir(directory):
        return []

    entries = [
        os.path.join(directory, name)
        for name in os.listdir(directory)
        if _is_video(name) and os.path.isfile(os.path.join(directory, name))
    ]

    def sort_key(path: str) -> tuple[int, int, str]:
        stem = os.path.splitext(os.path.basename(path))[0]
        match = EPISODE_PATTERN.match(stem)
        if match:
            return (0, int(match.group(1)), stem.lower())
        return (1, 0, stem.lower())

    return sorted(entries, key=sort_key)


def next_episode_index(directory: str) -> int:
    """Return the next free ``ep_NNN`` index in *directory* (1-based)."""
    highest = 0
    if os.path.isdir(directory):
        for name in os.listdir(directory):
            match = EPISODE_PATTERN.match(os.path.splitext(name)[0])
            if match:
                highest = max(highest, int(match.group(1)))
    return highest + 1


def _episode_name(index: int, extension: str = ".mp4") -> str:
    if not extension.startswith("."):
        extension = f".{extension}"
    return f"ep_{index:03d}{extension}"


def _yt_dlp_command() -> list[str]:
    """Return the best available way to invoke yt-dlp."""
    binary = shutil.which("yt-dlp")
    if binary:
        return [binary]
    try:  # fall back to the importable package (same venv, no PATH entry)
        import yt_dlp  # noqa: F401

        import sys

        return [sys.executable, "-m", "yt_dlp"]
    except ImportError as exc:  # pragma: no cover - dependency guard
        raise PipelineError(
            "yt-dlp is unavailable. Install it with: pip install yt-dlp"
        ) from exc


def _validate_download(path: str, min_bytes: int = 32_768) -> None:
    """Reject empty / truncated downloads early instead of failing at Demucs."""
    if not os.path.isfile(path):
        raise PipelineError(f"Download produced no file at {path}")
    size = os.path.getsize(path)
    if size < min_bytes:
        raise PipelineError(
            f"Download at {path} is only {size} bytes - likely an error page, not video."
        )


# --------------------------------------------------------------------------- #
# 1. Bilibili (and any yt-dlp supported site) playlist download
# --------------------------------------------------------------------------- #
def download_bilibili_playlist(
    playlist_url: str,
    output_dir: str,
    *,
    start_index: int | None = None,
    max_episodes: int | None = None,
    cookies_from_browser: str | None = None,
    cookie_file: str | None = None,
    format_selector: str = (
        "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best[ext=mp4]/best"
    ),
    extra_args: Sequence[str] | None = None,
    retries: int = 3,
) -> list[str]:
    """Download every video in *playlist_url* into *output_dir* as ``ep_NNN.mp4``.

    Args:
        playlist_url: Bilibili (or other yt-dlp supported) playlist / multi-part URL.
        output_dir: Destination directory; created when missing.
        start_index: First episode number to use. Defaults to one past whatever
            already exists in *output_dir*, so re-runs append instead of clobber.
        max_episodes: Optional cap on how many playlist entries to fetch.
        cookies_from_browser: e.g. ``"chrome"`` - needed for member-only content.
        cookie_file: Path to a Netscape cookie jar (alternative to the above).
        format_selector: yt-dlp ``-f`` expression.
        extra_args: Additional raw yt-dlp flags appended verbatim.
        retries: Attempts per playlist before giving up.

    Returns:
        Absolute paths of the downloaded episodes, in playlist order.
    """
    if not playlist_url or not playlist_url.strip():
        raise PipelineError("download_bilibili_playlist: playlist_url is empty.")

    ensure_dir(output_dir)
    output_dir = os.path.abspath(output_dir)
    base_index = next_episode_index(output_dir) if start_index is None else int(start_index)
    if base_index < 1:
        raise PipelineError("start_index must be >= 1")

    # Download into a staging dir so a partial run never pollutes raw_episodes/.
    staging = ensure_dir(os.path.join(output_dir, ".staging"))
    for stale in os.listdir(staging):
        stale_path = os.path.join(staging, stale)
        if os.path.isfile(stale_path):
            os.remove(stale_path)

    argv = _yt_dlp_command() + [
        "--ignore-config",
        "--no-warnings",
        "--newline",
        "--no-overwrites",
        "--continue",
        "--retries",
        "10",
        "--fragment-retries",
        "10",
        "--concurrent-fragments",
        "4",
        "--yes-playlist",
        "--playlist-start",
        "1",
        "-f",
        format_selector,
        "--merge-output-format",
        "mp4",
        "--referer",
        "https://www.bilibili.com/",
        "--user-agent",
        _DESKTOP_UA,
        "--extractor-args",
        "bilibili:player_client=android",
        "-o",
        os.path.join(staging, "%(playlist_index)05d_%(id)s.%(ext)s"),
    ]

    if max_episodes:
        argv += ["--playlist-end", str(int(max_episodes))]
    if cookies_from_browser:
        argv += ["--cookies-from-browser", cookies_from_browser]
    if cookie_file:
        if not os.path.isfile(cookie_file):
            raise PipelineError(f"cookie_file not found: {cookie_file}")
        argv += ["--cookies", cookie_file]
    if extra_args:
        argv += [str(a) for a in extra_args]

    argv.append(playlist_url)

    last_error: Exception | None = None
    for attempt in range(1, max(1, retries) + 1):
        log.info("yt-dlp playlist fetch (attempt %d/%d): %s", attempt, retries, playlist_url)
        try:
            run_command(argv, desc="yt-dlp", capture=False, check=True)
            last_error = None
            break
        except PipelineError as exc:
            last_error = exc
            log.warning("yt-dlp attempt %d failed: %s", attempt, exc)
            if attempt < retries:
                time.sleep(min(30, 5 * attempt))

    downloaded = sorted(
        os.path.join(staging, name) for name in os.listdir(staging) if _is_video(name)
    )
    if not downloaded:
        raise PipelineError(
            f"yt-dlp downloaded nothing from {playlist_url}."
            + (f" Last error: {last_error}" if last_error else "")
        )
    if last_error:
        log.warning(
            "yt-dlp reported an error but %d file(s) landed; keeping them.",
            len(downloaded),
        )

    final_paths: list[str] = []
    for offset, staged in enumerate(downloaded):
        extension = os.path.splitext(staged)[1].lower() or ".mp4"
        target = os.path.join(output_dir, _episode_name(base_index + offset, extension))
        if os.path.exists(target):
            log.warning("Overwriting existing %s", os.path.basename(target))
            os.remove(target)
        shutil.move(staged, target)
        _validate_download(target)
        duration = ffprobe_duration(target)
        log.info(
            "  -> %s (%.1f MiB, %.0fs)",
            os.path.basename(target),
            os.path.getsize(target) / 1048576,
            duration,
        )
        final_paths.append(target)

    shutil.rmtree(staging, ignore_errors=True)
    log.info("Playlist complete: %d episode(s) in %s", len(final_paths), output_dir)
    return final_paths


# --------------------------------------------------------------------------- #
# 2. Douyin watermark-free download
# --------------------------------------------------------------------------- #
def _expand_share_url(session: requests.Session, share_url: str, timeout: float) -> str:
    """Follow the ``v.douyin.com`` short-link redirect chain to the canonical URL."""
    try:
        response = session.get(share_url, timeout=timeout, allow_redirects=True)
        return response.url or share_url
    except requests.RequestException as exc:
        log.warning("Could not expand share URL (%s); using it as-is.", exc)
        return share_url


def extract_aweme_id(session: requests.Session, share_url: str, timeout: float = 20.0) -> str:
    """Resolve a Douyin share string to its numeric ``aweme_id``."""
    match = _SHARE_URL_PATTERN.search(share_url or "")
    if not match:
        raise PipelineError(f"No URL found in the supplied share text: {share_url!r}")
    url = match.group(0).rstrip(".,;")

    for pattern in _AWEME_ID_PATTERNS:  # already a full URL?
        found = pattern.search(url)
        if found:
            return found.group(1)

    resolved = _expand_share_url(session, url, timeout)
    for pattern in _AWEME_ID_PATTERNS:
        found = pattern.search(resolved)
        if found:
            return found.group(1)

    raise PipelineError(
        f"Could not extract an aweme_id from {url!r} (resolved to {resolved!r})."
    )


def _walk_for_play_urls(node: Any, found: list[str]) -> None:
    """Depth-first sweep collecting every ``url_list`` entry in a Douyin payload.

    The JSON shape shifts between endpoints and app versions, so structural
    traversal is far more durable than hard-coded key paths.
    """
    if isinstance(node, dict):
        for key, value in node.items():
            if key in {"url_list", "UrlList"} and isinstance(value, list):
                found.extend(str(item) for item in value if isinstance(item, str))
            elif key in {"play_addr", "playAddr", "download_addr", "url"} and isinstance(
                value, str
            ):
                found.append(value)
            else:
                _walk_for_play_urls(value, found)
    elif isinstance(node, list):
        for item in node:
            _walk_for_play_urls(item, found)


def _strip_watermark(url: str) -> str:
    """Rewrite a watermarked play address into the clean master address.

    Douyin serves the watermark-free file from the same CDN path with
    ``playwm`` replaced by ``play`` (``/aweme/v1/playwm/`` -> ``/aweme/v1/play/``).
    """
    clean = url.replace("playwm", "play")
    clean = clean.replace("/play_wm/", "/play/").replace("watermark=1", "watermark=0")
    if clean.startswith("//"):
        clean = f"https:{clean}"
    elif clean.startswith("http://"):
        clean = f"https://{clean[len('http://'):]}"
    return clean


def resolve_douyin_video_url(share_url: str, *, timeout: float = 20.0) -> dict[str, Any]:
    """Return metadata plus ranked watermark-free candidate URLs for *share_url*."""
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": _MOBILE_UA,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": "https://www.douyin.com/",
        }
    )

    aweme_id = extract_aweme_id(session, share_url, timeout)
    log.info("Douyin aweme_id resolved: %s", aweme_id)

    payload: dict[str, Any] | None = None
    errors: list[str] = []
    for template in _DOUYIN_DETAIL_ENDPOINTS:
        endpoint = template.format(aweme_id=aweme_id)
        try:
            response = session.get(endpoint, timeout=timeout)
            response.raise_for_status()
            candidate = response.json()
        except (requests.RequestException, json.JSONDecodeError, ValueError) as exc:
            errors.append(f"{endpoint} -> {exc}")
            continue
        if isinstance(candidate, dict) and candidate:
            payload = candidate
            log.debug("Douyin metadata served by %s", endpoint)
            break
        errors.append(f"{endpoint} -> empty payload")

    if payload is None:
        raise PipelineError(
            "All Douyin metadata endpoints failed:\n  " + "\n  ".join(errors)
        )

    raw_urls: list[str] = []
    _walk_for_play_urls(payload, raw_urls)

    seen: set[str] = set()
    candidates: list[str] = []
    for url in raw_urls:
        if not url.startswith(("http://", "https://", "//")):
            continue
        clean = _strip_watermark(url)
        if clean in seen:
            continue
        seen.add(clean)
        candidates.append(clean)

    # Prefer the endpoints that came from a watermarked play address, since those
    # are the ones the playwm->play swap is defined for.
    candidates.sort(key=lambda u: (0 if "/play/" in u or "aweme/v1/play" in u else 1, len(u)))

    if not candidates:
        raise PipelineError(
            f"No playable URL found in the Douyin payload for aweme_id={aweme_id}."
        )

    title = ""
    for key in ("desc", "title"):
        node = payload.get(key) if isinstance(payload, dict) else None
        if isinstance(node, str) and node.strip():
            title = node.strip()
            break
    if not title:
        detail = payload.get("aweme_detail") or {}
        item_list = payload.get("item_list") or []
        if isinstance(detail, dict) and isinstance(detail.get("desc"), str):
            title = detail["desc"].strip()
        elif item_list and isinstance(item_list[0], dict):
            title = str(item_list[0].get("desc", "")).strip()

    return {"aweme_id": aweme_id, "title": title, "candidates": candidates}


def _stream_to_file(
    session: requests.Session, url: str, output_path: str, timeout: float
) -> int:
    """Stream *url* to *output_path*; returns bytes written."""
    tmp = f"{output_path}.part"
    written = 0
    with session.get(url, timeout=timeout, stream=True, allow_redirects=True) as response:
        response.raise_for_status()
        content_type = (response.headers.get("Content-Type") or "").lower()
        if "text/html" in content_type:
            raise PipelineError(f"CDN returned HTML instead of video for {url}")
        with open(tmp, "wb") as handle:
            for chunk in response.iter_content(chunk_size=_CHUNK_BYTES):
                if chunk:
                    handle.write(chunk)
                    written += len(chunk)
    os.replace(tmp, output_path)
    return written


def download_douyin_no_watermark(
    share_url: str,
    output_path: str,
    *,
    timeout: float = 30.0,
    retries: int = 3,
) -> str:
    """Download a Douyin video without the burnt-in watermark.

    Resolves the share link to its ``aweme_id``, pulls the item metadata, swaps
    ``playwm`` for ``play`` in the returned play address, then streams the clean
    MP4 to *output_path*.

    Args:
        share_url: Share text or URL (``v.douyin.com/...`` short links are fine).
        output_path: Destination ``.mp4`` path.
        timeout: Per-request timeout in seconds.
        retries: Attempts per candidate URL.

    Returns:
        The absolute path of the downloaded file.
    """
    if not share_url or not share_url.strip():
        raise PipelineError("download_douyin_no_watermark: share_url is empty.")
    if not output_path:
        raise PipelineError("download_douyin_no_watermark: output_path is empty.")

    output_path = os.path.abspath(output_path)
    if not os.path.splitext(output_path)[1]:
        output_path += ".mp4"
    ensure_dir(os.path.dirname(output_path))

    info = resolve_douyin_video_url(share_url, timeout=timeout)
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": _MOBILE_UA,
            "Referer": "https://www.douyin.com/",
            "Accept": "*/*",
        }
    )

    last_error: Exception | None = None
    for index, url in enumerate(info["candidates"], start=1):
        for attempt in range(1, max(1, retries) + 1):
            log.info(
                "Fetching clean MP4 (candidate %d/%d, attempt %d): %s",
                index,
                len(info["candidates"]),
                attempt,
                url[:110],
            )
            try:
                written = _stream_to_file(session, url, output_path, timeout)
                _validate_download(output_path)
                log.info(
                    "Saved %s (%.2f MiB, no watermark)",
                    os.path.basename(output_path),
                    written / 1048576,
                )
                return output_path
            except (requests.RequestException, PipelineError, OSError) as exc:
                last_error = exc
                log.warning("Candidate failed: %s", exc)
                if os.path.exists(f"{output_path}.part"):
                    os.remove(f"{output_path}.part")
                if attempt < retries:
                    time.sleep(min(15, 3 * attempt))

    raise PipelineError(
        f"Every candidate URL failed for aweme_id={info['aweme_id']}. Last error: {last_error}"
    )


def download_douyin_batch(
    share_urls: Iterable[str],
    output_dir: str,
    *,
    start_index: int | None = None,
) -> list[str]:
    """Download several Douyin links into *output_dir* as ``ep_NNN.mp4``.

    Failures are logged and skipped so one dead link cannot abort the batch.
    """
    ensure_dir(output_dir)
    index = next_episode_index(output_dir) if start_index is None else int(start_index)
    saved: list[str] = []
    for url in share_urls:
        url = (url or "").strip()
        if not url or url.startswith("#"):
            continue
        target = os.path.join(output_dir, _episode_name(index))
        try:
            saved.append(download_douyin_no_watermark(url, target))
            index += 1
        except PipelineError as exc:
            log.error("Skipping %s: %s", url[:80], exc)
    log.info("Douyin batch finished: %d/%d saved", len(saved), index - 1)
    return saved


def download_series_by_query(
    query_or_url: str,
    output_dir: str,
    *,
    limit: int | None = None,
    auto_select: bool = True,
    cookies_from_browser: str | None = None,
    custom_blocklist: Sequence[str] | None = None,
) -> list[str]:
    """Download a manhua series by Bilibili URL or by searching for title/keywords.

    If a URL is provided, downloads directly.
    If keywords are provided, searches Bilibili, picks the best match, and downloads.
    """
    query = (query_or_url or "").strip()
    if not query:
        raise PipelineError("download_series_by_query: query or URL is empty.")

    if query.startswith("http://") or query.startswith("https://"):
        log.info("Direct URL detected. Initiating download: %s", query)
        return download_bilibili_playlist(
            query,
            output_dir,
            max_episodes=limit,
            cookies_from_browser=cookies_from_browser,
        )

    from . import discovery

    log.info("Searching Bilibili for series matching: %s", query)
    candidates = discovery.search_manhua_series(query, max_results=5, custom_blocklist=custom_blocklist)
    if not candidates:
        raise PipelineError(f"No series found on Bilibili for query: '{query}'")

    selected = candidates[0]
    log.info(
        "Selected series: '%s' (%s, %d episodes)",
        selected["title"],
        "Safe" if selected["is_safe"] else "Risk",
        selected["episodes"],
    )
    if not selected["is_safe"]:
        log.warning("Warning: Selected series has copyright risk: %s", selected["safety_reason"])

    return download_bilibili_playlist(
        selected["url"],
        output_dir,
        max_episodes=limit,
        cookies_from_browser=cookies_from_browser,
    )


