"""Smart Filler Trimmer Module for OneDrama Engine.

Analyzes dialogue boundaries from ASR alongside acoustic energy in Demucs
no_vocals stems to compress protracted pauses, stationary pan-and-scan panels,
and boring dead air while strictly preserving combat SFX and natural dialogue cadence.
"""

from __future__ import annotations

import math
import os
from typing import Any, Sequence

import numpy as np
import soundfile as sf

from . import ensure_dir, ffprobe_duration, log, read_json, write_json

PRE_CUSHION_DEFAULT = 0.40   # Lead-in seconds before speech starts
POST_CUSHION_DEFAULT = 0.45  # Lead-out seconds after speech ends
MIN_GAP_DEFAULT = 2.50       # Gaps shorter than this are kept intact
TARGET_PAUSE_DEFAULT = 1.00  # Compressed pause duration for dead filler
SFX_RMS_THRESHOLD = 0.075    # RMS threshold to detect combat/action in no_vocals
SFX_PEAK_THRESHOLD = 0.30    # Peak threshold for sudden explosive SFX


def compute_audio_window_energy(
    audio_path: str,
    start_sec: float,
    end_sec: float,
) -> tuple[float, float]:
    """Compute (rms_energy, peak_amplitude) of an audio segment."""
    if not os.path.isfile(audio_path) or start_sec >= end_sec:
        return 0.0, 0.0

    try:
        with sf.SoundFile(audio_path) as snd:
            sr = snd.samplerate
            channels = snd.channels
            start_frame = max(0, int(start_sec * sr))
            stop_frame = min(snd.frames, int(end_sec * sr))
            if stop_frame <= start_frame:
                return 0.0, 0.0

            snd.seek(start_frame)
            frames_to_read = stop_frame - start_frame
            data = snd.read(frames_to_read, dtype="float32")

            if channels > 1:
                # Average across stereo channels
                data = np.mean(data, axis=1)

            peak = float(np.max(np.abs(data))) if len(data) > 0 else 0.0
            rms = float(np.sqrt(np.mean(data**2))) if len(data) > 0 else 0.0
            return rms, peak
    except Exception as exc:
        log.debug("Failed to read audio window (%s: %.2f-%.2f): %s", audio_path, start_sec, end_sec, exc)
        return 0.0, 0.0


def plan_smart_trimming(
    video_duration: float,
    speech_cues: Sequence[dict[str, Any]],
    no_vocals_path: str | None = None,
    *,
    min_gap_sec: float = MIN_GAP_DEFAULT,
    pre_cushion_sec: float = PRE_CUSHION_DEFAULT,
    post_cushion_sec: float = POST_CUSHION_DEFAULT,
    target_pause_sec: float = TARGET_PAUSE_DEFAULT,
    sfx_threshold: float = SFX_RMS_THRESHOLD,
) -> dict[str, Any]:
    """Calculate the cushioned Edit Decision List (EDL) for an episode.

    Returns:
        A dict containing:
        - original_duration
        - trimmed_duration
        - saved_seconds
        - saved_percent
        - keep_segments: [{'start': float, 'end': float, 'type': str}]
        - time_remap: list of (orig_start, orig_end, new_start, new_end)
    """
    if video_duration <= 0.0:
        return {
            "original_duration": 0.0,
            "trimmed_duration": 0.0,
            "saved_seconds": 0.0,
            "saved_percent": "0.0%",
            "keep_segments": [],
            "time_remap": [],
        }

    # 1. Extract raw dialogue intervals
    raw_intervals = []
    for c in speech_cues:
        s = max(0.0, float(c.get("start", 0.0)))
        e = min(video_duration, float(c.get("end", 0.0)))
        if e > s:
            raw_intervals.append((s, e))

    raw_intervals.sort(key=lambda x: x[0])

    # 2. Expand with pre/post safety cushions
    cushioned_intervals = []
    for s, e in raw_intervals:
        c_start = max(0.0, s - pre_cushion_sec)
        c_end = min(video_duration, e + post_cushion_sec)
        cushioned_intervals.append([c_start, c_end])

    # 3. Merge overlapping or touching cushioned windows
    merged_dialogue = []
    for c_start, c_end in cushioned_intervals:
        if not merged_dialogue:
            merged_dialogue.append([c_start, c_end])
        else:
            prev_start, prev_end = merged_dialogue[-1]
            if c_start <= prev_end:
                merged_dialogue[-1][1] = max(prev_end, c_end)
            else:
                merged_dialogue.append([c_start, c_end])

    # 4. Audit gaps between merged dialogue windows
    keep_segments: list[dict[str, Any]] = []
    current_time = 0.0

    for idx, (d_start, d_end) in enumerate(merged_dialogue):
        # Gap before this dialogue
        if d_start > current_time:
            gap_duration = d_start - current_time
            if gap_duration <= min_gap_sec:
                # Short, natural pause -> keep completely
                keep_segments.append({
                    "start": round(current_time, 3),
                    "end": round(d_start, 3),
                    "duration": round(gap_duration, 3),
                    "type": "natural_pause",
                })
            else:
                # Long gap -> check for action SFX in no_vocals
                is_action = False
                rms, peak = 0.0, 0.0
                if no_vocals_path and os.path.isfile(no_vocals_path):
                    rms, peak = compute_audio_window_energy(no_vocals_path, current_time, d_start)
                    if rms >= sfx_threshold or peak >= SFX_PEAK_THRESHOLD:
                        is_action = True

                if is_action:
                    # Action / fight scene -> keep completely
                    keep_segments.append({
                        "start": round(current_time, 3),
                        "end": round(d_start, 3),
                        "duration": round(gap_duration, 3),
                        "type": "combat_action",
                        "rms": round(rms, 4),
                    })
                else:
                    # Dead filler -> compress to target_pause_sec
                    # Split transition: half at head, half at tail
                    half_pause = min(target_pause_sec / 2.0, gap_duration / 2.0)
                    part1_end = current_time + half_pause
                    part2_start = d_start - half_pause

                    if part1_end < part2_start:
                        keep_segments.append({
                            "start": round(current_time, 3),
                            "end": round(part1_end, 3),
                            "duration": round(half_pause, 3),
                            "type": "filler_transition_lead",
                        })
                        keep_segments.append({
                            "start": round(part2_start, 3),
                            "end": round(d_start, 3),
                            "duration": round(half_pause, 3),
                            "type": "filler_transition_tail",
                        })
                    else:
                        keep_segments.append({
                            "start": round(current_time, 3),
                            "end": round(d_start, 3),
                            "duration": round(gap_duration, 3),
                            "type": "shortened_pause",
                        })

        # Add the dialogue segment itself
        keep_segments.append({
            "start": round(d_start, 3),
            "end": round(d_end, 3),
            "duration": round(d_end - d_start, 3),
            "type": "cushioned_dialogue",
        })
        current_time = d_end

    # Trailing gap after last dialogue
    if current_time < video_duration:
        trailing_gap = video_duration - current_time
        if trailing_gap <= min_gap_sec:
            keep_segments.append({
                "start": round(current_time, 3),
                "end": round(video_duration, 3),
                "duration": round(trailing_gap, 3),
                "type": "outro_natural",
            })
        else:
            rms, peak = compute_audio_window_energy(no_vocals_path, current_time, video_duration) if no_vocals_path else (0.0, 0.0)
            if rms >= sfx_threshold or peak >= SFX_PEAK_THRESHOLD:
                keep_segments.append({
                    "start": round(current_time, 3),
                    "end": round(video_duration, 3),
                    "duration": round(trailing_gap, 3),
                    "type": "outro_action",
                })
            else:
                keep_end = min(video_duration, current_time + target_pause_sec)
                keep_segments.append({
                    "start": round(current_time, 3),
                    "end": round(keep_end, 3),
                    "duration": round(keep_end - current_time, 3),
                    "type": "outro_compressed",
                })

    # Merge contiguous keep segments if they share the exact boundary
    condensed_keep: list[dict[str, Any]] = []
    for seg in keep_segments:
        if not condensed_keep:
            condensed_keep.append(dict(seg))
        else:
            prev = condensed_keep[-1]
            if math.isclose(prev["end"], seg["start"], abs_tol=0.005):
                prev["end"] = seg["end"]
                prev["duration"] = round(prev["end"] - prev["start"], 3)
                if "dialogue" in seg["type"]:
                    prev["type"] = "dialogue_extended"
            else:
                condensed_keep.append(dict(seg))

    # 5. Build time remap function
    time_remap = []
    accumulated_new = 0.0
    for seg in condensed_keep:
        dur = seg["end"] - seg["start"]
        time_remap.append({
            "orig_start": seg["start"],
            "orig_end": seg["end"],
            "new_start": round(accumulated_new, 3),
            "new_end": round(accumulated_new + dur, 3),
        })
        accumulated_new += dur

    trimmed_duration = round(accumulated_new, 3)
    saved_seconds = round(video_duration - trimmed_duration, 3)
    saved_percent = round((saved_seconds / video_duration) * 100.0, 1) if video_duration > 0 else 0.0

    return {
        "original_duration": round(video_duration, 3),
        "trimmed_duration": trimmed_duration,
        "saved_seconds": saved_seconds,
        "saved_percent": f"{saved_percent}%",
        "keep_segments": condensed_keep,
        "time_remap": time_remap,
    }


def remap_timestamp(time_remap: list[dict[str, Any]], orig_t: float) -> float:
    """Map an original video timestamp to its position in the trimmed video."""
    if not time_remap:
        return orig_t

    for block in time_remap:
        if block["orig_start"] <= orig_t <= block["orig_end"]:
            offset = orig_t - block["orig_start"]
            return round(block["new_start"] + offset, 3)
        if orig_t < block["orig_start"]:
            # Falls inside a trimmed gap -> clamp to the new gap boundary
            return block["new_start"]

    # Past the last segment
    return time_remap[-1]["new_end"]


def remap_speech_cues(
    speech_cues: Sequence[dict[str, Any]],
    time_remap: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Produce a new list of speech cues with updated start/end times."""
    remapped = []
    for c in speech_cues:
        new_c = dict(c)
        s = float(c.get("start", 0.0))
        e = float(c.get("end", 0.0))
        new_s = remap_timestamp(time_remap, s)
        new_e = remap_timestamp(time_remap, e)
        new_c["start"] = new_s
        new_c["end"] = max(new_s + 0.1, new_e)
        new_c["duration"] = round(new_c["end"] - new_s, 3)
        remapped.append(new_c)
    return remapped


def trim_audio_stem(
    input_wav: str,
    keep_segments: Sequence[dict[str, Any]],
    output_wav: str,
) -> str:
    """Extract and concatenate keep_segments from an audio file with sample accuracy."""
    if not os.path.isfile(input_wav):
        raise FileNotFoundError(f"Input audio file not found: {input_wav}")

    ensure_dir(os.path.dirname(os.path.abspath(output_wav)))

    with sf.SoundFile(input_wav) as snd:
        sr = snd.samplerate
        channels = snd.channels
        pieces = []
        for seg in keep_segments:
            s_frame = max(0, int(round(float(seg["start"]) * sr)))
            e_frame = min(snd.frames, int(round(float(seg["end"]) * sr)))
            if e_frame > s_frame:
                snd.seek(s_frame)
                pieces.append(snd.read(e_frame - s_frame, dtype="float32"))

        if pieces:
            merged = np.concatenate(pieces, axis=0)
        else:
            merged = np.zeros((max(1, int(sr * 0.1)), channels), dtype="float32")

        sf.write(output_wav, merged, sr)

    log.debug("FillerTrimmer: Trimmed audio stem saved to %s", output_wav)
    return output_wav


def build_ffmpeg_select_filter(keep_segments: Sequence[dict[str, Any]]) -> str:
    """Generate the FFmpeg select filter expression to trim video to keep_segments."""
    if not keep_segments:
        return ""

    conditions = []
    for seg in keep_segments:
        s = float(seg["start"])
        e = float(seg["end"])
        conditions.append(f"between(t\\,{s:.3f}\\,{e:.3f})")

    select_expr = "+".join(conditions)
    return f"select='{select_expr}',setpts=N/FRAME_RATE/TB"
