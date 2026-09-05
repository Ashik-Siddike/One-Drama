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
  History,
  Target,
  ExternalLink,
  RefreshCw,
  Loader2,
} from 'lucide-react'
import type { Recommendation } from '../../types'
import {
  fetchTrending,
  searchManhua,
  fetchDaily3DSuggestions,
  search3DManhua,
  fetchSafeCreators,
  auditCreatorChannel,
  fetchProductionHistory,
  fetchNextCleanSeries,
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
  const [activeViewTab, setActiveViewTab] = useState<'radar' | 'safe_creators' | 'history'>('radar')
  const [selectedGenre, setSelectedGenre] = useState('3d_urban')
  const [searchQuery, setSearchQuery] = useState('')
  const [items, setItems] = useState<any[]>([])
  const [dailySuggestions, setDailySuggestions] = useState<any[]>([])
  const [activeThemeId, setActiveThemeId] = useState<string | null>(null)
  const [screenWatermarks, setScreenWatermarks] = useState(true)
  const [formatFilter, setFormatFilter] = useState<'all' | 'micro' | 'standard' | 'compilation'>('all')
  const [isLoading, setIsLoading] = useState(false)
  const [ingestingUrl, setIngestingUrl] = useState<string | null>(null)
  const [feedback, setFeedback] = useState<string | null>(null)

  // Safe Creators & Production History State
  const [safeCreators, setSafeCreators] = useState<any[]>([])
  const [productionHistory, setProductionHistory] = useState<any[]>([])
  const [creatorInput, setCreatorInput] = useState('')
  const [isAuditing, setIsAuditing] = useState(false)
  const [auditResult, setAuditResult] = useState<any | null>(null)
  const [nextCandidate, setNextCandidate] = useState<any | null>(null)
  const [isQueryingNext, setIsQueryingNext] = useState(false)

  useEffect(() => {
    fetchDaily3DSuggestions()
      .then((data) => setDailySuggestions(data.suggestions || []))
      .catch((err) => console.error('Failed to load daily 3D suggestions:', err))
    loadSafeCreators()
    loadHistory()
  }, [])

  const loadSafeCreators = async () => {
    try {
      const res = await fetchSafeCreators()
      setSafeCreators(res.all_creators || [])
    } catch (err) {
      console.error(err)
    }
  }

  const loadHistory = async () => {
    try {
      const res = await fetchProductionHistory()
      setProductionHistory(res.history || [])
    } catch (err) {
      console.error(err)
    }
  }

  const handleAuditCreator = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!creatorInput.trim()) return
    setIsAuditing(true)
    setAuditResult(null)
    try {
      const res = await auditCreatorChannel(creatorInput.trim())
      setAuditResult(res)
      await loadSafeCreators()
    } catch (err: any) {
      setFeedback(`Audit failed: ${err.message}`)
    } finally {
      setIsAuditing(false)
    }
  }

  const handleFindNextClean = async () => {
    setIsQueryingNext(true)
    setNextCandidate(null)
    try {
      const res = await fetchNextCleanSeries()
      if (res.candidate) {
        setNextCandidate(res.candidate)
      } else {
        setFeedback('No clean candidates found right now.')
      }
    } catch (err: any) {
      setFeedback(`Query failed: ${err.message}`)
    } finally {
      setIsQueryingNext(false)
    }
  }

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
      {/* View Switcher: 3D Radar vs Safe Creators Brain vs Production History */}
      <div className="flex flex-wrap items-center justify-between gap-3 p-1.5 rounded-2xl bg-zinc-900/80 border border-zinc-800">
        <div className="flex items-center gap-2">
          <button
            onClick={() => setActiveViewTab('radar')}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold font-mono tracking-wide transition-all ${
              activeViewTab === 'radar'
                ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40 shadow'
                : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/60'
            }`}
          >
            <Sparkles className="w-3.5 h-3.5 text-amber-400" />
            <span>3D Màn jù Radar</span>
          </button>

          <button
            onClick={() => {
              setActiveViewTab('safe_creators')
              loadSafeCreators()
            }}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold font-mono tracking-wide transition-all ${
              activeViewTab === 'safe_creators'
                ? 'bg-indigo-500/20 text-indigo-300 border border-indigo-500/40 shadow'
                : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/60'
            }`}
          >
            <ShieldCheck className="w-3.5 h-3.5 text-indigo-400" />
            <span>Safe Creators Brain ({safeCreators.length})</span>
          </button>

          <button
            onClick={() => {
              setActiveViewTab('history')
              loadHistory()
            }}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold font-mono tracking-wide transition-all ${
              activeViewTab === 'history'
                ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 shadow'
                : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/60'
            }`}
          >
            <History className="w-3.5 h-3.5 text-emerald-400" />
            <span>Production Ledger & Deduplication ({productionHistory.length})</span>
          </button>
        </div>

        {feedback && (
          <span className="text-xs font-mono px-3 py-1 rounded-lg bg-zinc-800 text-amber-300 border border-zinc-700">
            {feedback}
          </span>
        )}
      </div>

      {/* VIEW 1: 3D AI MÀN JÙ RADAR */}
      {activeViewTab === 'radar' && (
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
                <h3 className="text-base font-bold text-zinc-100 flex items-center gap-2">
                  <Flame className="w-5 h-5 text-amber-500" />
                  <span>3D AI Dynamic Manhua Discovery & Remote Keyframe Sniffer</span>
                </h3>
                <p className="text-xs text-zinc-400 mt-1">
                  Searches Bilibili for high-retention 3D motion comics. Screens 4 corner zones with 250 KB snippet sniffing before downloading.
                </p>
              </div>

              {/* Watermark Pre-Screening Toggle */}
              <div className="flex items-center gap-2 p-2 rounded-xl bg-black/40 border border-zinc-800">
                <ShieldCheck
                  className={`w-4 h-4 ${
                    screenWatermarks ? 'text-emerald-400' : 'text-zinc-500'
                  }`}
                />
                <span className="text-xs font-mono text-zinc-300">
                  Corner Watermark Sniffer:
                </span>
                <button
                  type="button"
                  onClick={() => setScreenWatermarks(!screenWatermarks)}
                  className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none ${
                    screenWatermarks ? 'bg-emerald-500' : 'bg-zinc-700'
                  }`}
                >
                  <span
                    className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                      screenWatermarks ? 'translate-x-4' : 'translate-x-0'
                    }`}
                  />
                </button>
              </div>
            </div>

            {/* Search Input Form */}
            <form onSubmit={handleSearch} className="flex gap-2">
              <div className="flex-1 relative">
                <Search className="w-4 h-4 text-zinc-500 absolute left-3.5 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search keywords: 都市重生 3D, 末日进化 动态漫, 剑道至尊, or specific BV id..."
                  className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-black/60 border border-zinc-800 text-xs text-zinc-100 placeholder-zinc-500 focus:outline-none focus:border-amber-500 font-mono"
                />
              </div>

              <button
                type="submit"
                disabled={isLoading || !searchQuery.trim()}
                className="px-5 py-2.5 rounded-xl bg-amber-500 hover:bg-amber-400 disabled:bg-zinc-800 disabled:text-zinc-600 text-zinc-950 text-xs font-bold font-mono tracking-wide transition-all shadow-md shadow-amber-500/20"
              >
                {isLoading ? 'Screening...' : 'Search & Audit'}
              </button>
            </form>

            {/* Genre Quick Filters */}
            <div className="flex flex-wrap items-center gap-2 mt-4 pt-4 border-t border-zinc-800/80">
              <span className="text-xs text-zinc-400 font-mono mr-1">Trending Themes:</span>
              {GENRES.map((g) => (
                <button
                  key={g.id}
                  onClick={() => {
                    setSelectedGenre(g.id)
                    setActiveThemeId(null)
                    setSearchQuery('')
                    loadTrending(g.id)
                  }}
                  className={`text-xs font-mono px-3 py-1 rounded-lg border transition-all ${
                    selectedGenre === g.id && !activeThemeId && !searchQuery
                      ? 'bg-amber-500/20 text-amber-300 border-amber-500/40'
                      : 'bg-zinc-800/60 text-zinc-400 border-zinc-700/60 hover:text-zinc-200 hover:border-zinc-600'
                  }`}
                >
                  {g.label}
                </button>
              ))}
            </div>

            {/* Content Format Filter Chips */}
            <div className="flex flex-wrap items-center gap-2 mt-3 pt-3 border-t border-zinc-800/60">
              <span className="text-[11px] font-mono text-zinc-400 mr-1">Content Format:</span>
              <button
                type="button"
                onClick={() => setFormatFilter('all')}
                className={`text-xs font-mono px-2.5 py-1 rounded-lg border transition-all ${
                  formatFilter === 'all'
                    ? 'bg-zinc-100 text-zinc-950 font-bold border-white'
                    : 'bg-zinc-800/60 text-zinc-400 border-zinc-700/60 hover:text-zinc-200'
                }`}
              >
                All Formats
              </button>
              <button
                type="button"
                onClick={() => setFormatFilter('micro')}
                className={`text-xs font-mono px-2.5 py-1 rounded-lg border transition-all flex items-center gap-1.5 ${
                  formatFilter === 'micro'
                    ? 'bg-amber-500 text-zinc-950 font-bold border-amber-400 shadow-md shadow-amber-500/20'
                    : 'bg-zinc-800/60 text-amber-300 border-zinc-700/60 hover:border-amber-500/50'
                }`}
              >
                <span>⚡ Micro-Series (3–5 min Motion Comic)</span>
                <span className="px-1.5 py-0.2 rounded bg-amber-400/20 text-[9px] font-bold">PRIORITY</span>
              </button>
              <button
                type="button"
                onClick={() => setFormatFilter('standard')}
                className={`text-xs font-mono px-2.5 py-1 rounded-lg border transition-all ${
                  formatFilter === 'standard'
                    ? 'bg-blue-600 text-white font-bold border-blue-400'
                    : 'bg-zinc-800/60 text-blue-300 border-zinc-700/60 hover:border-blue-500/50'
                }`}
              >
                📦 Standard Parts (14–15 min Batch)
              </button>
              <button
                type="button"
                onClick={() => setFormatFilter('compilation')}
                className={`text-xs font-mono px-2.5 py-1 rounded-lg border transition-all ${
                  formatFilter === 'compilation'
                    ? 'bg-purple-600 text-white font-bold border-purple-400'
                    : 'bg-zinc-800/60 text-purple-300 border-zinc-700/60 hover:border-purple-500/50'
                }`}
              >
                🎬 Full Compilation (25–30+ min)
              </button>
            </div>
          </div>

          {/* Results Grid */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h4 className="text-sm font-bold text-zinc-200 flex items-center gap-2">
                <Layers className="w-4 h-4 text-zinc-400" />
                <span>
                  Screened Candidates ({
                    items.filter((item) => {
                      if (formatFilter === 'all') return true
                      const dur = item.duration || 0
                      if (formatFilter === 'micro') return dur <= 360 || dur === 0
                      if (formatFilter === 'standard') return dur > 360 && dur <= 1200
                      if (formatFilter === 'compilation') return dur > 1200
                      return true
                    }).length
                  })
                </span>
              </h4>
            </div>

            {isLoading ? (
              <div className="py-12 text-center text-xs font-mono text-zinc-500 flex flex-col items-center justify-center gap-3">
                <div className="w-6 h-6 border-2 border-amber-500 border-t-transparent rounded-full animate-spin" />
                <span>Auditing keyframes for corner watermarks...</span>
              </div>
            ) : items.length === 0 ? (
              <div className="py-12 text-center text-xs font-mono text-zinc-500 italic border border-dashed border-zinc-800 rounded-2xl">
                No series match current filters. Try searching another 3D dynamic manhua trope.
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {items
                  .filter((item) => {
                    if (formatFilter === 'all') return true
                    const dur = item.duration || 0
                    if (formatFilter === 'micro') return dur <= 360 || dur === 0
                    if (formatFilter === 'standard') return dur > 360 && dur <= 1200
                    if (formatFilter === 'compilation') return dur > 1200
                    return true
                  })
                  .map((item, idx) => {
                    const dur = item.duration || 0
                    const isMicro = dur <= 360 || dur === 0
                    const isStandard = dur > 360 && dur <= 1200
                    const formatBadge = isMicro ? '⚡ Micro-Series' : isStandard ? '📦 Standard' : '🎬 Compilation'
                    const formatColor = isMicro ? 'bg-amber-500/10 text-amber-300 border-amber-500/30' : isStandard ? 'bg-blue-500/10 text-blue-300 border-blue-500/30' : 'bg-purple-500/10 text-purple-300 border-purple-500/30'
                  const isClean = item.is_clean !== false
                  const hasWm = item.watermark_detected === true || item.is_clean === false

                  return (
                    <div
                      key={idx}
                      className={`p-4 rounded-xl border transition-all flex flex-col justify-between gap-3 ${
                        hasWm
                          ? 'bg-zinc-900/30 border-rose-500/30 opacity-75'
                          : 'bg-zinc-900/70 border-zinc-800 hover:border-zinc-700'
                      }`}
                    >
                      <div>
                        <div className="flex items-center justify-between gap-2 mb-2">
                          <div className="flex items-center gap-1.5">
                            <span
                              className={`text-[10px] font-mono px-2 py-0.5 rounded border flex items-center gap-1 ${
                                hasWm
                                  ? 'bg-rose-500/15 text-rose-400 border-rose-500/30'
                                  : 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30'
                              }`}
                            >
                              {hasWm ? <XCircle className="w-3 h-3" /> : <CheckCircle2 className="w-3 h-3" />}
                              {hasWm ? 'WATERMARKED' : 'CLEAN (READY)'}
                            </span>
                            <span className={`text-[10px] font-mono px-2 py-0.5 rounded border ${formatColor}`}>
                              {formatBadge}
                            </span>
                          </div>

                          {item.view_count && (
                            <span className="text-[11px] font-mono text-zinc-400 flex items-center gap-1">
                              <Eye className="w-3 h-3" /> {item.view_count}
                            </span>
                          )}
                        </div>

                        <h5 className="text-xs font-bold text-zinc-100 line-clamp-2 leading-snug">
                          {item.title}
                        </h5>

                        <div className="flex items-center gap-2 text-[11px] font-mono text-zinc-400 mt-2">
                          <span>By {item.uploader || 'UP主'}</span>
                          {item.episodes && (
                            <>
                              <span>•</span>
                              <span>{item.episodes} episodes</span>
                            </>
                          )}
                        </div>

                        {hasWm && item.watermark_zone && (
                          <div className="mt-2 text-[10px] font-mono text-rose-400/90 bg-rose-950/30 px-2 py-1 rounded border border-rose-800/40">
                            Watermark in: {item.watermark_zone}
                          </div>
                        )}
                      </div>

                      <div className="pt-3 border-t border-zinc-800/80 flex items-center justify-between gap-2">
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
      )}

      {/* VIEW 2: SAFE CREATORS WHITELIST BRAIN */}
      {activeViewTab === 'safe_creators' && (
        <div className="space-y-6">
          {/* Autonomous Sourcing & Pre-Flight Gate Action */}
          <div className="p-6 rounded-2xl bg-gradient-to-r from-indigo-950/40 via-zinc-900 to-purple-950/40 border border-indigo-500/30">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <Target className="w-5 h-5 text-indigo-400" />
                  <h3 className="text-sm font-bold text-zinc-100">
                    Dual-Track Autonomous Sourcing (Safe Creators First)
                  </h3>
                </div>
                <p className="text-xs text-zinc-400">
                  Checks whitelist creators first, enforces 250 KB snippet pre-flight watermark scan, and deduplicates against production history.
                </p>
              </div>

              <button
                onClick={handleFindNextClean}
                disabled={isQueryingNext}
                className="flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:bg-zinc-800 text-white text-xs font-semibold tracking-wide transition-all shadow-lg shadow-indigo-600/20"
              >
                {isQueryingNext ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Sparkles className="w-4 h-4" />
                )}
                <span>{isQueryingNext ? 'Scouting Channels...' : 'Dispatch Next Clean Candidate'}</span>
              </button>
            </div>

            {nextCandidate && (
              <div className="mt-5 p-4 rounded-xl bg-black/60 border border-emerald-500/40 flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                      PASSED PRE-FLIGHT SCAN (0 Watermarks)
                    </span>
                    <span className="text-xs font-mono text-zinc-400">
                      Track: {nextCandidate.source_track}
                    </span>
                  </div>
                  <h4 className="text-sm font-bold text-zinc-100">{nextCandidate.title}</h4>
                  <div className="flex items-center gap-3 text-xs font-mono text-zinc-400 mt-1">
                    <span>Creator: {nextCandidate.creator_name}</span>
                    <span>•</span>
                    <a
                      href={nextCandidate.url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-indigo-400 hover:underline flex items-center gap-1"
                    >
                      <ExternalLink className="w-3 h-3" /> View on Bilibili
                    </a>
                  </div>
                </div>

                <button
                  onClick={() => handleIngest(nextCandidate.url)}
                  disabled={ingestingUrl === nextCandidate.url}
                  className="flex items-center justify-center gap-2 px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold transition-all shadow-md shadow-emerald-600/20"
                >
                  <Download className="w-4 h-4" />
                  <span>{ingestingUrl === nextCandidate.url ? 'Queueing...' : 'Ingest Verified Series'}</span>
                </button>
              </div>
            )}
          </div>

          {/* Audit & Whitelist New Creator */}
          <div className="p-5 rounded-2xl bg-zinc-900/60 border border-zinc-800">
            <h3 className="text-sm font-bold text-zinc-100 mb-2 flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-emerald-400" />
              <span>Audit & Profile New Creator Space</span>
            </h3>
            <p className="text-xs text-zinc-400 mb-4">
              Inspects 5 recent uploads from a creator's space with remote keyframe sniffing. If clean ratio &ge; 75%, creator is whitelisted.
            </p>

            <form onSubmit={handleAuditCreator} className="flex flex-col sm:flex-row gap-3">
              <input
                type="text"
                value={creatorInput}
                onChange={(e) => setCreatorInput(e.target.value)}
                disabled={isAuditing}
                placeholder="Enter Bilibili creator MID (e.g. 102553930) or Space URL..."
                className="flex-1 px-4 py-2.5 rounded-xl bg-black/60 border border-zinc-800 text-xs text-zinc-100 placeholder-zinc-500 focus:outline-none focus:border-indigo-500 font-mono"
              />
              <button
                type="submit"
                disabled={isAuditing || !creatorInput.trim()}
                className="flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl bg-zinc-800 hover:bg-zinc-700 disabled:opacity-50 text-white text-xs font-semibold font-mono border border-zinc-700"
              >
                {isAuditing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
                <span>{isAuditing ? 'Auditing Space...' : 'Run 5-Video Audit'}</span>
              </button>
            </form>

            {auditResult && (
              <div className="mt-4 p-4 rounded-xl bg-black/60 border border-zinc-800 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs font-mono">
                <div>
                  <div className="text-zinc-200 font-bold">{auditResult.name} (MID: {auditResult.creator_id})</div>
                  <div className="text-zinc-400 mt-1">
                    Clean Ratio: {((auditResult.clean_ratio || 0) * 100).toFixed(0)}% ({auditResult.clean_count}/{auditResult.total_audited} videos audited)
                  </div>
                </div>
                <div>
                  <span className={`px-2.5 py-1 rounded-lg border text-xs font-bold ${
                    auditResult.is_verified_safe
                      ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40'
                      : 'bg-amber-500/20 text-amber-400 border-amber-500/40'
                  }`}>
                    {auditResult.is_verified_safe ? 'VERIFIED SAFE CREATOR' : 'NOT WHITELISTED (<75% clean)'}
                  </span>
                </div>
              </div>
            )}
          </div>

          {/* Safe Creators Whitelist Table */}
          <div className="p-5 rounded-2xl bg-zinc-900/60 border border-zinc-800">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-bold text-zinc-100 flex items-center gap-2">
                <ShieldCheck className="w-4 h-4 text-indigo-400" />
                <span>Verified Whitelist Creators ({safeCreators.length})</span>
              </h3>
              <button
                onClick={loadSafeCreators}
                className="text-xs font-mono text-zinc-400 hover:text-zinc-200 flex items-center gap-1"
              >
                <RefreshCw className="w-3 h-3" /> Refresh
              </button>
            </div>

            {safeCreators.length === 0 ? (
              <div className="py-8 text-center text-xs text-zinc-500 font-mono italic border border-dashed border-zinc-800 rounded-xl">
                No creators audited yet. Audit a creator space above to populate the Safe Creators Brain.
              </div>
            ) : (
              <div className="space-y-2">
                {safeCreators.map((c: any) => (
                  <div
                    key={c.creator_id}
                    className="p-3.5 rounded-xl bg-black/40 border border-zinc-800/80 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs"
                  >
                    <div>
                      <div className="font-bold text-zinc-100">{c.name}</div>
                      <div className="font-mono text-zinc-400 text-[11px] mt-0.5">
                        MID: {c.creator_id} • Audited: {c.clean_count}/{c.total_audited} clean
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="font-mono px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                        {((c.clean_ratio || 0) * 100).toFixed(0)}% Clean Ratio
                      </span>
                      <a
                        href={c.space_url}
                        target="_blank"
                        rel="noreferrer"
                        className="px-2.5 py-1 rounded bg-zinc-800 text-zinc-300 hover:text-white text-[11px] font-mono flex items-center gap-1 border border-zinc-700"
                      >
                        <ExternalLink className="w-3 h-3" /> Space
                      </a>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* VIEW 3: PRODUCTION HISTORY & DEDUPLICATION LEDGER */}
      {activeViewTab === 'history' && (
        <div className="p-5 rounded-2xl bg-zinc-900/60 border border-zinc-800 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-bold text-zinc-100 flex items-center gap-2">
                <History className="w-4 h-4 text-emerald-400" />
                <span>Production History & Deduplication Ledger</span>
              </h3>
              <p className="text-xs text-zinc-400 mt-0.5">
                Every series worked, downloaded, or watermarked is tracked to prevent double-downloading.
              </p>
            </div>
            <button
              onClick={loadHistory}
              className="text-xs font-mono text-zinc-400 hover:text-zinc-200 flex items-center gap-1"
            >
              <RefreshCw className="w-3 h-3" /> Refresh
            </button>
          </div>

          {productionHistory.length === 0 ? (
            <div className="py-8 text-center text-xs text-zinc-500 font-mono italic border border-dashed border-zinc-800 rounded-xl">
              Production ledger is empty. Completed or screened series will automatically record here.
            </div>
          ) : (
            <div className="space-y-2">
              {productionHistory.map((item: any) => {
                const isDone = item.status === 'completed'
                const isRejected = item.status === 'rejected_watermarked'
                return (
                  <div
                    key={item.series_id}
                    className="p-3.5 rounded-xl bg-black/40 border border-zinc-800/80 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs"
                  >
                    <div>
                      <div className="font-bold text-zinc-100">{item.title || item.series_id}</div>
                      <div className="font-mono text-zinc-400 text-[11px] mt-0.5 flex items-center gap-2">
                        <span>ID: {item.series_id}</span>
                        <span>•</span>
                        <span>Recorded: {item.recorded_at}</span>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <span
                        className={`px-2.5 py-0.5 rounded-md font-mono text-[11px] border ${
                          isDone
                            ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                            : isRejected
                            ? 'bg-rose-500/10 text-rose-400 border-rose-500/30'
                            : 'bg-indigo-500/10 text-indigo-400 border-indigo-500/30'
                        }`}
                      >
                        {item.status.toUpperCase()}
                      </span>
                      {item.url && (
                        <a
                          href={item.url}
                          target="_blank"
                          rel="noreferrer"
                          className="px-2 py-0.5 rounded bg-zinc-800 text-zinc-400 hover:text-zinc-200 text-[11px] font-mono flex items-center gap-1 border border-zinc-700"
                        >
                          <ExternalLink className="w-3 h-3" /> URL
                        </a>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
