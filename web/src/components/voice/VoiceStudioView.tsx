import { useState } from 'react'
import { Mic, Play, Volume2, Sparkles, Sliders, CheckCircle2, Radio } from 'lucide-react'
import { synthesizeVoicePreview } from '../../services/api'

export const VoiceStudioView: React.FC = () => {
  const [text, setText] = useState(
    'उस रात लिन फेंग को पहली बार अपनी ही सेक्ट के गद्दार एल्डर्स के असली चेहरे का एहसास हुआ...'
  )
  const [engine, setEngine] = useState('f5-tts')
  const [speed, setSpeed] = useState(1.05)
  const [emotion, setEmotion] = useState('Dramatic Xianxia')
  const [isSynthesizing, setIsSynthesizing] = useState(false)
  const [audioUrl, setAudioUrl] = useState<string | null>(null)
  const [statusMsg, setStatusMsg] = useState<string | null>(null)

  const handleSynthesize = async () => {
    if (!text.trim()) return
    setIsSynthesizing(true)
    setStatusMsg('Synthesizing speech on engine...')
    try {
      const res = await synthesizeVoicePreview({
        text,
        engine,
        speed,
        emotion,
      })
      setAudioUrl(`${res.audio_url}?t=${Date.now()}`)
      setStatusMsg('Synthesis complete! Ready to playback.')
    } catch (err: any) {
      setStatusMsg(`Error: ${err.message}`)
    } finally {
      setIsSynthesizing(false)
    }
  }

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-5 rounded-2xl bg-zinc-900/60 border border-zinc-800/80 backdrop-blur-sm">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400">
            <Mic className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-base font-bold text-zinc-100">Voice Studio & Zero-Shot Cloning</h2>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                F5-TTS + EDGE-TTS HYBRID
              </span>
            </div>
            <p className="text-xs text-zinc-400 mt-0.5">
              Diffusion Transformer voice cloning with Devanagari transliteration and duration warping.
            </p>
          </div>
        </div>

        {statusMsg && (
          <span className="text-xs font-mono px-3 py-1.5 rounded-lg bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
            {statusMsg}
          </span>
        )}
      </div>

      {/* 2-Column Voice Studio Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left: Synth Controls (7 cols) */}
        <div className="lg:col-span-7 space-y-4">
          <div className="p-5 rounded-2xl bg-zinc-900/60 border border-zinc-800/80 space-y-4">
            <div className="flex items-center justify-between pb-2 border-b border-zinc-800">
              <h3 className="text-xs font-semibold text-zinc-300 uppercase tracking-wider flex items-center gap-2">
                <Sliders className="w-4 h-4 text-indigo-400" />
                Acoustic Parameters
              </h3>

              {/* Engine Toggle */}
              <div className="flex bg-black/60 p-1 rounded-xl border border-zinc-800">
                <button
                  onClick={() => setEngine('f5-tts')}
                  className={`px-3 py-1 rounded-lg text-xs font-mono font-semibold transition-all ${
                    engine === 'f5-tts'
                      ? 'bg-indigo-600 text-white shadow-sm'
                      : 'text-zinc-400 hover:text-zinc-200'
                  }`}
                >
                  F5-TTS (Local GPU)
                </button>
                <button
                  onClick={() => setEngine('edge-tts')}
                  className={`px-3 py-1 rounded-lg text-xs font-mono font-semibold transition-all ${
                    engine === 'edge-tts'
                      ? 'bg-indigo-600 text-white shadow-sm'
                      : 'text-zinc-400 hover:text-zinc-200'
                  }`}
                >
                  Edge-TTS (Cloud)
                </button>
              </div>
            </div>

            {/* Test Text Input */}
            <div>
              <label className="text-[11px] font-mono uppercase text-zinc-400 block mb-1">
                Hindi Dramatic Dialogue Script
              </label>
              <textarea
                rows={4}
                value={text}
                onChange={(e) => setText(e.target.value)}
                className="w-full p-3 rounded-xl bg-black/60 border border-zinc-800 text-xs font-sans text-indigo-100 focus:outline-none focus:border-indigo-500 leading-relaxed font-medium"
              />
            </div>

            {/* Sliders */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <div className="flex justify-between text-xs font-mono text-zinc-400 mb-1">
                  <span>Speed Warp</span>
                  <span className="text-indigo-400 font-bold">{speed}x</span>
                </div>
                <input
                  type="range"
                  min="0.85"
                  max="1.30"
                  step="0.05"
                  value={speed}
                  onChange={(e) => setSpeed(parseFloat(e.target.value))}
                  className="w-full accent-indigo-500"
                />
              </div>

              <div>
                <label className="text-[11px] font-mono uppercase text-zinc-400 block mb-1">
                  Emotional Delivery
                </label>
                <select
                  value={emotion}
                  onChange={(e) => setEmotion(e.target.value)}
                  className="w-full px-3 py-1.5 rounded-xl bg-black/60 border border-zinc-800 text-xs text-zinc-200 focus:outline-none"
                >
                  <option>Dramatic Xianxia</option>
                  <option>Epic Thunder Battle</option>
                  <option>Tragic Betrayal</option>
                  <option>Mysterious Lore</option>
                </select>
              </div>
            </div>

            <button
              onClick={handleSynthesize}
              disabled={isSynthesizing}
              className="w-full flex items-center justify-center gap-2 py-3 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:bg-zinc-800 text-white text-xs font-semibold tracking-wide transition-all shadow-md shadow-indigo-600/20"
            >
              {isSynthesizing ? (
                <>
                  <Radio className="w-4 h-4 animate-spin text-amber-400" />
                  <span>Synthesizing Voiceover on GPU...</span>
                </>
              ) : (
                <>
                  <Sparkles className="w-4 h-4" />
                  <span>Synthesize Voice Sample ({engine.toUpperCase()})</span>
                </>
              )}
            </button>
          </div>
        </div>

        {/* Right: Audio Playback & Voice Reference (5 cols) */}
        <div className="lg:col-span-5 space-y-4">
          {/* Synthesized Output Player */}
          <div className="p-5 rounded-2xl bg-zinc-900/60 border border-zinc-800/80 space-y-4">
            <h3 className="text-xs font-semibold text-zinc-300 uppercase tracking-wider pb-2 border-b border-zinc-800 flex items-center gap-2">
              <Volume2 className="w-4 h-4 text-emerald-400" />
              Generated Audio Monitor
            </h3>

            {audioUrl ? (
              <div className="space-y-3">
                <audio controls src={audioUrl} className="w-full" autoPlay />
                <div className="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-xs font-mono text-emerald-300 flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 shrink-0" />
                  <span>Audio synthesized successfully. Latency ~0.8s on RTX 4060.</span>
                </div>
              </div>
            ) : (
              <div className="py-10 text-center text-xs text-zinc-500 font-mono italic border border-dashed border-zinc-800 rounded-xl">
                Synthesize a phrase on the left to preview generated audio.
              </div>
            )}
          </div>

          {/* Reference Audio Card */}
          <div className="p-4 rounded-xl bg-black/60 border border-zinc-800 text-xs space-y-2 font-mono">
            <span className="text-[10px] uppercase text-zinc-500 block">
              Active Voice Clone Reference:
            </span>
            <div className="flex items-center justify-between text-zinc-200">
              <span>narrator_ref.wav</span>
              <span className="text-indigo-400">5.0s PCM 24kHz</span>
            </div>
            <p className="text-[11px] text-zinc-400 font-sans">
              Path: storage/voice_reference/narrator_ref.wav
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
