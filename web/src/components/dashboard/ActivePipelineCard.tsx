import { useEffect, useRef } from 'react'
import { CheckCircle2, Clock, Terminal, Radio } from 'lucide-react'
import type { PipelineStatus } from '../../types'

interface ActivePipelineCardProps {
  status: PipelineStatus | null
}

const STAGES = [
  { id: 'ingest', label: '1. Ingest / Downloader' },
  { id: 'separate', label: '2. Demucs CUDA Separation' },
  { id: 'transcribe', label: '3. SenseVoice ASR' },
  { id: 'recap', label: '4. Gemini Dramatic Story' },
  { id: 'tts', label: '5. F5-TTS Flow Voice' },
  { id: 'remaster', label: '6. FFmpeg Remaster & Delogo' },
  { id: 'concat', label: '7. Master Concat Movie' },
]

export const ActivePipelineCard: React.FC<ActivePipelineCardProps> = ({ status }) => {
  const logEndRef = useRef<HTMLDivElement>(null)
  const isRunning = status?.is_running

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [status?.logs])

  const getCurrentStageIndex = () => {
    if (!isRunning || !status?.current_stage) return -1
    const stage = status.current_stage.toLowerCase()
    if (stage.includes('download') || stage.includes('ingest')) return 0
    if (stage.includes('separat') || stage.includes('demucs')) return 1
    if (stage.includes('transcrib') || stage.includes('sensevoice')) return 2
    if (stage.includes('recap') || stage.includes('gemini') || stage.includes('translat'))
      return 3
    if (stage.includes('tts') || stage.includes('voice') || stage.includes('clon')) return 4
    if (stage.includes('remaster') || stage.includes('render')) return 5
    if (stage.includes('concat') || stage.includes('merg')) return 6
    return 1
  }

  const activeIndex = getCurrentStageIndex()

  return (
    <div className="p-5 rounded-2xl bg-gradient-to-b from-zinc-900/90 to-zinc-950 border border-zinc-800/80 shadow-xl backdrop-blur-sm">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-zinc-800/80">
        <div className="flex items-center gap-3">
          <div
            className={`p-2 rounded-xl ${
              isRunning
                ? 'bg-amber-500/10 text-amber-400 border border-amber-500/30'
                : 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30'
            }`}
          >
            {isRunning ? (
              <Radio className="w-5 h-5 animate-pulse" />
            ) : (
              <CheckCircle2 className="w-5 h-5" />
            )}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-base font-bold text-zinc-100">
                {isRunning ? 'Pipeline Job in Progress' : 'Studio Engine Ready'}
              </h3>
              <span
                className={`text-[10px] font-mono font-semibold px-2 py-0.5 rounded-full ${
                  isRunning
                    ? 'bg-amber-500/10 text-amber-400 border border-amber-500/30 animate-pulse'
                    : 'bg-zinc-800 text-zinc-400'
                }`}
              >
                {isRunning ? 'ACTIVE WORKER' : 'STANDBY'}
              </span>
            </div>
            <p className="text-xs text-zinc-400 mt-0.5">
              {isRunning
                ? status?.current_stage || 'Executing tasks...'
                : 'All background workers are idle. Ready for series ingestion or master render.'}
            </p>
          </div>
        </div>

        {isRunning && status?.started_at && (
          <div className="flex items-center gap-2 text-xs font-mono text-zinc-400 bg-zinc-900 px-3 py-1.5 rounded-lg border border-zinc-800">
            <Clock className="w-3.5 h-3.5 text-indigo-400" />
            <span>Started: {new Date(status.started_at * 1000).toLocaleTimeString()}</span>
          </div>
        )}
      </div>

      {/* 7-Stage Visual Pipeline Stepper */}
      <div className="py-4 overflow-x-auto">
        <div className="flex items-center justify-between min-w-[700px] gap-2">
          {STAGES.map((stage, idx) => {
            const isCompleted = isRunning && activeIndex > idx
            const isCurrent = isRunning && activeIndex === idx

            return (
              <div key={stage.id} className="flex-1 flex flex-col items-center">
                <div
                  className={`w-full h-1.5 rounded-full transition-all duration-300 mb-2 ${
                    isCompleted
                      ? 'bg-emerald-500'
                      : isCurrent
                      ? 'bg-indigo-500 animate-pulse'
                      : 'bg-zinc-800'
                  }`}
                />
                <span
                  className={`text-[11px] font-medium text-center truncate w-full ${
                    isCurrent
                      ? 'text-indigo-400 font-bold'
                      : isCompleted
                      ? 'text-zinc-300'
                      : 'text-zinc-600'
                  }`}
                >
                  {stage.label}
                </span>
              </div>
            )
          })}
        </div>
      </div>

      {/* Console Output Drawer */}
      <div className="mt-2 rounded-xl bg-black/80 border border-zinc-800/80 p-3 font-mono text-xs text-zinc-300">
        <div className="flex items-center justify-between pb-2 mb-2 border-b border-zinc-900 text-[10px] text-zinc-500 uppercase tracking-wider">
          <div className="flex items-center gap-1.5">
            <Terminal className="w-3 h-3 text-zinc-400" />
            <span>Live Studio Engine Console</span>
          </div>
          <span>{status?.logs?.length || 0} messages</span>
        </div>

        <div className="h-32 overflow-y-auto space-y-1 text-[11px] select-text">
          {status?.logs && status.logs.length > 0 ? (
            status.logs.map((log, index) => (
              <div
                key={index}
                className={`leading-relaxed ${
                  log.toLowerCase().includes('error')
                    ? 'text-rose-400 font-semibold'
                    : log.toLowerCase().includes('complete')
                    ? 'text-emerald-400'
                    : 'text-zinc-400'
                }`}
              >
                {log}
              </div>
            ))
          ) : (
            <div className="text-zinc-600 italic py-6 text-center">
              No active logs. Start a download or render job to see real-time pipeline output.
            </div>
          )}
          <div ref={logEndRef} />
        </div>
      </div>
    </div>
  )
}
