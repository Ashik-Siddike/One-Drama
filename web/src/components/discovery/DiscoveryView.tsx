import { useState, useEffect } from 'react'
import {
  Compass,
  Search,
  Download,
  Flame,
  ShieldCheck,
  AlertTriangle,
  Play,
  Sparkles,
  CheckCircle2,
  XCircle,
  Eye,
  Layers,
} from 'lucide-react'
import type { Recommendation } from '../../types'
import {
  fetchTrending,
  searchManhua,
  fetchDaily3DSuggestions,
  search3DManhua,
} from '../../services/api'

interface DiscoveryViewProps {
  onIngestSeries: (urlOrQuery: string) => Promise<void>
}

const GENRES = [
  { id: '3d_urban', label: '3D Urban Rebirth (3D 都市重生)' },
  { id: '3d_cultivation', label: '3D Xianxia (3D 玄幻修仙)' },
  { id: '3d_apocalypse', label: '3D Apocalypse (3D 末日系统)' },
  { id: '3d_all', label: '3D Master Collection (3D 漫剧)' },
  { id: 'cultivation', label: '2D Cultivation (修仙)' },
  { id: 'urban', label: '2D Urban (都市)' },
]

export const DiscoveryView: React.FC<DiscoveryViewProps> = ({ onIngestSeries }) => {
  const [selectedGenre, setSelectedGenre] = useState('3d_urban')
  const [searchQuery, setSearchQuery] = useState('')
  const [items, setItems] = useState<any[]>([])
  const [dailySuggestions, setDailySuggestions] = useState<any[]>([])
  const [activeThemeId, setActiveThemeId] = useState<string | null>(null)
  const [screenWatermarks, setScreenWatermarks] = useState(true)
  const [isLoading, setIsLoading] = useState(false)
  const [ingestingUrl, setIngestingUrl] = useState<string | null>(null)
  const [feedback, setFeedback] = useState<string | null>(null)

  useEffect(() => {
    fetchDaily3DSuggestions()
      .then((data) => setDailySuggestions(data.suggestions || []))
      .catch((err) => console.error('Failed to load daily 3D suggestions:', err))
  }, [])

  useEffect(() => {
    if (!activeThemeId && !searchQuery) {
      loadTrending(selectedGenre)
    }
  }, [selectedGenre])

  const loadTrending = async (genre: string) => {
    setIsLoading(true)
    try {
      const data = await fetchTrending(genre, 6)
      setItems(data.recommendations || [])
    } catch (err) {
      console.error('Failed to load trending:', err)
    } finally {
      setIsLoading(false)
    }
  }

  const handleSelectTrope = async (trope: any) => {
    setActiveThemeId(trope.id)
    setSearchQuery(trope.query)
    setIsLoading(true)
    try {
      const data = await search3DManhua(trope.query, 6, screenWatermarks)
      setItems(data.results || [])
    } catch (err) {
      console.error('3D Search failed:', err)
    } finally {
      setIsLoading(false)
    }
  }

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!searchQuery.trim()) return
    setIsLoading(true)
    setActiveThemeId(null)
    try {
      if (screenWatermarks) {
        const data = await search3DManhua(searchQuery.trim(), 6, true)
        setItems(data.results || [])
      } else {
        const data = await searchManhua(searchQuery.trim(), 8)
        setItems(data.results || [])
      }
    } catch (err) {
      console.error('Search failed:', err)
    } finally {
      setIsLoading(false)
    }
  }

  const handleIngest = async (url: string) => {
    setIngestingUrl(url)
    try {
      await onIngestSeries(url)
      setFeedback('Series download queued in background!')
      setTimeout(() => setFeedback(null), 4000)
    } catch (err: any) {
      setFeedback(`Error: ${err.message}`)
    } finally {
      setIngestingUrl(null)
    }
  }

  return (
    <div className="space-y-6">
      {/* Daily 3D Màn jù Radar (Trope Suggestions) */}
      <div className="p-5 rounded-2xl bg-gradient-to-r from-amber-950/30 via-zinc-900/70 to-indigo-950/30 border border-amber-500/20 shadow-xl">
        <div className="flex items-center justify-between gap-4 mb-3">
          <div className="flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-amber-400" />
            <h3 className="text-sm font-bold text-zinc-100 tracking-wide">
              Daily 3D AI Màn jù Radar (3D 漫剧每日精选)
            </h3>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20">
              High CTR Tropes
            </span>
          </div>
          <span className="text-xs text-zinc-400 font-mono hidden md:inline">
            Click any trope card to auto-search & screen clean 3D series
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {dailySuggestions.map((s) => (
            <div
              key={s.id}
              onClick={() => handleSelectTrope(s)}
              className={`p-3.5 rounded-xl border transition-all cursor-pointer flex flex-col justify-between gap-2 text-left group ${
                activeThemeId === s.id
                  ? 'bg-amber-500/15 border-amber-500/60 shadow-lg shadow-amber-500/10'
                  : 'bg-zinc-900/60 border-zinc-800/80 hover:border-zinc-700 hover:bg-zinc-800/50'
              }`}
            >
              <div>
                <div className="flex items-center justify-between gap-2 mb-1">
                  <span className="text-base">{s.icon}</span>
                  <span className="text-[10px] font-mono text-zinc-500 bg-zinc-800/80 px-2 py-0.5 rounded">
                    {s.category}
                  </span>
                </div>
                <h4 className="text-xs font-bold text-zinc-100 group-hover:text-amber-300 transition-colors">
                  {s.title}
                </h4>
                <p className="text-[11px] font-mono text-amber-400/90 mt-0.5">
                  {s.chinese_title}
                </p>
                <p className="text-[11px] text-zinc-400 mt-1 line-clamp-2 leading-relaxed">
                  {s.hook}
                </p>
              </div>

              <div className="pt-2 border-t border-zinc-800/60 flex items-center justify-between text-[10px] font-mono text-zinc-500">
                <span>{s.target_audience}</span>
                <span className="text-amber-400 group-hover:translate-x-0.5 transition-transform">
                  Search & Screen &rarr;
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Search & Pre-Screening Banner */}
      <div className="p-6 rounded-2xl bg-zinc-900/60 border border-zinc-800/80 backdrop-blur-sm">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-5">
          <div>
            <div className="flex items-center gap-2">
              <Compass className="w-5 h-5 text-indigo-400" />
              <h2 className="text-base font-bold text-zinc-100">Bilibili Dynamic Manhua Discovery</h2>
            </div>
            <p className="text-xs text-zinc-400 mt-1">
              Zero-Waste Remote Keyframe Sniping with Computer Vision Static Watermark Pre-Screening.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <label className="flex items-center gap-2 text-xs font-mono text-zinc-300 cursor-pointer bg-zinc-800/60 px-3 py-1.5 rounded-lg border border-zinc-700/60 hover:border-zinc-600">
              <input
                type="checkbox"
                checked={screenWatermarks}
                onChange={(e) => setScreenWatermarks(e.target.checked)}
                className="rounded bg-black border-zinc-700 text-indigo-600 focus:ring-0 cursor-pointer"
              />
              <span>Screen Watermarks (Zero-Bandwidth)</span>
            </label>

            {feedback && (
              <span className="text-xs font-mono px-3 py-1.5 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                {feedback}
              </span>
            )}
          </div>
        </div>

        {/* Search Input */}
        <form onSubmit={handleSearch} className="flex gap-2">
          <div className="relative flex-1">
            <Search className="w-4 h-4 text-zinc-500 absolute left-3.5 top-3" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search Bilibili 3D series (e.g. 都市仙尊 3D 动态漫画 纯享 or Martial Peak)..."
              className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-black/60 border border-zinc-800 text-xs text-zinc-100 placeholder-zinc-500 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 font-mono"
            />
          </div>
          <button
            type="submit"
            disabled={isLoading || !searchQuery.trim()}
            className="px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:bg-zinc-800 text-white text-xs font-semibold tracking-wide transition-all shadow-md shadow-indigo-600/20"
          >
            {isLoading ? 'Scanning...' : 'Search & Audit'}
          </button>
        </form>

        {/* Genre Tags */}
        <div className="flex items-center gap-2 mt-4 overflow-x-auto pb-1">
          {GENRES.map((g) => (
            <button
              key={g.id}
              onClick={() => {
                setSelectedGenre(g.id)
                setSearchQuery('')
                setActiveThemeId(null)
              }}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all shrink-0 ${
                selectedGenre === g.id && !searchQuery
                  ? 'bg-indigo-600/20 text-indigo-400 border border-indigo-500/40'
                  : 'bg-zinc-900/60 text-zinc-400 hover:text-zinc-200 border border-zinc-800'
              }`}
            >
              {g.label}
            </button>
          ))}
        </div>
      </div>

      {/* Results Grid */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider flex items-center gap-2">
            <Flame className="w-4 h-4 text-amber-400" />
            <span>
              {activeThemeId
                ? `Ranked Candidates for Active Theme (${items.length})`
                : `Candidates (${items.length})`}
            </span>
          </h3>
        </div>

        {isLoading ? (
          <div className="py-16 text-center text-xs font-mono text-indigo-400 animate-pulse flex flex-col items-center gap-2">
            <div className="w-6 h-6 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
            <span>Sniffing remote keyframes & auditing watermarks...</span>
          </div>
        ) : items.length === 0 ? (
          <div className="py-12 text-center text-xs text-zinc-500 font-mono italic border border-dashed border-zinc-800 rounded-xl">
            No series found for this query. Select a 3D trope card above or try another keyword.
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {items.map((item, idx) => {
              const isSafe = item.is_safe !== false && item.safe !== false
              const hasWm = item.has_watermark === true
              const isClean = item.is_clean === true || (!hasWm && item.is_clean !== false)
              const efs = item.efs_score ?? 75.0
              const grade = item.grade || 'A-TIER'

              return (
                <div
                  key={idx}
                  className={`p-4 rounded-xl border transition-all flex flex-col justify-between gap-3 ${
                    hasWm
                      ? 'bg-red-950/10 border-red-900/40 opacity-75'
                      : 'bg-zinc-900/50 border-zinc-800/80 hover:border-zinc-700'
                  }`}
                >
                  <div>
                    {/* Badges Bar */}
                    <div className="flex items-center justify-between gap-2 mb-2 flex-wrap">
                      <div className="flex items-center gap-1.5">
                        <span
                          className={`text-[10px] font-mono px-2 py-0.5 rounded flex items-center gap-1 ${
                            isSafe
                              ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                              : 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                          }`}
                        >
                          {isSafe ? (
                            <>
                              <ShieldCheck className="w-3 h-3" /> SAFE
                            </>
                          ) : (
                            <>
                              <AlertTriangle className="w-3 h-3" /> RISK
                            </>
                          )}
                        </span>

                        {/* Watermark Audit Badge */}
                        {item.watermark_audit && (
                          <span
                            className={`text-[10px] font-mono px-2 py-0.5 rounded flex items-center gap-1 ${
                              isClean
                                ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                                : 'bg-red-500/15 text-red-400 border border-red-500/30'
                            }`}
                          >
                            {isClean ? (
                              <>
                                <CheckCircle2 className="w-3 h-3" /> CLEAN SOURCE
                              </>
                            ) : (
                              <>
                                <XCircle className="w-3 h-3" /> LOGO: {item.watermark_zone}
                              </>
                            )}
                          </span>
                        )}
                      </div>

                      {/* EFS Score */}
                      {item.efs_score !== undefined && (
                        <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-indigo-500/15 text-indigo-300 border border-indigo-500/30">
                          {efs} PTS ({grade})
                        </span>
                      )}
                    </div>

                    <h4 className="text-xs font-semibold text-zinc-100 line-clamp-2 leading-relaxed">
                      {item.title}
                    </h4>

                    <div className="flex items-center justify-between text-[10px] text-zinc-500 mt-2 font-mono">
                      <span>{item.author || item.uploader || 'Bilibili'}</span>
                      <span>{item.episodes ? `${item.episodes} eps` : item.duration}</span>
                      {item.view_count && <span>{Number(item.view_count).toLocaleString()} views</span>}
                    </div>
                  </div>

                  <div className="pt-2 border-t border-zinc-800/60 flex items-center justify-between gap-2">
                    <a
                      href={item.url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-[11px] font-mono text-zinc-400 hover:text-indigo-400 truncate flex items-center gap-1"
                    >
                      <Play className="w-3 h-3" /> View Source
                    </a>

                    <button
                      onClick={() => handleIngest(item.url)}
                      disabled={ingestingUrl === item.url || hasWm}
                      className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                        hasWm
                          ? 'bg-zinc-800 text-zinc-500 border border-zinc-700/40 cursor-not-allowed'
                          : 'bg-indigo-600/15 hover:bg-indigo-600/30 text-indigo-300 border border-indigo-500/30'
                      }`}
                    >
                      <Download className="w-3 h-3" />
                      <span>
                        {ingestingUrl === item.url
                          ? 'Queueing...'
                          : hasWm
                          ? 'Watermark Blocked'
                          : 'Ingest 3D Series'}
                      </span>
                    </button>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
