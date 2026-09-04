# Voice Cloning Reference Directory

Place your 5 to 10 second clean reference audio clip here to clone any narrator voice using **F5-TTS**.

### Requirements for Best Cloning Quality:
1. **Filename:** `narrator_ref.wav` (WAV format, 16kHz or 24kHz or 44.1kHz mono).
2. **Duration:** 5 to 10 seconds of clear, uninterrupted speech.
3. **No Background Noise:** No background music, echo, or sound effects.
4. **Matching Reference Text:** The exact spoken words of `narrator_ref.wav` must be set in `config/settings.json` under `f5_tts.ref_text`.

### Example:
```json
"f5_tts": {
  "model_name": "F5-TTS",
  "ref_audio_path": "storage/voice_reference/narrator_ref.wav",
  "ref_text": "इस दुनिया में कमजोर की कोई जगह नहीं है, ताकत ही सब कुछ तय करती है।",
  "device": "cuda",
  "speed": 1.0
}
```
