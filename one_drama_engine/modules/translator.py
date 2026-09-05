"""Localization / recap-writing stage.

Sends batches of Chinese dialogue segments to Gemini through the official
``google-genai`` SDK and gets back a dramatic **third-person recap narration** in
the target language rather than a literal dub. That framing is deliberate: a
transformative recap with original commentary is what keeps the channel on the
right side of Fair Use, and it also reads far better as a voiceover.

Output segments keep the original ``id``/``start``/``end``/``duration`` so the TTS
and render stages can slot the audio back onto the source timeline exactly.
"""

from __future__ import annotations

import json
import os
import re
import time
from typing import Any, Iterable

from . import (
    PipelineError,
    chunked,
    log,
    write_json,
)

DEFAULT_MODEL = "gemini-2.5-flash"
DEFAULT_BATCH_SIZE = 20
DEFAULT_MAX_RETRIES = 4

LANGUAGE_NAMES: dict[str, str] = {
    "hi": "Hindi (Devanagari script)",
    "bn": "Bengali",
    "en": "English",
    "ur": "Urdu",
    "ta": "Tamil",
    "te": "Telugu",
    "mr": "Marathi",
    "id": "Indonesian",
    "es": "Spanish",
    "pt": "Portuguese",
    "ar": "Arabic",
    "vi": "Vietnamese",
    "th": "Thai",
    "tr": "Turkish",
    "ru": "Russian",
    "ja": "Japanese",
    "ko": "Korean",
}

# ~2.6 Hindi words/second is a comfortable narration pace for Edge-TTS.
WORDS_PER_SECOND = 2.6
MIN_WORDS = 3

_SYSTEM_INSTRUCTION = """\
You are a top-tier viral YouTube anime/manhwa/manhua RECAP NARRATOR and scriptwriter.
Your channel is famous for turning Chinese dynamic-manhua episodes into gripping,
binge-worthy recap videos that retain viewers for the full runtime.

YOUR JOB
Given raw machine-transcribed Chinese dialogue segments (each with an id, a start
time and a duration in seconds), rewrite them as a continuous, DRAMATIC,
THIRD-PERSON STORY RECAP with narrator commentary in {language_name}.

THIS IS A RECAP, NOT A DUB. That distinction is mandatory:
- NEVER write first-person dialogue lines or a literal translation of the speech.
- ALWAYS narrate what is happening in third person: describe the action, name the
  emotion, explain the stakes, and add your own commentary and reactions.
- Weave any essential quoted line into narration instead of reproducing it, e.g.
  "he warned the elder that this fight was already decided".
- Add transformative value: foreshadowing, cliffhanger teases, power-scaling notes,
  and short hype interjections that make the recap your own creative work.

STYLE
- Energetic, cinematic, punchy. Short sentences. Present tense.
- Sound like a human narrator speaking out loud, never like written prose.
- Keep character names transliterated consistently across every segment.
- Plain spoken text ONLY: no emoji, no markdown, no asterisks, no stage directions,
  no bracketed notes, no numbers written as digits when a word reads better aloud.
- If a segment's source text is noise, filler, or untranslatable, replace it with a
  short atmospheric narration beat that fits the story flow. Never leave it empty.

TIMING (critical - this text is fed to text-to-speech and must fit the shot)
- Each segment has a "duration" in seconds and a "target_words" hint.
- Write approximately target_words words for that segment: never fewer than half,
  never more than 1.3x. Trim adjectives before you overrun.

OUTPUT
Return ONLY a JSON object of this exact shape, with one entry per input segment,
same ids, in the same order:
{{"segments": [{{"id": <int>, "recap_text": "<narration in {language_name}>"}}]}}
No prose outside the JSON. No code fences.
"""

_USER_TEMPLATE = """\
Target language: {language_name}
Batch {batch_index} of {batch_total} (segment ids {first_id}-{last_id}).

{context_block}Rewrite each of the following segments as {language_name} recap narration.
Return JSON only.

INPUT SEGMENTS:
{payload}
"""


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _language_name(code: str) -> str:
    return LANGUAGE_NAMES.get((code or "").lower(), code or "Hindi (Devanagari script)")


def _target_words(duration: float) -> int:
    return max(MIN_WORDS, int(round(max(0.0, float(duration)) * WORDS_PER_SECOND)))


def _make_client(api_key: str):
    """Instantiate a ``google.genai`` client, validating the key first."""
    if not api_key or api_key.strip() in {"", "YOUR_GEMINI_API_KEY"}:
        raise PipelineError(
            "No Gemini API key configured. Set 'gemini_api_key' in config/settings.json "
            "or export GEMINI_API_KEY. Get a key at https://aistudio.google.com/apikey"
        )
    try:
        from google import genai
    except ImportError as exc:  # pragma: no cover - dependency guard
        raise PipelineError(
            "google-genai is not installed. Install it with: pip install google-genai"
        ) from exc

    try:
        return genai.Client(api_key=api_key.strip())
    except Exception as exc:
        raise PipelineError(f"Could not initialise the Gemini client: {exc}") from exc


def _make_clients(api_key: str = "", api_keys: Any = None) -> list:
    """Instantiate one or more Gemini clients for key pool rotation."""
    keys: list[str] = []
    if isinstance(api_keys, (list, tuple)):
        for k in api_keys:
            if isinstance(k, str) and k.strip() and k.strip() not in keys:
                keys.append(k.strip())
    if api_key and isinstance(api_key, str) and api_key.strip():
        cleaned = api_key.strip()
        if cleaned not in keys and cleaned != "YOUR_GEMINI_API_KEY":
            keys.insert(0, cleaned)

    valid_keys = [k for k in keys if k != "YOUR_GEMINI_API_KEY"]
    if not valid_keys:
        raise PipelineError(
            "No Gemini API key configured. Set 'gemini_api_key' or 'gemini_api_keys' in config/settings.json "
            "or export GEMINI_API_KEY."
        )

    clients = []
    for k in valid_keys:
        try:
            clients.append(_make_client(k))
        except Exception as exc:
            log.warning("Could not initialise Gemini client for key %s...: %s", k[:10], exc)

    if not clients:
        raise PipelineError("None of the configured Gemini API keys could be initialised.")
    return clients


def _build_config(system_instruction: str, temperature: float, max_tokens: int):
    """Build a JSON-mode generation config, tolerating SDK version differences."""
    try:
        from google.genai import types
    except ImportError:  # pragma: no cover - very old SDK
        return {
            "response_mime_type": "application/json",
            "system_instruction": system_instruction,
            "temperature": temperature,
        }

    kwargs: dict[str, Any] = {
        "response_mime_type": "application/json",
        "system_instruction": system_instruction,
        "temperature": temperature,
        "max_output_tokens": max_tokens,
    }
    try:
        return types.GenerateContentConfig(**kwargs)
    except TypeError:
        kwargs.pop("max_output_tokens", None)
        try:
            return types.GenerateContentConfig(**kwargs)
        except TypeError:
            return {"response_mime_type": "application/json", "temperature": temperature}


def _call_gemini(client, model: str, prompt: str, config) -> str:
    """Call ``generate_content`` and return the raw response text."""
    try:
        response = client.models.generate_content(model=model, contents=prompt, config=config)
    except TypeError:
        # Some SDK builds name the parameter generation_config.
        response = client.models.generate_content(
            model=model, contents=prompt, generation_config=config
        )

    text = getattr(response, "text", None)
    if text:
        return text

    # Fall back to walking the candidate parts.
    chunks: list[str] = []
    for candidate in getattr(response, "candidates", None) or []:
        content = getattr(candidate, "content", None)
        for part in getattr(content, "parts", None) or []:
            part_text = getattr(part, "text", None)
            if part_text:
                chunks.append(part_text)
    if chunks:
        return "".join(chunks)

    feedback = getattr(response, "prompt_feedback", None)
    raise PipelineError(
        "Gemini returned an empty response"
        + (f" (prompt_feedback={feedback})" if feedback else "")
        + ". The content may have been blocked by a safety filter."
    )


def _extract_json(raw: str) -> Any:
    """Parse a JSON payload out of a model response, stripping fences if present."""
    if not raw or not raw.strip():
        raise PipelineError("Gemini returned no text to parse.")

    text = raw.strip()
    fenced = re.search(r"```(?:json)?\s*(.+?)\s*```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    for opener, closer in (("{", "}"), ("[", "]")):
        start = text.find(opener)
        end = text.rfind(closer)
        if start != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                continue

    # Attempt to close truncated JSON array/object if cut off mid-response
    for suffix in ["]}", "}]", "\"\n}]", "\"\n}", "}", "]"]:
        try:
            return json.loads(text + suffix)
        except json.JSONDecodeError:
            pass

    raise PipelineError(f"Could not parse JSON from the Gemini response: {raw[:300]}")


def _coerce_entries(parsed: Any) -> list[dict]:
    """Normalise the many shapes a model may return into a list of dicts."""
    if isinstance(parsed, dict):
        for key in ("segments", "results", "data", "items", "output"):
            value = parsed.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        if "id" in parsed:  # a single segment object
            return [parsed]
        raise PipelineError(f"Unexpected JSON object keys from Gemini: {list(parsed)[:8]}")
    if isinstance(parsed, list):
        return [item for item in parsed if isinstance(item, dict)]
    raise PipelineError(f"Unexpected JSON type from Gemini: {type(parsed).__name__}")


_CLEAN_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"```[a-zA-Z]*"), " "),
    (re.compile(r"[*_#`>]+"), " "),
    (re.compile(r"\[(?:[^\]]*)\]"), " "),
    (re.compile(r"\((?:narrator|voice ?over|sfx|bgm)[^)]*\)", re.IGNORECASE), " "),
    (re.compile(r"^\s*(?:narrator|वर्णनकर्ता|नैरेटर)\s*[:：-]\s*", re.IGNORECASE), ""),
    (re.compile(r"[\U0001F300-\U0001FAFF\U00002600-\U000027BF]"), " "),
    (re.compile(r"\s{2,}"), " "),
)


def _clean_text(text: Any) -> str:
    """Strip markdown, emoji and stage directions so TTS never reads them aloud."""
    value = "" if text is None else str(text)
    for pattern, replacement in _CLEAN_PATTERNS:
        value = pattern.sub(replacement, value)
    return value.strip(" \t\n-–—:;")


def _fallback_text(segment: dict, language: str) -> str:
    """Neutral narration beat used when the model omits or blanks a segment."""
    if (language or "").lower().startswith("hi"):
        return "कहानी यहाँ एक नया मोड़ लेती है।"
    return "The story takes a sharp turn here."


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def generate_recap_script(
    segments: list,
    api_key: str = "",
    target_lang: str = "hi",
    *,
    model: str = DEFAULT_MODEL,
    batch_size: int = DEFAULT_BATCH_SIZE,
    temperature: float = 0.85,
    max_output_tokens: int = 8192,
    max_retries: int = DEFAULT_MAX_RETRIES,
    story_context: str = "",
    cache_path: str | None = None,
    overwrite: bool = False,
    api_keys: Sequence[str] | None = None,
) -> list[dict]:
    """Turn Chinese transcript segments into timed recap narration.

    Args:
        segments: Output of :func:`modules.transcriber.transcribe_chinese`.
        api_key: Gemini API key (or primary key).
        target_lang: BCP-47-ish language code, e.g. ``"hi"``.
        model: Gemini model id.
        batch_size: Segments per request. Smaller batches are more reliable;
            larger batches give the model more narrative context.
        temperature: Higher values read more dramatic; 0.85 is a good default.
        max_output_tokens: Response cap per batch.
        max_retries: Attempts per batch, with exponential backoff.
        story_context: Optional series synopsis / character-name sheet that keeps
            transliteration consistent across episodes.
        cache_path: Optional JSON file for resumable runs.
        overwrite: Ignore any existing cache.
        api_keys: Optional pool of Gemini API keys to rotate through.

    Returns:
        ``[{id, start, end, duration, original_text, recap_text, language}, ...]``
    """
    if not segments:
        log.warning("generate_recap_script: no input segments; nothing to localize.")
        return []

    if cache_path and not overwrite and os.path.isfile(cache_path):
        from . import read_json

        cached = read_json(cache_path)
        if isinstance(cached, list) and len(cached) == len(segments):
            log.info("Reusing cached recap script: %s", cache_path)
            return cached

    language_name = _language_name(target_lang)
    clients = _make_clients(api_key, api_keys)
    client_idx = 0
    system_instruction = _SYSTEM_INSTRUCTION.format(language_name=language_name)
    config = _build_config(system_instruction, temperature, max_output_tokens)

    context_block = ""
    if story_context.strip():
        context_block = (
            "SERIES CONTEXT (use these names/spellings consistently):\n"
            f"{story_context.strip()}\n\n"
        )

    batches = list(chunked(segments, max(1, int(batch_size))))
    log.info(
        "Generating %s recap narration for %d segment(s) in %d batch(es) via %s (with %d API key(s))...",
        language_name,
        len(segments),
        len(batches),
        model,
        len(clients),
    )

    recap_by_id: dict[int, str] = {}

    for batch_index, batch in enumerate(batches, start=1):
        payload = [
            {
                "id": int(seg.get("id", position)),
                "duration": round(float(seg.get("duration", 0.0)), 2),
                "target_words": _target_words(seg.get("duration", 0.0)),
                "chinese_text": str(seg.get("original_text", "")).strip(),
            }
            for position, seg in enumerate(batch)
        ]
        prompt = _USER_TEMPLATE.format(
            language_name=language_name,
            batch_index=batch_index,
            batch_total=len(batches),
            first_id=payload[0]["id"],
            last_id=payload[-1]["id"],
            context_block=context_block,
            payload=json.dumps(payload, ensure_ascii=False, indent=1),
        )

        last_error: Exception | None = None
        for attempt in range(1, max(1, max_retries) + 1):
            client = clients[client_idx % len(clients)]
            try:
                raw = _call_gemini(client, model, prompt, config)
                entries = _coerce_entries(_extract_json(raw))
                if not entries:
                    raise PipelineError("Gemini returned zero segments for this batch.")

                for position, entry in enumerate(entries):
                    try:
                        seg_id = int(entry.get("id", payload[min(position, len(payload) - 1)]["id"]))
                    except (TypeError, ValueError):
                        seg_id = payload[min(position, len(payload) - 1)]["id"]
                    text = _clean_text(
                        entry.get("recap_text")
                        or entry.get("text")
                        or entry.get("narration")
                        or entry.get("translated_text")
                    )
                    if text:
                        recap_by_id[seg_id] = text

                covered = sum(1 for item in payload if item["id"] in recap_by_id)
                log.info(
                    "  batch %d/%d -> %d/%d segment(s) narrated",
                    batch_index,
                    len(batches),
                    covered,
                    len(payload),
                )
                last_error = None
                if len(clients) > 1:
                    client_idx += 1
                break

            except PipelineError as exc:
                last_error = exc
                log.warning("  batch %d attempt %d failed: %s", batch_index, attempt, exc)
                if len(clients) > 1:
                    client_idx += 1
                    log.info("  rotating to next API key (%d/%d)...", (client_idx % len(clients)) + 1, len(clients))
                if attempt < max_retries:
                    time.sleep(min(45.0, 2.0 ** attempt))
            except Exception as exc:  # network / SDK / quota errors
                last_error = exc
                log.warning("  batch %d attempt %d errored: %s", batch_index, attempt, exc)
                if len(clients) > 1:
                    client_idx += 1
                    log.info("  rotating to next API key (%d/%d)...", (client_idx % len(clients)) + 1, len(clients))
                if attempt < max_retries:
                    time.sleep(min(45.0, 2.0 ** attempt))

        if last_error is not None:
            log.error(
                "  batch %d exhausted all retries (%s); those segments fall back to a "
                "generic narration beat.",
                batch_index,
                last_error,
            )

    dub_segments: list[dict] = []
    missing = 0
    for position, seg in enumerate(segments):
        seg_id = int(seg.get("id", position))
        recap = recap_by_id.get(seg_id, "")
        if not recap:
            recap = _fallback_text(seg, target_lang)
            missing += 1
        dub_segments.append(
            {
                "id": seg_id,
                "start": round(float(seg.get("start", 0.0)), 3),
                "end": round(float(seg.get("end", 0.0)), 3),
                "duration": round(float(seg.get("duration", 0.0)), 3),
                "original_text": str(seg.get("original_text", "")),
                "recap_text": recap,
                "language": target_lang,
            }
        )

    if missing:
        log.warning("%d/%d segment(s) used fallback narration.", missing, len(segments))
    log.info("Recap script ready: %d segment(s).", len(dub_segments))

    if cache_path:
        write_json(cache_path, dub_segments)

    return dub_segments


def build_story_context(dub_segments: Iterable[dict], max_chars: int = 900) -> str:
    """Condense already-localized segments into a context blurb for the next episode.

    Feeding this back into ``story_context`` is what keeps character-name
    transliteration stable across a 40-episode compilation.
    """
    pieces: list[str] = []
    total = 0
    for seg in dub_segments:
        text = str(seg.get("recap_text", "")).strip()
        if not text:
            continue
        pieces.append(text)
        total += len(text)
        if total >= max_chars:
            break
    blurb = " ".join(pieces)[:max_chars]
    return f"Previously in this series: {blurb}" if blurb else ""
