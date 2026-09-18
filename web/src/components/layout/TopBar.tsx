import { useState, useEffect, useRef } from 'react'
import {
  Cpu,
  HardDrive,
  Play,
  RefreshCw,
  FolderOpen,
  ChevronDown,
  Film,
  Tv,
  Scissors,
  Mic,
  Cloud,
  Folder,
  Check,
} from 'lucide-react'
import type { SystemStats, PipelineStatus } from '../../types'
import { openFolderInFileManager } from '../../services/api'

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
  const [isFolderMenuOpen, setIsFolderMenuOpen] = useState(false)
  const [openedCategory, setOpenedCategory] = useState<string | null>(null)
  const menuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setIsFolderMenuOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const handleOpenFolder = async (category: string) => {
    try {
      await openFolderInFileManager({ category })
      setOpenedCategory(category)
      setTimeout(() => setOpenedCategory(null), 2500)
    } catch (err) {
      console.error('Failed to open folder:', err)
    }
  }

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
        {/* GPU Hardware Acceleration Widget */}
        {stats?.gpu?.available && (
          <div
            className="hidden lg:flex items-center gap-2.5 px-3 py-1.5 rounded-lg bg-zinc-900/90 border border-zinc-800/80 font-mono text-xs cursor-default"
            title={`NVIDIA RTX 4060 Laptop GPU\nCompute Load: ${stats.gpu.util_percent ?? 0}%\nVRAM: ${stats.gpu.vram_used_gb}GB / ${stats.gpu.vram_total_gb}GB (${stats.gpu.vram_percent}%)\nTemp: ${stats.gpu.temperature_c ?? 0}°C\nHardware: CUDA & NVENC Active`}
          >
            <div className="p-1 rounded bg-emerald-500/10 text-emerald-400">
              <Cpu className="w-3.5 h-3.5" />
            </div>
            <div className="flex flex-col">
              <div className="flex items-center justify-between gap-2.5 text-[10px] text-zinc-400">
                <span className="flex items-center gap-1 font-semibold text-zinc-300">
                  <span>RTX 4060</span>
                  <span className="px-1 py-0.2 text-[9px] rounded bg-emerald-500/20 text-emerald-300 font-bold">
                    GPU {stats.gpu.util_percent ?? 0}%
                  </span>
                </span>
                <span className="text-zinc-400 text-[10px]" title={`Used VRAM: ${stats.gpu.vram_used_gb} GB out of ${stats.gpu.vram_total_gb || 8} GB total (${stats.gpu.vram_percent}%)`}>
                  VRAM {stats.gpu.vram_used_gb} / {stats.gpu.vram_total_gb || 8}GB
                </span>
              </div>
              <div className="w-32 h-1.5 bg-zinc-800 rounded-full overflow-hidden mt-0.5">
                <div
                  className="h-full bg-gradient-to-r from-emerald-500 via-indigo-500 to-violet-500 transition-all duration-500"
                  style={{
                    width: `${Math.min(100, Math.max((stats.gpu.util_percent ?? 0), stats.gpu.vram_percent))}%`,
                  }}
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

        {/* 1-Click File Explorer Launcher Dropdown */}
        <div className="relative" ref={menuRef}>
          <button
            type="button"
            onClick={() => setIsFolderMenuOpen(!isFolderMenuOpen)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 text-zinc-300 hover:text-white text-xs font-mono transition-all shadow-sm"
            title="Open project folders in local Windows File Explorer"
          >
            <FolderOpen className="w-3.5 h-3.5 text-amber-400" />
            <span className="hidden sm:inline">📂 ফোল্ডার</span>
            <ChevronDown className={`w-3 h-3 transition-transform duration-200 ${isFolderMenuOpen ? 'rotate-180 text-amber-400' : 'text-zinc-500'}`} />
          </button>

          {isFolderMenuOpen && (
            <div className="absolute right-0 mt-2 w-64 rounded-xl bg-zinc-900/95 border border-zinc-700/80 shadow-2xl backdrop-blur-md p-1.5 z-50 animate-in fade-in slide-in-from-top-1 duration-150">
              <div className="px-2.5 py-1.5 border-b border-zinc-800/80 mb-1">
                <span className="text-[10px] font-mono font-semibold text-zinc-400 uppercase tracking-wider">
                  Windows File Explorer Launcher
                </span>
              </div>

              <div className="space-y-0.5">
                <button
                  type="button"
                  onClick={() => {
                    handleOpenFolder('master')
                    setIsFolderMenuOpen(false)
                  }}
                  className="w-full flex items-center justify-between px-2.5 py-1.5 rounded-lg hover:bg-zinc-800 text-left text-xs text-zinc-200 transition-colors group"
                >
                  <div className="flex items-center gap-2">
                    <Film className="w-3.5 h-3.5 text-emerald-400" />
                    <div>
                      <div className="font-medium text-zinc-100">Master Export Movie</div>
                      <div className="text-[10px] text-zinc-500 font-mono">storage/master_export</div>
                    </div>
                  </div>
                  {openedCategory === 'master' && <Check className="w-3.5 h-3.5 text-emerald-400" />}
                </button>

                <button
                  type="button"
                  onClick={() => {
                    handleOpenFolder('processed')
                    setIsFolderMenuOpen(false)
                  }}
                  className="w-full flex items-center justify-between px-2.5 py-1.5 rounded-lg hover:bg-zinc-800 text-left text-xs text-zinc-200 transition-colors group"
                >
                  <div className="flex items-center gap-2">
                    <Tv className="w-3.5 h-3.5 text-indigo-400" />
                    <div>
                      <div className="font-medium text-zinc-100">Dubbed Episodes</div>
                      <div className="text-[10px] text-zinc-500 font-mono">storage/processed_episodes</div>
                    </div>
                  </div>
                  {openedCategory === 'processed' && <Check className="w-3.5 h-3.5 text-indigo-400" />}
                </button>

                <button
                  type="button"
                  onClick={() => {
                    handleOpenFolder('shorts')
                    setIsFolderMenuOpen(false)
                  }}
                  className="w-full flex items-center justify-between px-2.5 py-1.5 rounded-lg hover:bg-zinc-800 text-left text-xs text-zinc-200 transition-colors group"
                >
                  <div className="flex items-center gap-2">
                    <Scissors className="w-3.5 h-3.5 text-amber-400" />
                    <div>
                      <div className="font-medium text-zinc-100">9:16 Viral Shorts</div>
                      <div className="text-[10px] text-zinc-500 font-mono">storage/master_export/shorts</div>
                    </div>
                  </div>
                  {openedCategory === 'shorts' && <Check className="w-3.5 h-3.5 text-amber-400" />}
                </button>

                <button
                  type="button"
                  onClick={() => {
                    handleOpenFolder('raw')
                    setIsFolderMenuOpen(false)
                  }}
                  className="w-full flex items-center justify-between px-2.5 py-1.5 rounded-lg hover:bg-zinc-800 text-left text-xs text-zinc-200 transition-colors group"
                >
                  <div className="flex items-center gap-2">
                    <Folder className="w-3.5 h-3.5 text-blue-400" />
                    <div>
                      <div className="font-medium text-zinc-100">Raw Input Episodes</div>
                      <div className="text-[10px] text-zinc-500 font-mono">storage/raw_episodes</div>
                    </div>
                  </div>
                  {openedCategory === 'raw' && <Check className="w-3.5 h-3.5 text-blue-400" />}
                </button>

                <button
                  type="button"
                  onClick={() => {
                    handleOpenFolder('tts')
                    setIsFolderMenuOpen(false)
                  }}
                  className="w-full flex items-center justify-between px-2.5 py-1.5 rounded-lg hover:bg-zinc-800 text-left text-xs text-zinc-200 transition-colors group"
                >
                  <div className="flex items-center gap-2">
                    <Mic className="w-3.5 h-3.5 text-purple-400" />
                    <div>
                      <div className="font-medium text-zinc-100">TTS Audio & Voice Tracks</div>
                      <div className="text-[10px] text-zinc-500 font-mono">storage/tts_output</div>
                    </div>
                  </div>
                  {openedCategory === 'tts' && <Check className="w-3.5 h-3.5 text-purple-400" />}
                </button>

                <button
                  type="button"
                  onClick={() => {
                    handleOpenFolder('drive')
                    setIsFolderMenuOpen(false)
                  }}
                  className="w-full flex items-center justify-between px-2.5 py-1.5 rounded-lg hover:bg-zinc-800 text-left text-xs text-zinc-200 transition-colors group"
                >
                  <div className="flex items-center gap-2">
                    <Cloud className="w-3.5 h-3.5 text-cyan-400" />
                    <div>
                      <div className="font-medium text-zinc-100">Google Drive Folder</div>
                      <div className="text-[10px] text-zinc-500 font-mono">OneDrama_Uploads</div>
                    </div>
                  </div>
                  {openedCategory === 'drive' && <Check className="w-3.5 h-3.5 text-cyan-400" />}
                </button>
              </div>
            </div>
          )}
        </div>

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
