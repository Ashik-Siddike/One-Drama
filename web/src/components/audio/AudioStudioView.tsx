import { useState } from 'react'
import { Music, Volume2, Sliders, Activity, Mic, VolumeX, ShieldCheck } from 'lucide-react'

export const AudioStudioView: React.FC = () => {
  const [bgmDucking, setBgmDucking] = useState(0.35)
  const [voiceVol, setVoiceVol] = useState(1.0)
  const [sfxVol, setSfxVol] = useState(0.8)
  const [ambientVol, setAmbientVol] = useState(0.5)

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-5 rounded-2xl bg-zinc-900/60 border border-zinc-800/80 backdrop-blur-sm">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-purple-500/10 border border-purple-500/20 flex items-center justify-center text-purple-400">
            <Music className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-base font-bold text-zinc-100">Audio Studio & Mini DAW</h2>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-purple-500/10 text-purple-400 border border-purple-500/20">
                DYNAMIC DUCKING & REMIX
              </span>
            </div>
            <p className="text-xs text-zinc-400 mt-0.5">
              Demucs instrumental stem mixing, automatic dialogue ducking (-18dB), and LUFS broadcast mastering.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-xs font-mono">
          <ShieldCheck className="w-4 h-4" />
          <span>YouTube Standard: -14.0 LUFS</span>
        </div>
      </div>

      {/* Multi-Track Mixer Board */}
      <div className="p-6 rounded-2xl bg-zinc-900/60 border border-zinc-800/80 space-y-5">
        <h3 className="text-xs font-semibold text-zinc-300 uppercase tracking-wider pb-3 border-b border-zinc-800 flex items-center gap-2">
          <Sliders className="w-4 h-4 text-indigo-400" />
          4-Stem Channel Mixer
        </h3>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {/* Channel 1: Narration */}
          <div className="p-4 rounded-xl bg-black/60 border border-indigo-500/30 space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-indigo-300 flex items-center gap-1.5">
                <Mic className="w-3.5 h-3.5 text-indigo-400" />
                Narration Track
              </span>
              <span className="text-[10px] font-mono text-indigo-400">CH 1</span>
            </div>

            <div className="h-44 flex flex-col items-center justify-between py-2">
              <input
                type="range"
                min="0.0"
                max="1.5"
                step="0.05"
                value={voiceVol}
                onChange={(e) => setVoiceVol(parseFloat(e.target.value))}
                className="h-32 accent-indigo-500"
              />
              <span className="text-xs font-mono font-bold text-zinc-200 mt-2">
                {Math.round(voiceVol * 100)}%
              </span>
            </div>

            <div className="pt-2 border-t border-zinc-800 flex justify-center gap-2">
              <button className="px-2 py-1 rounded text-[10px] font-mono bg-zinc-800 text-zinc-300">
                SOLO
              </button>
              <button className="px-2 py-1 rounded text-[10px] font-mono bg-zinc-800 text-zinc-300">
                MUTE
              </button>
            </div>
          </div>

          {/* Channel 2: BGM Ducking */}
          <div className="p-4 rounded-xl bg-black/60 border border-purple-500/30 space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-purple-300 flex items-center gap-1.5">
                <Music className="w-3.5 h-3.5 text-purple-400" />
                BGM (Demucs)
              </span>
              <span className="text-[10px] font-mono text-purple-400">CH 2</span>
            </div>

            <div className="h-44 flex flex-col items-center justify-between py-2">
              <input
                type="range"
                min="0.10"
                max="0.80"
                step="0.05"
                value={bgmDucking}
                onChange={(e) => setBgmDucking(parseFloat(e.target.value))}
                className="h-32 accent-purple-500"
              />
              <span className="text-xs font-mono font-bold text-zinc-200 mt-2">
                Ducking: {Math.round(bgmDucking * 100)}%
              </span>
            </div>

            <div className="pt-2 border-t border-zinc-800 flex justify-center gap-2">
              <button className="px-2 py-1 rounded text-[10px] font-mono bg-zinc-800 text-zinc-300">
                SOLO
              </button>
              <button className="px-2 py-1 rounded text-[10px] font-mono bg-zinc-800 text-zinc-300">
                MUTE
              </button>
            </div>
          </div>

          {/* Channel 3: SFX */}
          <div className="p-4 rounded-xl bg-black/60 border border-amber-500/30 space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-amber-300 flex items-center gap-1.5">
                <Activity className="w-3.5 h-3.5 text-amber-400" />
                Battle SFX
              </span>
              <span className="text-[10px] font-mono text-amber-400">CH 3</span>
            </div>

            <div className="h-44 flex flex-col items-center justify-between py-2">
              <input
                type="range"
                min="0.0"
                max="1.5"
                step="0.05"
                value={sfxVol}
                onChange={(e) => setSfxVol(parseFloat(e.target.value))}
                className="h-32 accent-amber-500"
              />
              <span className="text-xs font-mono font-bold text-zinc-200 mt-2">
                {Math.round(sfxVol * 100)}%
              </span>
            </div>

            <div className="pt-2 border-t border-zinc-800 flex justify-center gap-2">
              <button className="px-2 py-1 rounded text-[10px] font-mono bg-zinc-800 text-zinc-300">
                SOLO
              </button>
              <button className="px-2 py-1 rounded text-[10px] font-mono bg-zinc-800 text-zinc-300">
                MUTE
              </button>
            </div>
          </div>

          {/* Channel 4: Ambience */}
          <div className="p-4 rounded-xl bg-black/60 border border-emerald-500/30 space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-emerald-300 flex items-center gap-1.5">
                <Volume2 className="w-3.5 h-3.5 text-emerald-400" />
                Ambience
              </span>
              <span className="text-[10px] font-mono text-emerald-400">CH 4</span>
            </div>

            <div className="h-44 flex flex-col items-center justify-between py-2">
              <input
                type="range"
                min="0.0"
                max="1.0"
                step="0.05"
                value={ambientVol}
                onChange={(e) => setAmbientVol(parseFloat(e.target.value))}
                className="h-32 accent-emerald-500"
              />
              <span className="text-xs font-mono font-bold text-zinc-200 mt-2">
                {Math.round(ambientVol * 100)}%
              </span>
            </div>

            <div className="pt-2 border-t border-zinc-800 flex justify-center gap-2">
              <button className="px-2 py-1 rounded text-[10px] font-mono bg-zinc-800 text-zinc-300">
                SOLO
              </button>
              <button className="px-2 py-1 rounded text-[10px] font-mono bg-zinc-800 text-zinc-300">
                MUTE
              </button>
            </div>
          </div>
        </div>

        {/* Dynamic Ducking Curve Visualizer */}
        <div className="p-4 rounded-xl bg-black/80 border border-zinc-800 text-xs font-mono space-y-2">
          <div className="flex items-center justify-between text-zinc-400">
            <span>Dynamic BGM Ducking Envelope</span>
            <span className="text-purple-400">Voice Spoken: -18dB (35%) • Pauses: 85%</span>
          </div>

          <div className="h-16 w-full bg-zinc-950 rounded-lg p-2 flex items-center relative overflow-hidden">
            {/* Waveform graphic representation */}
            <div className="w-full h-8 flex items-center gap-1">
              {Array.from({ length: 48 }).map((_, i) => {
                const isSpeech = i >= 8 && i <= 36
                const height = isSpeech ? 12 : 32
                return (
                  <div
                    key={i}
                    className={`flex-1 rounded-sm transition-all ${
                      isSpeech ? 'bg-purple-600/70' : 'bg-purple-400'
                    }`}
                    style={{ height: `${height}px` }}
                  />
                )
              })}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
