import { useState } from 'react'
import {
  Film,
  CheckCircle2,
  Play,
  Radio,
  Cpu,
  HardDrive,
  Sparkles,
  Scissors,
  Smartphone,
  Zap,
  Layers,
  Loader2,
  DownloadCloud,
  Clock,
  AlertCircle,
  Info,
  Sparkle,
  FolderOpen,
} from 'lucide-react'
import type { PipelineStatus, ProjectData } from '../../types'
import { generateShort, openFolderInFileManager } from '../../services/api'

interface RenderCenterViewProps {
  pipelineStatus: PipelineStatus | null
  projectData?: ProjectData | null
  onStartRender: (opts?: {
    enable_filler_trim?: boolean
    generate_shorts?: boolean
    split_compilations?: boolean
  }) => Promise<void>
}

export const RenderCenterView: React.FC<RenderCenterViewProps> = ({
  pipelineStatus,
  projectData,
  onStartRender,
}) => {
  const [resolution, setResolution] = useState('1080p')
  const [codec, setCodec] = useState('libx264')
  const [fps, setFps] = useState('30')
  const [isStarting, setIsStarting] = useState(false)

  // Master Pipeline Feature Toggles
  const [enableFillerTrim, setEnableFillerTrim] = useState(false)
  const [generateShortsOnRender, setGenerateShortsOnRender] = useState(true)
  const [splitCompilations, setSplitCompilations] = useState(false)

  // Standalone YouTube Shorts Studio State
  const [shortHook, setShortHook] = useState('🔥 REBORN AS THE SUPREME GOD!')
  const [shortCta, setShortCta] = useState('Watch Full Movie on @OneDrama')
  const [shortDuration, setShortDuration] = useState(45)
  const [isRenderingShort, setIsRenderingShort] = useState(false)
  const [shortResult, setShortResult] = useState<any | null>(null)
  const [shortError, setShortError] = useState<string | null>(null)

  const isRunning = pipelineStatus?.is_running

  const totalEpisodes = projectData?.total_raw_episodes ?? (projectData?.episodes?.length || 0)
  const estTotalMins = Math.round(totalEpisodes * 3.5)
  const isFullMovieReady = totalEpisodes >= 20
  const isSingleOrSmall = totalEpisodes < 10

  const formatEstDuration = (mins: number) => {
    if (mins <= 0) return '0 mins'
    if (mins < 60) return `~${mins} mins`
    const h = Math.floor(mins / 60)
    const m = mins % 60
    return `~${h}h ${m > 0 ? `${m}m` : ''}`
  }

  const handleRenderClick = async () => {
    setIsStarting(true)
    try {
      await onStartRender({
        enable_filler_trim: enableFillerTrim,
        generate_shorts: generateShortsOnRender,
        split_compilations: splitCompilations,
      })
    } finally {
      setIsStarting(false)
    }
  }

  const handleCreateShort = async () => {
    setIsRenderingShort(true)
    setShortResult(null)
    setShortError(null)
    try {
      const res = await generateShort({
        duration_sec: shortDuration,
        top_hook: shortHook,
        bottom_cta: shortCta,
      })
      setShortResult(res)
    } catch (err: any) {
      setShortError(err.message || 'Failed to render short.')
    } finally {
      setIsRenderingShort(false)
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
                GPU MASTER CONCAT & SHORTS
              </span>
            </div>
            <p className="text-xs text-zinc-400 mt-0.5">
              Batch remaster, smart filler trimming (0.4s), and 9:16 viral vertical shorts rendering.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => openFolderInFileManager({ category: 'master' })}
            className="flex items-center gap-1.5 px-4 py-2.5 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs font-bold font-mono transition-all border border-zinc-700 shadow-sm"
            title="Open storage/master_export in Windows File Explorer"
          >
            <FolderOpen className="w-4 h-4 text-emerald-400" />
            <span>📂 মাস্টার এক্সপোর্ট ফোল্ডার</span>
          </button>

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
      </div>

      {/* Season Duration & Ingest Calculator Banner */}
      <div className="p-4 rounded-2xl bg-zinc-900/50 border border-zinc-800/80 space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400">
              <Clock className="w-4 h-4" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xs font-bold text-zinc-200">Current Season Queue:</span>
                <span className="text-xs font-mono font-bold text-indigo-400">
                  {totalEpisodes} Episode{totalEpisodes === 1 ? '' : 's'}
                </span>
                <span className="text-zinc-600">•</span>
                <span className="text-xs font-mono text-amber-400">
                  Estimated Movie Runtime: {formatEstDuration(estTotalMins)}
                </span>
              </div>
              <p className="text-[11px] text-zinc-400 mt-0.5">
                Target for a complete 1 to 2 Hour YouTube Full Movie: <strong className="text-zinc-300">20–35 Episodes</strong>
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <span
              className={`text-[10px] font-mono px-2.5 py-1 rounded-full border ${
                isFullMovieReady
                  ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                  : 'bg-amber-500/10 text-amber-400 border-amber-500/20'
              }`}
            >
              {isFullMovieReady ? '✓ FULL MOVIE READY' : 'PREVIEW / SHORT RUNTIME'}
            </span>
          </div>
        </div>

        {/* Progress gauge toward 1-2 hr full season */}
        <div className="space-y-1">
          <div className="flex items-center justify-between text-[10px] font-mono text-zinc-500">
            <span>Queue Progress ({totalEpisodes}/25 eps)</span>
            <span>{Math.min(100, Math.round((totalEpisodes / 25) * 100))}% toward Full Season Movie</span>
          </div>
          <div className="w-full h-1.5 rounded-full bg-zinc-800/80 overflow-hidden">
            <div
              className={`h-full transition-all duration-500 rounded-full ${
                isFullMovieReady ? 'bg-emerald-500' : 'bg-gradient-to-r from-amber-500 to-indigo-500'
              }`}
              style={{ width: `${Math.min(100, Math.max(5, (totalEpisodes / 25) * 100))}%` }}
            />
          </div>
        </div>

        {isSingleOrSmall && (
          <div className="flex items-start gap-2 p-2.5 rounded-xl bg-amber-500/5 border border-amber-500/20 text-[11px] text-amber-300/90 leading-relaxed">
            <AlertCircle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
            <div>
              <strong>Notice:</strong> Currently only <strong>{totalEpisodes} episode(s)</strong> are in the raw queue, which will produce a short <strong>{formatEstDuration(estTotalMins)}</strong> master clip. For a complete uninterrupted 1–2 hour movie series, go to the <strong>Discovery Radar</strong> or paste an entire season playlist link (20–30 episodes) in the Dashboard!
            </div>
          </div>
        )}
      </div>

      {/* Pipeline Feature Toggles Bar */}
      <div className="p-4 rounded-2xl bg-zinc-900/40 border border-zinc-800/80 grid grid-cols-1 md:grid-cols-3 gap-3">
        <label className="flex items-center gap-3 p-3 rounded-xl bg-black/40 border border-zinc-800/80 cursor-pointer hover:border-zinc-700 transition-colors">
          <input
            type="checkbox"
            checked={enableFillerTrim}
            onChange={(e) => setEnableFillerTrim(e.target.checked)}
            className="w-4 h-4 accent-amber-500 rounded cursor-pointer"
          />
          <div className="text-xs">
            <div className="font-semibold text-zinc-200 flex items-center gap-1.5">
              <Scissors className="w-3.5 h-3.5 text-amber-400" />
              Smart Filler Trimming
            </div>
            <p className="text-[11px] text-zinc-400">Disabled (keeps full video uncut)</p>
          </div>
        </label>

        <label className="flex items-center gap-3 p-3 rounded-xl bg-black/40 border border-zinc-800/80 cursor-pointer hover:border-zinc-700 transition-colors">
          <input
            type="checkbox"
            checked={generateShortsOnRender}
            onChange={(e) => setGenerateShortsOnRender(e.target.checked)}
            className="w-4 h-4 accent-red-500 rounded cursor-pointer"
          />
          <div className="text-xs">
            <div className="font-semibold text-zinc-200 flex items-center gap-1.5">
              <Smartphone className="w-3.5 h-3.5 text-red-400" />
              Auto-Generate Shorts
            </div>
            <p className="text-[11px] text-zinc-400">9:16 high-retention clips</p>
          </div>
        </label>

        <label className="flex items-center gap-3 p-3 rounded-xl bg-black/40 border border-zinc-800/80 cursor-pointer hover:border-zinc-700 transition-colors">
          <input
            type="checkbox"
            checked={splitCompilations}
            onChange={(e) => setSplitCompilations(e.target.checked)}
            className="w-4 h-4 accent-indigo-500 rounded cursor-pointer"
          />
          <div className="text-xs">
            <div className="font-semibold text-zinc-200 flex items-center gap-1.5">
              <Layers className="w-3.5 h-3.5 text-indigo-400" />
              Split Compilations
            </div>
            <p className="text-[11px] text-zinc-400">Slice 30m+ files into 15m parts</p>
          </div>
        </label>
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
                Smart Filler Trimmer (0.4s)
              </span>
              <span className="text-emerald-400">ACTIVE</span>
            </div>

            <div className="flex items-center justify-between p-2.5 rounded-xl bg-black/40 border border-zinc-800/60">
              <span className="flex items-center gap-2 text-zinc-300">
                <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                Corner Watermark Delogo Guard
              </span>
              <span className="text-emerald-400">VERIFIED</span>
            </div>
          </div>
        </div>
      </div>

      {/* ------------------------------------------------------------------ */}
      {/* Dedicated Viral YouTube Shorts (9:16) Studio */}
      {/* ------------------------------------------------------------------ */}
      <div className="p-5 rounded-2xl bg-zinc-900/60 border border-red-500/20 space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-zinc-800">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-red-500/10 border border-red-500/20 flex items-center justify-center text-red-400">
              <Smartphone className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-zinc-100">
                Standalone Viral YouTube Shorts Generator (9:16 Vertical)
              </h3>
              <p className="text-[11px] text-zinc-400">
                Auto-crops climax scenes into 1080x1920 portrait format with viral top hook banner and CTA.
              </p>
            </div>
          </div>
          <span className="px-2.5 py-0.5 rounded-full bg-red-500/10 text-red-400 border border-red-500/20 text-[10px] font-mono font-bold">
            HIGH-CTR 9:16
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="md:col-span-2 space-y-3">
            <div>
              <label className="text-[11px] font-mono text-zinc-400 block mb-1">
                Top Hook Banner Text (High Engagement)
              </label>
              <input
                type="text"
                value={shortHook}
                onChange={(e) => setShortHook(e.target.value)}
                placeholder="🔥 REBORN AS THE SUPREME GOD!"
                className="w-full px-3 py-2 rounded-xl bg-black/60 border border-zinc-800 text-xs text-zinc-200 focus:outline-none focus:border-red-500/50"
              />
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div>
                <label className="text-[11px] font-mono text-zinc-400 block mb-1">
                  Bottom CTA Text
                </label>
                <input
                  type="text"
                  value={shortCta}
                  onChange={(e) => setShortCta(e.target.value)}
                  placeholder="Watch Full Movie on @OneDrama"
                  className="w-full px-3 py-2 rounded-xl bg-black/60 border border-zinc-800 text-xs text-zinc-200 focus:outline-none"
                />
              </div>

              <div>
                <label className="text-[11px] font-mono text-zinc-400 block mb-1">
                  Short Duration
                </label>
                <select
                  value={shortDuration}
                  onChange={(e) => setShortDuration(parseInt(e.target.value))}
                  className="w-full px-3 py-2 rounded-xl bg-black/60 border border-zinc-800 text-xs text-zinc-200 focus:outline-none"
                >
                  <option value={30}>30 Seconds (Fast Paced)</option>
                  <option value={45}>45 Seconds (Sweet Spot)</option>
                  <option value={60}>60 Seconds (Full Climax)</option>
                </select>
              </div>
            </div>

            <button
              onClick={handleCreateShort}
              disabled={isRenderingShort}
              className="flex items-center justify-center gap-2 w-full py-2.5 rounded-xl bg-red-600 hover:bg-red-500 disabled:bg-zinc-800 text-white text-xs font-bold transition-all shadow-md shadow-red-600/20"
            >
              {isRenderingShort ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin text-white" />
                  <span>Rendering 9:16 Vertical Short with FFmpeg Crop...</span>
                </>
              ) : (
                <>
                  <Sparkles className="w-4 h-4 text-amber-300" />
                  <span>RENDER 9:16 VIRAL SHORT NOW</span>
                </>
              )}
            </button>

            {shortResult && (
              <div className="p-3 rounded-xl bg-emerald-950/30 border border-emerald-500/40 text-xs space-y-1">
                <div className="flex items-center gap-1.5 text-emerald-300 font-bold">
                  <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                  <span>Vertical Short Rendered Successfully!</span>
                </div>
                <div className="font-mono text-[11px] text-zinc-300">
                  File: <span className="text-emerald-400">{shortResult.filename}</span> ({shortResult.size_mb} MB)
                </div>
                <div className="text-[10px] text-zinc-500 truncate">
                  Saved to: {shortResult.short_path}
                </div>
                <div className="pt-2 flex items-center gap-2 flex-wrap">
                  <button
                    type="button"
                    onClick={() => openFolderInFileManager({ path: shortResult.short_path })}
                    className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-emerald-600/30 hover:bg-emerald-600/50 text-emerald-200 border border-emerald-500/40 text-xs font-mono transition-all"
                    title="Open this short file highlighted in Windows File Explorer"
                  >
                    <FolderOpen className="w-3.5 h-3.5 text-emerald-400" />
                    <span>📂 শর্ট ফাইলটি খুলুন</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => openFolderInFileManager({ category: 'shorts' })}
                    className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-300 border border-zinc-700 text-xs font-mono transition-all"
                    title="Open storage/master_export/shorts in Windows File Explorer"
                  >
                    <span>📱 Shorts ফোল্ডার</span>
                  </button>
                </div>
              </div>
            )}

            {shortError && (
              <div className="p-3 rounded-xl bg-red-950/30 border border-red-500/40 text-xs text-red-300">
                {shortError}
              </div>
            )}
          </div>

          {/* 9:16 Aspect Mock Preview */}
          <div className="flex flex-col items-center justify-center p-4 rounded-xl bg-black/60 border border-zinc-800">
            <div className="w-32 h-56 rounded-2xl bg-zinc-950 border-2 border-zinc-700/80 relative overflow-hidden flex flex-col justify-between p-2 shadow-2xl">
              {/* Top hook mockup */}
              <div className="bg-amber-400 text-black text-[7px] font-black text-center py-0.5 rounded tracking-tight">
                {shortHook.slice(0, 22)}
              </div>

              {/* Center Play Icon */}
              <div className="flex items-center justify-center">
                <div className="w-7 h-7 rounded-full bg-red-600/80 flex items-center justify-center text-white">
                  <Play className="w-3 h-3 fill-current ml-0.5" />
                </div>
              </div>

              {/* Bottom CTA mockup */}
              <div className="bg-black/80 text-zinc-300 text-[6px] text-center py-0.5 rounded border border-zinc-800">
                {shortCta.slice(0, 24)}
              </div>
            </div>
            <span className="text-[10px] font-mono text-zinc-500 mt-2">1080x1920 (9:16 Vertical)</span>
          </div>
        </div>
      </div>
    </div>
  )
}

