"""Compilation stage.

Writes an FFmpeg concat demuxer list for every processed episode in
alphabetical order and joins them with ``-c copy`` - no re-encode, so a 40-episode
merge finishes in seconds instead of hours.

Stream-copy concatenation requires identical codecs, resolution, pixel format and
timebase across inputs. Because every episode came out of
:func:`modules.video_processor.render_dubbed_episode` with the same settings, that
holds by construction. :func:`merge_all_episodes` still verifies it up front and,
when a mismatch appears, falls back to a re-encoding concat rather than emitting a
file that stutters or desyncs.
"""

from __future__ import annotations

import json
import os
from typing import Any, Sequence

from . import (
    PipelineError,
    ensure_dir,
    ffprobe_duration,
    human_time,
    log,
    require_binary,
    run_command,
)

VIDEO_EXTENSIONS: tuple[str, ...] = (".mp4", ".mkv", ".mov", ".m4v", ".ts", ".webm")
SAMPLE_RATE = 44100


# --------------------------------------------------------------------------- #
# Discovery + probing
# --------------------------------------------------------------------------- #
def collect_episodes(processed_dir: str) -> list[str]:
    """Return processed episode files in alphabetical (== episode) order."""
    if not os.path.isdir(processed_dir):
        raise PipelineError(f"Processed directory does not exist: {processed_dir}")

    files = [
        os.path.join(processed_dir, name)
        for name in sorted(os.listdir(processed_dir), key=str.lower)
        if os.path.splitext(name)[1].lower() in VIDEO_EXTENSIONS
        and os.path.isfile(os.path.join(processed_dir, name))
        and os.path.getsize(os.path.join(processed_dir, name)) > 8192
    ]
    return files


def _probe_streams(path: str) -> dict[str, Any]:
    """Return codec / geometry fingerprints used for compatibility checking."""
    ffprobe = require_binary("ffprobe")
    proc = run_command(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "stream=codec_name,codec_type,width,height,pix_fmt,sample_rate,channels",
            "-of",
            "json",
            path,
        ],
        desc="ffprobe(streams)",
        check=False,
    )
    try:
        payload = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        payload = {}

    summary: dict[str, Any] = {"path": path, "video": None, "audio": None}
    for stream in payload.get("streams", []):
        if stream.get("codec_type") == "video" and summary["video"] is None:
            summary["video"] = (
                stream.get("codec_name"),
                stream.get("width"),
                stream.get("height"),
                stream.get("pix_fmt"),
            )
        elif stream.get("codec_type") == "audio" and summary["audio"] is None:
            summary["audio"] = (
                stream.get("codec_name"),
                str(stream.get("sample_rate")),
                stream.get("channels"),
            )
    return summary


def check_stream_compatibility(paths: Sequence[str]) -> tuple[bool, list[str]]:
    """Return ``(compatible, notes)`` for stream-copy concatenation."""
    if len(paths) < 2:
        return True, []

    reference = _probe_streams(paths[0])
    notes: list[str] = []
    compatible = True

    for path in paths[1:]:
        current = _probe_streams(path)
        name = os.path.basename(path)
        if current["video"] != reference["video"]:
            compatible = False
            notes.append(f"{name}: video {current['video']} != {reference['video']}")
        if current["audio"] != reference["audio"]:
            compatible = False
            notes.append(f"{name}: audio {current['audio']} != {reference['audio']}")
    return compatible, notes


# --------------------------------------------------------------------------- #
# Concat list
# --------------------------------------------------------------------------- #
def _escape_concat_path(path: str) -> str:
    """Escape a path for the concat demuxer's ``file '...'`` syntax."""
    normalised = os.path.abspath(path).replace("\\", "/")
    return normalised.replace("'", "'\\''")


def write_concat_list(paths: Sequence[str], list_path: str) -> str:
    """Write an FFmpeg concat demuxer list file and return its path."""
    if not paths:
        raise PipelineError("write_concat_list: no input files supplied.")
    ensure_dir(os.path.dirname(os.path.abspath(list_path)))
    with open(list_path, "w", encoding="utf-8") as handle:
        handle.write("# one_drama_engine concat list\n")
        for path in paths:
            handle.write(f"file '{_escape_concat_path(path)}'\n")
    log.info("Wrote concat list with %d entry/entries: %s", len(paths), list_path)
    return list_path


# --------------------------------------------------------------------------- #
# Merge
# --------------------------------------------------------------------------- #
def _concat_copy(list_path: str, output_master: str) -> None:
    ffmpeg = require_binary("ffmpeg")
    run_command(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            list_path,
            "-c",
            "copy",
            "-movflags",
            "+faststart",
            output_master,
        ],
        desc="ffmpeg(concat-copy)",
    )


def _concat_reencode(list_path: str, output_master: str, config: dict | None) -> None:
    """Fallback path used only when the inputs are not stream-copy compatible."""
    ffmpeg = require_binary("ffmpeg")
    encoding = (config or {}).get("encoding", {}) if isinstance(config, dict) else {}
    run_command(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            list_path,
            "-c:v",
            str(encoding.get("video_codec", "libx264")),
            "-preset",
            str(encoding.get("preset", "veryfast")),
            "-crf",
            str(encoding.get("crf", 20)),
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            str(encoding.get("audio_codec", "aac")),
            "-b:a",
            str(encoding.get("audio_bitrate", "192k")),
            "-ar",
            str(SAMPLE_RATE),
            "-ac",
            "2",
            "-movflags",
            "+faststart",
            output_master,
        ],
        desc="ffmpeg(concat-reencode)",
        capture=True,
    )


def merge_all_episodes(
    processed_dir: str,
    output_master: str,
    *,
    episode_paths: Sequence[str] | None = None,
    keep_list_file: bool = False,
    allow_reencode: bool = True,
    config: dict | None = None,
) -> str:
    """Merge every processed episode into one long compilation.

    Args:
        processed_dir: Folder of rendered episodes (scanned alphabetically).
        output_master: Destination MP4 for the compilation.
        episode_paths: Explicit ordered list, overriding the directory scan.
        keep_list_file: Keep the generated ``concat_list.txt``.
        allow_reencode: Re-encode when the inputs are not copy-compatible instead
            of failing. Slow but always produces a playable file.
        config: Optional settings dict used for the re-encode fallback.

    Returns:
        The absolute path of the merged master file.
    """
    paths = list(episode_paths) if episode_paths else collect_episodes(processed_dir)
    if not paths:
        raise PipelineError(
            f"No processed episodes found in {processed_dir}. Run the per-episode "
            "stages before merging."
        )

    missing = [path for path in paths if not os.path.isfile(path)]
    if missing:
        raise PipelineError(f"These episode files are missing: {missing}")

    output_master = os.path.abspath(output_master)
    ensure_dir(os.path.dirname(output_master))

    durations = [ffprobe_duration(path) for path in paths]
    total = sum(durations)
    log.info("Merging %d episode(s), estimated runtime %s", len(paths), human_time(total))
    for path, duration in zip(paths, durations):
        log.info("  + %-40s %s", os.path.basename(path)[:40], human_time(duration))

    list_path = os.path.join(os.path.dirname(output_master), "concat_list.txt")
    write_concat_list(paths, list_path)

    compatible, notes = check_stream_compatibility(paths)
    if not compatible:
        log.warning("Episodes are not stream-copy compatible:")
        for note in notes[:10]:
            log.warning("    %s", note)

    try:
        if compatible:
            log.info("Concatenating losslessly with -c copy...")
            _concat_copy(list_path, output_master)
        elif allow_reencode:
            log.warning("Falling back to a re-encoding concat (this takes a while)...")
            _concat_reencode(list_path, output_master, config)
        else:
            raise PipelineError(
                "Inputs are not stream-copy compatible and allow_reencode is False."
            )
    except PipelineError:
        if compatible and allow_reencode:
            log.warning("Lossless concat failed; retrying with a re-encode...")
            _concat_reencode(list_path, output_master, config)
        else:
            raise
    finally:
        if not keep_list_file and os.path.exists(list_path):
            try:
                os.remove(list_path)
            except OSError:
                pass

    if not os.path.isfile(output_master) or os.path.getsize(output_master) < 16384:
        raise PipelineError(f"Concatenation produced no usable output at {output_master}")

    final_duration = ffprobe_duration(output_master)
    log.info(
        "Master export complete: %s (%.2f GiB, %s)",
        output_master,
        os.path.getsize(output_master) / 1073741824,
        human_time(final_duration),
    )
    if final_duration and abs(final_duration - total) > max(5.0, total * 0.02):
        log.warning(
            "Merged runtime %s differs from the expected %s - inspect the output.",
            human_time(final_duration),
            human_time(total),
        )
    return output_master


def plan_compilations(
    processed_dir: str,
    *,
    target_hours_min: float = 2.0,
    target_hours_max: float = 3.0,
    episode_paths: Sequence[str] | None = None,
) -> list[list[str]]:
    """Group episodes into batches that each land in the target runtime window.

    Useful once a series exceeds three hours: instead of one unwatchably long
    upload you get sequential compilations, each in the 2-3 hour sweet spot.
    """
    paths = list(episode_paths) if episode_paths else collect_episodes(processed_dir)
    if not paths:
        return []

    max_seconds = max(target_hours_max, target_hours_min) * 3600
    min_seconds = min(target_hours_min, target_hours_max) * 3600

    batches: list[list[str]] = []
    current: list[str] = []
    running = 0.0

    for path in paths:
        duration = ffprobe_duration(path)
        if current and running + duration > max_seconds:
            batches.append(current)
            current, running = [], 0.0
        current.append(path)
        running += duration

    if current:
        # Fold a short tail into the previous batch when doing so stays under the cap.
        if batches and running < min_seconds * 0.5:
            previous_total = sum(ffprobe_duration(p) for p in batches[-1])
            if previous_total + running <= max_seconds * 1.1:
                batches[-1].extend(current)
                current = []
        if current:
            batches.append(current)

    log.info(
        "Planned %d compilation(s) from %d episode(s) for a %.1f-%.1fh target.",
        len(batches),
        len(paths),
        min_seconds / 3600,
        max_seconds / 3600,
    )
    return batches
