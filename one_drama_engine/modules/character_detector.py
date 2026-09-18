"""Character Discovery & Reference Lineup Generator.

Scans drama episodes, discovers the main recurring cast (Hero, Heroine, Villain,
Elders, Supporting), crops their portraits, and composites a labeled
'Character Lineup Reference Sheet' (character_lineup.jpg) used by Gemini Vision
to accurately identify who is speaking at each dialogue timestamp.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
from typing import Any, Sequence

from PIL import Image, ImageDraw, ImageFont

from . import (
    PipelineError,
    ensure_dir,
    log,
    require_binary,
    run_command,
    write_json,
    read_json,
)

_CASTING_SYSTEM_INSTRUCTION = """\
You are an expert anime, manhua, and short-drama casting director.
Analyze these sample keyframes from the drama series and discover the main recurring characters.

Identify up to 6 key characters:
1. HERO / Male Protagonist (lead young male)
2. HEROINE / Female Lead (lead young female)
3. VILLAIN / Antagonist (rival, evil master, or arrogant opponent)
4. FATHER / ELDER MALE (patriarch, master, or elder)
5. MOTHER / ELDER FEMALE (matriarch, elder woman)
6. SUPPORTING / COMPANION (loyal friend, sister, subordinate)

For each character identified:
- frame_index: 0-based index of the keyframe where their face/upper body is clearest
- box_ymin, box_xmin, box_ymax, box_xmax: Bounding box around their head & shoulders / face (0-1000 scale)
- role: "hero" | "heroine" | "villain" | "father" | "mother" | "supporting_male" | "supporting_female"
- name: Romanized or Chinese name (e.g. "Lin Feng", "Su Wan", "Elder Zhao")
- hindi_name: Transliterated name in Hindi Devanagari script (e.g. "लिन फेंग", "सु वान")
- gender: "male" | "female"
- visual_summary: Short visual cue (e.g. "young man in black martial robe with sword", "woman in white dress with hairpin")

OUTPUT FORMAT:
Return ONLY valid JSON matching this schema:
{
  "characters": [
    {
      "id": "C1",
      "role": "hero",
      "name": "Lin Feng",
      "hindi_name": "लिन फेंग",
      "gender": "male",
      "frame_index": 0,
      "box_ymin": 150,
      "box_xmin": 320,
      "box_ymax": 480,
      "box_xmax": 680,
      "visual_summary": "Young male lead, dark hair, blue tunic"
    }
  ]
}
No prose outside JSON.
"""


def extract_candidate_frames(
    video_path: str,
    timestamps: Sequence[float] = (4.0, 15.0, 30.0, 50.0, 75.0, 105.0, 140.0, 180.0),
    output_dir: str | None = None,
) -> list[str]:
    """Extract candidate keyframes across the video using FFmpeg."""
    ffmpeg = require_binary("ffmpeg")
    if not os.path.isfile(video_path):
        raise PipelineError(f"Video not found: {video_path}")

    out_dir = output_dir or tempfile.mkdtemp(prefix="od_cast_frames_")
    ensure_dir(out_dir)

    frame_paths: list[str] = []
    for idx, ts in enumerate(timestamps):
        out_file = os.path.join(out_dir, f"cast_frame_{idx:02d}.jpg")
        cmd = [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-ss",
            f"{ts:.2f}",
            "-i",
            video_path,
            "-frames:v",
            "1",
            "-q:v",
            "2",
            out_file,
        ]
        try:
            run_command(cmd, desc=f"extract_frame({ts}s)")
            if os.path.isfile(out_file) and os.path.getsize(out_file) > 1024:
                frame_paths.append(out_file)
        except Exception as exc:
            log.debug("Could not extract frame at %.1fs: %s", ts, exc)

    return frame_paths


def _extract_json(text: str) -> dict:
    cleaned = text.strip()
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL)
    if match:
        cleaned = match.group(1)
    else:
        m2 = re.search(r"(\{.*\})", cleaned, re.DOTALL)
        if m2:
            cleaned = m2.group(1)
    return json.loads(cleaned)


def _render_lineup_sheet(
    characters: list[dict],
    frame_paths: list[str],
    output_image_path: str,
    tile_size: int = 280,
) -> str:
    """Compose a high-resolution grid contact sheet with labeled portraits."""
    ensure_dir(os.path.dirname(output_image_path))
    count = max(1, len(characters))
    cols = min(4, count)
    rows = (count + cols - 1) // cols

    padding = 16
    header_h = 70
    card_w = tile_size
    card_h = tile_size + 65  # room for header banner and footer name tag
    canvas_w = cols * card_w + (cols + 1) * padding
    canvas_h = header_h + rows * card_h + (rows + 1) * padding

    canvas = Image.new("RGB", (canvas_w, canvas_h), color=(18, 18, 24))
    draw = ImageDraw.Draw(canvas)

    # Title Banner
    draw.rectangle([0, 0, canvas_w, header_h], fill=(28, 28, 38))
    draw.text(
        (padding + 8, 16),
        "ONE DRAMA: CHARACTER CAST REFERENCE SHEET",
        fill=(255, 255, 255),
    )
    draw.text(
        (padding + 8, 42),
        "Used for AI Speaker Identification & Multi-Voice Dubbing Alignment",
        fill=(160, 160, 185),
    )

    role_colors = {
        "hero": (59, 130, 246),       # Blue
        "heroine": (236, 72, 153),     # Pink
        "villain": (239, 68, 68),      # Red
        "father": (245, 158, 11),      # Amber
        "mother": (168, 85, 247),      # Purple
        "supporting_male": (16, 185, 129),  # Emerald
        "supporting_female": (20, 184, 166), # Teal
    }

    for idx, char in enumerate(characters):
        col = idx % cols
        row = idx // cols
        x0 = padding + col * (card_w + padding)
        y0 = header_h + padding + row * (card_h + padding)

        f_idx = char.get("frame_index", 0)
        crop_img = None
        if 0 <= f_idx < len(frame_paths) and os.path.isfile(frame_paths[f_idx]):
            try:
                src_img = Image.open(frame_paths[f_idx])
                sw, sh = src_img.size
                ymin = max(0, min(1000, int(char.get("box_ymin", 100))))
                xmin = max(0, min(1000, int(char.get("box_xmin", 100))))
                ymax = max(ymin + 50, min(1000, int(char.get("box_ymax", 600))))
                xmax = max(xmin + 50, min(1000, int(char.get("box_xmax", 600))))

                px_ymin = int(sh * (ymin / 1000.0))
                px_xmin = int(sw * (xmin / 1000.0))
                px_ymax = int(sh * (ymax / 1000.0))
                px_xmax = int(sw * (xmax / 1000.0))

                crop_w = max(20, px_xmax - px_xmin)
                crop_h = max(20, px_ymax - px_ymin)
                # Expand slightly to square
                max_dim = max(crop_w, crop_h)
                cx = (px_xmin + px_xmax) // 2
                cy = (px_ymin + px_ymax) // 2
                sq_xmin = max(0, cx - max_dim // 2)
                sq_ymin = max(0, cy - max_dim // 2)
                sq_xmax = min(sw, sq_xmin + max_dim)
                sq_ymax = min(sh, sq_ymin + max_dim)

                crop_img = src_img.crop((sq_xmin, sq_ymin, sq_xmax, sq_ymax))
                crop_img = crop_img.resize((card_w, tile_size), Image.Resampling.LANCZOS)
            except Exception as crop_err:
                log.debug("Portrait crop error for character %s: %s", char.get("id"), crop_err)

        if crop_img is None:
            crop_img = Image.new("RGB", (card_w, tile_size), color=(40, 42, 54))

        # Paste portrait
        canvas.paste(crop_img, (x0, y0 + 26))

        # Top ID Tag banner
        cid = char.get("id", f"C{idx+1}")
        role = str(char.get("role", "character")).lower()
        tag_color = role_colors.get(role, (99, 102, 241))
        draw.rectangle([x0, y0, x0 + card_w, y0 + 26], fill=tag_color)
        draw.text(
            (x0 + 8, y0 + 5),
            f"[{cid}] {role.upper()} ({char.get('gender', 'm/f')[:1].upper()})",
            fill=(255, 255, 255),
        )

        # Bottom Name Tag banner
        draw.rectangle([x0, y0 + 26 + tile_size, x0 + card_w, y0 + card_h], fill=(26, 26, 34))
        name = char.get("name", "Unknown")
        hname = char.get("hindi_name", "")
        display = f"{name} ({hname})" if hname else name
        draw.text(
            (x0 + 8, y0 + 30 + tile_size),
            display[:30],
            fill=(230, 230, 240),
        )
        draw.text(
            (x0 + 8, y0 + 47 + tile_size),
            char.get("visual_summary", "")[:36],
            fill=(140, 140, 160),
        )

        # Border
        draw.rectangle([x0, y0, x0 + card_w, y0 + card_h], outline=tag_color, width=2)

    canvas.save(output_image_path, "JPEG", quality=92)
    log.info("Saved character cast lineup sheet: %s (%dx%d)", output_image_path, canvas_w, canvas_h)
    return output_image_path


def ensure_character_lineup(
    video_paths: list[str] | str,
    config: dict | None = None,
    output_dir: str = "storage/characters",
    force: bool = False,
) -> dict:
    """Ensure character lineup sheet and metadata exist for the drama.

    If already created, returns the cached metadata. Otherwise analyzes the video
    keyframes using Gemini Vision, crops the faces, and generates character_lineup.jpg.
    """
    output_dir = os.path.abspath(output_dir)
    ensure_dir(output_dir)
    json_path = os.path.join(output_dir, "character_lineup.json")
    sheet_path = os.path.join(output_dir, "character_lineup.jpg")

    if isinstance(video_paths, str):
        v_list = [video_paths]
    else:
        v_list = [v for v in video_paths if os.path.isfile(v)]

    if not v_list:
        log.warning("No valid video files provided for character detection; using default roles.")
        return _default_lineup(output_dir)

    lead_video = v_list[0]
    lead_stem = os.path.splitext(os.path.basename(lead_video))[0]

    # Resolve true series title from series_info.json if available
    series_title = None
    raw_dir = os.path.dirname(os.path.abspath(lead_video))
    series_info_path = os.path.join(raw_dir, "series_info.json")
    if os.path.isfile(series_info_path):
        try:
            s_info = read_json(series_info_path)
            if isinstance(s_info, dict) and s_info.get("title"):
                series_title = s_info["title"]
        except Exception:
            pass

    current_title = series_title or ("series_master" if lead_stem.startswith("ep_") else lead_stem)

    if not force and os.path.isfile(json_path) and os.path.isfile(sheet_path):
        cached = read_json(json_path)
        if isinstance(cached, dict) and cached.get("characters") and len(cached["characters"]) > 0:
            cached_title = cached.get("drama_title")
            # Reuse cached lineup for the entire series
            if cached_title == current_title or (lead_stem.startswith("ep_") and (cached_title == "series_master" or str(cached_title).startswith("ep_"))):
                log.info("Character cast lineup already cached (%d characters). Reusing across series.", len(cached["characters"]))
                return cached
            else:
                log.info("Cached lineup drama_title ('%s') != current video ('%s'). Re-detecting characters.", cached_title, current_title)

    log.info("Inspecting video cast from: %s", os.path.basename(lead_video))

    frame_paths = extract_candidate_frames(lead_video, output_dir=os.path.join(output_dir, "samples"))
    if not frame_paths:
        log.warning("Could not extract candidate frames; returning default lineup.")
        return _default_lineup(output_dir)

    cfg = config or {}
    api_key = str(cfg.get("gemini_api_key", "")).strip()
    if not api_key or api_key == "YOUR_GEMINI_API_KEY":
        log.info("No Gemini API key available; returning standard default cast lineup.")
        return _default_lineup(output_dir, frame_paths)

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key, http_options={"timeout": 45000})
        model_name = cfg.get("gemini_model", "gemini-flash-lite-latest")
        candidate_models = [model_name, "gemini-flash-lite-latest", "gemini-2.5-flash", "gemini-3.1-flash-lite-preview"]
        candidate_models = list(dict.fromkeys(candidate_models))

        contents: list[Any] = [
            "Analyze these sample keyframes from the drama series. Identify the main recurring characters."
        ]
        for p in frame_paths:
            with open(p, "rb") as f:
                contents.append(types.Part.from_bytes(data=f.read(), mime_type="image/jpeg"))

        gen_config = types.GenerateContentConfig(
            response_mime_type="application/json",
            system_instruction=_CASTING_SYSTEM_INSTRUCTION,
            temperature=0.15,
        )

        response = None
        for cand in candidate_models:
            try:
                log.info("Scanning drama cast across %d frame(s) with %s...", len(frame_paths), cand)
                response = client.models.generate_content(
                    model=cand,
                    contents=contents,
                    config=gen_config,
                )
                if response and getattr(response, "text", ""):
                    break
            except Exception as m_err:
                log.warning("Casting probe on %s failed (%s); trying next model...", cand, m_err)

        if not response or not getattr(response, "text", ""):
            raise PipelineError("Failed to extract cast from Gemini Vision.")

        parsed = _extract_json(response.text)
        characters = parsed.get("characters", [])
        if not characters:
            raise PipelineError("Gemini returned empty character list.")

        # Ensure unique IDs and role consistency
        seen_roles = set()
        for i, c in enumerate(characters):
            c["id"] = f"C{i+1}"
            role = c.get("role", "supporting_male").lower()
            if role in seen_roles and role in ("hero", "heroine"):
                c["role"] = f"supporting_{c.get('gender', 'male')}"
            seen_roles.add(c["role"])

        _render_lineup_sheet(characters, frame_paths, sheet_path)

        meta = {
            "drama_title": current_title,
            "sheet_image": sheet_path,
            "characters": characters,
            "total_characters": len(characters),
        }
        write_json(json_path, meta)
        log.info("Character discovery successful: discovered %d key character(s).", len(characters))
        return meta

    except Exception as exc:
        log.warning("Automated cast discovery encountered issue (%s); falling back to standard lineup.", exc)
        return _default_lineup(output_dir, frame_paths)


def _default_lineup(output_dir: str, frame_paths: list[str] | None = None) -> dict:
    """Generate a clean default cast lineup so production never halts."""
    sheet_path = os.path.join(output_dir, "character_lineup.jpg")
    json_path = os.path.join(output_dir, "character_lineup.json")

    characters = [
        {
            "id": "C1",
            "role": "hero",
            "name": "Protagonist",
            "hindi_name": "नायक",
            "gender": "male",
            "frame_index": 0,
            "box_ymin": 150,
            "box_xmin": 250,
            "box_ymax": 650,
            "box_xmax": 750,
            "visual_summary": "Lead young male hero",
        },
        {
            "id": "C2",
            "role": "heroine",
            "name": "Female Lead",
            "hindi_name": "নায়িকা",
            "gender": "female",
            "frame_index": min(1, len(frame_paths) - 1) if frame_paths else 0,
            "box_ymin": 150,
            "box_xmin": 250,
            "box_ymax": 650,
            "box_xmax": 750,
            "visual_summary": "Lead young female heroine",
        },
        {
            "id": "C3",
            "role": "villain",
            "name": "Antagonist",
            "hindi_name": "ভিলেন",
            "gender": "male",
            "frame_index": min(2, len(frame_paths) - 1) if frame_paths else 0,
            "box_ymin": 150,
            "box_xmin": 250,
            "box_ymax": 650,
            "box_xmax": 750,
            "visual_summary": "Main opponent / rival",
        },
        {
            "id": "C4",
            "role": "father",
            "name": "Father / Patriarch",
            "hindi_name": "পিতা",
            "gender": "male",
            "frame_index": min(3, len(frame_paths) - 1) if frame_paths else 0,
            "box_ymin": 150,
            "box_xmin": 250,
            "box_ymax": 650,
            "box_xmax": 750,
            "visual_summary": "Elder father / master",
        },
        {
            "id": "C5",
            "role": "mother",
            "name": "Mother / Matriarch",
            "hindi_name": "মাতা",
            "gender": "female",
            "frame_index": min(4, len(frame_paths) - 1) if frame_paths else 0,
            "box_ymin": 150,
            "box_xmin": 250,
            "box_ymax": 650,
            "box_xmax": 750,
            "visual_summary": "Elder mother / matriarch",
        },
    ]

    _render_lineup_sheet(characters, frame_paths or [], sheet_path)
    meta = {
        "drama_title": "Default Drama Cast",
        "sheet_image": sheet_path,
        "characters": characters,
        "total_characters": len(characters),
    }
    write_json(json_path, meta)
    return meta
