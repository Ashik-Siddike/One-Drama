import { useState } from 'react'
import { createPortal } from 'react-dom'
import { Download, Sparkles, Film, UploadCloud } from 'lucide-react'
import { LocalImportDropzone } from '../projects/LocalImportDropzone'

interface QuickActionCenterProps {
  onDownload: (queryOrUrl: string, limit?: number) => Promise<void>
  onRunPipeline: (limit?: number) => Promise<void>
  onAutoProduce?: (opts: { query_or_url: string; limit?: number }) => Promise<void>
  onRefresh?: () => Promise<void>
  isBusy: boolean
  rawEpisodeCount?: number
}

export const QuickActionCenter: React.FC<QuickActionCenterProps> = ({
  onDownload,
  onRunPipeline,
  onAutoProduce,
  onRefresh,
  isBusy,
  rawEpisodeCount = 0,
}) => {
  const [inputUrl, setInputUrl] = useState('')
  const [episodeLimit, setEpisodeLimit] = useState<string>('')
  const [statusMsg, setStatusMsg] = useState<string | null>(null)
  const [showImportModal, setShowImportModal] = useState(false)

  const handleAutoProduceSubmit = async () => {
    if (!inputUrl.trim()) {
      if (rawEpisodeCount > 0) {
        await handleRenderSubmit()
        return
      }
      return
    }
    try {
      setStatusMsg('Starting 1-Click Auto Movie...')
      const lim = episodeLimit ? parseInt(episodeLimit, 10) : 25
      if (onAutoProduce) {
        await onAutoProduce({ query_or_url: inputUrl.trim(), limit: lim })
      } else {
        await onDownload(inputUrl.trim(), lim)
      }
      setStatusMsg('Auto-pilot started in background!')
      setInputUrl('')
      setTimeout(() => setStatusMsg(null), 3000)
    } catch (err: any) {
      setStatusMsg(`Error: ${err.message}`)
    }
  }

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
    <div className="p-5 rounded-2xl bg-zinc-900/60 border border-zinc-800/80 backdrop-blur-sm relative">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-indigo-400" />
          <h3 className="text-sm font-bold text-zinc-100">Quick Actions & Series Ingestion</h3>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setShowImportModal(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white text-xs font-bold transition-all shadow-md shadow-indigo-600/20"
            title="কম্পিউটারের ড্রামা ফোল্ডার বা ভিডিও ফাইল ড্র্যাগ-ড্রপ করে সরাসরি ইনপোর্ট করুন"
          >
            <UploadCloud className="w-3.5 h-3.5" />
            <span>📥 লোকাল সিরিজ ড্র্যাগ-ড্রপ</span>
          </button>
          {statusMsg && (
            <span className="text-xs font-mono px-2 py-0.5 rounded bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
              {statusMsg}
            </span>
          )}
        </div>
      </div>

      {/* Ready Local Episodes Banner */}
      {rawEpisodeCount > 0 && (
        <div className="mb-4 p-4 rounded-2xl bg-gradient-to-r from-emerald-950/80 via-teal-950/50 to-zinc-900/90 border-2 border-emerald-500/40 flex flex-col sm:flex-row items-center justify-between gap-4 shadow-xl shadow-emerald-950/40 animate-fadeIn">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-emerald-500/20 border border-emerald-500/30 flex items-center justify-center text-emerald-400 shrink-0">
              <Film className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-sm font-bold text-white flex items-center gap-1.5">
                  <span>✅ {rawEpisodeCount}টি ভিডিও ইনপোর্ট করা আছে!</span>
                </span>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 font-semibold">
                  Ready to Process
                </span>
              </div>
              <p className="text-xs text-zinc-300 mt-0.5">
                ডাউনলোডের প্রয়োজন নেই। এই বাটনে ক্লিক করলেই আপনার এই পর্বগুলোর হিন্দি ডাবিং ও ফুল মুভি রেন্ডার শুরু হয়ে যাবে।
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={handleRenderSubmit}
            disabled={isBusy}
            className="w-full sm:w-auto px-6 py-3 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-400 hover:to-teal-500 text-white text-xs font-black tracking-wide shadow-lg shadow-emerald-600/30 flex items-center justify-center gap-2 transition-all transform hover:scale-[1.02] shrink-0 disabled:opacity-50"
          >
            <Sparkles className="w-4 h-4 text-amber-200" />
            <span>🎬 এই {rawEpisodeCount}টি ভিডিও দিয়ে সরাসরি ফুল মুভি বানাও</span>
          </button>
        </div>
      )}

      <form onSubmit={handleDownloadSubmit} className="flex flex-col md:flex-row gap-3">
        <div className="flex-1 relative">
          <input
            type="text"
            value={inputUrl}
            onChange={(e) => {
              const val = e.target.value
              setInputUrl(val)
              // Auto-detect local path paste
              if (val.trim().length > 3 && (val.includes(':\\') || val.includes(':/') || val.startsWith('/'))) {
                setShowImportModal(true)
              }
            }}
            onDrop={(e) => {
              const text = e.dataTransfer.getData('text')
              if (text && (text.includes(':\\') || text.includes(':/') || text.startsWith('/'))) {
                e.preventDefault()
                setInputUrl(text)
                setShowImportModal(true)
              } else if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
                e.preventDefault()
                setShowImportModal(true)
              }
            }}
            disabled={isBusy}
            placeholder="Bilibili URL / টাইটেল পেস্ট করুন, অথবা লোকাল ফোল্ডার পাথ ড্রপ করুন..."
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
          type="button"
          onClick={handleAutoProduceSubmit}
          disabled={isBusy || (!inputUrl.trim() && rawEpisodeCount === 0)}
          className="flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-emerald-600 to-indigo-600 hover:from-emerald-500 hover:to-indigo-500 disabled:opacity-40 text-white text-xs font-bold tracking-wide transition-all shadow-md shadow-emerald-600/20"
        >
          <Sparkles className="w-4 h-4 text-amber-300" />
          <span>🚀 ১-ক্লিকে ফুল মুভি বানাও</span>
        </button>

        <button
          type="submit"
          disabled={isBusy || !inputUrl.trim()}
          title="শুধুমাত্র পর্বগুলো ডাউনলোড করে রাখুন"
          className="flex items-center justify-center gap-1.5 px-4 py-2.5 rounded-xl bg-indigo-600/20 hover:bg-indigo-600/40 disabled:bg-zinc-800 disabled:text-zinc-600 text-indigo-300 border border-indigo-500/30 text-xs font-medium tracking-wide transition-all"
        >
          <Download className="w-4 h-4" />
          <span>শুধু ডাউনলোড</span>
        </button>

        <button
          type="button"
          onClick={handleRenderSubmit}
          disabled={isBusy || (rawEpisodeCount === 0 && !inputUrl.trim())}
          title="ইতিমধ্যে ইনপোর্ট করা পর্বগুলো প্রসেস করুন"
          className="flex items-center justify-center gap-1.5 px-4 py-2.5 rounded-xl bg-emerald-600/20 hover:bg-emerald-600/30 disabled:bg-zinc-900 disabled:text-zinc-600 text-emerald-300 border border-emerald-500/40 text-xs font-bold tracking-wide transition-all shadow-sm"
        >
          <Film className="w-4 h-4 text-emerald-400" />
          <span>🎬 লোকাল রেন্ডার ({rawEpisodeCount} পর্ব)</span>
        </button>
      </form>

      {/* Local Drama Import Modal */}
      {showImportModal &&
        createPortal(
          <div
            className="fixed inset-0 z-[9999] flex items-center justify-center p-4 bg-black/80 backdrop-blur-md"
            onClick={() => setShowImportModal(false)}
          >
            <div className="w-full max-w-4xl" onClick={(e) => e.stopPropagation()}>
              <LocalImportDropzone
                isModal
                onClose={() => setShowImportModal(false)}
                onImportSuccess={async () => {
                  if (onRefresh) await onRefresh()
                  setShowImportModal(false)
                }}
                onStartProcessing={async () => {
                  setShowImportModal(false)
                  await handleRenderSubmit()
                }}
                onAutoProduce={async (opts) => {
                  setShowImportModal(false)
                  if (onAutoProduce) await onAutoProduce(opts)
                }}
              />
            </div>
          </div>,
          document.body
        )}
    </div>
  )
}
