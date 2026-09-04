"""YouTube SEO, Chaptering, and AI Thumbnail Master Prompt Generator.

Analyzes the full dramatic narrative generated across all episodes and produces
a complete, broadcast-ready YouTube Publishing Package:
  1. 5 High-CTR Viral Clickbait Titles
  2. Complete SEO Description with Fair Use legal notice
  3. Video Chapters & Timestamps (auto-calculated from episode durations)
  4. Viral Tags & Hashtags
  5. Character Visual Dossier & Engineered Master Prompts for Midjourney v6 / Flux.1
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Sequence

from . import PipelineError, human_time, log, write_json

DEFAULT_MODEL = "gemini-flash-latest"

SYSTEM_INSTRUCTION = """You are a world-class YouTube Anime & Manhua Recap Producer and Thumbnail Art Director.
You specialize in viral YouTube packaging for 2-3 hour full-length manhwa/manhua recap movies.
Your job is to read the dramatic recap script across episodes and generate an elite YouTube publishing package:
1. 5 High-CTR Viral Titles: Emotion-driven, high curiosity, power fantasy hooks (e.g. "He Was Kicked Out of His Clan, But Reincarnated as a God-Tier Master!").
2. YouTube Description: Hook summary, Fair Use disclaimer, and key character highlights.
3. Main Character Visual Dossier: Detailed appearance, distinctive traits, aura, outfit, and signature weapon.
4. Master Thumbnail Image Generation Prompt: Engineered specifically for Midjourney v6, Flux.1, and Stable Diffusion XL.
   Must specify: cinematic anime manhua style, dynamic action perspective, hyper-vivid lighting, glowing eyes/aura, high-contrast palette, 16:9 aspect ratio, and suggested viral text badge overlay.

Output strictly valid JSON with the requested schema.
"""


def _make_client(api_keys: Sequence[str] | None, primary_key: str | None = None):
    try:
        from google import genai
    except ImportError as exc:
        raise PipelineError("google-genai is not installed.") from exc

    candidates = [k for k in (list(api_keys or []) + [primary_key]) if k and k != "YOUR_GEMINI_API_KEY"]
    if not candidates:
        raise PipelineError("No valid Gemini API key configured.")

    for key in candidates:
        try:
            return genai.Client(api_key=key.strip())
        except Exception:
            continue
    raise PipelineError("Failed to initialize any Gemini client.")


def generate_youtube_package(
    episodes_data: list[dict[str, Any]],
    config: dict[str, Any],
    master_duration_seconds: float = 0.0,
    output_dir: str | None = None,
) -> dict[str, Any]:
    """Generate viral titles, SEO description, chapter timestamps, and AI thumbnail prompts."""
    if not episodes_data:
        log.warning("generate_youtube_package: No episode data provided.")
        return {}

    # Build storyline summary and calculate chapter timestamps
    story_corpus = []
    chapters = []
    accumulated_time = 0.0

    for idx, ep in enumerate(episodes_data, start=1):
        ep_name = ep.get("episode") or f"Episode {idx}"
        duration = float(ep.get("duration", 0.0))
        context_text = ep.get("context") or ep.get("summary") or ""

        chapters.append(
            {
                "time_str": human_time(accumulated_time),
                "seconds": accumulated_time,
                "title": f"Episode {idx}: Chapter {idx}",
            }
        )
        accumulated_time += duration

        if context_text:
            story_corpus.append(f"[Episode {idx}]: {context_text[:400]}")

    full_story = "\n".join(story_corpus) if story_corpus else "A high-stakes manhua adventure of betrayal, power leveling, and martial arts triumph."

    client = _make_client(
        config.get("gemini_api_keys"), config.get("gemini_api_key")
    )
    model_name = config.get("gemini_model", DEFAULT_MODEL)

    prompt = f"""Analyze this manhua story and generate a viral YouTube package:

STORY SUMMARY:
{full_story[:4000]}

TOTAL RUNTIME: {human_time(master_duration_seconds or accumulated_time)}

Return JSON adhering strictly to this schema:
{{
  "viral_titles": [
    "Title 1 (High CTR clickbait)",
    "Title 2",
    "Title 3",
    "Title 4",
    "Title 5"
  ],
  "synopsis": "Engaging 3-4 sentence hook summary of the full movie",
  "tags": ["manhua recap", "hindi recap", "anime explained", "full movie"],
  "hashtags": ["#manhuarecap", "#hindirecap", "#donghua"],
  "main_character": {{
    "name": "Protagonist name",
    "role": "Title / Identity",
    "appearance": "Visual description (hair, eyes, age, expression)",
    "outfit": "Armor or robe styling",
    "powers_and_weapon": "Signature weapon, glowing aura, elemental power"
  }},
  "thumbnail_master_prompt": "Cinematic anime manhua style masterpiece, dynamic extreme angle, [Character details], glowing aura, high contrast dramatic lighting, 8k resolution, photorealistic shading, vibrant colors, cinematic composition --ar 16:9 --v 6.0",
  "thumbnail_text_hook": "2-3 word bold text overlay recommendation for thumbnail (e.g. 'BETRAYED GOD', 'MAX LEVEL')"
}}
"""

    log.info("Generating YouTube SEO metadata & AI Thumbnail Master Prompt via Gemini...")
    try:
        from google.genai import types

        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                response_mime_type="application/json",
                temperature=0.7,
            ),
        )
        package = json.loads(response.text)
    except Exception as exc:
        log.warning("Gemini failed to generate SEO package (%s); using fallback.", exc)
        package = {
            "viral_titles": [
                "[Hindi] Betrayed By His Clan, But Reincarnated With A God-Tier System! | Full Manhua Recap",
                "He Was Called Trash, Until He Unlocked The Ancient Dragon Emperor Powers!",
                "100 Hours In Another World: From Weakling To The Undefeated Celestial Overlord!",
            ],
            "synopsis": "In a cruel world where strength dictates fate, an outcast awakens a legendary power and embarks on a relentless path of revenge and dominance.",
            "tags": ["manhua recap", "hindi dubbed", "anime explained in hindi", "full manhwa movie"],
            "hashtags": ["#manhuarecap", "#hindidubbed", "#donghua"],
            "main_character": {
                "name": "The Protagonist",
                "appearance": "Jet black spiky hair, fierce glowing golden eyes, confident ruthless expression",
                "outfit": "Dark martial arts battle robes with dragon gold embroidery",
                "powers_and_weapon": "Wielding a giant ancient flaming greatsword with swirling celestial aura",
            },
            "thumbnail_master_prompt": "Cinematic anime manhua style, dynamic low-angle camera, handsome male cultivator with glowing golden eyes holding a celestial flaming sword, epic battle background with stormy skies and lightning, hyper-detailed, vibrant lighting, masterpiece --ar 16:9 --v 6.0",
            "thumbnail_text_hook": "MAX LEVEL GOD!",
        }

    package["chapters"] = chapters

    # Save outputs if output_dir given
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        json_path = os.path.join(output_dir, "youtube_package.json")
        write_json(json_path, package)

        md_path = os.path.join(output_dir, "YOUTUBE_PUBLISH_GUIDE.md")
        _render_publish_guide(package, md_path)
        log.info("Saved YouTube Package: %s & %s", json_path, md_path)

    return package


def _render_publish_guide(pkg: dict[str, Any], output_path: str) -> None:
    """Render a markdown guide ready for copy-pasting into YouTube Studio."""
    titles = "\n".join(f"- **Option {i}**: {t}" for i, t in enumerate(pkg.get("viral_titles", []), 1))
    tags = ", ".join(pkg.get("tags", []))
    hashtags = " ".join(pkg.get("hashtags", []))
    chapters = "\n".join(f"{c['time_str']} - {c['title']}" for c in pkg.get("chapters", []))

    mc = pkg.get("main_character", {})
    prompt = pkg.get("thumbnail_master_prompt", "")
    badge = pkg.get("thumbnail_text_hook", "")

    content = f"""# 🎬 YouTube Publishing Guide (Copy-Paste Ready)

## 📌 Recommended Viral Titles
{titles}

---

## 📝 YouTube Description
{pkg.get('synopsis', '')}

### ⏱️ Video Chapters & Timestamps
{chapters}

---
### ⚖️ Fair Use Disclaimer
Copyright Disclaimer Under Section 107 of the Copyright Act 1976, allowance is made for "fair use" for purposes such as criticism, comment, news reporting, teaching, scholarship, and research. Fair use is a use permitted by copyright statute that might otherwise be infringing. This video is a transformative recap with original commentary and voiceover.

### 🏷️ Hashtags
{hashtags}

---

## 🏷️ YouTube Tags (Paste into Studio Tags box)
```text
{tags}
```

---

## 🎨 AI Thumbnail Generation Master Guide (Midjourney / Flux / SDXL)

### 👤 Main Character Visual Profile:
- **Name/Title:** {mc.get('name', 'Protagonist')} ({mc.get('role', 'Cultivator')})
- **Appearance:** {mc.get('appearance', '')}
- **Attire:** {mc.get('outfit', '')}
- **Powers/Weapon:** {mc.get('powers_and_weapon', '')}

### 🖼️ Master Prompt (Copy-Paste into Midjourney v6 or Flux.1):
```text
{prompt}
```

### 🔤 Suggested Thumbnail Text Badge:
> **"{badge}"** *(Place in bold, high-contrast yellow/red font with black stroke on the top-left corner)*
"""
    with open(output_path, "w", encoding="utf-8") as handle:
        handle.write(content)
