#!/usr/bin/env python3
"""one_drama_engine - master CLI runner.

Takes raw Chinese dynamic-manhua episodes and produces one long localized
compilation, in six stages per episode:

    1. separate  - Demucs strips the Chinese vocals, keeps music + SFX
    2. transcribe - Whisper reads the isolated vocals (zh)
    3. translate  - Gemini rewrites them as a dramatic third-person recap
    4. tts        - Edge-TTS voices the recap, time-synced to the source cues
    5. render     - FFmpeg filters the video and mixes bed + narration
    6. merge      - all episodes joined losslessly into the master export

Per-episode artefacts are cached, so an interrupted run resumes instead of
restarting. Examples::

    python pipeline.py                      # run everything in storage/raw_episodes
    python pipeline.py --limit 3            # first three episodes only
    python pipeline.py --episode ep_004.mp4 # one episode
    python pipeline.py --merge-only         # rebuild the compilation
    python pipeline.py --skip-merge         # render episodes, merge later
    python pipeline.py --download-playlist URL
    python pipeline.py --list-voices hi
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback
from typing import Any

if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from modules import (  # noqa: E402
    PipelineError,
    ensure_dir,
    ffprobe_duration,
    get_logger,
    human_time,
    read_json,
    require_binary,
    safe_stem,
    write_json,
)

log = get_logger("pipeline")

DEFAULT_CONFIG_PATH = os.path.join(BASE_DIR, "config", "settings.json")

STAGES = ("separate", "transcribe", "translate", "tts", "render")

FALLBACK_CONFIG: dict[str, Any] = {
    "gemini_api_key": "YOUR_GEMINI_API_KEY",
    "gemini_model": "gemini-flash-latest",
    "target_language": "hi",
    "tts_voice": "hi-IN-MadhurNeural",
    "whisper_model": "medium",
    "source_language": "zh",
    "storage_paths": {
        "raw": "storage/raw_episodes",
        "separated": "storage/audio_separated",
        "tts": "storage/tts_output",
        "processed": "storage/processed_episodes",
        "master": "storage/master_export",
    },
    "visual_filters": {
        "zoom_percent": 1.04,
        "crop_bottom": 80,
        "contrast": 1.05,
        "saturation": 1.08,
    },
    "audio_mixing": {"bgm_volume": 0.35, "voice_volume": 1.0},
    "tts_sync": {"atempo_min": 0.8, "atempo_max": 1.35},
    "encoding": {
        "video_codec": "libx264",
        "audio_codec": "aac",
        "crf": 20,
        "preset": "veryfast",
        "audio_bitrate": "192k",
        "fps": 30,
        "sample_rate": 44100,
    },
    "master_export": {
        "filename": "full_manhua_movie.mp4",
        "target_hours_min": 2.0,
        "target_hours_max": 3.0,
    },
}


# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #
def _deep_merge(base: dict, override: dict) -> dict:
    merged = dict(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_config(config_path: str = DEFAULT_CONFIG_PATH) -> dict:
    """Load settings.json, merge over defaults, and resolve storage paths."""
    if not os.path.isfile(config_path):
        log.warning("Config not found at %s - using built-in defaults.", config_path)
        config = dict(FALLBACK_CONFIG)
    else:
        try:
            with open(config_path, "r", encoding="utf-8") as handle:
                user_config = json.load(handle)
        except json.JSONDecodeError as exc:
            raise PipelineError(f"settings.json is not valid JSON: {exc}") from exc
        except OSError as exc:
            raise PipelineError(f"Could not read {config_path}: {exc}") from exc
        if not isinstance(user_config, dict):
            raise PipelineError("settings.json must contain a JSON object.")
        config = _deep_merge(FALLBACK_CONFIG, user_config)

    # An env var always wins over the file, so keys never need committing.
    env_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if env_key:
        config["gemini_api_key"] = env_key
        log.debug("Using Gemini API key from the environment.")

    resolved: dict[str, str] = {}
    for name, relative in config["storage_paths"].items():
        path = relative if os.path.isabs(relative) else os.path.join(BASE_DIR, relative)
        resolved[name] = ensure_dir(os.path.abspath(path))
    config["storage_paths"] = resolved
    config["_base_dir"] = BASE_DIR
    config["_config_path"] = config_path
    return config


def check_environment(*, need_gemini: bool = True, config: dict | None = None) -> list[str]:
    """Return a list of human-readable environment problems (empty == all good)."""
    problems: list[str] = []

    for binary in ("ffmpeg", "ffprobe"):
        try:
            require_binary(binary)
        except PipelineError as exc:
            problems.append(str(exc))

    asr_engine = (config.get("asr_engine") if config else "sensevoice") or "sensevoice"
    required_packages = [
        ("demucs", "demucs"),
        ("edge_tts", "edge-tts"),
        ("google.genai", "google-genai"),
        ("requests", "requests"),
    ]
    if asr_engine == "whisper":
        required_packages.append(("whisper", "openai-whisper"))
    else:
        required_packages.append(("funasr", "funasr"))
        required_packages.append(("modelscope", "modelscope"))

    for module_name, package in required_packages:
        try:
            __import__(module_name)
        except ImportError:
            problems.append(f"Python package '{package}' is not installed (import {module_name}).")

    if need_gemini and config is not None:
        key = str(config.get("gemini_api_key", "")).strip()
        keys = config.get("gemini_api_keys") or []
        has_key = (key and key != "YOUR_GEMINI_API_KEY") or any(
            isinstance(k, str) and k.strip() and k.strip() != "YOUR_GEMINI_API_KEY" for k in keys
        )
        if not has_key:
            problems.append(
                "gemini_api_key is unset. Put it in config/settings.json or export GEMINI_API_KEY."
            )

    tts_engine_name = (config.get("tts_engine") if config else "f5-tts") or "f5-tts"
    if tts_engine_name == "f5-tts" and config is not None:
        ref_path = config.get("f5_tts", {}).get("ref_audio_path", "storage/voice_reference/narrator_ref.wav")
        abs_ref = os.path.abspath(ref_path) if not os.path.isabs(ref_path) else ref_path
        if not os.path.isfile(abs_ref):
            log.warning(
                "Notice: F5-TTS reference clip missing at '%s'. "
                "Drop a 5-10s clean narrator audio clip there, or the engine will fallback to Edge-TTS.",
                ref_path,
            )
    return problems


# --------------------------------------------------------------------------- #
# Per-episode state
# --------------------------------------------------------------------------- #
class EpisodeWorkspace:
    """Paths and cached artefacts for a single episode."""

    def __init__(self, video_path: str, config: dict) -> None:
        self.video_path = os.path.abspath(video_path)
        self.stem = safe_stem(video_path)
        paths = config["storage_paths"]

        self.separated_dir = os.path.join(paths["separated"], self.stem)
        self.tts_dir = os.path.join(paths["tts"], self.stem)
        self.vocals_path = os.path.join(self.separated_dir, "vocals.wav")
        self.no_vocals_path = os.path.join(self.separated_dir, "no_vocals.wav")
        self.transcript_path = os.path.join(self.tts_dir, "transcript.json")
        self.script_path = os.path.join(self.tts_dir, "recap_script.json")
        self.tracks_path = os.path.join(self.tts_dir, "voice_tracks.json")
        self.state_path = os.path.join(self.tts_dir, "state.json")
        self.subtitle_path = os.path.join(self.tts_dir, f"{self.stem}.hi.srt")
        self.output_path = os.path.join(paths["processed"], f"{self.stem}_dubbed.mp4")

        ensure_dir(self.tts_dir)
        self.state: dict[str, Any] = read_json(self.state_path, default={}) or {}

    def mark(self, stage: str, status: str = "done", **extra: Any) -> None:
        entry = {"status": status, "at": time.strftime("%Y-%m-%d %H:%M:%S")}
        entry.update(extra)
        self.state[stage] = entry
        write_json(self.state_path, self.state)

    def is_done(self, stage: str) -> bool:
        return (self.state.get(stage) or {}).get("status") == "done"


# --------------------------------------------------------------------------- #
# Stages
# --------------------------------------------------------------------------- #
def stage_separate(workspace: EpisodeWorkspace, config: dict, args) -> tuple[str, str]:
    from modules import audio_separator

    if (
        not args.force
        and os.path.isfile(workspace.vocals_path)
        and os.path.isfile(workspace.no_vocals_path)
    ):
        log.info("  [1/5] separate  : cached")
        return workspace.vocals_path, workspace.no_vocals_path

    log.info("  [1/5] separate  : running Demucs (htdemucs, two-stem)...")
    vocals, no_vocals = audio_separator.split_audio(
        workspace.video_path,
        config["storage_paths"]["separated"],
        device=args.device,
        jobs=args.demucs_jobs,
        overwrite=args.force,
    )
    workspace.mark("separate")
    return vocals, no_vocals


def stage_transcribe(workspace: EpisodeWorkspace, config: dict, args) -> list[dict]:
    from modules import transcriber

    if not args.force:
        cached = read_json(workspace.transcript_path)
        if isinstance(cached, list) and cached:
            log.info("  [2/5] transcribe: cached (%d segments)", len(cached))
            return cached

    engine = config.get("asr_engine", "sensevoice")
    log.info("  [2/5] transcribe: %s ASR (%s)...", engine.upper(), config.get("source_language", "zh"))
    segments = transcriber.transcribe_chinese(
        workspace.vocals_path,
        engine=engine,
        model_size=config.get("whisper_model", "medium"),
        language=config.get("source_language", "zh"),
        device=args.device,
        cache_path=workspace.transcript_path,
        overwrite=args.force,
    )
    workspace.mark("transcribe", segments=len(segments))
    return segments


def stage_translate(
    workspace: EpisodeWorkspace,
    config: dict,
    args,
    segments: list[dict],
    story_context: str = "",
) -> list[dict]:
    from modules import translator

    if not args.force:
        cached = read_json(workspace.script_path)
        if isinstance(cached, list) and cached:
            log.info("  [3/5] translate : cached (%d segments)", len(cached))
            return cached

    log.info(
        "  [3/5] translate : Gemini Flash recap (%s -> %s)...",
        config.get("source_language", "zh"),
        config["target_language"],
    )
    dub_segments = translator.generate_recap_script(
        segments,
        api_key=config.get("gemini_api_key", ""),
        target_lang=config["target_language"],
        model=config.get("gemini_model", "gemini-flash-latest"),
        story_context=story_context,
        cache_path=workspace.script_path,
        overwrite=args.force,
        api_keys=config.get("gemini_api_keys"),
    )
    workspace.mark("translate", segments=len(dub_segments))
    return dub_segments


def stage_tts(workspace: EpisodeWorkspace, config: dict, args, dub_segments: list[dict]) -> list[dict]:
    from modules import tts_engine

    if not args.force:
        cached = read_json(workspace.tracks_path)
        if isinstance(cached, list) and cached:
            if all(os.path.isfile(track.get("audio_path", "")) for track in cached):
                log.info("  [4/5] tts       : cached (%d clips)", len(cached))
                return cached
            log.info("  [4/5] tts       : cache stale (clips missing) - regenerating")

    sync = config.get("tts_sync", {})
    engine_name = config.get("tts_engine", "f5-tts")
    log.info("  [4/5] tts       : %s + atempo sync...", engine_name.upper())
    tracks = tts_engine.generate_voiceover_tracks(
        dub_segments,
        workspace.tts_dir,
        voice=config.get("tts_voice", "hi-IN-MadhurNeural"),
        config=config,
        atempo_min=float(sync.get("atempo_min", 0.85)),
        atempo_max=float(sync.get("atempo_max", 1.30)),
        concurrency=args.tts_concurrency,
        manifest_path=workspace.tracks_path,
    )
    workspace.mark("tts", clips=len(tracks))
    return tracks


def stage_render(
    workspace: EpisodeWorkspace,
    config: dict,
    args,
    tracks: list[dict],
    dub_segments: list[dict],
) -> str:
    from modules import transcriber, video_processor

    if not args.force and os.path.isfile(workspace.output_path):
        if os.path.getsize(workspace.output_path) > 8192:
            log.info("  [5/5] render    : cached")
            return workspace.output_path

    subtitle_path = None
    if args.burn_subtitles:
        transcriber.segments_to_srt(dub_segments, workspace.subtitle_path, text_key="recap_text")
        subtitle_path = workspace.subtitle_path

    log.info("  [5/5] render    : filtering video + mixing audio...")
    output = video_processor.render_dubbed_episode(
        workspace.video_path,
        workspace.no_vocals_path,
        tracks,
        workspace.output_path,
        config,
        subtitle_path=subtitle_path,
    )
    workspace.mark("render", output=output)
    return output


# --------------------------------------------------------------------------- #
# Episode orchestration
# --------------------------------------------------------------------------- #
def process_episode(
    video_path: str, config: dict, args, story_context: str = ""
) -> dict[str, Any]:
    """Run all five per-episode stages. Returns a result summary."""
    started = time.perf_counter()
    workspace = EpisodeWorkspace(video_path, config)
    name = os.path.basename(video_path)
    source_duration = ffprobe_duration(video_path)

    log.info("=" * 74)
    log.info("EPISODE %s  (%s)", name, human_time(source_duration))
    log.info("=" * 74)

    result: dict[str, Any] = {
        "episode": name,
        "stem": workspace.stem,
        "output": None,
        "ok": False,
        "error": None,
        "segments": 0,
        "clips": 0,
        "context": story_context,
    }

    try:
        stage_separate(workspace, config, args)
        segments = stage_transcribe(workspace, config, args)

        if not segments:
            raise PipelineError(
                "No dialogue was transcribed - cannot build a recap for this episode."
            )
        result["segments"] = len(segments)

        dub_segments = stage_translate(workspace, config, args, segments, story_context)
        tracks = stage_tts(workspace, config, args, dub_segments)
        result["clips"] = len(tracks)

        output = stage_render(workspace, config, args, tracks, dub_segments)
        result["output"] = output
        result["ok"] = True

        from modules.translator import build_story_context

        result["context"] = build_story_context(dub_segments)

        if args.cleanup_stems:
            from modules import audio_separator

            audio_separator.cleanup_separated(workspace.separated_dir)

        log.info(
            "DONE %s in %s -> %s",
            name,
            human_time(time.perf_counter() - started),
            os.path.basename(output),
        )

    except PipelineError as exc:
        result["error"] = str(exc)
        workspace.mark("error", status="failed", message=str(exc))
        log.error("FAILED %s: %s", name, exc)
    except KeyboardInterrupt:
        raise
    except Exception as exc:  # unexpected: keep the traceback for debugging
        result["error"] = f"{type(exc).__name__}: {exc}"
        workspace.mark("error", status="failed", message=result["error"])
        log.error("FAILED %s: %s", name, result["error"])
        log.debug("%s", traceback.format_exc())

    return result


def run_pipeline(config: dict, args) -> int:
    """Run the full pipeline. Returns a process exit code."""
    from modules import concatenator
    from modules.downloader import list_episodes

    raw_dir = config["storage_paths"]["raw"]
    processed_dir = config["storage_paths"]["processed"]
    master_dir = config["storage_paths"]["master"]
    master_name = config.get("master_export", {}).get("filename", "full_manhua_movie.mp4")
    master_path = os.path.join(master_dir, master_name)

    if args.merge_only:
        log.info("Merge-only mode: building the compilation from %s", processed_dir)
        concatenator.merge_all_episodes(processed_dir, master_path, config=config)
        return 0

    episodes = list_episodes(raw_dir)
    if args.episode:
        wanted = {os.path.basename(name).lower() for name in args.episode}
        episodes = [
            path
            for path in episodes
            if os.path.basename(path).lower() in wanted
            or safe_stem(path).lower() in {os.path.splitext(w)[0] for w in wanted}
        ]
        if not episodes:
            log.error("None of %s were found in %s", args.episode, raw_dir)
            return 1
    if args.start_at:
        episodes = episodes[max(0, args.start_at - 1) :]
    if args.limit:
        episodes = episodes[: args.limit]

    if not episodes:
        log.error(
            "No episodes found in %s. Drop ep_001.mp4, ep_002.mp4 ... there, or use "
            "--download-playlist.",
            raw_dir,
        )
        return 1

    total_runtime = sum(ffprobe_duration(path) for path in episodes)
    log.info("")
    log.info("#" * 74)
    log.info("ONE DRAMA ENGINE")
    log.info("  episodes        : %d (%s of source)", len(episodes), human_time(total_runtime))
    log.info("  target language : %s", config["target_language"])
    log.info("  whisper model   : %s", config["whisper_model"])
    log.info("  tts voice       : %s", config["tts_voice"])
    log.info("  gemini model    : %s", config.get("gemini_model"))
    log.info("  output          : %s", master_path)
    log.info("#" * 74)

    results: list[dict[str, Any]] = []
    story_context = args.story_context or ""
    pipeline_started = time.perf_counter()

    for index, video_path in enumerate(episodes, start=1):
        log.info("")
        log.info(">>> %d/%d", index, len(episodes))
        result = process_episode(video_path, config, args, story_context)
        results.append(result)

        if result["ok"] and args.carry_context and result.get("context"):
            story_context = result["context"]

        if not result["ok"] and not args.keep_going:
            log.error("Stopping after a failure. Pass --keep-going to skip failures.")
            break

    succeeded = [r for r in results if r["ok"]]
    failed = [r for r in results if not r["ok"]]

    log.info("")
    log.info("#" * 74)
    log.info(
        "EPISODE SUMMARY: %d succeeded, %d failed, elapsed %s",
        len(succeeded),
        len(failed),
        human_time(time.perf_counter() - pipeline_started),
    )
    for result in results:
        flag = "ok  " if result["ok"] else "FAIL"
        detail = (
            f"{result['segments']} seg / {result['clips']} clips"
            if result["ok"]
            else str(result["error"])[:70]
        )
        log.info("  [%s] %-28s %s", flag, result["episode"][:28], detail)
    log.info("#" * 74)

    write_json(
        os.path.join(master_dir, "run_report.json"),
        {
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "target_language": config["target_language"],
            "episodes": results,
        },
    )

    if not succeeded:
        log.error("No episodes rendered successfully - nothing to merge.")
        return 1

    if args.skip_merge:
        log.info("Skipping the merge step (--skip-merge). Episodes are in %s", processed_dir)
        return 0

    log.info("")
    log.info("Building the final compilation...")
    export_cfg = config.get("master_export", {})

    if args.split_compilations:
        batches = concatenator.plan_compilations(
            processed_dir,
            target_hours_min=float(export_cfg.get("target_hours_min", 2.0)),
            target_hours_max=float(export_cfg.get("target_hours_max", 3.0)),
        )
        base, extension = os.path.splitext(master_path)
        for number, batch in enumerate(batches, start=1):
            target = master_path if len(batches) == 1 else f"{base}_part{number:02d}{extension}"
            concatenator.merge_all_episodes(
                processed_dir, target, episode_paths=batch, config=config
            )
    else:
        concatenator.merge_all_episodes(processed_dir, master_path, config=config)
        final_duration = ffprobe_duration(master_path)
        low = float(export_cfg.get("target_hours_min", 2.0)) * 3600
        high = float(export_cfg.get("target_hours_max", 3.0)) * 3600
        if final_duration < low:
            log.warning(
                "Compilation is %s, shorter than the %.1fh target - add more episodes.",
                human_time(final_duration),
                low / 3600,
            )
        elif final_duration > high:
            log.warning(
                "Compilation is %s, longer than the %.1fh target - consider "
                "--split-compilations.",
                human_time(final_duration),
                high / 3600,
            )

    try:
        from modules import seo_generator

        log.info("")
        log.info("Generating YouTube SEO Package & AI Thumbnail Master Prompt...")
        dur = ffprobe_duration(master_path) if os.path.isfile(master_path) else 0.0
        pkg = seo_generator.generate_youtube_package(
            results,
            config,
            master_duration_seconds=dur,
            output_dir=master_dir,
        )
        if pkg:
            titles = pkg.get("viral_titles", [])
            prompt = pkg.get("thumbnail_master_prompt", "")
            if titles:
                log.info("Top Viral Title: %s", titles[0])
            if prompt:
                log.info("Thumbnail Master Prompt generated in: %s", os.path.join(master_dir, "YOUTUBE_PUBLISH_GUIDE.md"))
    except Exception as exc:
        log.warning("Could not generate YouTube SEO package: %s", exc)

    # --------------------------------------------------------------------------- #
    # Stage 8: Google Drive Auto-Sync
    # --------------------------------------------------------------------------- #
    gdrive_cfg = config.get("google_drive_sync", {})
    if gdrive_cfg.get("enabled", True):
        try:
            from modules import drive_sync

            log.info("")
            log.info("Exporting to Google Drive...")
            guide_path = os.path.join(master_dir, "YOUTUBE_PUBLISH_GUIDE.md")
            json_pkg_path = os.path.join(master_dir, "youtube_package.json")
            gdrive_folder = drive_sync.sync_to_google_drive(
                movie_path=master_path,
                guide_path=guide_path,
                json_pkg_path=json_pkg_path,
                series_title=args.story_context or None,
                destination_folder_name=gdrive_cfg.get("destination_folder_name", "OneDrama_Uploads"),
                custom_drive_path=gdrive_cfg.get("custom_drive_path"),
            )
            if gdrive_folder:
                log.info("Google Drive Ready: %s", gdrive_folder)
        except Exception as exc:
            log.warning("Could not sync to Google Drive: %s", exc)

    log.info("")
    log.info("ALL DONE. Master export: %s", master_path)
    return 0 if not failed else 0


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pipeline.py",
        description="Automated Chinese manhua -> localized recap dub compilation engine.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument("--config", default=DEFAULT_CONFIG_PATH, help="Path to settings.json")

    selection = parser.add_argument_group("episode selection")
    selection.add_argument("--episode", nargs="+", help="Process only these filenames")
    selection.add_argument("--limit", type=int, help="Process at most N episodes")
    selection.add_argument("--start-at", type=int, help="Skip to the Nth episode (1-based)")

    behaviour = parser.add_argument_group("behaviour")
    behaviour.add_argument("--force", action="store_true", help="Ignore caches and redo every stage")
    behaviour.add_argument(
        "--keep-going", action="store_true", help="Continue past a failing episode"
    )
    behaviour.add_argument("--skip-merge", action="store_true", help="Do not build the compilation")
    behaviour.add_argument(
        "--merge-only", action="store_true", help="Only merge already-processed episodes"
    )
    behaviour.add_argument(
        "--split-compilations",
        action="store_true",
        help="Emit several 2-3h compilations instead of one long file",
    )
    behaviour.add_argument(
        "--cleanup-stems", action="store_true", help="Delete Demucs stems after each render"
    )
    behaviour.add_argument(
        "--burn-subtitles", action="store_true", help="Hard-burn the recap text as subtitles"
    )
    behaviour.add_argument(
        "--carry-context",
        action="store_true",
        help="Feed each episode's recap summary into the next for name consistency",
    )
    behaviour.add_argument("--story-context", default="", help="Series synopsis / name sheet")
    behaviour.add_argument("--verbose", "-v", action="store_true", help="Debug logging")

    performance = parser.add_argument_group("performance")
    performance.add_argument(
        "--device", choices=["cuda", "cpu"], help="Force the torch device for Demucs/Whisper"
    )
    performance.add_argument("--demucs-jobs", type=int, default=1, help="Demucs worker processes")
    performance.add_argument(
        "--tts-concurrency", type=int, default=4, help="Parallel Edge-TTS requests"
    )

    utilities = parser.add_argument_group("utilities")
    utilities.add_argument("--check-env", action="store_true", help="Verify dependencies and exit")
    utilities.add_argument("--list-voices", metavar="LANG", help="List Edge-TTS voices and exit")
    utilities.add_argument("--download-playlist", metavar="URL", help="Fetch a playlist and exit")
    utilities.add_argument(
        "--download-douyin", nargs="+", metavar="URL", help="Fetch Douyin links and exit"
    )
    utilities.add_argument(
        "--search", metavar="QUERY", help="Search Bilibili for dynamic manhua series and exit"
    )
    utilities.add_argument(
        "--discover",
        action="store_true",
        help="Discover trending copyright-safe manhua recommendations and exit",
    )
    utilities.add_argument(
        "--genre",
        choices=["urban", "cultivation", "system", "isekai"],
        help="Filter discovery by genre (urban, cultivation, system, isekai)",
    )
    utilities.add_argument(
        "--download-series",
        metavar="QUERY_OR_URL",
        help="Download complete manhua series by Bilibili URL or title search into storage/raw_episodes/ and exit",
    )
    utilities.add_argument(
        "--cookies",
        metavar="BROWSER",
        default=None,
        help="Browser to extract cookies from (e.g. chrome, edge) for Bilibili VIP content",
    )
    utilities.add_argument(
        "--suggest-3d",
        action="store_true",
        help="Show daily 3D AI Dynamic Manhua (漫剧) curated suggestions and exit",
    )
    utilities.add_argument(
        "--screen-watermarks",
        action="store_true",
        help="Pre-screen candidates for corner watermarks using remote snippet sniffing",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.verbose:
        import logging

        logging.getLogger("one_drama").setLevel(logging.DEBUG)
        logging.getLogger("pipeline").setLevel(logging.DEBUG)

    try:
        config = load_config(args.config)
    except PipelineError as exc:
        log.error("%s", exc)
        return 1

    if args.suggest_3d:
        from modules import discovery

        suggestions = discovery.generate_daily_3d_suggestions()
        print("\n" + "=" * 82)
        print("  🌟 DAILY 3D AI DYNAMIC MANHUA (漫剧) CURATED SUGGESTIONS 🌟")
        print("=" * 82)
        for idx, s in enumerate(suggestions, start=1):
            print(f"[{idx}] {s['icon']}  {s['title']}")
            print(f"     Chinese: {s['chinese_title']} | Genre: {s['category']}")
            print(f"     Hook:    {s['hook']}")
            print(f"     Target:  {s['target_audience']}")
            print(f"     Search:  python pipeline.py --search \"{s['query']}\" --screen-watermarks")
            print("-" * 82)
        return 0

    if args.check_env:
        problems = check_environment(config=config)
        if problems:
            log.error("Environment problems:")
            for problem in problems:
                log.error("  - %s", problem)
            return 1
        log.info("Environment looks good: FFmpeg, Whisper, Demucs, Edge-TTS, Gemini all present.")
        return 0

    if args.list_voices:
        from modules import tts_engine

        try:
            voices = tts_engine.list_voices(args.list_voices)
        except PipelineError as exc:
            log.error("%s", exc)
            return 1
        for voice in voices:
            log.info(
                "%-32s %-8s %s",
                voice.get("ShortName", "?"),
                voice.get("Gender", "?"),
                voice.get("Locale", "?"),
            )
        log.info("%d voice(s) matched '%s'.", len(voices), args.list_voices)
        return 0

    if args.download_playlist:
        from modules.downloader import download_bilibili_playlist

        try:
            paths = download_bilibili_playlist(
                args.download_playlist, config["storage_paths"]["raw"]
            )
        except PipelineError as exc:
            log.error("%s", exc)
            return 1
        log.info("Downloaded %d episode(s).", len(paths))
        return 0

    if args.download_douyin:
        from modules.downloader import download_douyin_batch

        paths = download_douyin_batch(args.download_douyin, config["storage_paths"]["raw"])
        return 0 if paths else 1

    if args.search:
        from modules import discovery

        custom_blocks = config.get("discovery", {}).get("blocked_franchises", [])
        log.info("Searching Bilibili for dynamic manhua: '%s'...", args.search)

        if args.screen_watermarks:
            log.info("Ultra-low-bandwidth watermark pre-screening enabled (sniffing remote keyframes)...")
            candidates = discovery.search_and_screen_3d_manhua(
                args.search, max_candidates=5, screen_watermarks=True, custom_blocklist=custom_blocks
            )
            print("\n" + "=" * 82)
            print(f"{'#':<3} {'STATUS':<10} {'EFS':<8} {'EPS':<6} {'SERIES TITLE & AUDIT'}")
            print("=" * 82)
            clean_candidates = []
            for idx, c in enumerate(candidates, start=1):
                badge = "[CLEAN]" if c.get("is_clean") else "[DIRTY]"
                score_str = f"{c.get('efs_score', 0):.1f}pt"
                print(f"{idx:<3} {badge:<10} {score_str:<8} {c.get('episodes', 1):<6} {c['title'][:48]}")
                print(f"    URL: {c['url']} | Author: {c['uploader']} | Views: {c['view_count']}")
                if not c.get("is_clean"):
                    print(f"    [!] Watermark detected in {c.get('watermark_zone')} (confidence: {c.get('watermark_audit', {}).get('confidence')}) -> EXCLUDED")
                else:
                    clean_candidates.append(c)
                print("-" * 82)

            if clean_candidates:
                log.info(
                    "\nTop Approved Clean Series (Ready for Dubbing):\n  python pipeline.py --download-series \"%s\"",
                    clean_candidates[0]["url"],
                )
            else:
                log.warning("No clean, watermark-free series found for this query. Try another theme.")
            return 0

        candidates = discovery.search_manhua_series(args.search, custom_blocklist=custom_blocks)
        print(discovery.format_catalogue_table(candidates))
        if candidates:
            log.info(
                "\nTo download the full series, copy the URL and run:\n  python pipeline.py --download-series \"%s\"",
                candidates[0]["url"],
            )
        return 0

    if args.discover:
        from modules import discovery

        custom_blocks = config.get("discovery", {}).get("blocked_franchises", [])
        genre_label = args.genre or "all genres"
        log.info("Discovering trending copyright-safe manhua (%s)...", genre_label)
        recs = discovery.discover_trending_gems(genre=args.genre, custom_blocklist=custom_blocks)
        log.info("=== TRENDING COPYRIGHT-SAFE DYNAMIC MANHUA RECOMMENDATIONS ===")
        print(discovery.format_catalogue_table(recs))
        if recs:
            log.info(
                "\nTo download any recommended series, run:\n  python pipeline.py --download-series \"%s\"",
                recs[0]["url"],
            )
        return 0

    if args.download_series:
        from modules import downloader

        custom_blocks = config.get("discovery", {}).get("blocked_franchises", [])
        raw_dir = config["storage_paths"]["raw"]
        try:
            paths = downloader.download_series_by_query(
                args.download_series,
                raw_dir,
                limit=args.limit,
                cookies_from_browser=args.cookies,
                custom_blocklist=custom_blocks,
            )
        except PipelineError as exc:
            log.error("%s", exc)
            return 1
        log.info("Download complete! %d episode(s) saved in %s", len(paths), raw_dir)
        return 0

    problems = check_environment(config=config, need_gemini=not args.merge_only)
    if problems:
        log.error("Cannot start - fix these first:")
        for problem in problems:
            log.error("  - %s", problem)
        log.error("Install Python deps with: pip install -r requirements.txt")
        return 1

    try:
        return run_pipeline(config, args)
    except KeyboardInterrupt:
        log.warning("Interrupted by user. Progress is cached; re-run to resume.")
        return 130
    except PipelineError as exc:
        log.error("Pipeline error: %s", exc)
        return 1
    except Exception as exc:  # pragma: no cover - last-resort guard
        log.error("Unexpected failure: %s: %s", type(exc).__name__, exc)
        log.debug("%s", traceback.format_exc())
        return 1


if __name__ == "__main__":
    sys.exit(main())
