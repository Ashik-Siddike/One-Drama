import React, { useEffect, useState } from 'react'
import { Loader2, Clock, Square } from 'lucide-react'
import type { PipelineStatus } from '../../types'
import { stopPipeline } from '../../services/api'

interface GlobalPipelineProgressBarProps {
  status: PipelineStatus | null
}

export const GlobalPipelineProgressBar: React.FC<GlobalPipelineProgressBarProps> = ({ status }) => {
  const isRunning = status?.is_running
  const [elapsedSeconds, setElapsedSeconds] = useState(0)
  const [isStopping, setIsStopping] = useState(false)

  const handleStop = async () => {
    if (confirm('আপনি কি নিশ্চিত যে চলমান কাজটি বাতিল ও বন্ধ করতে চান?')) {
      try {
        setIsStopping(true)
        await stopPipeline()
      } catch (err) {
        console.error('Failed to stop pipeline:', err)
      } finally {
        setIsStopping(false)
      }
    }
  }

  useEffect(() => {
    if (!isRunning || !status?.started_at) {
      setElapsedSeconds(0)
      return
    }
    const updateTimer = () => {
      const sec = Math.max(0, Math.floor(Date.now() / 1000 - status.started_at!))
      setElapsedSeconds(sec)
    }
    updateTimer()
    const timer = setInterval(updateTimer, 1000)
    return () => clearInterval(timer)
  }, [isRunning, status?.started_at])

  if (!isRunning && (!status || status.progress_percent === 0 || status.progress_percent === 100)) {
    return null
  }

  const percent = Math.min(100, Math.max(0, status?.progress_percent || 0))
  const stageName = status?.current_stage || 'কাজ প্রক্রিয়াধীন...'
  const latestLog = status?.logs && status.logs.length > 0 ? status.logs[status.logs.length - 1] : ''

  const formatElapsed = (sec: number) => {
    const m = Math.floor(sec / 60)
    const s = sec % 60
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}s`
  }

  const getJobTitle = () => {
    if (status?.job_type === 'download') return '📥 সিরিজ পর্ব ডাউনলোড হচ্ছে (Raw Queue Ingest)'
    if (status?.job_type === 'autopilot') return '🎬 ১-ক্লিক ফুল ড্রামা মুভি অটো-প্রোডাকশন'
    return '⚙️ ৬-ধাপের মাস্টার রেন্ডার ইঞ্জিন'
  }

  return (
    <div className="bg-gradient-to-r from-zinc-950 via-zinc-900 to-indigo-950/90 border-b border-amber-500/40 px-6 py-3 shadow-2xl relative overflow-hidden z-30">
      {/* Subtle top indicator */}
      <div className="absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r from-amber-500 via-orange-500 to-indigo-500 animate-pulse" />

      <div className="flex flex-col gap-2.5 max-w-7xl mx-auto">
        {/* Top Row: Title, Stage Badge, Time & Percent */}
        <div className="flex items-center justify-between gap-4 flex-wrap">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-amber-500/20 border border-amber-500/40 flex items-center justify-center text-amber-400 shrink-0">
              <Loader2 className="w-4 h-4 animate-spin" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xs font-bold text-zinc-100 flex items-center gap-1.5">
                  {getJobTitle()}
                </span>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-amber-500/15 text-amber-300 border border-amber-500/30 animate-pulse">
                  LIVE PROGRESS
                </span>
              </div>
              <p className="text-[11px] font-mono text-amber-300/90 mt-0.5">
                বর্তমান পর্যায়: <strong className="text-white">{stageName}</strong>
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3 text-xs font-mono">
            {elapsedSeconds > 0 && (
              <div className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-zinc-900/90 border border-zinc-800 text-zinc-300">
                <Clock className="w-3.5 h-3.5 text-indigo-400" />
                <span>সময়: {formatElapsed(elapsedSeconds)}</span>
              </div>
            )}
            <div className="flex items-center gap-1 px-3 py-1 rounded-lg bg-gradient-to-r from-amber-500/20 to-orange-500/20 border border-amber-500/40 text-amber-300 font-bold text-sm">
              <span>{percent > 0 ? percent.toFixed(1) : '5.0'}%</span>
            </div>

            <button
              onClick={handleStop}
              disabled={isStopping}
              className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-red-950/60 border border-red-500/40 text-red-300 hover:bg-red-900 hover:text-white transition font-sans text-xs font-semibold cursor-pointer shadow-sm"
              title="চলমান কাজ বন্ধ বা বাতিল করুন"
            >
              <Square className="w-3 h-3 fill-red-400 text-red-400" />
              <span>{isStopping ? 'বাতিল হচ্ছে...' : 'বাতিল'}</span>
            </button>
          </div>
        </div>

        {/* Middle Row: The Animated Progress Bar */}
        <div className="relative w-full h-3 bg-zinc-950 rounded-full overflow-hidden border border-zinc-800 p-0.5 shadow-inner">
          <div
            className="h-full rounded-full bg-gradient-to-r from-amber-500 via-orange-500 to-indigo-500 transition-all duration-700 relative overflow-hidden shadow-lg shadow-amber-500/20"
            style={{ width: `${Math.max(4, percent)}%` }}
          />
        </div>

        {/* Bottom Row: Live Ticker Log */}
        {latestLog && (
          <div className="flex items-center justify-between text-[10px] font-mono text-zinc-400 truncate pt-0.5">
            <div className="flex items-center gap-2 truncate flex-1">
              <span className="text-amber-400 font-bold">&gt;</span>
              <span className="truncate text-zinc-300">{latestLog}</span>
            </div>
            <span className="text-zinc-500 hidden sm:inline ml-3 shrink-0">
              OneDrama Studio Engine v1.0
            </span>
          </div>
        )}
      </div>
    </div>
  )
}
