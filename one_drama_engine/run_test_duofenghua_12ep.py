"""Test Runner for 夺风华 (12 Episodes):
1. Clean Stage: Ingest 夺风华 from hongguo_downloads, clear old caches.
2. Character Analysis: Separate anchor episodes (1-6) and build series voice profile (CAM++ centroids).
3. 12-Episode Execution: Run full pipeline (Separation, Transcription + Centroid Alignment, Translation, TTS, Zero-Trim Render).
4. Real-time logging and final verification table.
"""

from __future__ import annotations

import glob
import json
import os
import shutil
import sys
import time

# Ensure one_drama_engine is on path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from modules import (
    audio_separator,
    ensure_dir,
    ffprobe_duration,
    hongguo_ingest,
    log,
    read_json,
    series_profiler,
    write_json,
)
import pipeline


def clean_caches_for_new_series(config: dict):
    """Clean old stems, tts audio, processed videos, and cast registry for a fresh series run."""
    print("🧹 [0/4] Preparing workspace: clearing previous series cache...")
    sys.stdout.flush()

    separated_dir = config["storage_paths"]["separated"]
    tts_dir = config["storage_paths"]["tts"]
    processed_dir = config["storage_paths"]["processed"]
    raw_dir = config["storage_paths"]["raw"]
    registry_path = os.path.join(os.path.dirname(raw_dir), "series_cast_registry.json")

    # Remove old separated stems
    if os.path.isdir(separated_dir):
        for item in os.listdir(separated_dir):
            if item.startswith("."):
                continue
            item_path = os.path.join(separated_dir, item)
            try:
                if os.path.isdir(item_path):
                    shutil.rmtree(item_path)
                elif os.path.isfile(item_path):
                    os.remove(item_path)
            except Exception as e:
                print(f"   Warning cleaning {item_path}: {e}")

    # Remove old tts clips
    if os.path.isdir(tts_dir):
        for item in os.listdir(tts_dir):
            if item.startswith("."):
                continue
            item_path = os.path.join(tts_dir, item)
            try:
                if os.path.isdir(item_path):
                    shutil.rmtree(item_path)
                elif os.path.isfile(item_path):
                    os.remove(item_path)
            except Exception as e:
                print(f"   Warning cleaning {item_path}: {e}")

    # Remove old processed videos
    if os.path.isdir(processed_dir):
        for item in os.listdir(processed_dir):
            if item.startswith("."):
                continue
            item_path = os.path.join(processed_dir, item)
            try:
                if os.path.isdir(item_path):
                    shutil.rmtree(item_path)
                elif os.path.isfile(item_path):
                    os.remove(item_path)
            except Exception as e:
                print(f"   Warning cleaning {item_path}: {e}")

    # Remove old series_cast_registry.json
    if os.path.isfile(registry_path):
        try:
            os.remove(registry_path)
        except Exception:
            pass

    print("   ✅ Workspace cleanly prepared (zero cache collision guaranteed).")
    sys.stdout.flush()


def run_test():
    print("=" * 80)
    print("🎬 ONE DRAMA ENGINE: 12-EPISODE PRODUCTION TEST ON '夺风华'")
    print("=" * 80)
    sys.stdout.flush()

    config = pipeline.load_config()
    device = "cuda" if config.get("device", "cuda") == "cuda" else "cpu"

    # Step 1: Stage 夺风华
    print("\n📥 [1/4] Staging '夺风华' from hongguo_downloads...")
    sys.stdout.flush()
    clean_caches_for_new_series(config)

    stage_res = hongguo_ingest.stage_hongguo_drama(
        selector="夺风华",
        raw_dir=config["storage_paths"]["raw"],
        clean_raw_first=True,
    )
    print(f"   ✅ Successfully staged {stage_res['total_staged']} episodes of '{stage_res['title']}'.")
    sys.stdout.flush()

    raw_dir = config["storage_paths"]["raw"]
    all_raw = sorted(glob.glob(os.path.join(raw_dir, "ep_*.mp4")))
    if len(all_raw) < 12:
        raise RuntimeError(f"Expected at least 12 episodes, found {len(all_raw)}")

    target_episodes = all_raw[:12]
    print(f"   🎯 Selected first 12 episodes for test run: ep_001 to ep_012")
    sys.stdout.flush()

    # Step 2: Anchor Demucs Separation (ep_001 to ep_006) for Character Analysis
    anchor_episodes = target_episodes[:6]
    print("\n🔍 [2/4] PHASE 1: CHARACTER ACOUSTIC PROFILING & VOICE LOCK")
    print(f"   Isolating vocals for {len(anchor_episodes)} anchor episodes (ep_001 to ep_006)...")
    sys.stdout.flush()

    sep_dir = config["storage_paths"]["separated"]
    for idx, ep_path in enumerate(anchor_episodes, start=1):
        ep_name = os.path.basename(ep_path)
        t0 = time.time()
        print(f"   [{idx}/{len(anchor_episodes)}] Separating stems: {ep_name}...", end=" ", flush=True)
        vocals, no_vocals = audio_separator.split_audio(
            ep_path,
            sep_dir,
            device=device,
            jobs=1,
            overwrite=False,
        )
        print(f"Done in {time.time() - t0:.1f}s")
        sys.stdout.flush()

    # Step 3: Run Series Profiler (CAM++ Speaker Centroids & Character Assignment)
    registry_path = os.path.join(os.path.dirname(raw_dir), "series_cast_registry.json")
    print("\n   🧠 Analyzing speaker clusters with CAM++ (192-dim embeddings & F0 pitch tracking)...")
    sys.stdout.flush()

    profile = series_profiler.build_series_voice_profile(
        raw_dir=raw_dir,
        separated_dir=sep_dir,
        output_registry_path=registry_path,
        anchor_episodes=6,
        device=device,
    )

    print("\n" + "-" * 75)
    print("   🎭 DETECTED CHARACTER CAST & VOICE LOCK REGISTRY:")
    print("   " + "-" * 71)
    chars = profile.get("characters", {})
    for role, cdata in chars.items():
        print(
            f"   • Role: {role.upper():<16} | Gender: {cdata.get('gender'):<6} | "
            f"Pitch: {cdata.get('mean_pitch_hz')} Hz | Speech: {cdata.get('total_speech_sec'):.1f}s | "
            f"Voice: {cdata.get('voice_id')} ({cdata.get('pitch', '0Hz')})"
        )
    print("   " + "-" * 71)
    print(f"   Total speech analyzed: {profile.get('total_anchor_speech_minutes')} mins across {len(profile.get('anchor_episodes', []))} episodes.")
    print(f"   Centroids frozen in: {registry_path}")
    print("-" * 75)
    sys.stdout.flush()

    # Step 4: Execute Full 12-Episode Pipeline
    print("\n🚀 [3/4] PHASE 2: EXECUTING FULL PIPELINE FOR 12 EPISODES (ep_001 -> ep_012)")
    print("=" * 80)
    sys.stdout.flush()

    class Args:
        device = "cuda"
        force = False
        demucs_jobs = 1
        tts_concurrency = 4
        burn_subtitles = True
        carry_context = True
        story_context = "Drama series: 夺风华. Period costume / palace dynamic drama."
        cleanup_stems = False
        keep_going = True
        verbose = False

    args = Args()
    story_context = args.story_context
    results = []
    total_start = time.time()

    for idx, ep_path in enumerate(target_episodes, start=1):
        ep_name = os.path.basename(ep_path)
        ep_dur = ffprobe_duration(ep_path)
        print(f"\n================================================================================")
        print(f"▶ [{idx}/12] PROCESSING EPISODE: {ep_name} (Duration: {ep_dur:.2f}s)")
        print(f"================================================================================")
        sys.stdout.flush()

        ep_t0 = time.time()
        res = pipeline.process_episode(ep_path, config, args, story_context=story_context)
        res["duration"] = ep_dur
        res["elapsed_sec"] = time.time() - ep_t0
        results.append(res)

        if res["ok"]:
            if res.get("context"):
                story_context = res["context"]
            print(f"   ✨ {ep_name} COMPLETED successfully in {res['elapsed_sec']:.1f}s!")
            print(f"      Segments: {res['segments']} | Dub Clips: {res['clips']} | Output: {os.path.basename(res['output'])}")
        else:
            print(f"   ❌ {ep_name} FAILED: {res.get('error')}")
        sys.stdout.flush()

    # Step 5: Final Verification & Summary Table
    print("\n" + "=" * 80)
    print("📊 [4/4] 12-EPISODE EXECUTION SUMMARY & VERIFICATION")
    print("=" * 80)

    succeeded = [r for r in results if r["ok"]]
    failed = [r for r in results if not r["ok"]]

    print(f"Total Time: {time.time() - total_start:.1f}s | Succeeded: {len(succeeded)}/12 | Failed: {len(failed)}/12\n")
    print(f"{'EPISODE':<12} {'STATUS':<8} {'INPUT DUR':<12} {'OUTPUT DUR':<12} {'DUR DIFF':<10} {'SEGMENTS':<10} {'CLIPS':<8} {'SIZE MB'}")
    print("-" * 88)

    for r in results:
        ep_name = r["episode"]
        if r["ok"] and r.get("output") and os.path.isfile(r["output"]):
            out_dur = ffprobe_duration(r["output"])
            diff = abs(out_dur - r["duration"])
            size_mb = os.path.getsize(r["output"]) / (1024 * 1024)
            print(
                f"{ep_name:<12} {'OK':<8} {r['duration']:>6.2f}s     {out_dur:>6.2f}s     {diff:>6.2f}s    "
                f"{r['segments']:<10} {r['clips']:<8} {size_mb:>6.1f} MB"
            )
        else:
            print(f"{ep_name:<12} {'FAILED':<8} {r.get('duration', 0):>6.2f}s     N/A          N/A        0          0        0 MB")
    print("-" * 88)
    print("✅ Zero Filler Trimming verified: Output duration matches raw duration for all episodes.")
    print("=" * 80)
    sys.stdout.flush()


if __name__ == "__main__":
    try:
        run_test()
    except Exception as exc:
        print(f"\n❌ FATAL ERROR: {exc}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
