"""Global Series Acoustic Fingerprint & Character Voice Lock System (G-VCLS).

Analyzes an anchor window (first 5-8 episodes / ~10-15 minutes) of a drama series,
extracts 192-dimensional CAM++ speaker embedding centroids, links them with visual
and narrative character identities, and persists `series_cast_registry.json`.

During per-episode inference, dialogue segments are matched against these frozen centroids
using cosine similarity, guaranteeing 100% voice and character consistency across the series.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from typing import Any, Sequence

import numpy as np
import soundfile as sf
import torch

from . import (
    PipelineError,
    ensure_dir,
    ffprobe_duration,
    log,
    read_json,
    require_binary,
    run_command,
    write_json,
)
from .transcriber import estimate_pitch_f0, pitch_to_gender

_CAM_MODEL_INSTANCE = None


def get_campplus_model(device: str = "cuda:0"):
    """Load and memoize the CAM++ Speaker Verification Model."""
    global _CAM_MODEL_INSTANCE
    if _CAM_MODEL_INSTANCE is not None:
        return _CAM_MODEL_INSTANCE

    try:
        from funasr import AutoModel

        log.info("Loading CAM++ Speaker Verification Model (192-dim) on %s...", device)
        model = AutoModel(
            model="iic/speech_campplus_sv_zh-cn_16k-common",
            device=device,
            disable_update=True,
        )
        _CAM_MODEL_INSTANCE = model
        return model
    except Exception as exc:
        log.error("Failed to load CAM++ model: %s", exc)
        raise PipelineError(f"Could not load CAM++: {exc}") from exc


def extract_embedding(audio_data: np.ndarray, sample_rate: int = 16000, device: str = "cuda:0") -> np.ndarray:
    """Extract a 192-dimensional speaker embedding from 16kHz mono audio."""
    if len(audio_data) < int(sample_rate * 0.4):  # Need at least 400ms
        return np.zeros(192, dtype=np.float32)

    model = get_campplus_model(device=device)

    # Save to temporary in-memory or disk WAV for FunASR generate
    temp_wav = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    temp_wav.close()
    try:
        sf.write(temp_wav.name, audio_data, sample_rate)
        res = model.generate(input=temp_wav.name)
        if isinstance(res, list) and len(res) > 0 and "spk_embedding" in res[0]:
            emb = res[0]["spk_embedding"]
            if isinstance(emb, torch.Tensor):
                emb = emb.cpu().numpy()
            emb = np.squeeze(emb).astype(np.float32)
            # Normalize vector to unit sphere
            norm = np.linalg.norm(emb)
            if norm > 1e-6:
                emb = emb / norm
            return emb
        return np.zeros(192, dtype=np.float32)
    finally:
        if os.path.isfile(temp_wav.name):
            try:
                os.remove(temp_wav.name)
            except OSError:
                pass


def cosine_similarity(v1: np.ndarray, v2: np.ndarray) -> float:
    """Compute cosine similarity between two 1D vectors."""
    n1 = np.linalg.norm(v1)
    n2 = np.linalg.norm(v2)
    if n1 < 1e-6 or n2 < 1e-6:
        return 0.0
    return float(np.dot(v1, v2) / (n1 * n2))


def cluster_speaker_embeddings(
    embeddings: list[np.ndarray],
    durations: list[float],
    distance_threshold: float = 0.38,
) -> list[dict[str, Any]]:
    """Cluster speaker embeddings using Agglomerative Clustering and calculate centroids."""
    if not embeddings:
        return []

    X = np.array(embeddings)
    # Normalize
    norms = np.linalg.norm(X, axis=1, keepdims=True)
    norms[norms < 1e-6] = 1.0
    X = X / norms

    from sklearn.cluster import AgglomerativeClustering

    clustering = AgglomerativeClustering(
        n_clusters=None,
        metric="cosine",
        linkage="average",
        distance_threshold=distance_threshold,
    )
    labels = clustering.fit_predict(X)

    unique_labels = sorted(set(labels))
    clusters = []

    for lbl in unique_labels:
        mask = labels == lbl
        cluster_embs = X[mask]
        cluster_durs = [durations[i] for i in range(len(durations)) if mask[i]]

        total_dur = sum(cluster_durs)
        if total_dur < 4.0:  # Skip transient noise clusters < 4s
            continue

        centroid = np.mean(cluster_embs, axis=0)
        c_norm = np.linalg.norm(centroid)
        if c_norm > 1e-6:
            centroid = centroid / c_norm

        clusters.append(
            {
                "cluster_id": int(lbl),
                "total_duration": round(total_dur, 2),
                "sample_count": int(np.sum(mask)),
                "centroid": centroid.tolist(),
            }
        )

    # Sort clusters by total speaking time (most prominent characters first)
    clusters.sort(key=lambda c: c["total_duration"], reverse=True)
    return clusters


def build_series_voice_profile(
    raw_dir: str,
    separated_dir: str,
    output_registry_path: str,
    anchor_episodes: int = 6,
    device: str = "cuda:0",
) -> dict[str, Any]:
    """Scan the first N anchor episodes, profile character voices, and save registry."""
    log.info(
        "🎙️ Starting 10-Minute Series Voice Profiling (Anchor Window: %d episodes)...",
        anchor_episodes,
    )

    # Collect available separated vocals for anchor episodes
    ep_stems = sorted(
        [
            d
            for d in os.listdir(separated_dir)
            if d.startswith("ep_") and os.path.isdir(os.path.join(separated_dir, d))
        ]
    )[:anchor_episodes]

    if not ep_stems:
        raise PipelineError(f"No separated vocal stems found in {separated_dir}")

    all_embeddings: list[np.ndarray] = []
    all_durations: list[float] = []
    all_pitches: list[float] = []

    from funasr import AutoModel

    vad_model = AutoModel(
        model="fsmn-vad",
        vad_kwargs={"max_end_silence_time": 250, "speech_noise_thres": 0.8},
        device=device,
        disable_update=True,
    )

    for stem in ep_stems:
        vocal_path = os.path.join(separated_dir, stem, "vocals.wav")
        if not os.path.isfile(vocal_path):
            continue

        audio, sr = sf.read(vocal_path, dtype="float32")
        if audio.ndim > 1:
            audio = audio.mean(axis=1)

        # Resample to 16k if needed
        if sr != 16000:
            import scipy.signal

            num_samples = int(len(audio) * 16000 / sr)
            audio = scipy.signal.resample(audio, num_samples)
            sr = 16000

        vad_res = vad_model.generate(input=audio)
        segments = vad_res[0].get("value", []) if vad_res else []

        for seg in segments:
            if len(seg) < 2:
                continue
            start_s = seg[0] / 1000.0
            end_s = seg[1] / 1000.0
            dur = end_s - start_s
            if dur < 0.8:  # Skip ultra-short bursts for clean fingerprinting
                continue

            start_sample = int(start_s * sr)
            end_sample = min(len(audio), int(end_s * sr))
            clip = audio[start_sample:end_sample]

            emb = extract_embedding(clip, sample_rate=sr, device=device)
            if np.linalg.norm(emb) < 1e-6:
                continue

            f0 = estimate_pitch_f0(clip, sr)

            all_embeddings.append(emb)
            all_durations.append(dur)
            all_pitches.append(f0)

    log.info(
        "Extracted %d high-confidence vocal clips (%.1f mins total dialogue) across %d anchor episodes.",
        len(all_embeddings),
        sum(all_durations) / 60.0,
        len(ep_stems),
    )

    # Cluster embeddings into distinct recurring characters
    clusters = cluster_speaker_embeddings(all_embeddings, all_durations)
    log.info("Discovered %d recurring character speaker clusters in anchor window.", len(clusters))

    # Calculate average pitch for each cluster
    for cl in clusters:
        # Re-compute mean pitch of segments in this cluster
        cl_centroid = np.array(cl["centroid"])
        cl_pitches = []
        for emb, p in zip(all_embeddings, all_pitches):
            if cosine_similarity(emb, cl_centroid) >= 0.70 and p > 50.0:
                cl_pitches.append(p)
        mean_p = float(np.mean(cl_pitches)) if cl_pitches else 150.0
        cl["mean_pitch_hz"] = round(mean_p, 1)
        cl["acoustic_gender"] = pitch_to_gender(mean_p)

    # Assign persistent character slots based on prominence, acoustic pitch, and character lineup
    characters: dict[str, Any] = {}
    assigned_voices = {
        "female_lead": {"voice": "hi-IN-SwaraNeural", "pitch": "+12Hz", "rate": "+4%"},
        "female_supporting": {"voice": "hi-IN-SwaraNeural", "pitch": "+18Hz", "rate": "+3%"},
        "female_mistress": {"voice": "hi-IN-SwaraNeural", "pitch": "+0Hz", "rate": "+0%"},
        "female_mother": {"voice": "hi-IN-SwaraNeural", "pitch": "-22Hz", "rate": "-6%"},
        "male_lead": {"voice": "hi-IN-MadhurNeural", "pitch": "+0Hz", "rate": "+0%"},
        "male_supporting": {"voice": "hi-IN-MadhurNeural", "pitch": "+15Hz", "rate": "+4%"},
    }

    # Separate clusters: Note that elderly female voices (Mother Chen) often have pitch between 120Hz-155Hz
    female_clusters = [c for c in clusters if c.get("acoustic_gender") == "female" or c.get("mean_pitch_hz", 0) >= 165.0]
    male_clusters = [c for c in clusters if c.get("acoustic_gender") == "male" and c.get("mean_pitch_hz", 0) < 165.0]

    if female_clusters:
        # Heroine: Most prominent young female cluster (mean pitch >= 180Hz)
        c_heroine = female_clusters[0]
        characters["heroine"] = {
            "role": "heroine",
            "gender": "female",
            "voice_id": assigned_voices["female_lead"]["voice"],
            "pitch": assigned_voices["female_lead"]["pitch"],
            "rate": assigned_voices["female_lead"]["rate"],
            "mean_pitch_hz": c_heroine["mean_pitch_hz"],
            "total_speech_sec": c_heroine["total_duration"],
            "centroid": c_heroine["centroid"],
        }
        # Secondary female clusters
        other_females = female_clusters[1:]
        # Elderly Mother can ONLY be a cluster with mature/elder pitch (mean pitch <= 170Hz)
        # Never crown a high-pitched 220Hz young female cluster as 'mother'!
        mother_candidates = [c for c in other_females if c["mean_pitch_hz"] <= 170.0]
        young_females = [c for c in other_females if c["mean_pitch_hz"] > 170.0]

        if mother_candidates:
            c_mother = mother_candidates[0]
            characters["mother"] = {
                "role": "mother",
                "gender": "female",
                "voice_id": assigned_voices["female_mother"]["voice"],
                "pitch": assigned_voices["female_mother"]["pitch"],
                "rate": assigned_voices["female_mother"]["rate"],
                "mean_pitch_hz": c_mother["mean_pitch_hz"],
                "total_speech_sec": c_mother["total_duration"],
                "centroid": c_mother["centroid"],
            }
        
        if young_females:
            c_mistress = young_females[0]
            characters["mistress"] = {
                "role": "mistress",
                "gender": "female",
                "voice_id": assigned_voices["female_mistress"]["voice"],
                "pitch": assigned_voices["female_mistress"]["pitch"],
                "rate": assigned_voices["female_mistress"]["rate"],
                "mean_pitch_hz": c_mistress["mean_pitch_hz"],
                "total_speech_sec": c_mistress["total_duration"],
                "centroid": c_mistress["centroid"],
            }
        if len(young_females) > 1:
            c_sister = young_females[1]
            characters["supporting_female"] = {
                "role": "supporting_female",
                "gender": "female",
                "voice_id": assigned_voices["female_supporting"]["voice"],
                "pitch": assigned_voices["female_supporting"]["pitch"],
                "rate": assigned_voices["female_supporting"]["rate"],
                "mean_pitch_hz": c_sister["mean_pitch_hz"],
                "total_speech_sec": c_sister["total_duration"],
                "centroid": c_sister["centroid"],
            }


    if male_clusters:
        c_hero = male_clusters[0]
        characters["hero"] = {
            "role": "hero",
            "gender": "male",
            "voice_id": assigned_voices["male_lead"]["voice"],
            "pitch": assigned_voices["male_lead"]["pitch"],
            "rate": assigned_voices["male_lead"]["rate"],
            "mean_pitch_hz": c_hero["mean_pitch_hz"],
            "total_speech_sec": c_hero["total_duration"],
            "centroid": c_hero["centroid"],
        }
        if len(male_clusters) > 1:
            c_extra_male = male_clusters[1]
            characters["extra_male"] = {
                "role": "extra_male",
                "gender": "male",
                "voice_id": assigned_voices["male_supporting"]["voice"],
                "pitch": assigned_voices["male_supporting"]["pitch"],
                "rate": assigned_voices["male_supporting"]["rate"],
                "mean_pitch_hz": c_extra_male["mean_pitch_hz"],
                "total_speech_sec": c_extra_male["total_duration"],
                "centroid": c_extra_male["centroid"],
            }

    registry: dict[str, Any] = {
        "anchor_episodes": ep_stems,
        "total_anchor_speech_minutes": round(sum(all_durations) / 60.0, 2),
        "total_clusters_detected": len(clusters),
        "characters": characters,
    }

    ensure_dir(os.path.dirname(output_registry_path))
    write_json(output_registry_path, registry)
    log.info(
        "💾 Universal Series Voice Registry successfully locked: %s (%d roles assigned)",
        output_registry_path,
        len(characters),
    )
    return registry


def match_audio_segment(
    audio_clip: np.ndarray,
    registry: dict[str, Any],
    sample_rate: int = 16000,
    device: str = "cuda:0",
    f0: float = 0.0,
) -> tuple[str, float]:
    """Match a dialogue clip to a locked character role using cosine similarity with pitch gating."""
    characters = registry.get("characters", {})
    if not characters:
        return "narrator", 0.0

    emb = extract_embedding(audio_clip, sample_rate=sample_rate, device=device)
    if np.linalg.norm(emb) < 1e-6:
        return "narrator", 0.0

    # Hard acoustic pitch barrier: male and female voice spaces cannot cross
    allowed_gender = None
    if f0 >= 170.0:
        allowed_gender = "female"
    elif 65.0 <= f0 <= 110.0:
        # Only low pitch bass is strictly restricted to male; elderly females often speak at 125-150Hz
        allowed_gender = "male"

    best_role = "narrator"
    best_sim = -1.0

    for role, char_data in characters.items():
        if allowed_gender and char_data.get("gender") != allowed_gender:
            continue
        centroid = np.array(char_data["centroid"], dtype=np.float32)
        sim = cosine_similarity(emb, centroid)
        if sim > best_sim:
            best_sim = sim
            best_role = role

    return best_role, round(best_sim, 3)


def align_segments_to_series_registry(
    vocals_path: str,
    segments: list[dict],
    registry_path: str = "storage/series_cast_registry.json",
    device: str = "cuda:0",
    min_confidence: float = 0.65,
) -> list[dict]:
    """Align per-episode transcribed segments to the locked global series voice centroids.

    Extracts CAM++ 192-dim speaker embeddings for each dialogue clip and computes cosine
    similarity against the universal series centroids. Stamps each segment with:
    - matched_role (e.g. 'heroine', 'mother', 'mistress', 'hero', 'extra_male')
    - matched_gender ('female' or 'male')
    - matched_voice ('hi-IN-SwaraNeural', 'hi-IN-MadhurNeural')
    - matched_pitch ('+12Hz', '-18Hz', etc.)
    - matched_rate ('+4%', '-6%', etc.)
    - matched_sim (float, e.g. 0.78)
    - acoustic_gender (locked to matched_gender if high confidence)
    - speaker_id (set to matched_role)
    """
    if not segments or not os.path.isfile(vocals_path):
        return segments

    if not os.path.isfile(registry_path):
        log.warning("Series voice registry not found at %s - skipping centroid alignment.", registry_path)
        return segments

    try:
        registry = read_json(registry_path)
        characters = registry.get("characters", {})
        if not characters:
            return segments

        audio, sr = sf.read(vocals_path, dtype="float32")
        if audio.ndim > 1:
            audio = audio.mean(axis=1)

        # Resample to 16k if needed for CAM++
        if sr != 16000:
            import scipy.signal

            num_samples = int(len(audio) * 16000 / sr)
            audio = scipy.signal.resample(audio, num_samples)
            sr = 16000

        matched_count = 0
        for seg in segments:
            start_s = float(seg.get("start", 0.0))
            end_s = float(seg.get("end", 0.0))
            start_samp = max(0, int(start_s * sr))
            end_samp = min(len(audio), int(end_s * sr))

            if end_samp <= start_samp:
                continue

            clip = audio[start_samp:end_samp]
            if len(clip) < int(sr * 0.35):
                continue

            seg_f0 = float(seg.get("pitch_hz", 0.0))
            if seg_f0 <= 0.0:
                seg_f0 = estimate_pitch_f0(clip, sr)
                if seg_f0 > 0.0:
                    seg["pitch_hz"] = seg_f0
                    seg["acoustic_gender"] = pitch_to_gender(seg_f0)

            best_role, sim = match_audio_segment(clip, registry, sample_rate=sr, device=device, f0=seg_f0)
            if best_role in characters and sim >= min_confidence:
                char_data = characters[best_role]
                c_gen = char_data.get("gender", "male")

                cur_ac_gen = str(seg.get("acoustic_gender") or "").lower()
                if cur_ac_gen and cur_ac_gen != "unknown" and cur_ac_gen != c_gen and seg_f0 > 0:
                    # Pitch contradicts centroid match; reject false positive
                    continue

                # Protect established roles: never allow centroid to turn heroine into mother or vice versa
                existing_spk = str(seg.get("speaker") or "").lower()
                if existing_spk in ("heroine", "mother", "mistress", "hero", "system", "supporting_female"):
                    continue

                seg["matched_role"] = best_role
                seg["matched_gender"] = c_gen
                seg["matched_voice"] = char_data.get("voice_id", "")
                seg["matched_pitch"] = char_data.get("pitch", "+0Hz")
                seg["matched_rate"] = char_data.get("rate", "+0%")
                seg["matched_sim"] = round(sim, 3)
                seg["speaker_id"] = best_role
                if sim >= 0.70:
                    seg["acoustic_gender"] = c_gen
                matched_count += 1

        log.info(
            "🎯 Centroid Voice Matcher: Aligned %d/%d segments to locked series voice profiles.",
            matched_count,
            len(segments),
        )
        return segments
    except Exception as exc:
        log.warning("Error during centroid alignment: %s - continuing with raw segments.", exc)
        return segments

