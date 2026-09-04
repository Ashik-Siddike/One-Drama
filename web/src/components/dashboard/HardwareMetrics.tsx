import { Cpu, HardDrive, Layers, Zap } from 'lucide-react'
import type { SystemStats } from '../../types'

interface HardwareMetricsProps {
  stats: SystemStats | null
}

export const HardwareMetrics: React.FC<HardwareMetricsProps> = ({ stats }) => {
  if (!stats) return null

  const gpu = stats.gpu
  const storage = stats.storage_breakdown

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      {/* GPU Card */}
      <div className="p-4 rounded-xl bg-zinc-900/60 border border-zinc-800/80 backdrop-blur-sm">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2 text-xs font-semibold text-zinc-300">
            <div className="p-1.5 rounded-lg bg-indigo-500/10 text-indigo-400">
              <Zap className="w-4 h-4" />
            </div>
            <span>GPU Acceleration</span>
          </div>
          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            CUDA 12.4
          </span>
        </div>

        <div className="space-y-2">
          <div className="text-sm font-medium text-zinc-100 truncate">
            {gpu.name || 'NVIDIA GeForce RTX 4060'}
          </div>

          <div className="flex items-center justify-between text-xs font-mono text-zinc-400">
            <span>VRAM Allocation</span>
            <span className="text-zinc-200">
              {gpu.vram_used_gb} / {gpu.vram_total_gb} GB ({gpu.vram_percent}%)
            </span>
          </div>

          <div className="w-full h-2 bg-zinc-800 rounded-full overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-indigo-500 to-violet-500 transition-all duration-500"
              style={{ width: `${Math.min(100, gpu.vram_percent)}%` }}
            />
          </div>
        </div>
      </div>

      {/* CPU & RAM Card */}
      <div className="p-4 rounded-xl bg-zinc-900/60 border border-zinc-800/80 backdrop-blur-sm">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2 text-xs font-semibold text-zinc-300">
            <div className="p-1.5 rounded-lg bg-blue-500/10 text-blue-400">
              <Cpu className="w-4 h-4" />
            </div>
            <span>Host Computing</span>
          </div>
          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-zinc-800 text-zinc-400">
            16-Core
          </span>
        </div>

        <div className="space-y-3">
          <div>
            <div className="flex items-center justify-between text-xs font-mono text-zinc-400 mb-1">
              <span>CPU Load</span>
              <span className="text-zinc-200">{stats.cpu_percent}%</span>
            </div>
            <div className="w-full h-1.5 bg-zinc-800 rounded-full overflow-hidden">
              <div
                className="h-full bg-blue-500 transition-all"
                style={{ width: `${Math.min(100, stats.cpu_percent)}%` }}
              />
            </div>
          </div>

          <div>
            <div className="flex items-center justify-between text-xs font-mono text-zinc-400 mb-1">
              <span>System Memory</span>
              <span className="text-zinc-200">
                {stats.ram_used_gb} / {stats.ram_total_gb} GB
              </span>
            </div>
            <div className="w-full h-1.5 bg-zinc-800 rounded-full overflow-hidden">
              <div
                className="h-full bg-emerald-500 transition-all"
                style={{ width: `${Math.min(100, stats.ram_percent)}%` }}
              />
            </div>
          </div>
        </div>
      </div>

      {/* Storage Breakdown Card */}
      <div className="p-4 rounded-xl bg-zinc-900/60 border border-zinc-800/80 backdrop-blur-sm">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2 text-xs font-semibold text-zinc-300">
            <div className="p-1.5 rounded-lg bg-amber-500/10 text-amber-400">
              <HardDrive className="w-4 h-4" />
            </div>
            <span>Studio Storage</span>
          </div>
          <span className="text-xs font-mono font-bold text-amber-400">
            {stats.total_storage_mb.toFixed(1)} MB
          </span>
        </div>

        <div className="space-y-1.5 text-[11px] font-mono text-zinc-400">
          <div className="flex justify-between">
            <span>Raw Video:</span>
            <span className="text-zinc-200">{storage.raw_episodes_mb} MB</span>
          </div>
          <div className="flex justify-between">
            <span>Stems & SFX:</span>
            <span className="text-zinc-200">{storage.audio_separated_mb} MB</span>
          </div>
          <div className="flex justify-between">
            <span>TTS Voiceovers:</span>
            <span className="text-zinc-200">{storage.tts_output_mb} MB</span>
          </div>
          <div className="flex justify-between">
            <span>Master Exports:</span>
            <span className="text-zinc-200">{storage.master_export_mb} MB</span>
          </div>
        </div>
      </div>

      {/* Engine Stack Summary */}
      <div className="p-4 rounded-xl bg-zinc-900/60 border border-zinc-800/80 backdrop-blur-sm">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2 text-xs font-semibold text-zinc-300">
            <div className="p-1.5 rounded-lg bg-purple-500/10 text-purple-400">
              <Layers className="w-4 h-4" />
            </div>
            <span>AI Engine Models</span>
          </div>
          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-purple-500/10 text-purple-400 border border-purple-500/20">
            ACTIVE
          </span>
        </div>

        <div className="space-y-2 text-xs">
          <div className="flex items-center justify-between">
            <span className="text-zinc-400">ASR:</span>
            <span className="font-mono text-zinc-200 font-medium">
              {stats.asr_engine.toUpperCase()}
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-zinc-400">TTS Model:</span>
            <span className="font-mono text-indigo-400 font-medium">
              {stats.tts_engine.toUpperCase()} (CUDA)
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-zinc-400">Target Voice:</span>
            <span className="font-mono text-zinc-200">
              {stats.target_language === 'hi' ? 'Hindi (Dramatic)' : stats.target_language}
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-zinc-400">Remaster:</span>
            <span className="font-mono text-zinc-200">1.04x Pan + Lanczos</span>
          </div>
          <div className="flex items-center justify-between pt-1 border-t border-zinc-800/80">
            <span className="text-zinc-400">Google Drive:</span>
            <span className={`font-mono text-[11px] font-bold ${stats.google_drive?.connected ? 'text-emerald-400' : 'text-zinc-500'}`}>
              {stats.google_drive?.connected ? 'G:\\ SYNC ACTIVE' : 'OFFLINE'}
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}
