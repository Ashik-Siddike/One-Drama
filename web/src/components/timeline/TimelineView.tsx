import { useState } from 'react'
import { Clock, Play, Pause, ZoomIn, ZoomOut, Bookmark, Scissors, Layers } from 'lucide-react'

export const TimelineView: React.FC = () => {
  const [isPlaying, setIsPlaying] = useState(false)
  const [currentTime, setCurrentTime] = useState(45.2)

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-5 rounded-2xl bg-zinc-900/60 border border-zinc-800/80 backdrop-blur-sm">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-blue-500/10 border border-blue-500/20 flex items-center justify-center text-blue-400">
            <Clock className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-base font-bold text-zinc-100">Multi-Track Production Timeline</h2>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-blue-500/10 text-blue-400 border border-blue-500/20">
                FRAME-ACCURATE NLE
              </span>
            </div>
            <p className="text-xs text-zinc-400 mt-0.5">
              Full movie assembly timeline with synchronized video, voiceover, BGM stems, and YouTube chapter cues.
            </p>
          </div>
        </div>

        {/* Transport Controls */}
        <div className="flex items-center gap-3">
          <div className="px-4 py-2 rounded-xl bg-black/60 border border-zinc-800 font-mono text-xs font-bold text-indigo-400">
            00:02:31.07 / 02:30:00.00
          </div>

          <button
            onClick={() => setIsPlaying(!isPlaying)}
            className="p-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white shadow-md shadow-indigo-600/20"
          >
            {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4 fill-current ml-0.5" />}
          </button>
        </div>
      </div>

      {/* Multi-Track Canvas */}
      <div className="p-5 rounded-2xl bg-zinc-900/60 border border-zinc-800/80 space-y-4">
        {/* Toolbar */}
        <div className="flex items-center justify-between pb-3 border-b border-zinc-800 text-xs">
          <div className="flex items-center gap-2">
            <button className="p-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-300">
              <Scissors className="w-4 h-4" />
            </button>
            <button className="p-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-300">
              <Bookmark className="w-4 h-4" />
            </button>
            <span className="text-zinc-600">|</span>
            <span className="font-mono text-zinc-400 text-[11px]">Snapping: ON (Frame)</span>
          </div>

          <div className="flex items-center gap-2 text-zinc-400">
            <button className="p-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-300">
              <ZoomOut className="w-3.5 h-3.5" />
            </button>
            <span className="font-mono text-[11px]">100%</span>
            <button className="p-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-300">
              <ZoomIn className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        {/* Tracks List */}
        <div className="space-y-2">
          {/* Time Ruler */}
          <div className="h-6 w-full bg-black/60 rounded-lg flex items-center justify-between px-4 font-mono text-[10px] text-zinc-500 border border-zinc-800/60">
            <span>00:00</span>
            <span>00:30</span>
            <span>01:00</span>
            <span>01:30</span>
            <span>02:00</span>
            <span>02:30</span>
          </div>

          {/* Track 1: Video */}
          <div className="flex items-center gap-3">
            <div className="w-24 shrink-0 font-mono text-[11px] text-zinc-400 font-semibold">
              V1 (Video)
            </div>
            <div className="flex-1 h-12 bg-indigo-950/40 border border-indigo-500/30 rounded-lg relative overflow-hidden flex items-center px-3">
              <span className="text-xs font-mono text-indigo-300 font-semibold truncate">
                ep_001_dubbed.mp4 [1280x720 30fps Lanczos]
              </span>
            </div>
          </div>

          {/* Track 2: Voiceover */}
          <div className="flex items-center gap-3">
            <div className="w-24 shrink-0 font-mono text-[11px] text-emerald-400 font-semibold">
              A1 (Hindi Voice)
            </div>
            <div className="flex-1 h-12 bg-emerald-950/40 border border-emerald-500/30 rounded-lg relative overflow-hidden flex items-center px-3 gap-1">
              {Array.from({ length: 12 }).map((_, i) => (
                <div
                  key={i}
                  className="flex-1 h-8 bg-emerald-500/30 border border-emerald-500/50 rounded flex items-center justify-center text-[10px] font-mono text-emerald-300 truncate px-1"
                >
                  Cue {i + 1}
                </div>
              ))}
            </div>
          </div>

          {/* Track 3: BGM */}
          <div className="flex items-center gap-3">
            <div className="w-24 shrink-0 font-mono text-[11px] text-purple-400 font-semibold">
              A2 (Demucs BGM)
            </div>
            <div className="flex-1 h-12 bg-purple-950/40 border border-purple-500/30 rounded-lg relative overflow-hidden flex items-center px-3">
              <span className="text-xs font-mono text-purple-300 truncate">
                no_vocals.wav [35% Ducking Automated Envelope]
              </span>
            </div>
          </div>

          {/* Track 4: SFX */}
          <div className="flex items-center gap-3">
            <div className="w-24 shrink-0 font-mono text-[11px] text-amber-400 font-semibold">
              A3 (SFX Hits)
            </div>
            <div className="flex-1 h-8 bg-black/50 border border-zinc-800 rounded-lg relative flex items-center px-4">
              <div className="w-4 h-4 rounded-full bg-amber-500/30 border border-amber-500 text-[9px] font-mono text-amber-300 flex items-center justify-center">
                !
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
