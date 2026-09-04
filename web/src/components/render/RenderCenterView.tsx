import { useState } from 'react'
import { Film, CheckCircle2, Play, Radio, Cpu, HardDrive, Sparkles } from 'lucide-react'
import type { PipelineStatus } from '../../types'

interface RenderCenterViewProps {
  pipelineStatus: PipelineStatus | null
  onStartRender: () => Promise<void>
}

export const RenderCenterView: React.FC<RenderCenterViewProps> = ({
  pipelineStatus,
  onStartRender,
}) => {
  const [resolution, setResolution] = useState('1080p')
  const [codec, setCodec] = useState('libx264')
  const [fps, setFps] = useState('30')
  const [isStarting, setIsStarting] = useState(false)

  const isRunning = pipelineStatus?.is_running

  const handleRenderClick = async () => {
    setIsStarting(true)
    try {
      await onStartRender()
    } finally {
      setIsStarting(false)
    }
  }

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-5 rounded-2xl bg-zinc-900/60 border border-zinc-800/80 backdrop-blur-sm">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400">
            <Film className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-base font-bold text-zinc-100">Production Render Center</h2>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                GPU MASTER CONCAT
              </span>
            </div>
            <p className="text-xs text-zinc-400 mt-0.5">
              Batch remaster, audio ducking mix, and 2-3 hour full movie lossless concatenation.
            </p>
          </div>
        </div>

        <button
          onClick={handleRenderClick}
          disabled={isRunning || isStarting}
          className={`flex items-center gap-2 px-6 py-2.5 rounded-xl text-xs font-bold tracking-wide transition-all shadow-xl ${
            isRunning
              ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40 cursor-not-allowed'
              : 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-emerald-600/20 hover:shadow-emerald-600/30'
          }`}
        >
          {isRunning ? (
            <>
              <Radio className="w-4 h-4 animate-spin text-amber-400" />
              <span>Rendering in Progress...</span>
            </>
          ) : (
            <>
              <Play className="w-4 h-4 fill-current" />
              <span>START MASTER RENDER</span>
            </>
          )}
        </button>
      </div>

      {/* 2-Column Grid: Config & Checklist */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Render Profile Config */}
        <div className="p-5 rounded-2xl bg-zinc-900/60 border border-zinc-800/80 space-y-4">
          <h3 className="text-xs font-semibold text-zinc-300 uppercase tracking-wider pb-2 border-b border-zinc-800">
            Encoding Profile (FFmpeg remux)
          </h3>

          <div>
            <label className="text-[11px] font-mono uppercase text-zinc-400 block mb-1">
              Master Resolution
            </label>
            <div className="grid grid-cols-3 gap-2">
              {['720p (Fast)', '1080p (Full HD)', '4K (Ultra HD)'].map((r) => {
                const val = r.split(' ')[0]
                return (
                  <button
                    key={val}
                    onClick={() => setResolution(val)}
                    className={`py-2 rounded-xl text-xs font-mono font-semibold transition-all ${
                      resolution === val
                        ? 'bg-indigo-600 text-white'
                        : 'bg-black/60 text-zinc-400 border border-zinc-800 hover:text-zinc-200'
                    }`}
                  >
                    {val}
                  </button>
                )
              })}
            </div>
          </div>

          <div>
            <label className="text-[11px] font-mono uppercase text-zinc-400 block mb-1">
              Hardware Video Codec
            </label>
            <select
              value={codec}
              onChange={(e) => setCodec(e.target.value)}
              className="w-full px-3 py-2 rounded-xl bg-black/60 border border-zinc-800 text-xs text-zinc-200 focus:outline-none font-mono"
            >
              <option value="libx264">libx264 (Universal High Quality)</option>
              <option value="h264_nvenc">h264_nvenc (RTX 4060 GPU Turbo)</option>
              <option value="hevc_nvenc">hevc_nvenc (H.265 Space Saver)</option>
            </select>
          </div>

          <div>
            <label className="text-[11px] font-mono uppercase text-zinc-400 block mb-1">
              Framerate Target
            </label>
            <div className="grid grid-cols-2 gap-2">
              {['30 fps (Anime Standard)', '60 fps (Smooth)'].map((f) => {
                const val = f.split(' ')[0]
                return (
                  <button
                    key={val}
                    onClick={() => setFps(val)}
                    className={`py-2 rounded-xl text-xs font-mono font-semibold transition-all ${
                      fps === val
                        ? 'bg-indigo-600 text-white'
                        : 'bg-black/60 text-zinc-400 border border-zinc-800 hover:text-zinc-200'
                    }`}
                  >
                    {f}
                  </button>
                )
              })}
            </div>
          </div>
        </div>

        {/* Pre-Flight Production Checklist */}
        <div className="p-5 rounded-2xl bg-zinc-900/60 border border-zinc-800/80 space-y-4">
          <h3 className="text-xs font-semibold text-zinc-300 uppercase tracking-wider pb-2 border-b border-zinc-800">
            Pre-Flight Production Checklist
          </h3>

          <div className="space-y-2.5 text-xs font-mono">
            <div className="flex items-center justify-between p-2.5 rounded-xl bg-black/40 border border-zinc-800/60">
              <span className="flex items-center gap-2 text-zinc-300">
                <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                Demucs Vocal Separation
              </span>
              <span className="text-emerald-400">READY</span>
            </div>

            <div className="flex items-center justify-between p-2.5 rounded-xl bg-black/40 border border-zinc-800/60">
              <span className="flex items-center gap-2 text-zinc-300">
                <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                SenseVoice Chinese ASR
              </span>
              <span className="text-emerald-400">SYNCED</span>
            </div>

            <div className="flex items-center justify-between p-2.5 rounded-xl bg-black/40 border border-zinc-800/60">
              <span className="flex items-center gap-2 text-zinc-300">
                <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                Gemini Dramatic Recap Script
              </span>
              <span className="text-emerald-400">ADAPTED</span>
            </div>

            <div className="flex items-center justify-between p-2.5 rounded-xl bg-black/40 border border-zinc-800/60">
              <span className="flex items-center gap-2 text-zinc-300">
                <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                F5-TTS Hindi Audio Tracks
              </span>
              <span className="text-emerald-400">GENERATED</span>
            </div>

            <div className="flex items-center justify-between p-2.5 rounded-xl bg-black/40 border border-zinc-800/60">
              <span className="flex items-center gap-2 text-zinc-300">
                <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                Watermark Delogo & Subtitle Crop
              </span>
              <span className="text-emerald-400">AUTOMATED</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
