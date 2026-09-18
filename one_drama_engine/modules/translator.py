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

DEFAULT_MODEL = "gemini-flash-lite-latest"
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

# ~2.2 Hindi words/second is the natural conversational tempo for studio drama dubs (prevents rushed tempo and overflow).
WORDS_PER_SECOND = 2.2
MIN_WORDS = 2

# --------------------------------------------------------------------------- #
# Pass 1: Episode Story Dossier & Literal Translation
# --------------------------------------------------------------------------- #
_PASS1_SYSTEM_INSTRUCTION = """\
You are an expert anime, manhua, and short-drama narrative analyst, casting director, and translator.
Analyze the provided Chinese dialogue segments alongside speaker clusters, acoustic pitch analysis, and visual character lineup to produce:

1. EPISODE STORY DOSSIER:
   - Identify the MAIN CHARACTER / PROTAGONIST who drives the story.
   - Protagonist Name: Transliterate their original name phonetically into {language_name} (e.g. in Devanagari script for Hindi: लिन फेंग, बाई निंग, शियाओ यान, आदि). DO NOT invent random Indian names (no Rahul, Rohan, Siya).
   - Protagonist Gender: "male" or "female".
   - Protagonist Role: "hero" (if male lead) or "heroine" (if female lead).
   - Protagonist Archetype & Vibe: (e.g. "reincarnated cultivator reaching quasi-emperor stage with supreme confidence", "witty underdog", "arrogant cold regent duke").
   - Opponents / Key Characters: List names and roles of antagonists, system interface, or major companions.
   - Plot Synopsis: 2-3 sentences explaining the core conflict, drama, and what happens in this episode.

2. CAST ROLES & GENDER IDENTIFICATION (CRITICAL FOR DUBBING VOICES):
   - Available Speaker Roles:
     * "king" (The Emperor / Monarch / King / Royal Ruler on the throne - e.g. 陛下, 皇上, 朕) -> GENDER: ALWAYS "male".
     * "hero" (Male Lead / Protagonist / Young Cultivator / General / Duke / Hero) -> GENDER: ALWAYS "male".
     * "heroine" (Female Lead / Protagonist / Young Maiden / Goddess / Heroine) -> GENDER: ALWAYS "female".
     * "mistress" (Supporting Female / Antagonist Rival / Step-sister / Concubine) -> GENDER: ALWAYS "female".
     * "mother" (Elder Female / Madam / Matriarch / Empress Dowager / Mother-in-law) -> GENDER: ALWAYS "female".
     * "father" (Elder Male / Minister / Duke / Master / Patriarch / Father-in-law) -> GENDER: ALWAYS "male".
     * "villain" (Main Enemy / Antagonist Boss / Corrupt Lord / Opponent) -> GENDER: ALWAYS "male".
     * "extra_male" (ALL other third-party male characters: guards, soldiers, thugs, drivers, hotel staff, passersby) -> GENDER: ALWAYS "male".
     * "extra_female" (ALL other third-party female characters: maids, female passersby, nurses, receptionists) -> GENDER: ALWAYS "female".
     * "system" (AI System / Game Mentor / Heavenly Interface / Spiritual Assistant / Tutor System) -> GENDER: ALWAYS "female".
     * "narrator" (Voiceover / Background context) -> GENDER: "male".
   - CRITICAL IDENTIFICATION RULES:
     * CHARACTER IDENTITY DEFINES GENDER: In a drama, a King or Emperor (陛下, 朕) is a MAN. He must ALWAYS be assigned role "king" and gender "male". He can NEVER be female!
     * Female Lead (Heroine, 姑娘, 女主) and Rival Sister (妹妹, 柔哲) are WOMEN. They must ALWAYS be assigned gender "female".
     * DIALOGUE CONTINUITY: When a character speaks a sentence or multi-clause thought cut across speech pauses, MAINTAIN THE SAME SPEAKER AND GENDER throughout! Never flip a character's voice mid-speech!

3. SPEAKER MAP:
   - Map each speaker cluster (e.g. "spk_0", "spk_1", "spk_2") to its established character role.

4. SEGMENT-BY-SEGMENT LITERAL TRANSLATION & DIALOGUE TURN SPLITTING:
   - Accurately translate each Chinese segment into faithful, natural {language_name}.
   - Identify who is speaking (using one of the roles above), their gender ("male" | "female"), and their name in {language_name}.
   - MULTI-TURN DIALOGUE SPLITTING (MANDATORY):
     If a segment contains dialogue from TWO OR MORE different characters spoken back-to-back, YOU MUST SPLIT IT into "turns"!
     Key examples to watch for:
     * One person speaking followed by someone addressing another (e.g. "出来玩还能让咱们住普通地方陈先生您预定的是三十碗海湾行政套房早餐下午茶和专车服务都包含在内" -> Turn 1: "出来玩还能让咱们住普通地方" [mother, female], Turn 2: "陈先生您预定的是三十晚海湾行政套房早餐下午茶和专车服务都包含在内" [extra_male, male]).
     * Direct exchange between protagonist and subordinate (e.g. "那第一碗算了大小姐您的意思是后面二十九晚全部取消全部" -> Turn 1: "那第一晚算了" [heroine, female], Turn 2: "大小姐您的意思是后面二十九晚全部取消" [extra_male, male], Turn 3: "全部" [heroine, female]).
     * Rapid social exchange (e.g. "阿姨我站旁边就行什么旁边不旁边的都是自己人" -> Turn 1: "阿姨我站旁边就行" [mistress, female], Turn 2: "什么旁边不旁边的都是自己人" [mother, female]).
     Whenever there is a change of speaker within a single segment, return "turns" with each speaker's exact text, role, gender, speaker_name, and translation!

OUTPUT FORMAT:
Return ONLY a valid JSON object of this exact shape:
{{
  "protagonist": {{
    "name": "<Transliterated name in {language_name}>",
    "gender": "male" | "female",
    "role": "hero" | "heroine",
    "vibe": "<personality traits>"
  }},
  "plot_synopsis": "<2-3 sentence overview of this episode>",
  "speaker_map": {{
    "spk_0": "hero" | "heroine" | "mother" | "mistress" | "extra_male",
    "spk_1": "hero" | "heroine" | "mother" | "mistress" | "extra_male"
  }},
  "segments": [
    {{
      "id": <int>,
      "speaker": "hero" | "heroine" | "mistress" | "mother" | "father" | "extra_male" | "extra_female" | "system" | "villain" | "narrator",
      "gender": "male" | "female",
      "speaker_name": "<name in {language_name}>",
      "literal_translation": "<faithful translation in {language_name}>",
      "turns": [
        {{
          "text": "<turn 1 chinese text>",
          "speaker": "hero" | "heroine" | "mistress" | "mother" | "extra_male",
          "gender": "male" | "female",
          "speaker_name": "<name in {language_name}>",
          "translation": "<turn 1 translation>"
        }},
        {{
          "text": "<turn 2 chinese text>",
          "speaker": "hero" | "heroine" | "mistress" | "mother" | "extra_male",
          "gender": "male" | "female",
          "speaker_name": "<name in {language_name}>",
          "translation": "<turn 2 translation>"
        }}
      ]
    }}
  ]
}}
No prose outside JSON. No markdown code fences.
"""

_PASS1_USER_TEMPLATE = """\
Target language: {language_name}
Total segments: {total_segments} (segment ids {first_id}-{last_id})

{cast_block}{context_block}Analyze these Chinese dialogue segments. Extract the story dossier and literal translations.
Return JSON only.

INPUT SEGMENTS:
{payload}
"""

# --------------------------------------------------------------------------- #
# Pass 2: First-Person Protagonist POV Creative Rewrite
# --------------------------------------------------------------------------- #
_PASS2_SYSTEM_INSTRUCTION = """\
You are the MAIN CHARACTER (PROTAGONIST) of this anime/manhwa/manhua drama, recounting your own crazy story directly to your audience in FIRST-PERSON {language_name}.
You are recounting what just happened to you like a charismatic, street-smart, witty Indian friend sharing your wildest moments over chai.

PROTAGONIST PROFILE:
- Name: {protagonist_name}
- Gender: {protagonist_gender}
- Role & Vibe: {protagonist_vibe}
- Episode Plot: {plot_synopsis}

STRICT GRAMMAR & GENDER AGREEMENT:
{gender_rules}

CORE RULES:
1. FIRST-PERSON POV & ACTIVE STORYTELLING (not a dry quote dub):
   - You are the PROTAGONIST recounting the story! Use "मैं", "मुझे", "मैंने", "मेरा", "मेरी", "तुम्हारा भाई", "तुम्हारी ये क्वीन".
   - DO NOT just dryly quote dialogue lines (AVOID "वो बोला X, फिर मैंने कहा Y").
   - INSTEAD, EXPLAIN and REACT to what is happening on screen with witty commentary, sarcasm, and real-time reactions!
   - Examples of how to transform scenes:
     * When an opponent insults or challenges you:
       "अब ये घमंडी नमूना मेरे सामने आकर ऐसी हेकड़ी दिखा रहा था मानो अंबानी का दामाद यही हो! कहता है तेरी अंदर आने की औकात नहीं! भाई, अपने बाप का राज समझ रखा है क्या?"
     * When an opponent attacks:
       "लो भाई, इस चोमू ने अपने चमचों को भेज दिया मेरी टांगें तोड़ने! अरे पहले खुद तो ठीक से खड़ा हो जा!"
     * When system activates or you get power:
       "और तभी भाई की किस्मत का ताला खुला! दिमाग में घंटी बजी और तगड़ा सुपर सिस्टम अनलॉक हो गया! अब आएगा ना असली मज़ा!"
     * When you fight back or defeat them:
       "फिर तुम्हारे भाई ने वो तगड़ा झटका दिया कि इसका पूरा सिस्टम ही हैंग हो गया! एकदम पैसा वसूल सीन!"

2. VIBRANT DESI YOUTH BANTER & SLANG (दोस्ताना, मजेदार देसी बोली):
   - STRICTLY FORBIDDEN: NEVER use formal, textbook, Sanskritized Hindi (NO 'कल्पना कीजिए', 'सहपाठी', 'उद्धारकर्ता', 'प्रतिशोध', 'अलौकिक', 'सहोदर').
   - INSTEAD, use authentic, casual, friendly conversational language as young people talk over chai:
     * "अरे यार!", "भाई साहब!", "सच बताऊं तो...", "दिमाग की दही मत कर!", "सिस्टम ही हैंग कर दिया!", "चूना लगा दिया!", "छोमू समझ रखा है क्या?", "अपने बाप का राज है क्या?", "पैसा वसूल सीन!", "औकात दिखा दी!", "वाट लग गई!", "खत्म, टाटा, बाय-बाय!"
   - Witty cultural analogies & memes where fitting:
     * Comparing wealth or arrogance to Ambani: "खुद को अंबानी से भी बड़ा रईस समझ रहा था", "जैसे अंबानी का दामाद यही हो!", "बैंक खाते में चवन्नी नहीं पर स्वैग पूरे पांच सौ करोड़ का!"

3. ZERO CHINESE CHARACTERS & NO FAKE INDIAN NAMES:
   - NEVER leave any Chinese hanzi (like 炼气期) in the text! Transliterate cultivation terms into Hindi or plain concepts ("शुरुआती लेवल", "कल्टीवेशन स्टेज", "मार्शल आर्ट").
   - Use original character names transliterated into Hindi (e.g. {protagonist_name}, झांग, वांग) or funny roles ("ये अमीरजादा", "ये गुंडा भाई साहब", "प्रिंसिपल साहब"). NEVER invent random names like Rahul, Rohan, Siya.

4. NATURAL LENGTH & COMPLETE SENTENCES (NO CUTOFFS):
   - Translate each dialogue into a COMPLETE, natural sentence.
   - Do NOT write bloated paragraphs or unnecessary essays—keep the length proportionate to the original dialogue.
   - Never cut off a thought mid-sentence! The listener must clearly understand what the character is saying.
   - Plain spoken text ONLY: NO emoji, NO asterisks/markdown, NO bracketed notes or stage directions.

OUTPUT:
Return ONLY a valid JSON object matching this schema:
{{"segments": [{{"id": <int>, "recap_text": "<Witty first-person storytelling in {language_name}>"}}]}}
No prose outside JSON. No code fences.
"""

_PASS2_USER_TEMPLATE = """\
Target language: {language_name}
Batch {batch_index} of {batch_total} (segment ids {first_id}-{last_id}).

PROTAGONIST: {protagonist_name} ({protagonist_gender}) - {protagonist_vibe}
SCENE CONTEXT: {plot_synopsis}

Rewrite each segment into punchy FIRST-PERSON PROTAGONIST narration.
Adhere strictly to target_words and conversational youth banter.
Return JSON only.

SEGMENTS TO REWRITE:
{payload}
"""

# --------------------------------------------------------------------------- #
# Pass 2 Alternative: Multi-Character Dramatic Dubbing
# --------------------------------------------------------------------------- #
_MULTICHAR_DUB_SYSTEM_INSTRUCTION = """\
You are an expert anime, manhua, and short-drama dubbing director and dialogue writer in {language_name}.
Translate and adapt each Chinese dialogue segment into authentic, modern, cinematic spoken dialogue.

CAST & CHARACTERS REFERENCE:
{cast_block}

RULES FOR DRAMATIC MULTI-CHARACTER DUBBING:
1. SPEAKER ATTRIBUTION & ROLES:
   - Identify who is speaking each line:
     * "hero" (Male Lead / Cultivator / Duke / Warrior)
     * "heroine" (Female Lead / Reincarnated Goddess / Young Maiden)
     * "system" (AI System / Game Mentor / Interface / Spiritual Tutor - ONLY when the AI itself speaks; when the hero talks TO or ABOUT the system, the speaker is the hero/heroine!)
     * "villain" (Main Antagonist / Enemy Boss / Arrogant Opponent)
     * "father" (Elder Male / Master / Patriarch)
     * "mother" (Elder Female / Madam / Matriarch)
     * "extra_male" (ALL other third-party male characters: guards, thugs, servants, bystanders, passersby, citizens, doctors)
     * "extra_female" (ALL other third-party female characters: maids, nurses, crowd women, female passersby)
     * "narrator" (Voiceover / Background context)
   - ALWAYS set "gender": "male" or "female".
   - Set "speaker_name" to their transliterated character or role name in {language_name} (e.g. 'सिस्टम', 'लिन फेंग', 'गार्ड', 'नागरिक').
   - CRITICAL: Ensure ALL dialogue lines are assigned!

2. STRICT GRAMMATICAL GENDER AGREEMENT (CRITICAL FOR ACCURACY):
   - When a FEMALE or SYSTEM speaks ("heroine", "system", "extra_female", "mother"):
     * MUST use FEMININE Hindi verb forms and pronouns: 'रही हूँ', 'चुकी हूँ', 'गयी', 'मेरी', 'मरी नहीं', 'सोची', 'बच गई'.
     * Example for System: "चेतावनी! नया मिशन प्राप्त हुआ है, कृपया ध्यान दें!"
     * Example for Heroine: "98 बार आसमानी बिजली झेल चुकी हूँ, आज मुझे कोई नहीं रोक सकता!"
     * STRICTLY FORBIDDEN: NEVER use masculine verb endings ('झेल चुका हूँ', 'मरा नहीं', 'आ गया', 'तुम्हारा भाई') for female characters!
   - When a MALE speaks ("hero", "extra_male", "villain", "father"):
     * Uses masculine Hindi grammar: 'रहा हूँ', 'चुका हूँ', 'गया', 'मेरा', 'मरा नहीं', 'तुम्हारा भाई'.
     * Example for Hero: "अरे भाई, मुझे इन सब ड्रामों की जरूरत नहीं, मैं तो पहले से ही नौवें लेवल पर हूँ!"
     * Example for Extra Male / Guard: "हट यहाँ से! अंदर जाने की अनुमति किसी को नहीं है!"

3. CASUAL, FRIENDLY, AND ENGAGING CONVERSATIONAL STYLE (दोस्ताना, मजेदार देसी बोली):
   - Translate into everyday, casual, expressive spoken language (just like friends chatting, gossiping, or bantering over chai).
   - STRICTLY FORBIDDEN: Heavy archaic, literary Sanskritized Hindi! DO NOT use dry textbook words like:
     * 'वज्र आपदा' (use 'थंडर स्ट्राइक / आसमानी बिजली')
     * 'आरोहण / साधना' (use 'लेवल अप / पावर / गॉड मोड / ट्रेनिंग')
     * 'स्वर्गीय मार्ग / 天道' (use 'ऊपरवाला / कुदरत / हेवन')
     * 'अशुभ तारा / 丧门星' (use 'मनहूस / पनौती')
     * 'कदापि नहीं' (use 'बिल्कुल नहीं / कभी नहीं')
     * 'धत तेरे की' (use 'अरे यार / तेरी तो / क्या बकवास है')
     * 'वास्तव में' (use 'सच में / असली में')
     * 'अवगत' (use 'पता है')
   - USE modern conversational Hindi/Hinglish as spoken naturally by young people:
     * 'अरे यार!', 'भाई!', 'बॉस', 'सीन', 'चिल', 'वेट', 'टेंशन मत ले', 'प्लान', 'अटैक', 'शॉक', 'टाइम'
   - Witty cultural analogies & memes where appropriate:
     * Comparing arrogance or wealth to Ambani: "खुद को अंबानी से भी बड़ा रईस समझ रहा है क्या?", "जैसे अंबानी का दामाद यही हो!", "पैसा इतना कि अंबानी भी शर्मा जाए!"
     * Punchy dialogue reactions: "दिमाग का दही मत कर!", "सिस्टम ही हैंग कर दिया!", "पैसा वसूल सीन!", "खत्म, टाटा, बाय-बाय!"
   - Deliver authentic emotions: if angry, sound genuinely angry and fierce; if humorous, sound witty; if emotional, sound touching.

4. NATURAL LENGTH & COMPLETE SENTENCES (NO SENTENCE CUTOFFS):
   - Translate the dialogue naturally so that EVERY SENTENCE IS COMPLETE, coherent, and clearly understandable.
   - Do NOT write bloated paragraphs or unnecessary essays—keep the length proportionate to the original dialogue.
   - For quick reactions (< 1.2s), use punchy natural 1-3 word reactions ("क्या?!", "अरे रुको!", "ओह भाई!", "सही है!", "लो भाई!").
   - For regular dialogue, convey the complete thought naturally. Never stop mid-sentence or cut off ideas!
   - Plain spoken text ONLY: NO stage directions, NO asterisks, NO emoji, NO parenthetical notes.
   - Set "emotion": "angry" | "sarcastic" | "emotional" | "crying" | "laughing" | "shocked" | "neutral".

OUTPUT FORMAT:
Return ONLY a valid JSON object matching this schema:
{{
  "segments": [
    {{
      "id": <int>,
      "speaker": "hero" | "heroine" | "mistress" | "mother" | "system" | "villain" | "father" | "extra_male" | "extra_female" | "narrator",
      "speaker_name": "<name in {language_name}>",
      "gender": "male" | "female",
      "recap_text": "<Spoken dramatic dialogue in modern {language_name}>",
      "emotion": "angry" | "sarcastic" | "emotional" | "crying" | "laughing" | "shocked" | "neutral"
    }}
  ]
}}
No prose outside JSON. No markdown code fences.
"""

_MULTICHAR_DUB_USER_TEMPLATE = """\
Target language: {language_name}
Batch {batch_index} of {batch_total} (segment ids {first_id}-{last_id}).
SCENE CONTEXT: {plot_synopsis}

CAST ROLES:
{cast_summary}

Write authentic, dramatic spoken character dialogue for each segment.
Adhere strictly to target_words and assign the correct speaker and gender.
Return JSON only.

SEGMENTS TO DUB:
{payload}
"""



# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _language_name(code: str) -> str:
    return LANGUAGE_NAMES.get((code or "").lower(), code or "Hindi (Devanagari script)")


def _target_words(duration: float) -> int:
    return max(MIN_WORDS, int(round(max(0.0, float(duration)) * WORDS_PER_SECOND)))


def _max_words(duration: float) -> int:
    dur = max(0.0, float(duration))
    if dur <= 0.8:
        return 2
    elif dur <= 1.4:
        return 3
    elif dur <= 2.2:
        return 5
    else:
        return max(2, int(round(dur * 2.3)))


def _condense_dialogue_if_needed(text: str, duration: float = 0.0, max_w: int = 0) -> str:
    """Clean and normalize dialogue text, preserving full complete sentences without truncation."""
    if not text:
        return ""
    cleaned = text.strip()
    # Strip any accidental brackets or stage directions
    cleaned = re.sub(r"\[.*?\]|\(.*?\)", "", cleaned).strip()
    return cleaned


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
    """Call ``generate_content`` with automatic model cascade fallback on 429 quota limits."""
    candidates = [model, "gemini-flash-lite-latest", "gemini-3.1-flash-lite-preview", "gemini-2.5-flash"]
    candidates = list(dict.fromkeys(candidates))

    last_exc = None
    for cand in candidates:
        try:
            try:
                response = client.models.generate_content(model=cand, contents=prompt, config=config)
            except TypeError:
                response = client.models.generate_content(
                    model=cand, contents=prompt, generation_config=config
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

        except Exception as exc:
            last_exc = exc
            log.warning("Gemini model %s failed (%s). Trying next candidate...", cand, exc)

    feedback = getattr(last_exc, "message", str(last_exc))
    raise PipelineError(
        f"All Gemini models exhausted. Last error: {feedback}"
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
    for suffix in ['"}]}', '"}]', '"]}', '}]', '"}', '}', '"]']:
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
    """1st-person protagonist narration beat used when the model omits or blanks a segment."""
    if (language or "").lower().startswith("hi"):
        return "अरे यार, यहाँ कहानी में ऐसा मोड़ आया कि मैं भी हैरान रह गया!"
    return "The story takes an unexpected turn here."


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
    character_lineup: dict | None = None,
    dubbing_mode: str = "multi_character",
    video_path: str | None = None,
) -> list[dict]:
    """Turn Chinese transcript segments into timed 1st-Person Protagonist POV narration via 2-Pass AI.

    - Pass 1: Analyzes dialogue to build the Episode Story Dossier (Protagonist identity,
              gender: male/female, personality vibe, antagonist, plot) + faithful literal translation.
    - Pass 2: Rewrites each batch into punchy, hilarious First-Person Protagonist POV narration
              with authentic Indian street youth banter, desi pop-culture comparisons, and timing adherence.

    Args:
        segments: Output of :func:`modules.transcriber.transcribe_chinese`.
        api_key: Gemini API key (or primary key).
        target_lang: BCP-47-ish language code, e.g. ``"hi"``.
        model: Gemini model id.
        batch_size: Segments per request in Pass 2.
        temperature: Higher values read more dramatic/witty; 0.85 is a good default.
        max_output_tokens: Response cap per request.
        max_retries: Attempts per batch, with exponential backoff and key rotation.
        story_context: Optional series synopsis / character-name sheet that keeps
            transliteration and character continuity consistent across episodes.
        cache_path: Optional JSON file for resumable runs.
        overwrite: Ignore any existing cache.
        api_keys: Optional pool of Gemini API keys to rotate through.

    Returns:
        ``[{id, start, end, duration, original_text, recap_text, language, protagonist_name, protagonist_gender}, ...]``
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

    context_block = ""
    if story_context.strip():
        context_block = (
            "SERIES CONTEXT (use these names/spellings consistently):\n"
            f"{story_context.strip()}\n\n"
        )

    # Auto-load character lineup and series title if not passed
    if not character_lineup:
        from . import read_json
        for candidate_path in [
            "storage/characters/character_lineup.json",
            os.path.join(os.path.dirname(__file__), "..", "storage", "characters", "character_lineup.json"),
        ]:
            if os.path.isfile(candidate_path):
                character_lineup = read_json(candidate_path, default=None)
                if character_lineup:
                    break

    series_title = ""
    for info_path in [
        "storage/raw_episodes/series_info.json",
        os.path.join(os.path.dirname(__file__), "..", "storage", "raw_episodes", "series_info.json"),
    ]:
        if os.path.isfile(info_path):
            from . import read_json
            s_info = read_json(info_path, default={})
            series_title = s_info.get("title", "")
            if series_title:
                break

    if series_title and f"《{series_title}》" not in context_block:
        context_block = f"DRAMA TITLE: 《{series_title}》\n" + context_block

    # Build known character lineup before Pass 1
    cast_lines = []
    heroine_candidate = None
    hero_candidate = None
    if character_lineup and isinstance(character_lineup.get("characters"), list):
        for c in character_lineup["characters"]:
            cid = c.get("id", "")
            crole = c.get("role", "supporting")
            cname = c.get("name", "")
            chname = c.get("hindi_name", "")
            cgen = c.get("gender", "male")
            cvis = c.get("visual_summary", "")
            disp_name = f"{cname} ({chname})" if chname else cname
            cast_lines.append(f"- [{cid}] {crole.upper()} ({cgen}): {disp_name} - {cvis}")
            if crole == "heroine" or cgen == "female":
                if not heroine_candidate:
                    heroine_candidate = c
            elif crole == "hero" or (cgen == "male" and not hero_candidate):
                hero_candidate = c

    existing_roles = {c.get("role") for c in (character_lineup.get("characters", []) if character_lineup else [])}
    if "mistress" not in existing_roles:
        cast_lines.append("- [C4] MISTRESS (female): Xu Qingya (श्यू किंग्या) - Childhood friend / rival mistress")
    if "extra_male" not in existing_roles:
        cast_lines.append("- [C5] EXTRA_MALE (male): Subordinate / Concierge / Assistant (सहायक / कर्मचारी)")
    if "supporting_female" not in existing_roles:
        cast_lines.append("- [C6] SUPPORTING_FEMALE (female): Chen Jing'an (बहन / 陳景安) - Younger sister / sister-in-law")

    cast_block = ("KNOWN DRAMA CAST FROM VIDEO ANALYSIS:\n" + "\n".join(cast_lines) + "\n\n") if cast_lines else ""

    # ----------------------------------------------------------------------- #
    # PASS 1: Extract Story Dossier & Establishing Speaker Map
    # ----------------------------------------------------------------------- #
    pass1_instruction = _PASS1_SYSTEM_INSTRUCTION.format(language_name=language_name)
    pass1_config = _build_config(pass1_instruction, 0.4, max_output_tokens)

    pass1_data_by_id: dict[int, dict] = {}
    speaker_map: dict[str, str] = {}
    protagonist_info: dict[str, str] = {
        "name": "हमारा हीरो",
        "gender": "male",
        "role": "hero",
        "vibe": "street-smart, witty, confident",
    }
    if heroine_candidate and (not hero_candidate or "离婚" in series_title or "苏小姐" in series_title):
        protagonist_info["name"] = heroine_candidate.get("hindi_name") or heroine_candidate.get("name") or "सु वानकिंग"
        protagonist_info["gender"] = "female"
        protagonist_info["role"] = "heroine"
        protagonist_info["vibe"] = "proud, rich heiress, powerful composed woman"
    elif hero_candidate and not heroine_candidate:
        protagonist_info["name"] = hero_candidate.get("hindi_name") or hero_candidate.get("name") or "हमारा हीरो"
        protagonist_info["gender"] = "male"
        protagonist_info["role"] = "hero"

    plot_synopsis = ""

    # Long Video Optimization (5-Minute Scene Sampling):
    # For any episode (especially 1.5h - 2.5h videos), discover the protagonist dossier,
    # storyline conflict, and speaker cluster map from the first 5 minutes (start <= 300s).
    establishing_segments = [s for s in segments if float(s.get("start", 0.0)) <= 300.0]
    if len(establishing_segments) < 15:
        establishing_segments = segments[: min(45, len(segments))]
    pass1_target_segments = establishing_segments if len(segments) > 60 else segments
    pass1_chunks = list(chunked(pass1_target_segments, 45))

    log.info(
        "Pass 1/2: Extracting Story Dossier & Speaker Map from %d establishing segment(s) (%d chunk(s)) via %s...",
        len(pass1_target_segments),
        len(pass1_chunks),
        model,
    )

    for p1_idx, p1_chunk in enumerate(pass1_chunks, start=1):
        p1_payload = [
            {
                "id": int(seg.get("id", pos)),
                "chinese_text": str(seg.get("original_text", "")).strip(),
                "detected_emotion": seg.get("detected_emotion", "neutral"),
                "speaker_cluster": (seg.get("matched_role") if float(seg.get("matched_sim", 0.0)) >= 0.65 else "") or seg.get("speaker_id", "spk_0"),
                "pitch_hz": seg.get("pitch_hz", 0.0),
                "acoustic_gender": seg.get("acoustic_gender", "unknown"),
            }
            for pos, seg in enumerate(p1_chunk)
        ]
        p1_prompt = _PASS1_USER_TEMPLATE.format(
            language_name=language_name,
            total_segments=len(p1_payload),
            first_id=p1_payload[0]["id"],
            last_id=p1_payload[-1]["id"],
            cast_block=cast_block,
            context_block=context_block,
            payload=json.dumps(p1_payload, ensure_ascii=False, indent=1),
        )

        for attempt in range(1, max(1, max_retries) + 1):
            client = clients[client_idx % len(clients)]
            try:
                raw = _call_gemini(client, model, p1_prompt, pass1_config)
                parsed = _extract_json(raw)
                if isinstance(parsed, dict):
                    if "protagonist" in parsed and isinstance(parsed["protagonist"], dict):
                        p_obj = parsed["protagonist"]
                        if p_obj.get("name"):
                            protagonist_info["name"] = str(p_obj["name"]).strip()
                        if p_obj.get("gender"):
                            g = str(p_obj["gender"]).strip().lower()
                            protagonist_info["gender"] = (
                                "female" if any(f in g for f in ("female", "स्त्री", "महिला", "लड़की", "queen", "heroine")) else "male"
                            )
                        if p_obj.get("role"):
                            protagonist_info["role"] = str(p_obj["role"]).strip()
                        if p_obj.get("vibe"):
                            protagonist_info["vibe"] = str(p_obj["vibe"]).strip()

                    if parsed.get("plot_synopsis"):
                        plot_synopsis = str(parsed["plot_synopsis"]).strip()

                    if "speaker_map" in parsed and isinstance(parsed["speaker_map"], dict):
                        for spk_k, spk_v in parsed["speaker_map"].items():
                            speaker_map[str(spk_k).strip()] = str(spk_v).strip().lower()

                    p1_segs = parsed.get("segments") or []
                    for seg_entry in p1_segs:
                        if isinstance(seg_entry, dict) and "id" in seg_entry:
                            sid = int(seg_entry["id"])
                            pass1_data_by_id[sid] = seg_entry
                            # Populate speaker map from segment level predictions if available
                            for orig_s in p1_chunk:
                                if int(orig_s.get("id", -1)) == sid:
                                    s_spk_cluster = orig_s.get("speaker_id")
                                    if s_spk_cluster and s_spk_cluster not in speaker_map:
                                        speaker_map[s_spk_cluster] = str(seg_entry.get("speaker", "hero")).lower()

                if len(clients) > 1:
                    client_idx += 1
                break
            except Exception as exc:
                log.warning("  Pass 1 chunk %d attempt %d failed: %s", p1_idx, attempt, exc)
                if len(clients) > 1:
                    client_idx += 1
                    log.info("  rotating to next API key (%d/%d)...", (client_idx % len(clients)) + 1, len(clients))
                if attempt < max_retries:
                    time.sleep(min(30.0, 2.0 ** attempt))

    protagonist_name = protagonist_info.get("name", "हमारा हीरो")
    protagonist_gender = protagonist_info.get("gender", "male")
    protagonist_vibe = protagonist_info.get("vibe", "witty, street-smart")

    log.info(
        "Pass 1 Complete: Protagonist '%s' (%s, %s). Speaker Map: %s. Synopsis: %s",
        protagonist_name,
        protagonist_gender,
        protagonist_vibe,
        speaker_map,
        plot_synopsis[:100] if plot_synopsis else "N/A",
    )

    # ----------------------------------------------------------------------- #
    # Multi-Turn Segment De-merging (Tier 1 Semantic Turn Splitter)
    # ----------------------------------------------------------------------- #
    expanded_segments: list[dict] = []
    expanded_pass1: dict[int, dict] = {}
    next_id = 0

    for seg in segments:
        sid = int(seg.get("id", len(expanded_segments)))
        p1_entry = pass1_data_by_id.get(sid, {})
        turns = p1_entry.get("turns")

        if isinstance(turns, list) and len(turns) >= 2:
            log.info("✂️ De-merging multi-turn segment %d into %d distinct speaker turns!", sid, len(turns))
            start_s = float(seg.get("start", 0.0))
            end_s = float(seg.get("end", 0.0))
            total_dur = max(0.2, end_s - start_s)

            char_lens = [max(1, len(str(t.get("text", "")))) for t in turns]
            total_chars = max(1, sum(char_lens))

            cur_t = start_s
            for t_idx, turn in enumerate(turns):
                t_dur = round(total_dur * (char_lens[t_idx] / total_chars), 2)
                t_end = round(cur_t + t_dur, 2) if t_idx < len(turns) - 1 else end_s

                sub_seg = dict(seg)
                sub_seg["id"] = next_id
                sub_seg["start"] = cur_t
                sub_seg["end"] = t_end
                sub_seg["duration"] = round(t_end - cur_t, 2)
                sub_seg["original_text"] = str(turn.get("text") or "").strip()
                sub_seg["speaker_id"] = f"{seg.get('speaker_id', 'spk_0')}_{t_idx}"

                expanded_segments.append(sub_seg)
                expanded_pass1[next_id] = {
                    "id": next_id,
                    "speaker": turn.get("speaker", p1_entry.get("speaker", "hero")),
                    "gender": turn.get("gender", p1_entry.get("gender", "male")),
                    "speaker_name": turn.get("speaker_name", p1_entry.get("speaker_name", "")),
                    "literal_translation": turn.get("translation", ""),
                }
                cur_t = t_end
                next_id += 1
        else:
            sub_seg = dict(seg)
            sub_seg["id"] = next_id
            expanded_segments.append(sub_seg)
            expanded_pass1[next_id] = p1_entry
            next_id += 1

    segments = expanded_segments
    pass1_data_by_id = expanded_pass1

    # ----------------------------------------------------------------------- #
    # PASS 2: Multi-Character Dramatic Dubbing OR Protagonist POV
    # ----------------------------------------------------------------------- #
    is_multi_char = (dubbing_mode == "multi_character")

    if is_multi_char:
        pass2_instruction = _MULTICHAR_DUB_SYSTEM_INSTRUCTION.format(
            language_name=language_name,
            cast_block=cast_block or "- HEROINE (female): Female Lead\n- HERO (male): Male Lead\n- VILLAIN (male): Antagonist\n- EXTRA_MALE: Guards / Thugs",
        )
    else:
        if protagonist_gender == "female":
            gender_rules = (
                "- The protagonist is FEMALE. Use feminine Hindi verb endings and pronouns:\n"
                "  * 'मैं गई', 'मैंने सोचा', 'मेरी एंट्री', 'तुम्हारी ये बहन / तुम्हारी क्वीन', 'मुझसे पंगा लिया'\n"
                "  * NEVER use masculine self-references like 'तुम्हारा भाई' or 'मैं गया'!"
            )
        else:
            gender_rules = (
                "- The protagonist is MALE. Use masculine Hindi verb endings and pronouns:\n"
                "  * 'मैं गया', 'मैंने सोचा', 'तुम्हारा भाई', 'मेरा जलवा', 'मुझसे पंगा लिया'\n"
                "  * NEVER use feminine self-references like 'मैं गई' or 'मेरी एंट्री'!"
            )

        pass2_instruction = _PASS2_SYSTEM_INSTRUCTION.format(
            language_name=language_name,
            protagonist_name=protagonist_name,
            protagonist_gender=protagonist_gender,
            protagonist_vibe=protagonist_vibe,
            plot_synopsis=plot_synopsis or "Action and dramatic confrontation.",
            gender_rules=gender_rules,
        )
    pass2_config = _build_config(pass2_instruction, temperature, max_output_tokens)

    batches = list(chunked(segments, max(1, int(batch_size))))
    mode_label = "Multi-Character Dramatic Cast Dubbing" if is_multi_char else "1st-Person Protagonist POV Narration"
    log.info(
        "Pass 2/2: Generating %s for %d segment(s) in %d batch(es)...",
        mode_label,
        len(segments),
        len(batches),
    )

    seg_map: dict[int, dict] = {int(s.get("id", idx)): s for idx, s in enumerate(segments)}

    recap_by_id: dict[int, str] = {}
    speaker_by_id: dict[int, str] = {}
    speaker_name_by_id: dict[int, str] = {}
    gender_by_id: dict[int, str] = {}
    emotion_by_id: dict[int, str] = {}

    for batch_index, batch in enumerate(batches, start=1):
        payload = []
        for position, seg in enumerate(batch):
            seg_id = int(seg.get("id", position))
            p1_entry = pass1_data_by_id.get(seg_id, {})
            det_emo = seg.get("detected_emotion") or p1_entry.get("detected_emotion") or "neutral"
            spk_cluster = seg.get("speaker_id", "spk_0")
            ac_gen = str(seg.get("acoustic_gender") or "unknown").lower()
            ac_pitch = seg.get("pitch_hz", 0.0)

            matched_r = seg.get("matched_role")
            matched_g = seg.get("matched_gender")
            matched_sim = float(seg.get("matched_sim", 0.0))

            # Suggest role from acoustic centroid lock (top priority!), pass 1, or speaker_map
            if matched_r and matched_sim >= 0.40:
                suggested_spk = matched_r
                suggested_gen = matched_g
            else:
                suggested_spk = p1_entry.get("speaker") or speaker_map.get(spk_cluster)
                if not suggested_spk:
                    orig_txt = str(seg.get("original_text", ""))
                    if "叮" in orig_txt or "本系统" in orig_txt or "【系统" in orig_txt:
                        suggested_spk = "system"
                    elif ac_gen == "male":
                        suggested_spk = "hero"
                    elif ac_gen == "female":
                        suggested_spk = "heroine" if protagonist_gender == "female" else "system"
                    else:
                        suggested_spk = "heroine" if protagonist_gender == "female" else "hero"

                suggested_gen = "male" if ac_gen == "male" else ("female" if ac_gen == "female" else ("female" if suggested_spk in ("heroine", "system", "mother", "extra_female") else "male"))

            payload.append(
                {
                    "id": seg_id,
                    "duration": round(float(seg.get("duration", 0.0)), 2),
                    "target_words": _target_words(seg.get("duration", 0.0)),
                    "max_words": _max_words(seg.get("duration", 0.0)),
                    "speaker": suggested_spk,
                    "gender": suggested_gen,
                    "speaker_cluster": spk_cluster,
                    "pitch_hz": ac_pitch,
                    "acoustic_gender": ac_gen,
                    "speaker_name": p1_entry.get("speaker_name", ""),
                    "detected_emotion": det_emo,
                    "literal_meaning": p1_entry.get("literal_translation", seg.get("original_text", "")),
                    "chinese_text": str(seg.get("original_text", "")).strip(),
                }
            )

        if is_multi_char:
            prompt = _MULTICHAR_DUB_USER_TEMPLATE.format(
                language_name=language_name,
                batch_index=batch_index,
                batch_total=len(batches),
                first_id=payload[0]["id"],
                last_id=payload[-1]["id"],
                plot_synopsis=plot_synopsis or "Action and dramatic confrontation.",
                cast_summary=cast_block,
                payload=json.dumps(payload, ensure_ascii=False, indent=1),
            )
        else:
            prompt = _PASS2_USER_TEMPLATE.format(
                language_name=language_name,
                batch_index=batch_index,
                batch_total=len(batches),
                first_id=payload[0]["id"],
                last_id=payload[-1]["id"],
                protagonist_name=protagonist_name,
                protagonist_gender=protagonist_gender,
                protagonist_vibe=protagonist_vibe,
                plot_synopsis=plot_synopsis or "Action and dramatic confrontation.",
                payload=json.dumps(payload, ensure_ascii=False, indent=1),
            )

        last_error: Exception | None = None
        for attempt in range(1, max(1, max_retries) + 1):
            client = clients[client_idx % len(clients)]
            try:
                raw = _call_gemini(client, model, prompt, pass2_config)
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
                        or entry.get("dialogue_text")
                        or entry.get("text")
                        or entry.get("narration")
                        or entry.get("translated_text")
                    )
                    if text:
                        cur_seg = seg_map.get(seg_id, {})
                        dur = float(cur_seg.get("duration", 0.0))
                        text = _condense_dialogue_if_needed(text, dur, _max_words(dur))
                        recap_by_id[seg_id] = text
                        p1_e = pass1_data_by_id.get(seg_id, {})
                        orig_t = str(cur_seg.get("original_text", ""))
                        s_name = str(entry.get("speaker_name") or p1_e.get("speaker_name") or "")
                        spk = str(entry.get("speaker") or p1_e.get("speaker") or payload[min(position, len(payload) - 1)].get("speaker", "hero")).lower()
                        raw_gen = str(entry.get("gender") or p1_e.get("gender") or payload[min(position, len(payload) - 1)].get("gender", "male")).lower()
                        ac_gen = str(cur_seg.get("acoustic_gender") or "").lower()
                        spk_cluster = cur_seg.get("speaker_id", "spk_0")
                        cluster_role = speaker_map.get(spk_cluster)

                        matched_r = cur_seg.get("matched_role")
                        matched_g = cur_seg.get("matched_gender")
                        matched_sim = float(cur_seg.get("matched_sim", 0.0))

                        p1_spk = str(p1_e.get("speaker") or entry.get("speaker") or "").lower()
                        p1_gen = str(p1_e.get("gender") or entry.get("gender") or "").lower()
                        ac_pitch = float(cur_seg.get("pitch_hz", 0.0))

                        # --- Universal Consensus Arbitrator ---
                        semantic_role = None
                        # Cast-Bound Character Dubbing Architecture (CCDA)
                        ROLE_GENDER_MAP = {
                            "king": "male",
                            "emperor": "male",
                            "hero": "male",
                            "villain": "male",
                            "father": "male",
                            "extra_male": "male",
                            "supporting_male": "male",
                            "heroine": "female",
                            "mistress": "female",
                            "mother": "female",
                            "extra_female": "female",
                            "supporting_female": "female",
                            "system": "female",
                        }

                        # Step 1: Detect Character Role directly from Story & Dialogue Context
                        s_name_lower = str(s_name or p1_e.get("speaker_name") or "").lower()
                        orig_lower = str(orig_t).lower()

                        if any(w in s_name_lower for w in ("सम्राट", "राजा", "महाराज", "king", "emperor", "陛下", "皇帝", "श्याओ तियान")) or any(w in orig_lower for w in ("朕", "本皇", "本帝")):
                            spk = "king"
                            s_name = s_name or "सम्राट"
                        elif "叮" in orig_t or "本系统" in orig_t or "【系统" in orig_t:
                            spk = "system"
                            s_name = "सिस्टम"
                        elif p1_spk in ROLE_GENDER_MAP:
                            spk = p1_spk
                        elif entry.get("speaker") and str(entry.get("speaker")).lower() in ROLE_GENDER_MAP:
                            spk = str(entry.get("speaker")).lower()
                        elif matched_r in ROLE_GENDER_MAP and matched_sim >= 0.70:
                            spk = matched_r
                        else:
                            spk = "heroine" if protagonist_gender == "female" else "hero"

                        # Step 2: Determine Gender Directly from Character Role
                        # A King is ALWAYS Male. A Heroine is ALWAYS Female.
                        # No background music audio pitch can EVER override character gender!
                        gen = ROLE_GENDER_MAP.get(spk, "female" if "female" in spk else "male")
                        is_fem = (gen == "female")

                        # Ensure consistent name dynamically from Pass 1 or Protagonist profile
                        if not s_name:
                            if spk == "king":
                                s_name = "सम्राट"
                            elif spk in ("hero", "heroine") and protagonist_name:
                                s_name = protagonist_name
                            elif spk == "system":
                                s_name = "सिस्टम"
                            elif spk == "mother":
                                s_name = "माँ"
                            elif spk == "father":
                                s_name = "पिताजी"
                            elif spk == "mistress":
                                s_name = "सौतेली बहन" if "बहन" in orig_t else "विरोधी"
                            elif spk == "extra_female":
                                s_name = "महिला"
                            elif spk == "extra_male":
                                s_name = "सहायक"
                            else:
                                s_name = spk.capitalize()

                        speaker_by_id[seg_id] = spk
                        gender_by_id[seg_id] = "female" if is_fem else "male"
                        speaker_name_by_id[seg_id] = s_name
                        emotion_by_id[seg_id] = str(entry.get("emotion") or "neutral").lower()
                        emotion_by_id[seg_id] = str(entry.get("emotion") or "neutral").lower()

                covered = sum(1 for item in payload if item["id"] in recap_by_id)
                log.info(
                    "  Pass 2 batch %d/%d -> %d/%d segment(s) scripted in %s",
                    batch_index,
                    len(batches),
                    covered,
                    len(payload),
                    mode_label,
                )
                last_error = None
                if len(clients) > 1:
                    client_idx += 1
                break

            except PipelineError as exc:
                last_error = exc
                log.warning("  Pass 2 batch %d attempt %d failed: %s", batch_index, attempt, exc)
                if len(clients) > 1:
                    client_idx += 1
                    log.info("  rotating to next API key (%d/%d)...", (client_idx % len(clients)) + 1, len(clients))
                if attempt < max_retries:
                    time.sleep(min(30.0, 2.0 ** attempt))
            except Exception as exc:  # network / SDK / quota errors
                last_error = exc
                log.warning("  Pass 2 batch %d attempt %d errored: %s", batch_index, attempt, exc)
                if len(clients) > 1:
                    client_idx += 1
                    log.info("  rotating to next API key (%d/%d)...", (client_idx % len(clients)) + 1, len(clients))
                if attempt < max_retries:
                    time.sleep(min(30.0, 2.0 ** attempt))

        if last_error is not None:
            log.error(
                "  Pass 2 batch %d exhausted all retries (%s); falling back to Pass 1 translation.",
                batch_index,
                last_error,
            )

    # ----------------------------------------------------------------------- #
    # Assemble final dub_segments
    # ----------------------------------------------------------------------- #
    dub_segments: list[dict] = []
    missing = 0
    for position, seg in enumerate(segments):
        seg_id = int(seg.get("id", position))
        recap = recap_by_id.get(seg_id, "")
        p1_entry = pass1_data_by_id.get(seg_id, {})
        if not recap:
            recap = _clean_text(p1_entry.get("literal_translation")) or _fallback_text(seg, target_lang)
            missing += 1

        # The Consensus Arbitrator in Pass 2 already computed the final speaker role, gender, and name!
        seg_spk = speaker_by_id.get(seg_id) or str(p1_entry.get("speaker") or ("heroine" if protagonist_gender == "female" else "hero")).lower()
        seg_gender = gender_by_id.get(seg_id) or ("female" if seg_spk in ("heroine", "mother", "mistress", "extra_female", "supporting_female", "system") else "male")
        seg_name = speaker_name_by_id.get(seg_id) or str(p1_entry.get("speaker_name") or "")

        # High-confidence centroid alignment (sim >= 0.70) can ONLY refine generic/unknown roles!
        if seg_spk not in ("heroine", "mother", "mistress", "hero", "system", "supporting_female"):
            if matched_r and matched_sim >= 0.70 and matched_g == seg_gender:
                seg_spk = matched_r

        # Strict Gender Guardrail
        if seg_spk in ("heroine", "mother", "mistress", "extra_female", "supporting_female", "system"):
            seg_gender = "female"
        elif seg_spk in ("hero", "extra_male", "father", "villain"):
            seg_gender = "male"

        seg_emotion = emotion_by_id.get(seg_id)
        if not seg_emotion or seg_emotion == "neutral":
            seg_emotion = seg.get("detected_emotion") or "neutral"

        dub_segments.append(
            {
                "id": seg_id,
                "start": round(float(seg.get("start", 0.0)), 3),
                "end": round(float(seg.get("end", 0.0)), 3),
                "duration": round(float(seg.get("duration", 0.0)), 3),
                "original_text": str(seg.get("original_text", "")),
                "recap_text": recap,
                "speaker": seg_spk,
                "speaker_name": seg_name,
                "gender": seg_gender,
                "emotion": seg_emotion,
                "detected_emotion": seg.get("detected_emotion", "neutral"),
                "audio_event": seg.get("audio_event", "speech"),
                "speaker_id": seg.get("speaker_id", "spk_0"),
                "pitch_hz": seg.get("pitch_hz", 0.0),
                "acoustic_gender": seg.get("acoustic_gender", "unknown"),
                "matched_role": seg.get("matched_role", ""),
                "matched_gender": seg.get("matched_gender", ""),
                "matched_voice": seg.get("matched_voice", ""),
                "matched_pitch": seg.get("matched_pitch", "+0Hz"),
                "matched_rate": seg.get("matched_rate", "+0%"),
                "matched_sim": float(seg.get("matched_sim", 0.0)),
                "language": target_lang,
                "protagonist_name": protagonist_name,
                "protagonist_gender": protagonist_gender,
            }
        )

    if missing:
        log.warning("%d/%d segment(s) used fallback narration.", missing, len(segments))
    log.info(
        "Recap script ready: %d segment(s) [Protagonist: '%s' (%s)].",
        len(dub_segments),
        protagonist_name,
        protagonist_gender,
    )

    # Apply Dialogue Continuity & Voice Flip Smoothing
    dub_segments = smooth_dialogue_speakers(
        dub_segments,
        protagonist_gender=protagonist_gender,
        protagonist_name=protagonist_name,
    )

    if cache_path:
        write_json(cache_path, dub_segments)

    return dub_segments


def smooth_dialogue_speakers(
    segments: list[dict],
    protagonist_gender: str = "female",
    protagonist_name: str = "",
) -> list[dict]:
    """Cast-Bound Character Dubbing Architecture (CCDA) - Role & Gender Lock Validator.

    Guarantees:
    1. Character identity determines voice & gender deterministically.
    2. The Emperor / King is IMMUTABLY Male ('king', 'hi-IN-MadhurNeural').
    3. Male roles (king, hero, father, villain, extra_male) are 100% Male.
    4. Female roles (heroine, mistress, mother, extra_female) are 100% Female.
    5. Consecutive micro-fragments from the same speaker maintain identical role & gender.
    6. Zero reliance on noisy background music audio pitch!
    """
    if not segments:
        return segments

    FEMALE_ROLES = {"heroine", "mother", "mistress", "extra_female", "supporting_female", "system"}
    MALE_ROLES = {"king", "emperor", "hero", "extra_male", "father", "villain", "supporting_male", "driver", "bystander"}

    for i, s in enumerate(segments):
        s_name = str(s.get("speaker_name") or "")
        s_name_lower = s_name.lower()
        orig_text = str(s.get("original_text") or "")
        role = str(s.get("speaker") or "").lower()

        # Rule 1: The Emperor / King Lock
        if any(w in s_name_lower for w in ("सम्राट", "राजा", "महाराज", "king", "emperor", "陛下", "皇帝", "श्याओ तियान")) or any(w in orig_text for w in ("朕", "本皇", "本帝")):
            s["speaker"] = "king"
            s["gender"] = "male"
            s["speaker_name"] = "सम्राट"
            continue

        # Rule 2: Continuation - if a short fragment (<= 0.35s gap) has no distinct speaker,
        # it belongs to the previous speaker continuing their thought.
        if i > 0:
            prev = segments[i - 1]
            gap_prev = float(s["start"]) - float(prev["end"])
            if gap_prev <= 0.35 and (not s_name or s_name == prev.get("speaker_name") or role in ("extra_male", "extra_female")):
                prev_role = str(prev.get("speaker") or "").lower()
                if prev_role in MALE_ROLES or prev_role in FEMALE_ROLES:
                    s["speaker"] = prev_role
                    s["gender"] = prev.get("gender")
                    s["speaker_name"] = prev.get("speaker_name")
                    continue

        # Rule 3: Role & Gender Synchronization
        cur_role = str(s.get("speaker") or "").lower()
        if cur_role in MALE_ROLES:
            s["gender"] = "male"
        elif cur_role in FEMALE_ROLES:
            s["gender"] = "female"
        else:
            if protagonist_gender == "female" and cur_role in ("heroine", "hero"):
                s["speaker"] = "heroine"
                s["gender"] = "female"
            elif protagonist_gender == "male" and cur_role in ("heroine", "hero"):
                s["speaker"] = "hero"
                s["gender"] = "male"
            else:
                s["gender"] = "female" if "female" in cur_role else "male"

    return segments


def build_story_context(dub_segments: Iterable[dict], max_chars: int = 900) -> str:
    """Condense already-localized segments into a context blurb for the next episode.

    Feeding this back into ``story_context`` keeps character names and protagonist
    perspective stable across a series compilation.
    """
    pieces: list[str] = []
    protagonist_name = ""
    protagonist_gender = ""
    total = 0
    for seg in dub_segments:
        if not protagonist_name and seg.get("protagonist_name"):
            protagonist_name = seg["protagonist_name"]
        if not protagonist_gender and seg.get("protagonist_gender"):
            protagonist_gender = seg["protagonist_gender"]
        text = str(seg.get("recap_text", "")).strip()
        if not text:
            continue
        pieces.append(text)
        total += len(text)
        if total >= max_chars:
            break
    blurb = " ".join(pieces)[:max_chars]
    header = ""
    if protagonist_name:
        header = f"Protagonist: {protagonist_name} ({protagonist_gender}). "
    return f"{header}Previously in this series: {blurb}" if blurb else ""
