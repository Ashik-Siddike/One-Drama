import { useState } from 'react'
import { Film, CheckCircle2, Video, Sparkles, Play, Cloud, Check, Loader2 } from 'lucide-react'
import type { ProjectData } from '../../types'
import { syncToGoogleDrive } from '../../services/api'

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

  return (
    <div className="p-5 rounded-2xl bg-zinc-900/60 border border-zinc-800/80 backdrop-blur-sm">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
        <div className="flex items-center gap-2">
          <Film className="w-4 h-4 text-emerald-400" />
          <h3 className="text-sm font-bold text-zinc-100">Exported Master Movies & Google Drive Sync</h3>
        </div>
        <span className="text-xs font-mono text-zinc-400">
          {masterMovies.length} Master Movie(s) Available
        </span>
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
