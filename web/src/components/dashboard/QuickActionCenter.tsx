import { useState } from 'react'
import { Download, Sparkles, Film } from 'lucide-react'

interface QuickActionCenterProps {
  onDownload: (queryOrUrl: string, limit?: number) => Promise<void>
  onRunPipeline: (limit?: number) => Promise<void>
  isBusy: boolean
}

export const QuickActionCenter: React.FC<QuickActionCenterProps> = ({
  onDownload,
  onRunPipeline,
  isBusy,
}) => {
  const [inputUrl, setInputUrl] = useState('')
  const [episodeLimit, setEpisodeLimit] = useState<string>('')
  const [statusMsg, setStatusMsg] = useState<string | null>(null)

  const handleDownloadSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!inputUrl.trim()) return
    try {
      setStatusMsg('Queueing download...')
      const lim = episodeLimit ? parseInt(episodeLimit, 10) : undefined
      await onDownload(inputUrl.trim(), lim)
      setStatusMsg('Download queued in background!')
      setInputUrl('')
      setTimeout(() => setStatusMsg(null), 3000)
    } catch (err: any) {
      setStatusMsg(`Error: ${err.message}`)
    }
  }

  const handleRenderSubmit = async () => {
    try {
      setStatusMsg('Triggering pipeline...')
      const lim = episodeLimit ? parseInt(episodeLimit, 10) : undefined
      await onRunPipeline(lim)
      setStatusMsg('Pipeline started!')
      setTimeout(() => setStatusMsg(null), 3000)
    } catch (err: any) {
      setStatusMsg(`Error: ${err.message}`)
    }
  }

  return (
    <div className="p-5 rounded-2xl bg-zinc-900/60 border border-zinc-800/80 backdrop-blur-sm">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-indigo-400" />
          <h3 className="text-sm font-bold text-zinc-100">Quick Actions & Series Ingestion</h3>
        </div>
        {statusMsg && (
          <span className="text-xs font-mono px-2 py-0.5 rounded bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
            {statusMsg}
          </span>
        )}
      </div>

      <form onSubmit={handleDownloadSubmit} className="flex flex-col md:flex-row gap-3">
        <div className="flex-1 relative">
          <input
            type="text"
            value={inputUrl}
            onChange={(e) => setInputUrl(e.target.value)}
            disabled={isBusy}
            placeholder="Paste Bilibili playlist URL (e.g. BV1TRt... or search title like: 都市修仙)..."
            className="w-full px-4 py-2.5 rounded-xl bg-black/60 border border-zinc-800 text-xs text-zinc-100 placeholder-zinc-500 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all font-mono"
          />
        </div>

        <div className="w-full md:w-32">
          <input
            type="number"
            value={episodeLimit}
            onChange={(e) => setEpisodeLimit(e.target.value)}
            disabled={isBusy}
            placeholder="Limit (optional)"
            className="w-full px-3 py-2.5 rounded-xl bg-black/60 border border-zinc-800 text-xs text-zinc-100 placeholder-zinc-500 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 font-mono"
          />
        </div>

        <button
          type="submit"
          disabled={isBusy || !inputUrl.trim()}
          className="flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:bg-zinc-800 disabled:text-zinc-600 text-white text-xs font-semibold tracking-wide transition-all shadow-md shadow-indigo-600/20"
        >
          <Download className="w-4 h-4" />
          <span>Ingest Series</span>
        </button>

        <button
          type="button"
          onClick={handleRenderSubmit}
          disabled={isBusy}
          className="flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl bg-zinc-800 hover:bg-zinc-700 disabled:bg-zinc-900 disabled:text-zinc-600 text-zinc-100 text-xs font-semibold tracking-wide transition-all border border-zinc-700/60"
        >
          <Film className="w-4 h-4 text-emerald-400" />
          <span>Render Local Episodes</span>
        </button>
      </form>
    </div>
  )
}
