"""Automated Multi-Emotion Reference Voice Bank Builder.

Generates and maintains clean, studio-acoustics 24kHz reference WAV clips
and Devanagari transcripts for F5-TTS Zero-Shot In-Context Cloning across
diverse characters (Hero, Heroine, Villain, Elders, Common) and emotional
states (Calm, Angry, Sad, Fierce).
"""

from __future__ import annotations

import asyncio
import os
import subprocess
from typing import Any

from . import ensure_dir, log, require_binary

VOICE_PROFILES: dict[str, dict[str, Any]] = {
    "heroine_calm": {
        "text": "मैं इस दुनिया की सबसे ताकतवर महारानी बनकर रहूंगी, मुझे कोई नहीं रोक सकता।",
        "voice": "hi-IN-SwaraNeural",
        "pitch": "+10Hz",
        "rate": "+2%",
        "filename": "heroine_calm.wav",
        "description": "Sweet, confident young female protagonist (calm / normal)",
    },
    "heroine_angry": {
        "text": "तुम्हारी इतनी हिम्मत कैसे हुई मेरे सामने खड़े होने की! अब भुगतो!",
        "voice": "hi-IN-SwaraNeural",
        "pitch": "+22Hz",
        "rate": "+12%",
        "filename": "heroine_angry.wav",
        "description": "Fierce, screaming, highly emotional female lead (rage / combat)",
    },
    "heroine_sad": {
        "text": "सब कुछ खत्म हो गया... क्या मैं वाकई इस मुश्किल से बच पाऊंगी?",
        "voice": "hi-IN-SwaraNeural",
        "pitch": "-8Hz",
        "rate": "-10%",
        "filename": "heroine_sad.wav",
        "description": "Trembling, wounded, sorrowful female lead (crying / grief)",
    },
    "hero_calm": {
        "text": "इस दुनिया में कमजोर की कोई जगह नहीं है, ताकत ही सब कुछ तय करती है।",
        "voice": "hi-IN-MadhurNeural",
        "pitch": "-5Hz",
        "rate": "+0%",
        "filename": "hero_calm.wav",
        "description": "Authoritative, commanding young male protagonist",
    },
    "hero_angry": {
        "text": "रुक जाओ वहीं! आज कोई भी तुम्हें मेरे गुस्से से नहीं बचा सकता!",
        "voice": "hi-IN-MadhurNeural",
        "pitch": "-15Hz",
        "rate": "+10%",
        "filename": "hero_angry.wav",
        "description": "Furious, battle-ready male protagonist shout",
    },
    "villain_aggressive": {
        "text": "हा हा हा, तुम सब कीड़े-मकोड़े हो! मेरे सामने तुम्हारी कोई औकात नहीं!",
        "voice": "hi-IN-MadhurNeural",
        "pitch": "-35Hz",
        "rate": "-3%",
        "filename": "villain_aggressive.wav",
        "description": "Cruel, menacing, deep-toned male villain",
    },
    "elder_male": {
        "text": "धैर्य रखो बेटा, जीवन में हर परीक्षा का एक समय होता है।",
        "voice": "hi-IN-MadhurNeural",
        "pitch": "-28Hz",
        "rate": "-8%",
        "filename": "elder_male.wav",
        "description": "Wise, deep, slow-cadence elder master / father",
    },
    "common_male": {
        "text": "अरे भाई, देखो वहां क्या हो रहा है! चलो जल्दी भागो यहां से!",
        "voice": "hi-IN-MadhurNeural",
        "pitch": "+0Hz",
        "rate": "+0%",
        "filename": "common_male.wav",
        "description": "Neutral conversational common male / guards / bystanders",
    },
    "common_female": {
        "text": "दीदी, बाहर बहुत भीड़ जमा हो गई है, जरा संभल कर रहना।",
        "voice": "hi-IN-SwaraNeural",
        "pitch": "+8Hz",
        "rate": "+2%",
        "filename": "common_female.wav",
        "description": "Neutral conversational common female / maids / passersby",
    },
}


async def _generate_single_reference(
    profile_id: str,
    profile_data: dict[str, Any],
    target_dir: str,
    ffmpeg: str,
) -> str:
    """Generate a 24kHz mono reference WAV file using Edge-TTS synthesis and FFmpeg transcoding."""
    import edge_tts

    out_wav = os.path.join(target_dir, profile_data["filename"])
    if os.path.isfile(out_wav) and os.path.getsize(out_wav) > 1024:
        log.debug("Voice reference '%s' already exists at %s", profile_id, out_wav)
        return out_wav

    temp_mp3 = os.path.join(target_dir, f"_temp_{profile_id}.mp3")
    log.info("Building reference voice audio for '%s' (%s)...", profile_id, profile_data["voice"])

    comm = edge_tts.Communicate(
        text=profile_data["text"],
        voice=profile_data["voice"],
        pitch=profile_data.get("pitch", "+0Hz"),
        rate=profile_data.get("rate", "+0%"),
    )
    await comm.save(temp_mp3)

    # Convert to 24000Hz mono 16-bit PCM WAV (ideal for F5-TTS and Vocos)
    cmd = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        temp_mp3,
        "-ar",
        "24000",
        "-ac",
        "1",
        out_wav,
    ]
    subprocess.run(cmd, check=True)

    if os.path.isfile(temp_mp3):
        try:
            os.remove(temp_mp3)
        except OSError:
            pass

    log.info("Created reference voice clip: %s (size: %d bytes)", out_wav, os.path.getsize(out_wav))
    return out_wav


def build_reference_voice_bank(target_dir: str = "storage/voice_reference") -> dict[str, dict[str, Any]]:
    """Ensure the complete multi-emotion voice reference library exists on disk."""
    ffmpeg = require_binary("ffmpeg")
    target_dir = ensure_dir(os.path.abspath(target_dir))

    # Also check if existing custom ravi_gupta.wav or narrator_ref.wav exist
    ravi_path = os.path.join(target_dir, "ravi_gupta.wav")
    if os.path.isfile(ravi_path) and os.path.getsize(ravi_path) > 1024:
        VOICE_PROFILES["hero_calm"]["filename"] = "ravi_gupta.wav"
        VOICE_PROFILES["hero_calm"]["text"] = (
            "उन्होंने बहुत कम रखा, दो तीन हजार पर बात फसी हुई थी और उनका जो मटेरियल था, "
            "वो प्रीमियम नहीं था, सुपारी उनकी मसूले में चुप गई थी मेरे"
        )

    async def _build_all():
        tasks = [
            _generate_single_reference(pid, pdata, target_dir, ffmpeg)
            for pid, pdata in VOICE_PROFILES.items()
        ]
        await asyncio.gather(*tasks)

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import nest_asyncio
            nest_asyncio.apply()
            loop.run_until_complete(_build_all())
        else:
            loop.run_until_complete(_build_all())
    except RuntimeError:
        asyncio.run(_build_all())

    # Build manifest
    manifest: dict[str, dict[str, Any]] = {}
    for pid, pdata in VOICE_PROFILES.items():
        wav_path = os.path.join(target_dir, pdata["filename"])
        manifest[pid] = {
            "ref_audio": wav_path,
            "ref_text": pdata["text"],
            "description": pdata["description"],
            "exists": os.path.isfile(wav_path),
        }
    return manifest


if __name__ == "__main__":
    result = build_reference_voice_bank()
    print("Voice Bank Ready:")
    for k, v in result.items():
        print(f"  [{k}] -> {v['ref_audio']} ({'EXISTS' if v['exists'] else 'MISSING'})")
