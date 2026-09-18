import { useState } from 'react'
import {
  Film,
  CheckCircle2,
  Video,
  Sparkles,
  Play,
  Cloud,
  Check,
  Loader2,
  Clapperboard,
  Scissors,
  FolderOpen,
  Folder,
  ExternalLink,
} from 'lucide-react'
import type { ProjectData } from '../../types'
import { syncToGoogleDrive, generateShort, openFolderInFileManager } from '../../services/api'

interface MasterMoviesTableProps {
  projectData: ProjectData | null
}

export const MasterMoviesTable: React.FC<MasterMoviesTableProps> = ({ projectData }) => {
  const masterMovies = projectData?.master_movies || []
  const pkg = projectData?.youtube_package || {}
  const hasGuide = projectData?.has_publish_guide

  const [isSyncing, setIsSyncing] = useState(false)
  const [syncResult, setSyncResult] = useState<string | null>(null)
  const [syncError, setSyncError] = useState<string | null>(null)

  const [isGeneratingShort, setIsGeneratingShort] = useState(false)
  const [shortResult, setShortResult] = useState<any | null>(null)
  const [folderNotice, setFolderNotice] = useState<string | null>(null)

  const handleOpenLocation = async (opts: { category?: string; path?: string; select_file?: string }) => {
    try {
      const res = await openFolderInFileManager(opts)
      setFolderNotice(res.message || 'Opened in File Manager')
      setTimeout(() => setFolderNotice(null), 3500)
    } catch (err: any) {
      setSyncError(err.message || 'Failed to open file manager')
      setTimeout(() => setSyncError(null), 4000)
    }
  }

  const handleSync = async () => {
    setIsSyncing(true)
    setSyncResult(null)
    setSyncError(null)
    try {
      const res = await syncToGoogleDrive()
      setSyncResult(res.destination)
    } catch (err: any) {
      setSyncError(err.message || 'Sync failed')
    } finally {
      setIsSyncing(false)
    }
  }

  const handleGenerateShort = async (moviePath: string) => {
    setIsGeneratingShort(true)
    setShortResult(null)
    try {
      const res = await generateShort({ video_path: moviePath })
      setShortResult(res)
    } catch (err: any) {
      setSyncError(err.message || 'Short generation failed')
    } finally {
      setIsGeneratingShort(false)
    }
  }

  return (
    <div className="p-5 rounded-2xl bg-zinc-900/60 border border-zinc-800/80 backdrop-blur-sm">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
        <div className="flex items-center gap-2">
          <Film className="w-4 h-4 text-emerald-400" />
          <h3 className="text-sm font-bold text-zinc-100">Exported Master Movies & Google Drive Sync</h3>
        </div>
        <div className="flex items-center gap-2">
          {folderNotice && (
            <span className="text-xs font-mono px-2.5 py-1 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 animate-fade-in flex items-center gap-1">
              <CheckCircle2 className="w-3.5 h-3.5" />
              {folderNotice}
            </span>
          )}
          <span className="text-xs font-mono text-zinc-400">
            {masterMovies.length} Master Movie(s) Available
          </span>
        </div>
      </div>

      {/* 1-Click Fast Storage Navigation Toolbar */}
      <div className="flex items-center gap-2 flex-wrap mb-4 p-2.5 rounded-xl bg-black/40 border border-zinc-800/70 text-xs">
        <span className="text-[11px] font-mono text-zinc-400 font-semibold uppercase tracking-wider mr-1 flex items-center gap-1">
          <Folder className="w-3.5 h-3.5 text-indigo-400" /> 1-Click File Explorer:
        </span>
        <button
          type="button"
          onClick={() => handleOpenLocation({ category: 'master' })}
          className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-zinc-900 hover:bg-zinc-800 text-zinc-200 border border-zinc-700/60 hover:border-zinc-500 text-[11px] font-mono transition-all"
          title="Open storage/master_export in Windows File Explorer"
        >
          <span>🎬 Master Export</span>
        </button>
        <button
          type="button"
          onClick={() => handleOpenLocation({ category: 'processed' })}
          className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-zinc-900 hover:bg-zinc-800 text-zinc-200 border border-zinc-700/60 hover:border-zinc-500 text-[11px] font-mono transition-all"
          title="Open storage/processed_episodes in Windows File Explorer"
        >
          <span>📺 Dubbed Episodes</span>
        </button>
        <button
          type="button"
          onClick={() => handleOpenLocation({ category: 'shorts' })}
          className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-zinc-900 hover:bg-zinc-800 text-zinc-200 border border-zinc-700/60 hover:border-zinc-500 text-[11px] font-mono transition-all"
          title="Open storage/master_export/shorts in Windows File Explorer"
        >
          <span>📱 Shorts Folder</span>
        </button>
        <button
          type="button"
          onClick={() => handleOpenLocation({ category: 'raw' })}
          className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-zinc-900 hover:bg-zinc-800 text-zinc-200 border border-zinc-700/60 hover:border-zinc-500 text-[11px] font-mono transition-all"
          title="Open storage/raw_episodes in Windows File Explorer"
        >
          <span>📥 Raw Episodes</span>
        </button>
        <button
          type="button"
          onClick={() => handleOpenLocation({ category: 'drive' })}
          className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-zinc-900 hover:bg-zinc-800 text-zinc-200 border border-zinc-700/60 hover:border-zinc-500 text-[11px] font-mono transition-all"
          title="Open Google Drive Synced Folder in Windows File Explorer"
        >
          <Cloud className="w-3 h-3 text-cyan-400" />
          <span>Google Drive</span>
        </button>
      </div>

      {masterMovies.length === 0 ? (
        <div className="py-8 text-center text-xs text-zinc-500 font-mono italic border border-dashed border-zinc-800 rounded-xl">
          No master movies rendered yet. Ingest episodes and run the pipeline to build a full movie compilation.
        </div>
      ) : (
        <div className="space-y-3">
          {masterMovies.map((movie, idx) => (
            <div
              key={idx}
              className="p-4 rounded-xl bg-black/60 border border-zinc-800 flex flex-col md:flex-row md:items-center justify-between gap-4"
            >
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400">
                  <Play className="w-5 h-5 fill-current" />
                </div>
                <div>
                  <h4 className="text-sm font-bold text-zinc-100">{movie.filename}</h4>
                  <div className="flex items-center gap-3 text-xs font-mono text-zinc-400 mt-0.5">
                    <span>Size: {movie.size_mb} MB</span>
                    <span>•</span>
                    <span className="text-emerald-400 flex items-center gap-1">
                      <CheckCircle2 className="w-3 h-3" /> Remastered & Inpainted
                    </span>
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-3">
                {hasGuide && (
                  <span className="text-[11px] font-mono px-2.5 py-1 rounded bg-red-500/10 text-red-400 border border-red-500/20 flex items-center gap-1.5">
                    <Video className="w-3.5 h-3.5" />
                    YouTube Package Ready
                  </span>
                )}

                <button
                  type="button"
                  onClick={() => handleOpenLocation({ path: movie.path })}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-200 hover:text-white text-xs font-semibold font-mono tracking-wide transition-all border border-zinc-700 shadow-sm"
                  title="Open this movie file directly highlighted in Windows File Explorer"
                >
                  <FolderOpen className="w-3.5 h-3.5 text-indigo-400" />
                  <span>📂 লোকেশন খুলুন</span>
                </button>

                <button
                  onClick={() => handleGenerateShort(movie.path)}
                  disabled={isGeneratingShort}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-600 hover:bg-amber-500 disabled:bg-zinc-800 text-white text-xs font-semibold font-mono tracking-wide transition-all shadow-md shadow-amber-600/20"
                >
                  {isGeneratingShort ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <Scissors className="w-3.5 h-3.5 text-amber-200" />
                  )}
                  <span>{isGeneratingShort ? 'Carving Short...' : 'Carve 9:16 Short'}</span>
                </button>

                <button
                  onClick={handleSync}
                  disabled={isSyncing}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:bg-zinc-800 text-white text-xs font-semibold font-mono tracking-wide transition-all shadow-md shadow-indigo-600/20"
                >
                  {isSyncing ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  ) : syncResult ? (
                    <Check className="w-3.5 h-3.5 text-emerald-300" />
                  ) : (
                    <Cloud className="w-3.5 h-3.5" />
                  )}
                  <span>{isSyncing ? 'Syncing...' : syncResult ? 'Synced to Drive!' : 'Sync to Google Drive'}</span>
                </button>
              </div>
            </div>
          ))}

          {/* Short Generation Feedback */}
          {shortResult && (
            <div className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/20 text-xs font-mono text-amber-300 flex items-center justify-between gap-2 flex-wrap">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 shrink-0 text-amber-400" />
                <span>
                  Viral 9:16 Short Ready: <strong>{shortResult.filename}</strong> ({shortResult.size_mb} MB)
                </span>
              </div>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => handleOpenLocation({ path: shortResult.short_path })}
                  className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-amber-500/20 hover:bg-amber-500/30 text-amber-200 border border-amber-500/30 text-xs font-mono transition-all"
                  title="Open this short in Windows File Explorer"
                >
                  <FolderOpen className="w-3.5 h-3.5 text-amber-300" />
                  <span>📂 শর্ট ফাইলটি ওপেন করুন</span>
                </button>
                <span className="text-[11px] text-zinc-400">Ready in storage/master_export/shorts/</span>
              </div>
            </div>
          )}

          {/* Sync Result Feedback */}
          {syncResult && (
            <div className="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-xs font-mono text-emerald-300 flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-400" />
              <span>Synced directly to: <strong>{syncResult}</strong> (auto-uploading to Cloud)</span>
            </div>
          )}

          {syncError && (
            <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-xs font-mono text-rose-300">
              Error: {syncError}
            </div>
          )}

          {/* YouTube Viral Package Card */}
          {pkg?.titles && pkg.titles.length > 0 && (
            <div className="mt-4 p-4 rounded-xl bg-zinc-950/80 border border-indigo-500/30">
              <div className="flex items-center gap-2 text-xs font-semibold text-indigo-400 mb-2">
                <Sparkles className="w-4 h-4" />
                <span>AI Master Thumbnail & Viral Title Strategy (Gemini Optimized)</span>
              </div>

              <div className="space-y-2 text-xs">
                <div>
                  <span className="text-zinc-500 font-mono uppercase text-[10px]">
                    Top Viral Title:
                  </span>
                  <p className="text-zinc-200 font-medium">{pkg.titles[0]}</p>
                </div>

                {pkg.ai_thumbnail_prompt && (
                  <div>
                    <span className="text-zinc-500 font-mono uppercase text-[10px]">
                      Midjourney v6 / Flux Master Prompt:
                    </span>
                    <p className="text-indigo-300 font-mono text-[11px] bg-zinc-900/80 p-2 rounded border border-zinc-800 mt-1 select-all">
                      {pkg.ai_thumbnail_prompt}
                    </p>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
