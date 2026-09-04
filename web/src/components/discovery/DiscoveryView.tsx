import { useState, useEffect } from 'react'
import {
  Compass,
  Search,
  Download,
  Flame,
  ShieldCheck,
  AlertTriangle,
  Play,
} from 'lucide-react'
import type { Recommendation } from '../../types'
import { fetchTrending, searchManhua } from '../../services/api'

interface DiscoveryViewProps {
  onIngestSeries: (urlOrQuery: string) => Promise<void>
}

const GENRES = [
  { id: 'cultivation', label: 'Cultivation & Xianxia (修仙)' },
  { id: 'urban', label: 'Urban Rebirth (都市修仙)' },
  { id: 'system', label: 'Overpowered System (无敌系统)' },
  { id: 'isekai', label: 'Isekai & Fantasy (异界重生)' },
]

export const DiscoveryView: React.FC<DiscoveryViewProps> = ({ onIngestSeries }) => {
  const [selectedGenre, setSelectedGenre] = useState('cultivation')
  const [searchQuery, setSearchQuery] = useState('')
  const [items, setItems] = useState<Recommendation[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [ingestingUrl, setIngestingUrl] = useState<string | null>(null)
  const [feedback, setFeedback] = useState<string | null>(null)

  useEffect(() => {
    loadTrending(selectedGenre)
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

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!searchQuery.trim()) return
    setIsLoading(true)
    try {
      const data = await searchManhua(searchQuery.trim(), 8)
      setItems(data.results || [])
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
      {/* Search & Ingest Banner */}
      <div className="p-6 rounded-2xl bg-gradient-to-r from-indigo-950/40 via-zinc-900/60 to-zinc-900/40 border border-zinc-800/80 backdrop-blur-sm">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-5">
          <div>
            <div className="flex items-center gap-2">
              <Compass className="w-5 h-5 text-indigo-400" />
              <h2 className="text-base font-bold text-zinc-100">Bilibili Dynamic Manhua Discovery</h2>
            </div>
            <p className="text-xs text-zinc-400 mt-1">
              Curated viral manhua playlists filtered with pure clean cut ('纯享' & '无PDD') keywords.
            </p>
          </div>

          {feedback && (
            <span className="text-xs font-mono px-3 py-1.5 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              {feedback}
            </span>
          )}
        </div>

        {/* Search Input */}
        <form onSubmit={handleSearch} className="flex gap-2">
          <div className="relative flex-1">
            <Search className="w-4 h-4 text-zinc-500 absolute left-3.5 top-3" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search Bilibili series in Chinese or English (e.g. 开局无敌 动态漫画 or Martial Peak)..."
              className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-black/60 border border-zinc-800 text-xs text-zinc-100 placeholder-zinc-500 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 font-mono"
            />
          </div>
          <button
            type="submit"
            disabled={isLoading || !searchQuery.trim()}
            className="px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:bg-zinc-800 text-white text-xs font-semibold tracking-wide transition-all shadow-md shadow-indigo-600/20"
          >
            Search
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
            <span>Recommended Viral Series ({items.length})</span>
          </h3>
        </div>

        {isLoading ? (
          <div className="py-16 text-center text-xs font-mono text-indigo-400 animate-pulse">
            Querying Bilibili safe dynamic manhua API...
          </div>
        ) : items.length === 0 ? (
          <div className="py-12 text-center text-xs text-zinc-500 font-mono italic border border-dashed border-zinc-800 rounded-xl">
            No series found for this query. Try a different genre or keyword.
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {items.map((item, idx) => (
              <div
                key={idx}
                className="p-4 rounded-xl bg-zinc-900/50 border border-zinc-800/80 hover:border-zinc-700 transition-all flex flex-col justify-between gap-3"
              >
                <div>
                  <div className="flex items-center justify-between gap-2 mb-2">
                    <span
                      className={`text-[10px] font-mono px-2 py-0.5 rounded flex items-center gap-1 ${
                        item.safe
                          ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                          : 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                      }`}
                    >
                      {item.safe ? (
                        <>
                          <ShieldCheck className="w-3 h-3" /> SAFE ADAPTATION
                        </>
                      ) : (
                        <>
                          <AlertTriangle className="w-3 h-3" /> HIGH COPYRIGHT
                        </>
                      )}
                    </span>

                    {item.duration && (
                      <span className="text-[10px] font-mono text-zinc-500">
                        {item.duration}
                      </span>
                    )}
                  </div>

                  <h4 className="text-xs font-semibold text-zinc-100 line-clamp-2 leading-relaxed">
                    {item.title}
                  </h4>
                  {item.author && (
                    <p className="text-[10px] text-zinc-500 mt-1 font-mono">
                      Channel: {item.author}
                    </p>
                  )}
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
                    disabled={ingestingUrl === item.url}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-600/15 hover:bg-indigo-600/30 text-indigo-300 border border-indigo-500/30 text-xs font-medium transition-all"
                  >
                    <Download className="w-3 h-3" />
                    <span>{ingestingUrl === item.url ? 'Queueing...' : 'Ingest Series'}</span>
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
