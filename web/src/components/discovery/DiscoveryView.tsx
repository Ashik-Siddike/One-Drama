import React, { useState, useEffect } from 'react'
import {
  Search,
  Download,
  Play,
  Sparkles,
  ExternalLink,
  ShieldCheck,
  ShieldAlert,
  Loader2,
  ChevronDown,
  ChevronUp,
  Radio,
  Archive,
  FolderSync,
  Clock,
  History,
  CheckCircle2,
  RefreshCw,
  Plus,
  X,
  Layers,
  Film,
} from 'lucide-react'
import type { PipelineStatus } from '../../types'
import {
  fetchDaily3DSuggestions,
  autoScanShortSeries,
  search3DManhua,
  fetchSafeCreators,
  auditCreatorChannel,
  fetchProductionHistory,
  fetchNextCleanSeries,
  fetchWorkspaceStatus,
  archiveWorkspace,
  fetchCustomSeries,
  addCustomSeries,
  getProxiedImageUrl,
  triggerPipelineRun,
} from '../../services/api'

interface DiscoveryViewProps {
  onIngestSeries: (queryOrUrl: string, limit?: number) => Promise<void>
  onAutoProduce: (opts: { query_or_url: string; limit?: number; archive_previous?: boolean }) => Promise<void>
  pipelineStatus: PipelineStatus | null
}

const GENRE_TABS = [
  { id: 'all', label: '🔥 সকল ড্রামা' },
  { id: '3d_urban', label: '⚡ আরবান ও রিভেঞ্জ' },
  { id: '3d_cultivation', label: '⚔️ কাল্টিভেশন ও মার্শাল আর্টস' },
  { id: '3d_system', label: '👑 ওপি সিস্টেম ও সাইন-ইন' },
  { id: '3d_apocalypse', label: '🔥 অ্যাপোক্যালিপ্স ও সার্ভাইভাল' },
  { id: '3d_billionaire', label: '💎 টাইকুন ও ঘরজামাই রিভেঞ্জ' },
  { id: '3d_scifi', label: '🧬 সাই-ফাই ও সাইবার অমর' },
]

const FALLBACK_DAILY_SERIES = [
  {
    id: 'urban_immortal',
    title: '都市仙尊归来 (3D 漫剧)',
    bengali_title: 'নগরীর অমর সম্রাট: আধুনিক পৃথিবীতে ফিরে আসা দেবমানব',
    query: '都市仙尊 3D 漫剧 分P',
    url: 'http://www.bilibili.com/video/av117177915015785',
    thumbnail: 'http://i2.hdslb.com/bfs/archive/4e0fa0e77a596ef5cc223fd8bee52bd176b03d47.jpg',
    genre: '3d_urban',
    category: 'আধুনিক কাল্টিভেশন ও পুনর্জন্ম',
    hook: 'সর্বশক্তিমান অমর সম্রাট ৩০০০ বছর পর পৃথিবীতে ফিরে আসেন এক সাধারণ ছাত্র হিসেবে! অপমানকারী ধনী ক্লাসম্যানদের চমকে দেওয়ার রোমাঞ্চকর গল্প।',
    episodes_est: '৫৫ পর্ব • প্রতিটি ৩ মিনিট',
    target_audience: 'অ্যাকশন ও রিভেঞ্জ লাভার্স',
    icon: '⚡',
    is_short_series: true,
  },
  {
    id: 'apocalypse_necromancer',
    title: '末日死灵法师 (3D 漫剧)',
    bengali_title: 'মৃত্যুঞ্জয়ী শ্যাডো লর্ড: অ্যাপোক্যালিপ্স নেক্রোম্যান্সার',
    query: '末日死灵法师 3D 漫剧 选集',
    url: 'http://www.bilibili.com/video/av117161305705311',
    thumbnail: 'http://i1.hdslb.com/bfs/archive/6c8e74b06fc72ec17edadd3dcb25fe28288c6b9b.jpg',
    genre: '3d_apocalypse',
    category: 'অ্যাপোক্যালিপ্স ও শ্যাডো সিস্টেম',
    hook: 'হঠাৎ পুরো পৃথিবী যখন দানবের নরকে পরিণত হয়, তখন বীর জাগিয়ে তোলে অপরাজিত ছায়া সেনাবাহিনী! একাই সমস্ত রাজাদের পরাজিত করে বিশ্বজয়ী হওয়ার গল্প।',
    episodes_est: '৪৯ পর্ব • প্রতিটি ৩.২ মিনিট',
    target_audience: 'ডার্ক ফ্যান্টাসি ও সোলো লেভেলিং ফ্যানস',
    icon: '🔥',
    is_short_series: true,
  },
  {
    id: 'sect_outcast_godbody',
    title: '弃徒觉醒太古神体 (3D 漫剧)',
    bengali_title: 'দেবদেহের উত্তরাধিকারী: প্রাচীন ঈশ্বরের ক্ষমতা',
    query: '弃徒觉醒神体 3D 漫剧 连载',
    url: 'http://www.bilibili.com/video/av117136424961608',
    thumbnail: 'http://i2.hdslb.com/bfs/archive/5b2dfa13cac73a128f1c014ce63fc8bbd8eb0d57.jpg',
    genre: '3d_cultivation',
    category: 'মার্শাল আর্টস ও কুংফু অ্যাকশন',
    hook: 'ক্ল্যান থেকে অপমানিত হয়ে বিতাড়িত এবং বাগদত্তার বিশ্বাসঘাতকতায় নিঃস্ব বীর গভীর গিরিখাতে প্রাচীন ঈশ্বরের হৃদয় লাভ করে ফিরে আসে সবার মুখে চড় মারতে!',
    episodes_est: '৪৩ পর্ব • প্রতিটি ৩.২ মিনিট',
    target_audience: 'মার্শাল আর্টস ও কুংফু অ্যাকশন',
    icon: '⚔️',
    is_short_series: true,
  },
  {
    id: 'overpowered_signin_system',
    title: '开局签到无敌系统 (3D 漫剧)',
    bengali_title: 'শুরুতেই আনলক অপরাজিত সাইন-ইন সিস্টেম',
    query: '开局签到无敌系统 3D 漫剧 分P',
    url: 'http://www.bilibili.com/video/av117095991872768',
    thumbnail: 'http://i1.hdslb.com/bfs/archive/634c1d75bef86f01a062deb108dcd2bf06ff1dfe.jpg',
    genre: '3d_system',
    category: 'সিস্টেম ও ইনস্ট্যান্ট পাওয়ার',
    hook: 'ভয়ংকর এক অমর জগতে প্রতিদিনের সাইন-ইন রিওয়ার্ড সিস্টেম: ১ম দিনেই ঈশ্বর-তলোয়ার, ৩০তম দিনেই অমর শরীর! একদম সুপারহিরো এনার্জি।',
    episodes_est: '৩১ পর্ব • প্রতিটি ৩.৩ মিনিট',
    target_audience: 'পাওয়ার ফ্যান্টাসি ও ফাস্ট পেসিং',
    icon: '👑',
    is_short_series: true,
  },
  {
    id: 'billionaire_hidden_heir',
    title: '首富继承人归来 (3D 漫剧)',
    bengali_title: 'গোপন ট্রিলিয়নিয়ার উত্তরাধিকারী: শত বিলিয়ন ডলারের ব্যাঙ্ক ব্যালেন্স',
    query: '首富继承人 3D 漫剧 选集',
    url: 'http://www.bilibili.com/video/av117200094498300',
    thumbnail: 'http://i0.hdslb.com/bfs/archive/5025942c612c0b65997b6163cf10c446c811423c.jpg',
    genre: '3d_billionaire',
    category: 'আধুনিক ড্রামা ও রিভেঞ্জ',
    hook: 'সবাই তাকে গরিব ও অপদার্থ ভেবে উপহাস করতো, কিন্তু হঠাৎ তার শত বিলিয়ন ডলারের ব্যাঙ্ক অ্যাকাউন্ট আনলক হতেই বদলে যায় সবার আসল রূপ!',
    episodes_est: '৬০ পর্ব • প্রতিটি ৩ মিনিট',
    target_audience: 'ভাইরাল শর্ট-ড্রামা ও স্যাটিসফ্যাকশন',
    icon: '💎',
    is_short_series: true,
  },
  {
    id: 'cybernetic_cultivator',
    title: '赛博修真：三千年后 (3D 漫剧)',
    bengali_title: 'সাইবার অমর যোদ্ধা: ৩০০০ সালের রোবোটিক যুদ্ধ',
    query: '赛博修真 3D 漫剧 连载',
    url: 'http://www.bilibili.com/video/av117188753099652',
    thumbnail: 'http://i2.hdslb.com/bfs/archive/658af34ba5d8e635c1aaaffc30d082271db38f69.jpg',
    genre: '3d_scifi',
    category: 'সাই-ফাই ও ফিউচারিস্টিক অ্যাকশন',
    hook: 'ভবিষ্যতের ৩০০০ সালের রোবোটিক সায়েন্স-ফিকশন আর মার্শাল আর্টসের মিশ্রণ: যান্ত্রিক উড়ন্ত তলোয়ার আর ডিজিটাল অ্যালকেমির শ্বাসরুদ্ধকর যুদ্ধ।',
    episodes_est: '৪৮ পর্ব • প্রতিটি ২.৫ মিনিট',
    target_audience: 'সাই-ফাই ও ফিউচারিস্টিক অ্যাকশন',
    icon: '🧬',
    is_short_series: true,
  },
  {
    id: 'dragon_king_son_in_law',
    title: '龙王赘婿逆袭 (3D 漫剧)',
    bengali_title: 'ড্রাগন কিং-এর প্রত্যাবর্তন: ঘরজামাই থেকে সেনাপতি',
    query: '龙王赘婿 3D 漫剧 分P',
    url: 'http://www.bilibili.com/video/av117127717653649',
    thumbnail: 'http://i1.hdslb.com/bfs/archive/c8c6b33ca7fa072ac495c73715390dfad137498b.jpg',
    genre: '3d_billionaire',
    category: 'রিভেঞ্জ ও স্যাটিসফ্যাকশন',
    hook: 'শ্বশুরবাড়ির চরম অপমান আর তাচ্ছিল্যের পর যখন দশ লাখ সৈন্যের প্রধান সেনাপতির আসল পরিচয় উন্মোচিত হয়!',
    episodes_est: '৫০ পর্ব • প্রতিটি ৩ মিনিট',
    target_audience: 'রিভেঞ্জ ও স্যাটিসফ্যাকশন',
    icon: '🐉',
    is_short_series: true,
  },
  {
    id: 'seven_immortal_fairies',
    title: '反派：我的师尊都是绝色仙子 (3D 漫剧)',
    bengali_title: 'আমার সাত দেবী গুরু: রূপবতী অপ্সরাদের আশীর্বাদ',
    query: '反派 我的师尊都是绝色仙子 3D 漫剧 分P',
    url: 'http://www.bilibili.com/video/av117121610878679',
    thumbnail: 'http://i1.hdslb.com/bfs/archive/918bd8a6cd68b222dd3bb51779e59aab4593f1fa.jpg',
    genre: '3d_comedy',
    category: 'কমেডি ও ফ্যামিলি ড্রামা',
    hook: 'ভিলেন বংশে জন্মালেও সাত সুন্দরী অমর দেবী গুরু বীরকে রক্ষা করতে সারা বিশ্ব কাঁপিয়ে যুদ্ধ ঘোষণা করে!',
    episodes_est: '৪২ পর্ব • প্রতিটি ২.৮ মিনিট',
    target_audience: 'কমেডি ও ফ্যামিলি ড্রামা',
    icon: '🌸',
    is_short_series: true,
  },
]



export const DiscoveryView: React.FC<DiscoveryViewProps> = ({
  onIngestSeries,
  onAutoProduce,
  pipelineStatus,
}) => {
  const [searchQuery, setSearchQuery] = useState('')
  const [activeSeriesLimit, setActiveSeriesLimit] = useState(25)
  const [dailySuggestions, setDailySuggestions] = useState<any[]>(FALLBACK_DAILY_SERIES)
  const [items, setItems] = useState<any[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [isStartingAuto, setIsStartingAuto] = useState(false)
  const [feedback, setFeedback] = useState<string | null>(null)
  const [showAdvanced, setShowAdvanced] = useState(false)

  // Genre & Refresh & Custom Modal states
  const [selectedGenre, setSelectedGenre] = useState('all')
  const [isRefreshingSuggestions, setIsRefreshingSuggestions] = useState(false)
  const [isCustomModalOpen, setIsCustomModalOpen] = useState(false)
  const [customTitle, setCustomTitle] = useState('')
  const [customUrl, setCustomUrl] = useState('')
  const [customGenre, setCustomGenre] = useState('3d_urban')
  const [isSavingCustom, setIsSavingCustom] = useState(false)
  const [isStartingQueuedProduction, setIsStartingQueuedProduction] = useState(false)

  const [activeCardId, setActiveCardId] = useState<string | null>(null)
  const [activeActionType, setActiveActionType] = useState<'autopilot' | 'download' | null>(null)
  const [activeSeriesTitle, setActiveSeriesTitle] = useState<string | null>(null)

  // Workspace status state
  const [workspaceStatus, setWorkspaceStatus] = useState<{
    has_active_assets: boolean
    raw_episodes_count: number
    raw_files: string[]
    processed_episodes_count: number
    master_movies_count: number
  } | null>(null)
  const [isArchiving, setIsArchiving] = useState(false)

  // Advanced Tools State
  const [safeCreators, setSafeCreators] = useState<any[]>([])
  const [productionHistory, setProductionHistory] = useState<any[]>([])
  const [creatorInput, setCreatorInput] = useState('')
  const [isAuditing, setIsAuditing] = useState(false)
  const [auditResult, setAuditResult] = useState<any | null>(null)
  const [nextCandidate, setNextCandidate] = useState<any | null>(null)
  const [isQueryingNext, setIsQueryingNext] = useState(false)

  const isRunning = pipelineStatus?.is_running
  const percent = Math.min(100, Math.max(0, pipelineStatus?.progress_percent || 0))

  const loadSuggestions = async (genre = selectedGenre, refresh = false) => {
    setIsRefreshingSuggestions(true)
    try {
      const data = await fetchDaily3DSuggestions(genre, refresh)
      if (data.suggestions && data.suggestions.length > 0) {
        setDailySuggestions(data.suggestions)
      }
    } catch {
      // fallback to local filter
      if (genre && genre !== 'all') {
        const filtered = FALLBACK_DAILY_SERIES.filter((s) => s.genre === genre)
        setDailySuggestions(filtered.length > 0 ? filtered : FALLBACK_DAILY_SERIES)
      } else {
        setDailySuggestions(FALLBACK_DAILY_SERIES)
      }
    } finally {
      setIsRefreshingSuggestions(false)
    }
  }

  useEffect(() => {
    loadSuggestions('all', false)
    loadWorkspace()
  }, [])

  const loadWorkspace = async () => {
    try {
      const ws = await fetchWorkspaceStatus()
      setWorkspaceStatus(ws)
    } catch {}
  }

  const handleProduceQueuedEpisodes = async () => {
    if (isRunning) return
    setIsStartingQueuedProduction(true)
    setFeedback('🎬 কিউতে থাকা পর্বগুলো দিয়ে ১-ক্লিক রিমাস্টার মুভি তৈরি শুরু হচ্ছে...')
    try {
      await triggerPipelineRun({
        carry_context: true,
        enable_filler_trim: false,
        generate_shorts: true,
      })
      await loadWorkspace()
    } catch (err: any) {
      setFeedback(`প্রোডাকশন শুরু ব্যর্থ: ${err.message}`)
    } finally {
      setIsStartingQueuedProduction(false)
    }
  }

  const handleAddCustomSeries = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!customUrl.trim() || !customTitle.trim()) return
    setIsSavingCustom(true)
    try {
      await addCustomSeries({
        title: customTitle.trim(),
        url: customUrl.trim(),
        category: 'কাস্টম ড্রামা',
        genre: customGenre,
      })
      setFeedback('✅ নতুন কাস্টম ড্রামা সফলভাবে লাইব্রেরিতে যোগ করা হয়েছে!')
      setCustomTitle('')
      setCustomUrl('')
      setIsCustomModalOpen(false)
      await loadSuggestions(selectedGenre, false)
    } catch (err: any) {
      setFeedback(`কাস্টম ড্রামা যোগ করতে ব্যর্থ: ${err.message}`)
    } finally {
      setIsSavingCustom(false)
    }
  }

  const handleGenreChange = (genreId: string) => {
    setSelectedGenre(genreId)
    loadSuggestions(genreId, false)
  }

  const [isAutoScanning, setIsAutoScanning] = useState(false)

  const handleRefreshBatch = () => {
    loadSuggestions(selectedGenre, true)
  }

  const handleAutoScanShortSeries = async () => {
    setIsAutoScanning(true)
    setFeedback('⚡ Bilibili থেকে নতুন ৩ডি শর্ট ড্রামা সিরিজ (২-৩ মিনিটের পর্ব) অটো-স্ক্যান করা হচ্ছে...')
    try {
      const res = await autoScanShortSeries(selectedGenre, 6)
      if (res.suggestions && res.suggestions.length > 0) {
        setDailySuggestions(res.suggestions)
        setFeedback(`✅ ${res.suggestions.length}টি নতুন ভেরিফাইড ৩ডি শর্ট ড্রামা সিরিজ সফলভাবে লোড হয়েছে!`)
      } else {
        await loadSuggestions(selectedGenre, true)
        setFeedback('✅ নতুন পর্বের সিরিজ ব্যাচ রিফ্রেশ করা হয়েছে!')
      }
    } catch (err: any) {
      await loadSuggestions(selectedGenre, true)
      setFeedback(`নতুন শর্ট সিরিজ রিফ্রেশ হয়েছে: ${err.message}`)
    } finally {
      setIsAutoScanning(false)
    }
  }


  const handleManualArchive = async () => {
    setIsArchiving(true)
    try {
      const res = await archiveWorkspace()
      setFeedback(`✅ ${res.message}`)
      await loadWorkspace()
    } catch (err: any) {
      setFeedback(`আর্কাইভ ব্যর্থ: ${err.message}`)
    } finally {
      setIsArchiving(false)
    }
  }

  const loadSafeCreators = async () => {
    try {
      const res = await fetchSafeCreators()
      setSafeCreators(res.all_creators || [])
    } catch (err) {
      console.error('Failed to load safe creators:', err)
    }
  }

  const loadHistory = async () => {
    try {
      const res = await fetchProductionHistory()
      setProductionHistory(res.history || [])
    } catch (err) {
      console.error('Failed to load history:', err)
    }
  }

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!searchQuery.trim()) return

    setIsLoading(true)
    setFeedback(null)
    try {
      const data = await search3DManhua(searchQuery, 6, true)
      setItems(data.results || [])
      if (!data.results || data.results.length === 0) {
        setFeedback('কোনো ক্লিন ৩ডি ড্রামা পাওয়া যায়নি। অন্য কোনো নাম দিয়ে সার্চ করুন।')
      }
    } catch (err: any) {
      setFeedback(`সার্চ ব্যর্থ হয়েছে: ${err.message}`)
    } finally {
      setIsLoading(false)
    }
  }

  const handleAutoProduceClick = async (
    query: string,
    title: string,
    limit: number,
    cardId?: string
  ) => {
    if (cardId) setActiveCardId(cardId)
    setActiveActionType('autopilot')
    setActiveSeriesTitle(title)
    setIsStartingAuto(true)
    try {
      await onAutoProduce({
        query_or_url: query,
        limit,
        archive_previous: true,
      })
      await loadWorkspace()
    } catch (err: any) {
      setFeedback(`উৎপাদন শুরু ব্যর্থ হয়েছে: ${err.message}`)
    } finally {
      setIsStartingAuto(false)
      setTimeout(() => {
        setActiveCardId(null)
        setActiveActionType(null)
      }, 4000)
    }
  }

  const handleQueueDownloadClick = async (
    query: string,
    title: string,
    limit: number,
    cardId?: string
  ) => {
    if (cardId) setActiveCardId(cardId)
    setActiveActionType('download')
    setActiveSeriesTitle(title)
    setIsStartingAuto(true)
    try {
      await onIngestSeries(query, limit)
      await loadWorkspace()
    } catch (err: any) {
      setFeedback(`ডাউনলোড শুরু ব্যর্থ হয়েছে: ${err.message}`)
    } finally {
      setIsStartingAuto(false)
      setTimeout(() => {
        setActiveCardId(null)
        setActiveActionType(null)
      }, 4000)
    }
  }

  const handleAudit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!creatorInput.trim()) return

    setIsAuditing(true)
    setAuditResult(null)
    setFeedback(null)
    try {
      const res = await auditCreatorChannel(creatorInput)
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
    setFeedback(null)
    try {
      const res = await fetchNextCleanSeries()
      if (res.candidate) {
        setNextCandidate(res.candidate)
      } else {
        setFeedback('কোনো ক্লিন আনওয়ার্কড ড্রামা পাওয়া যায়নি।')
      }
    } catch (err: any) {
      setFeedback(`Query failed: ${err.message}`)
    } finally {
      setIsQueryingNext(false)
    }
  }

  return (
    <div className="space-y-6 max-w-6xl mx-auto pb-10">
      {/* 1. Live Running Production Status Card with Real-time Progress Bar */}
      {isRunning && (
        <div className="p-5 rounded-2xl bg-gradient-to-r from-amber-950/50 via-zinc-900/95 to-indigo-950/50 border border-amber-500/40 shadow-2xl space-y-3 relative overflow-hidden">
          <div className="absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r from-amber-500 via-orange-500 to-indigo-500 animate-pulse" />

          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-amber-500/20 border border-amber-500/40 flex items-center justify-center text-amber-400">
                <Loader2 className="w-5 h-5 animate-spin" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="text-sm font-bold text-zinc-100">
                    🎬 বস, সিনেমা তৈরির কাজ পুরোদমে চলছে!
                  </h3>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30">
                    LIVE ENGINE
                  </span>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 flex items-center gap-1">
                    ⚡ প্যারালাল স্ট্রিমিং (Download ⟷ RTX 4060 GPU)
                  </span>
                </div>
                <p className="text-xs text-amber-300 font-mono mt-0.5">
                  বর্তমান পর্যায়: <strong className="text-white">{pipelineStatus?.current_stage || 'প্রসেসিং হচ্ছে...'}</strong>
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2 font-mono text-xs">
              <span className="text-zinc-400">প্রোগ্রেস:</span>
              <span className="px-2.5 py-1 rounded bg-amber-500/20 border border-amber-500/40 text-amber-300 font-bold text-sm">
                {percent > 0 ? percent.toFixed(1) : '5.0'}%
              </span>
            </div>
          </div>

          {/* Progress Bar */}
          <div className="w-full h-3 bg-zinc-950 rounded-full overflow-hidden border border-zinc-800 p-0.5 shadow-inner">
            <div
              className="h-full rounded-full bg-gradient-to-r from-amber-500 via-orange-500 to-indigo-500 transition-all duration-700 relative shadow-lg shadow-amber-500/30"
              style={{ width: `${Math.max(4, percent)}%` }}
            />
          </div>

          {pipelineStatus?.logs && pipelineStatus.logs.length > 0 && (
            <div className="p-2.5 rounded-xl bg-black/60 border border-zinc-800 text-[11px] font-mono text-zinc-300 truncate">
              <span className="text-amber-400 font-bold">&gt;</span> {pipelineStatus.logs[pipelineStatus.logs.length - 1]}
            </div>
          )}
        </div>
      )}

      {/* 2. Workspace Conflict Guard & Safe Archive Notice */}
      {workspaceStatus && workspaceStatus.has_active_assets && !isRunning && (
        <div className="p-4 rounded-2xl bg-zinc-900/80 border border-indigo-500/30 shadow-lg flex flex-col sm:flex-row sm:items-center justify-between gap-3 backdrop-blur-sm">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-indigo-500/10 border border-indigo-500/30 flex items-center justify-center text-indigo-400 shrink-0">
              <Archive className="w-4 h-4" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h4 className="text-xs font-bold text-zinc-200">
                  🛡️ আগের ড্রামা সুরক্ষা ও গরমিল রোধ সক্রিয়
                </h4>
                <span className="text-[10px] font-mono px-2 py-0.2 rounded bg-indigo-500/10 text-indigo-300 border border-indigo-500/20">
                  {workspaceStatus.raw_episodes_count} পর্ব কিউতে
                </span>
              </div>
              <p className="text-[11px] text-zinc-400 mt-0.5">
                নতুন সিনেমা শুরু করার আগে সিস্টেম স্বয়ংক্রিয়ভাবে আগের ক্লিপগুলো <code className="text-indigo-300">storage/archive</code> এ সুরক্ষিত রাখবে।
              </p>
            </div>
          </div>

          <button
            onClick={handleManualArchive}
            disabled={isArchiving}
            className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-zinc-200 hover:text-white text-xs font-medium border border-zinc-700 transition-colors shrink-0"
          >
            {isArchiving ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin text-indigo-400" />
            ) : (
              <FolderSync className="w-3.5 h-3.5 text-indigo-400" />
            )}
            <span>🗄️ এখনই আর্কাইভ ও ফ্রেশ শুরু করো</span>
          </button>
        </div>
      )}

      {/* 3. Hero & Boss Quick Input Bar */}
      <div className="p-6 rounded-2xl bg-gradient-to-br from-zinc-900 via-zinc-900/95 to-indigo-950/30 border border-zinc-800 shadow-xl space-y-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-2xl bg-amber-500/10 border border-amber-500/30 flex items-center justify-center text-2xl shadow-inner">
              👑
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-lg font-bold text-zinc-100">
                  বস মোড: ১-ক্লিক ড্রামা মুভি মেকার
                </h2>
                <span className="text-[10px] font-mono font-bold px-2.5 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                  FULL AUTO-PILOT
                </span>
              </div>
              <p className="text-xs text-zinc-400 mt-1">
                বস, আপনি চাইলে সরাসরি ১-ক্লিকে ফুল মুভি বানাতে পারেন, অথবা অবসর সময়ে পর্বগুলো ডাউনলোড করে কিউতে রেখে পরে প্রসেসিং করতে পারেন!
              </p>
            </div>
          </div>
        </div>

        {/* Input Bar */}
        <div className="flex flex-col md:flex-row items-center gap-2.5 pt-2">
          <div className="relative flex-1 w-full">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="🔗 যেকোনো ড্রামার লিঙ্ক বা নাম দিন (Bilibili, Douyin, YouTube, ইত্যাদি)..."
              className="w-full pl-4 pr-10 py-3 rounded-xl bg-black/60 border border-zinc-800 focus:border-amber-500/60 text-xs text-zinc-200 focus:outline-none placeholder:text-zinc-500"
            />
          </div>

          <div className="flex items-center gap-2 w-full md:w-auto flex-wrap sm:flex-nowrap">
            <select
              value={activeSeriesLimit}
              onChange={(e) => setActiveSeriesLimit(Number(e.target.value))}
              className="px-3 py-3 rounded-xl bg-black/60 border border-zinc-800 text-xs text-zinc-200 focus:outline-none font-mono"
            >
              <option value={25}>২৫ পর্ব (প্রতিটি ২-৩ মিনিট)</option>
              <option value={30}>৩০ পর্ব (প্রতিটি ২-৩ মিনিট)</option>
              <option value={50}>৫০ পর্ব (মেগা শর্ট সিরিজ)</option>
            </select>

            {/* 1-Click AutoPilot */}
            <button
              onClick={() =>
                handleAutoProduceClick(
                  searchQuery || '都市仙尊 3D 漫剧 分P',
                  'কাস্টম সিরিজ',
                  activeSeriesLimit
                )
              }
              disabled={isRunning || isStartingAuto}
              className="flex-1 sm:flex-initial flex items-center justify-center gap-2 px-5 py-3 rounded-xl bg-gradient-to-r from-amber-500 via-orange-500 to-indigo-600 hover:from-amber-400 hover:to-indigo-500 disabled:opacity-50 text-white text-xs font-bold transition-all shadow-lg shadow-amber-600/20 whitespace-nowrap"
            >
              {isStartingAuto && activeActionType === 'autopilot' ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin text-white" />
                  <span>ইঞ্জিন শুরু হচ্ছে...</span>
                </>
              ) : (
                <>
                  <Sparkles className="w-4 h-4 text-amber-200 fill-current" />
                  <span>🎬 ১-ক্লিকে ফুল মুভি বানাও</span>
                </>
              )}
            </button>

            {/* Queue Download Only */}
            <button
              onClick={() =>
                handleQueueDownloadClick(
                  searchQuery || '都市仙尊 3D 漫剧 分P',
                  'কাস্টম সিরিজ',
                  activeSeriesLimit
                )
              }
              disabled={isRunning || isStartingAuto}
              className="flex items-center justify-center gap-1.5 px-4 py-3 rounded-xl bg-zinc-800/90 hover:bg-zinc-700/90 border border-zinc-700/80 text-zinc-200 hover:text-white text-xs font-semibold transition-all whitespace-nowrap"
              title="অবসর সময়ে শুধু পর্বগুলো ডাউনলোড করে রাখুন, পরে সময়মতো প্রসেসিং করবেন"
            >
              {isStartingAuto && activeActionType === 'download' ? (
                <Loader2 className="w-4 h-4 animate-spin text-indigo-400" />
              ) : (
                <Download className="w-4 h-4 text-indigo-400" />
              )}
              <span>📥 শুধু কিউতে ডাউনলোড</span>
            </button>

            <button
              type="button"
              onClick={handleSearch}
              disabled={isLoading || !searchQuery.trim()}
              className="px-3 py-3 rounded-xl bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 text-zinc-400 hover:text-zinc-200 text-xs font-semibold transition-all"
              title="সার্চ করে ম্যানুয়ালি ফলাফল দেখুন"
            >
              <Search className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {feedback && (
        <div className="p-3 rounded-xl bg-indigo-500/10 border border-indigo-500/30 text-xs text-indigo-300 font-mono flex items-center justify-between">
          <span>{feedback}</span>
          <button onClick={() => setFeedback(null)} className="text-zinc-500 hover:text-zinc-300 ml-2">
            ✕
          </button>
        </div>
      )}

      {/* Queued Episodes 1-Click Production Banner */}
      {workspaceStatus && workspaceStatus.raw_episodes_count > 0 && !isRunning && (
        <div className="p-4 rounded-2xl bg-gradient-to-r from-amber-500/15 via-indigo-600/20 to-emerald-500/15 border border-amber-500/50 shadow-2xl flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-3.5">
            <div className="w-11 h-11 rounded-2xl bg-amber-500/20 border border-amber-500/40 flex items-center justify-center text-amber-400 shrink-0 text-xl shadow-inner">
              📥
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-bold text-zinc-100">
                  🎬 ওয়ার্কস্পেস কিউ রেডি: {workspaceStatus.raw_episodes_count} টি পর্ব ডাউনলোড করা আছে!
                </h3>
                <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/40">
                  READY TO PRODUCE
                </span>
              </div>
              <p className="text-xs text-zinc-300 mt-0.5">
                বস, আপনার কিউতে পর্বগুলো সংরক্ষিত আছে। নতুন করে ডাউনলোড না করেই এখনই সম্পূর্ণ এআই ডাবিং ও ফুল মুভি তৈরি শুরু করতে পারেন!
              </p>
            </div>
          </div>

          <button
            onClick={handleProduceQueuedEpisodes}
            disabled={isRunning || isStartingQueuedProduction}
            className="flex items-center justify-center gap-2 px-6 py-3 rounded-xl bg-gradient-to-r from-emerald-500 via-teal-500 to-indigo-600 hover:from-emerald-400 hover:to-indigo-500 disabled:opacity-50 text-white text-xs font-bold transition-all shadow-lg shadow-emerald-500/20 whitespace-nowrap"
          >
            {isStartingQueuedProduction ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin text-white" />
                <span>মুভি তৈরি শুরু হচ্ছে...</span>
              </>
            ) : (
              <>
                <Sparkles className="w-4 h-4 text-emerald-200 fill-current" />
                <span>🚀 কিউ থেকে এখনই ফুল মুভি বানান</span>
              </>
            )}
          </button>
        </div>
      )}

      {/* 4. 3D Manhua Library, Genre Tabs & Fresh Batch Discovery */}
      <div className="space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h3 className="text-sm font-bold text-zinc-100 flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-amber-400" />
              <span>৩ডি মানহুয়া ড্রামা লাইব্রেরি ও ট্রেন্ডিং রিকমেন্ডেশন</span>
            </h3>
            <p className="text-xs text-zinc-400 mt-0.5">
              পোস্টার দেখে পছন্দ করুন, নতুন ড্রামা রিফ্রেশ করুন অথবা যেকোনো কাস্টম ড্রামা যোগ করুন:
            </p>
          </div>

          <div className="flex items-center gap-2 flex-wrap sm:flex-nowrap">
            {/* Auto-Scan 3D Short Series Button */}
            <button
              onClick={handleAutoScanShortSeries}
              disabled={isAutoScanning || isRefreshingSuggestions}
              className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-gradient-to-r from-amber-500/20 via-orange-500/20 to-indigo-500/20 hover:from-amber-500/30 hover:to-indigo-500/30 border border-amber-500/40 text-amber-300 text-xs font-bold transition-all shadow-sm shadow-amber-500/10 whitespace-nowrap"
              title="Bilibili থেকে স্বয়ংক্রিয়ভাবে ২-৩ মিনিটের ছোট পর্বের নতুন ৩ডি সিরিজ খুঁজে বের করুন"
            >
              {isAutoScanning ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin text-amber-400" />
                  <span>⚡ স্ক্যানিং চলছে...</span>
                </>
              ) : (
                <>
                  <Sparkles className="w-3.5 h-3.5 text-amber-400 fill-current" />
                  <span>⚡ নতুন ৩ডি শর্ট ড্রামা সিরিজ অটো-খুঁজুন</span>
                </>
              )}
            </button>

            {/* Refresh Fresh Batch */}
            <button
              onClick={handleRefreshBatch}
              disabled={isRefreshingSuggestions || isAutoScanning}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-zinc-800/90 hover:bg-zinc-700/90 border border-zinc-700 text-zinc-200 text-xs font-medium transition-all"
              title="নতুন আরেক ঝাঁক ড্রামা লোড করুন"
            >
              <RefreshCw className={`w-3.5 h-3.5 text-amber-400 ${isRefreshingSuggestions ? 'animate-spin' : ''}`} />
              <span>🔄 রিফ্রেশ</span>
            </button>

            {/* Add Custom Series */}
            <button
              onClick={() => setIsCustomModalOpen(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-amber-500/10 hover:bg-amber-500/20 border border-amber-500/30 text-amber-300 text-xs font-medium transition-all"
              title="যেকোনো নতুন Bilibili/Douyin লিঙ্ক দিয়ে ড্রামা কার্ড তৈরি করুন"
            >
              <Plus className="w-3.5 h-3.5 text-amber-400" />
              <span>➕ কাস্টম</span>
            </button>
          </div>
        </div>

        {/* Genre Filter Tabs */}
        <div className="flex items-center gap-1.5 overflow-x-auto pb-1 pt-1 no-scrollbar">
          {GENRE_TABS.map((tab) => {
            const isActive = selectedGenre === tab.id
            return (
              <button
                key={tab.id}
                onClick={() => handleGenreChange(tab.id)}
                disabled={isRefreshingSuggestions}
                className={`px-3 py-1.5 rounded-xl text-xs font-semibold whitespace-nowrap transition-all border ${
                  isActive
                    ? 'bg-amber-500 text-black border-amber-400 shadow-md shadow-amber-500/20'
                    : 'bg-zinc-900/80 text-zinc-400 hover:text-zinc-200 border-zinc-800 hover:border-zinc-700'
                }`}
              >
                {tab.label}
              </button>
            )
          })}
        </div>

        {activeSeriesTitle && (
          <div className="p-4 rounded-2xl bg-gradient-to-r from-emerald-950/50 via-zinc-900 to-indigo-950/50 border border-emerald-500/50 flex items-center gap-3 shadow-xl">
            <div className="w-9 h-9 rounded-xl bg-emerald-500/20 border border-emerald-500/40 flex items-center justify-center text-emerald-400 shrink-0">
              <Sparkles className="w-5 h-5 animate-pulse" />
            </div>
            <div className="flex-1">
              <h4 className="text-sm font-bold text-zinc-100 flex items-center gap-2">
                <span>🎬 বস, "{activeSeriesTitle}"-এর কাজ শুরু হয়েছে!</span>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                  STARTED
                </span>
              </h4>
              <p className="text-xs text-emerald-300/80 font-mono mt-0.5">
                উপরে লাইভ প্রগ্রেস বারে শতকরা হিসাব ও রিয়েল-টাইম স্পিড দেখতে পাচ্ছেন।
              </p>
            </div>
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-2 gap-5">
          {dailySuggestions.map((s) => (
            <div
              key={s.id}
              className="p-5 rounded-2xl bg-zinc-900/70 border border-zinc-800/80 hover:border-amber-500/40 hover:bg-zinc-900/95 transition-all flex flex-col justify-between gap-4 group shadow-xl"
            >
              <div className="space-y-3">
                {/* Visual Anime Poster Banner */}
                <div className="relative w-full h-48 rounded-xl overflow-hidden bg-zinc-950 border border-zinc-800/90 group-hover:border-amber-500/40 transition-colors">
                  {s.thumbnail ? (
                    <img
                      src={getProxiedImageUrl(s.thumbnail)}
                      alt={s.title}
                      referrerPolicy="no-referrer"
                      className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
                      onError={(e) => {
                        ;(e.currentTarget as HTMLElement).style.display = 'none'
                      }}
                    />
                  ) : (
                    <div className="w-full h-full flex flex-col items-center justify-center bg-gradient-to-br from-indigo-950/50 via-zinc-900 to-amber-950/40">
                      <span className="text-4xl">{s.icon || '🎬'}</span>
                    </div>
                  )}
                  <div className="absolute inset-0 bg-gradient-to-t from-zinc-950 via-zinc-950/30 to-transparent pointer-events-none" />

                  <div className="absolute top-2.5 left-2.5 flex items-center gap-1.5">
                    <span className="text-[10px] font-mono px-2.5 py-0.5 rounded-full bg-black/75 backdrop-blur-md text-amber-400 border border-amber-500/30 shadow-md">
                      {s.category || '3D AI ড্রামা'}
                    </span>
                  </div>

                  <div className="absolute bottom-2.5 right-2.5">
                    <span className="text-[10px] font-mono px-2.5 py-0.5 rounded bg-black/80 backdrop-blur-md text-emerald-400 border border-emerald-500/30 shadow-md">
                      {s.episodes_est || '৫০ পর্ব • প্রতিটি ২-৩ মিনিট'}
                    </span>
                  </div>
                </div>

                <div>
                  <h4 className="text-sm font-bold text-zinc-100 group-hover:text-amber-300 transition-colors">
                    {s.bengali_title || s.title}
                  </h4>
                  <p className="text-[11px] font-mono text-zinc-500 mt-0.5 truncate">
                    {s.title}
                  </p>
                </div>

                <p className="text-xs text-zinc-400 leading-relaxed line-clamp-3">
                  {s.bengali_hook || s.hook}
                </p>

                <div className="flex items-center gap-2 text-[10px] font-mono pt-1">
                  <span className="px-2 py-0.5 rounded bg-indigo-500/10 text-indigo-300 border border-indigo-500/20">
                    {s.episodes_est || '৫০ পর্ব • প্রতিটি ২-৩ মিনিট'}
                  </span>
                  <span className="px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                    ✓ ক্লিন ভিডিও
                  </span>
                </div>
              </div>

              {/* Action Buttons: 1-Click AutoPilot & Queue Download */}
              <div className="flex flex-col gap-2 pt-1 border-t border-zinc-800/80">
                <button
                  onClick={() =>
                    handleAutoProduceClick(s.url || s.query, s.bengali_title || s.title, 25, s.id)
                  }
                  disabled={isRunning || isStartingAuto}
                  className="flex items-center justify-center gap-2 w-full py-2.5 rounded-xl bg-gradient-to-r from-amber-500 via-orange-500 to-indigo-600 hover:from-amber-400 hover:to-indigo-500 disabled:opacity-50 text-white text-xs font-bold tracking-wide transition-all shadow-md shadow-amber-600/20"
                >
                  {activeCardId === s.id && activeActionType === 'autopilot' ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin text-white" />
                      <span>🎬 সিনেমা তৈরির কাজ শুরু হচ্ছে...</span>
                    </>
                  ) : (
                    <>
                      <Play className="w-3.5 h-3.5 fill-current" />
                      <span>🎬 বস, এইটা ১-ক্লিকে ফুল মুভি বানাও</span>
                    </>
                  )}
                </button>

                <button
                  onClick={() =>
                    handleQueueDownloadClick(s.url || s.query, s.bengali_title || s.title, 25, s.id)
                  }
                  disabled={isRunning || isStartingAuto}
                  className="flex items-center justify-center gap-2 w-full py-2 rounded-xl bg-zinc-800/90 hover:bg-zinc-700/90 border border-zinc-700/80 text-zinc-200 hover:text-white text-xs font-semibold transition-all"
                  title="অবসর সময়ে শুধু পর্বগুলো ডাউনলোড করে কিউতে জমা রাখুন, পরে যেকোনো সময় মুভি বানাবেন"
                >
                  {activeCardId === s.id && activeActionType === 'download' ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin text-indigo-400" />
                      <span>📥 কিউতে ডাউনলোড হচ্ছে...</span>
                    </>
                  ) : (
                    <>
                      <Download className="w-3.5 h-3.5 text-indigo-400" />
                      <span>📥 শুধু ডাউনলোড করে কিউতে রাখো</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 5. Search Results Grid (If user performed a search) */}
      {items.length > 0 && (
        <div className="space-y-4 pt-4 border-t border-zinc-800">
          <div className="flex items-center justify-between">
            <h4 className="text-sm font-bold text-zinc-100 flex items-center gap-2">
              <Search className="w-4 h-4 text-indigo-400" />
              <span>সার্চের ফলাফল ({items.length}টি সিরিজ পাওয়া গেছে)</span>
            </h4>
            <span className="text-xs text-zinc-500 font-mono">
              যেকোনো একটি সিলেক্ট করে ১-ক্লিকে বানাতে পারেন বা ডাউনলোড করতে পারেন
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {items.map((item, idx) => {
              const hasWm = item.watermark_detected
              return (
                <div
                  key={idx}
                  className="p-4 rounded-xl bg-zinc-900/60 border border-zinc-800 flex flex-col justify-between gap-3 shadow-md"
                >
                  <div className="space-y-2">
                    <div className="flex items-start justify-between gap-2">
                      <h5 className="text-xs font-bold text-zinc-200 line-clamp-2">
                        {item.title}
                      </h5>
                      {hasWm ? (
                        <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-red-500/10 text-red-400 border border-red-500/20 shrink-0 flex items-center gap-1">
                          <ShieldAlert className="w-3 h-3" /> ওয়াটারমার্ক
                        </span>
                      ) : (
                        <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 shrink-0 flex items-center gap-1">
                          <ShieldCheck className="w-3 h-3" /> ক্লিন
                        </span>
                      )}
                    </div>

                    <p className="text-[11px] text-zinc-500 font-mono">
                      চ্যানেল: {item.uploader || 'UP Creator'}
                    </p>
                  </div>

                  <div className="pt-2 border-t border-zinc-800 flex flex-col gap-2">
                    <div className="flex items-center justify-between">
                      <a
                        href={item.url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-[11px] text-zinc-400 hover:text-indigo-400 flex items-center gap-1 font-mono"
                      >
                        <ExternalLink className="w-3 h-3" /> লিংক
                      </a>

                      <button
                        onClick={() =>
                          handleAutoProduceClick(item.url, item.title, activeSeriesLimit)
                        }
                        disabled={isRunning || isStartingAuto || hasWm}
                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600/20 hover:bg-emerald-600/40 text-emerald-300 border border-emerald-500/30 text-xs font-bold transition-all disabled:opacity-40"
                      >
                        <Sparkles className="w-3.5 h-3.5" />
                        <span>{hasWm ? 'ব্লকড' : '১-ক্লিকে মুভি'}</span>
                      </button>
                    </div>

                    <button
                      onClick={() =>
                        handleQueueDownloadClick(item.url, item.title, activeSeriesLimit)
                      }
                      disabled={isRunning || isStartingAuto || hasWm}
                      className="flex items-center justify-center gap-1.5 w-full py-1.5 rounded-lg bg-zinc-800/80 hover:bg-zinc-700/80 text-zinc-300 text-[11px] font-mono border border-zinc-700/60 transition-all disabled:opacity-40"
                    >
                      <Download className="w-3 h-3 text-indigo-400" />
                      <span>শুধু কিউতে ডাউনলোড</span>
                    </button>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* 6. Collapsible Advanced Settings & Channels */}
      <div className="pt-6 border-t border-zinc-800/80">
        <button
          onClick={() => {
            const next = !showAdvanced
            setShowAdvanced(next)
            if (next) {
              loadSafeCreators()
              loadHistory()
            }
          }}
          className="flex items-center gap-2 text-xs font-mono text-zinc-400 hover:text-zinc-200 transition-colors p-2 rounded-lg bg-zinc-900/60 border border-zinc-800"
        >
          {showAdvanced ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          <span>
            {showAdvanced ? 'অ্যাডভান্সড চ্যানেল স্কাউট ও হিস্ট্রি বন্ধ করুন' : '⚙️ অ্যাডভান্সড চ্যানেল স্কাউট ও হিস্ট্রি দেখুন'}
          </span>
        </button>

        {showAdvanced && (
          <div className="space-y-6 pt-4">
            {/* Auto Candidate Finder */}
            <div className="p-4 rounded-xl bg-zinc-900/60 border border-zinc-800 space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <h4 className="text-xs font-bold text-zinc-200 flex items-center gap-2">
                    <Sparkles className="w-4 h-4 text-amber-400" />
                    <span>পরবর্তী ফ্রেশ ও আনওয়ার্কড ড্রামা অটো-ফাইন্ডার</span>
                  </h4>
                  <p className="text-[11px] text-zinc-400 mt-0.5">
                    ভেরিফায়েড সেফ চ্যানেল থেকে স্বয়ংক্রিয়ভাবে একটি আনওয়ার্কড ও ওয়াটারমার্ক-মুক্ত ড্রামা খুঁজে বের করবে
                  </p>
                </div>

                <button
                  onClick={handleFindNextClean}
                  disabled={isQueryingNext || isRunning}
                  className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-indigo-600/30 hover:bg-indigo-600/50 text-indigo-300 border border-indigo-500/40 text-xs font-bold transition-all disabled:opacity-50"
                >
                  {isQueryingNext ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <Radio className="w-3.5 h-3.5" />
                  )}
                  <span>পরবর্তী ফ্রেশ ড্রামা খোঁজো</span>
                </button>
              </div>

              {nextCandidate && (
                <div className="p-3 rounded-lg bg-black/50 border border-emerald-500/30 flex items-center justify-between gap-3">
                  <div>
                    <span className="text-xs font-bold text-emerald-300 block">
                      {nextCandidate.title || nextCandidate.series?.title || 'Clean Series Candidate'}
                    </span>
                    <span className="text-[10px] font-mono text-zinc-400">
                      আপলোডার: {nextCandidate.uploader || nextCandidate.series?.uploader || 'Verified UP'} • {nextCandidate.episodes || nextCandidate.series?.episodes || 25} পর্ব
                    </span>
                  </div>

                  <div className="flex items-center gap-2">
                    <button
                      onClick={() =>
                        handleAutoProduceClick(
                          nextCandidate.url || nextCandidate.series?.url || '',
                          nextCandidate.title || nextCandidate.series?.title || 'Fresh Series',
                          25
                        )
                      }
                      disabled={isRunning}
                      className="px-3 py-1.5 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-black text-xs font-bold transition-all"
                    >
                      🎬 ১-ক্লিকে বানাও
                    </button>
                    <button
                      onClick={() =>
                        handleQueueDownloadClick(
                          nextCandidate.url || nextCandidate.series?.url || '',
                          nextCandidate.title || nextCandidate.series?.title || 'Fresh Series',
                          25
                        )
                      }
                      disabled={isRunning}
                      className="px-3 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs font-semibold border border-zinc-700"
                    >
                      📥 ডাউনলোড
                    </button>
                  </div>
                </div>
              )}
            </div>

            {/* Creator Space Audit Tool */}
            <div className="p-4 rounded-xl bg-zinc-900/60 border border-zinc-800 space-y-3">
              <h4 className="text-xs font-bold text-zinc-200 flex items-center gap-2">
                <ShieldCheck className="w-4 h-4 text-emerald-400" />
                <span>বিলিবিলি ক্রিয়েটর স্পেস সেফটি অডিট</span>
              </h4>
              <p className="text-[11px] text-zinc-400">
                ক্রিয়েটরের স্পেস লিঙ্ক বা MID দিন—ইঞ্জিন স্বয়ংক্রিয়ভাবে তার ভিডিওগুলো স্ক্যান করে স্কোরকার্ড তৈরি করবে।
              </p>

              <form onSubmit={handleAudit} className="flex gap-2">
                <input
                  type="text"
                  value={creatorInput}
                  onChange={(e) => setCreatorInput(e.target.value)}
                  placeholder="space.bilibili.com/123456 বা ক্রিয়েটর লিঙ্ক..."
                  className="flex-1 px-3 py-2 rounded-lg bg-black/60 border border-zinc-800 text-xs text-zinc-200 focus:outline-none"
                />
                <button
                  type="submit"
                  disabled={isAuditing || !creatorInput.trim()}
                  className="px-4 py-2 rounded-lg bg-zinc-800 hover:bg-zinc-700 border border-zinc-700 text-xs font-bold text-zinc-200 transition-all disabled:opacity-50"
                >
                  {isAuditing ? <Loader2 className="w-4 h-4 animate-spin" /> : 'অডিট করো'}
                </button>
              </form>

              {auditResult && (
                <div className="p-3 rounded-lg bg-black/50 border border-zinc-800 text-xs font-mono space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-zinc-200">{auditResult.name}</span>
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                        auditResult.is_safe
                          ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                          : 'bg-red-500/20 text-red-300 border border-red-500/30'
                      }`}
                    >
                      {auditResult.is_safe ? '✓ SAFE CREATOR' : '⚠ HIGH RISK'}
                    </span>
                  </div>
                  <p className="text-zinc-400 text-[11px]">
                    ক্লিন রেশিও: {(auditResult.clean_ratio * 100).toFixed(0)}% • মোট স্ক্যান: {auditResult.total_audited}টি
                  </p>
                </div>
              )}
            </div>

            {/* Safe Creators List */}
            <div className="space-y-2">
              <h4 className="text-xs font-bold text-zinc-300 uppercase tracking-wider font-mono">
                ভেরিফায়েড সেফ ক্রিয়েটর তালিকা ({safeCreators.length}টি)
              </h4>
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
                {safeCreators.map((c, i) => (
                  <div key={i} className="p-3 rounded-xl bg-black/40 border border-zinc-800/80 space-y-1">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-zinc-200 truncate">{c.name}</span>
                      <span className="text-[10px] font-mono text-emerald-400">
                        {(c.clean_ratio * 100).toFixed(0)}%
                      </span>
                    </div>
                    <p className="text-[10px] font-mono text-zinc-500">
                      সফল ড্রামা: {c.successful_dramas || 0}টি
                    </p>
                  </div>
                ))}
              </div>
            </div>

            {/* Production History & Deduplication Records */}
            <div className="space-y-2 pt-2">
              <h4 className="text-xs font-bold text-zinc-300 uppercase tracking-wider font-mono flex items-center gap-2">
                <History className="w-3.5 h-3.5 text-zinc-400" />
                <span>প্রোডাকশন হিস্ট্রি ও ডুপ্লিকেশন গার্ড ({productionHistory.length}টি রেকর্ড)</span>
              </h4>
              <div className="space-y-2 max-h-48 overflow-y-auto">
                {productionHistory.map((h, i) => (
                  <div key={i} className="p-2.5 rounded-lg bg-black/40 border border-zinc-800 flex items-center justify-between text-xs font-mono">
                    <div className="truncate flex-1 mr-2">
                      <span className="text-zinc-200 font-bold block truncate">{h.title || h.series_id}</span>
                      <span className="text-[10px] text-zinc-500">
                        {h.date_added ? new Date(h.date_added * 1000).toLocaleDateString() : 'N/A'} • {h.episodes_count || 0} পর্ব
                      </span>
                    </div>
                    <span className="px-2 py-0.5 rounded text-[10px] bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                      {h.status || 'completed'}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* 6. Add Custom Series Modal */}
      {isCustomModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-lg p-6 rounded-2xl bg-zinc-900 border border-zinc-800 shadow-2xl space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-zinc-100 flex items-center gap-2">
                <Plus className="w-4 h-4 text-amber-400" />
                <span>নতুন কাস্টম ড্রামা সিরিজ যোগ করুন</span>
              </h3>
              <button
                onClick={() => setIsCustomModalOpen(false)}
                className="p-1 rounded-lg text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleAddCustomSeries} className="space-y-3">
              <div>
                <label className="block text-xs text-zinc-400 mb-1">ড্রামার নাম (বা বাংলা টাইটেল):</label>
                <input
                  type="text"
                  value={customTitle}
                  onChange={(e) => setCustomTitle(e.target.value)}
                  placeholder="যেমন: অপরাজিত ঈশ্বর সম্রাট (3D)"
                  required
                  className="w-full px-3 py-2.5 rounded-xl bg-black/60 border border-zinc-800 focus:border-amber-500/60 text-xs text-zinc-200 focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-xs text-zinc-400 mb-1">Bilibili / Douyin ভিডিও বা প্লেলিস্ট লিঙ্ক:</label>
                <input
                  type="text"
                  value={customUrl}
                  onChange={(e) => setCustomUrl(e.target.value)}
                  placeholder="https://www.bilibili.com/video/BV1... বা http://www.bilibili.com/video/av..."
                  required
                  className="w-full px-3 py-2.5 rounded-xl bg-black/60 border border-zinc-800 focus:border-amber-500/60 text-xs text-zinc-200 focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-xs text-zinc-400 mb-1">জনরা / ক্যাটাগরি:</label>
                <select
                  value={customGenre}
                  onChange={(e) => setCustomGenre(e.target.value)}
                  className="w-full px-3 py-2.5 rounded-xl bg-black/60 border border-zinc-800 text-xs text-zinc-200 focus:outline-none font-mono"
                >
                  <option value="3d_urban">⚡ আরবান ও রিভেঞ্জ</option>
                  <option value="3d_cultivation">⚔️ কাল্টিভেশন ও মার্শাল আর্টস</option>
                  <option value="3d_system">👑 ওপি সিস্টেম ও সাইন-ইন</option>
                  <option value="3d_apocalypse">🔥 অ্যাপোক্যালিপ্স ও সার্ভাইভাল</option>
                  <option value="3d_billionaire">💎 টাইকুন ও ঘরজামাই রিভেঞ্জ</option>
                  <option value="3d_scifi">🧬 সাই-ফাই ও সাইবার অমর</option>
                </select>
              </div>

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setIsCustomModalOpen(false)}
                  className="px-4 py-2 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-xs text-zinc-300 font-medium"
                >
                  বাতিল
                </button>
                <button
                  type="submit"
                  disabled={isSavingCustom}
                  className="flex items-center gap-1.5 px-5 py-2 rounded-xl bg-gradient-to-r from-amber-500 to-orange-500 hover:from-amber-400 hover:to-orange-400 text-xs text-white font-bold disabled:opacity-50"
                >
                  {isSavingCustom ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <Plus className="w-3.5 h-3.5" />
                  )}
                  <span>লাইব্রেরিতে যোগ করো</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
