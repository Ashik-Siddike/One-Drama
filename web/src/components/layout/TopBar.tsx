import { Cpu, HardDrive, Play, RefreshCw } from 'lucide-react'
import type { SystemStats, PipelineStatus } from '../../types'

interface TopBarProps {
  stats: SystemStats | null
  pipelineStatus: PipelineStatus | null
  activeProjectName: string
  onTriggerPipeline: () => void
  onRefresh: () => void
  isLoading: boolean
}

export const TopBar: React.FC<TopBarProps> = ({
  stats,
  pipelineStatus,
  activeProjectName,
  onTriggerPipeline,
  onRefresh,
  isLoading,
}) => {
  const isRunning = pipelineStatus?.is_running

  return (
    <header className="h-16 px-6 bg-zinc-950/80 backdrop-blur border-b border-zinc-800/80 flex items-center justify-between z-20">
      {/* Left: Active Project Indicator */}
      <div className="flex items-center gap-3">
        <div className="flex flex-col">
          <div className="flex items-center gap-2">
            <span className="text-[11px] font-mono uppercase tracking-wider text-zinc-500">
              Active Project
            </span>
            <span className="inline-flex items-center px-1.5 py-0.2 rounded text-[10px] font-mono bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
              PROD
            </span>
          </div>
          <h2 className="text-sm font-semibold text-zinc-100 flex items-center gap-2">
            {activeProjectName}
          </h2>
        </div>
      </div>

      {/* Center/Right: Live Hardware Telemetry Pills */}
      <div className="flex items-center gap-4">
        {/* GPU VRAM Widget */}
        {stats?.gpu?.available && (
          <div className="hidden lg:flex items-center gap-2.5 px-3 py-1.5 rounded-lg bg-zinc-900/90 border border-zinc-800/80 font-mono text-xs">
            <div className="p-1 rounded bg-indigo-500/10 text-indigo-400">
              <Cpu className="w-3.5 h-3.5" />
            </div>
            <div className="flex flex-col">
              <div className="flex items-center justify-between gap-3 text-[10px] text-zinc-400">
                <span>RTX 4060 VRAM</span>
                <span className="text-indigo-400 font-semibold">
                  {stats.gpu.vram_percent}%
                </span>
              </div>
              <div className="w-28 h-1.5 bg-zinc-800 rounded-full overflow-hidden mt-0.5">
                <div
                  className="h-full bg-gradient-to-r from-indigo-500 to-violet-500 transition-all duration-500"
                  style={{ width: `${Math.min(100, stats.gpu.vram_percent)}%` }}
                />
              </div>
            </div>
          </div>
        )}

        {/* CPU / RAM Pill */}
        {stats && (
          <div className="hidden md:flex items-center gap-3 px-3 py-1.5 rounded-lg bg-zinc-900/90 border border-zinc-800/80 font-mono text-xs text-zinc-300">
            <div className="flex items-center gap-1.5">
              <span className="text-zinc-500 text-[10px]">CPU</span>
              <span>{stats.cpu_percent}%</span>
            </div>
            <span className="text-zinc-700">|</span>
            <div className="flex items-center gap-1.5">
              <span className="text-zinc-500 text-[10px]">RAM</span>
              <span>{stats.ram_used_gb}G</span>
            </div>
            <span className="text-zinc-700">|</span>
            <div className="flex items-center gap-1.5">
              <HardDrive className="w-3 h-3 text-zinc-500" />
              <span>{Math.round(stats.total_storage_mb)}MB</span>
            </div>
          </div>
        )}

        {/* Refresh button */}
        <button
          onClick={onRefresh}
          disabled={isLoading}
          title="Refresh Data"
          className="p-2 rounded-lg bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 text-zinc-400 hover:text-zinc-200 transition-colors"
        >
          <RefreshCw
            className={`w-4 h-4 ${isLoading ? 'animate-spin text-indigo-400' : ''}`}
          />
        </button>

        {/* Master Pipeline Action Button */}
        <button
          onClick={onTriggerPipeline}
          disabled={isRunning}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold tracking-wide transition-all shadow-md ${
            isRunning
              ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30 cursor-not-allowed'
              : 'bg-indigo-600 hover:bg-indigo-500 text-white shadow-indigo-500/20 hover:shadow-indigo-500/30'
          }`}
        >
          {isRunning ? (
            <>
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-amber-500"></span>
              </span>
              <span>Running Pipeline...</span>
            </>
          ) : (
            <>
              <Play className="w-3.5 h-3.5 fill-current" />
              <span>Run Master Engine</span>
            </>
          )}
        </button>
      </div>
    </header>
  )
}
