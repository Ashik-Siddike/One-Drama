import { useState } from 'react'
import { createPortal } from 'react-dom'
import {
  FolderKanban,
  CheckCircle2,
  FileText,
  ChevronRight,
  Eye,
  UploadCloud,
  Sparkles,
  FolderOpen,
  Play,
} from 'lucide-react'
import type { ProjectData } from '../../types'
import { fetchEpisodeDetails, openFolderInFileManager } from '../../services/api'
import { LocalImportDropzone } from './LocalImportDropzone'

interface ProjectWorkspaceProps {
  projectData: ProjectData | null
  onRefresh?: () => Promise<void>
  onAutoProduce?: (opts: { query_or_url: string; limit?: number }) => Promise<void>
  onRunPipeline?: (limit?: number) => Promise<void>
  isBusy?: boolean
}

export const ProjectWorkspace: React.FC<ProjectWorkspaceProps> = ({
  projectData,
  onRefresh,
  onAutoProduce,
  onRunPipeline,
  isBusy = false,
}) => {
  const [selectedStem, setSelectedStem] = useState<string | null>(null)
  const [episodeDetails, setEpisodeDetails] = useState<any>(null)
  const [isLoadingDetails, setIsLoadingDetails] = useState(false)
  const [showImportModal, setShowImportModal] = useState(false)

  const episodes = projectData?.episodes || []

  const handleSelectEpisode = async (stem: string) => {
    setSelectedStem(stem)
    setIsLoadingDetails(true)
    try {
      const data = await fetchEpisodeDetails(stem)
      setEpisodeDetails(data)
    } catch (err) {
      console.error('Failed to load episode details:', err)
    } finally {
      setIsLoadingDetails(false)
    }
  }

  return (
    <div className="space-y-6 relative">
      {/* Workspace Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-5 rounded-2xl bg-zinc-900/60 border border-zinc-800/80 backdrop-blur-sm">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400">
            <FolderKanban className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-base font-bold text-zinc-100">
                {projectData?.active_project || 'Current Series Workspace'}
              </h2>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                {episodes.length} Episodes
              </span>
            </div>
            <p className="text-xs text-zinc-400 mt-0.5">
              Multi-track timeline, Chinese dialogue transcription, and Hindi dramatic adaptation inspector.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          {episodes.length > 0 && onRunPipeline && (
            <button
              type="button"
              onClick={() => onRunPipeline()}
              disabled={isBusy}
              className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-emerald-600 via-teal-600 to-indigo-600 hover:from-emerald-500 hover:to-teal-500 disabled:opacity-40 text-white text-xs font-black transition-all shadow-lg shadow-emerald-600/30 transform hover:scale-[1.02]"
            >
              <Sparkles className="w-4 h-4 text-amber-300 animate-pulse" />
              <span>🎬 এই {episodes.length}টি ভিডিও দিয়ে সরাসরি ফুল মুভি বানাও</span>
            </button>
          )}

          <button
            type="button"
            onClick={() => openFolderInFileManager({ category: 'processed' })}
            className="flex items-center gap-1.5 px-3.5 py-2.5 rounded-xl bg-zinc-800/90 hover:bg-zinc-700 text-zinc-200 text-xs font-semibold font-mono border border-zinc-700/80 transition-all shadow-sm"
            title="Open storage/processed_episodes in Windows File Explorer"
          >
            <FolderOpen className="w-4 h-4 text-emerald-400" />
            <span>📂 ডাবড ফোল্ডার</span>
          </button>

          <button
            type="button"
            onClick={() => setShowImportModal(true)}
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white text-xs font-bold transition-all shadow-md shadow-indigo-600/20"
          >
            <UploadCloud className="w-4 h-4" />
            <span>📥 ড্র্যাগ-ড্রপ / নতুন ড্রামা ইনপোর্ট</span>
          </button>
        </div>
      </div>

      {/* Main Grid & Inspector Split */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: Episodes List (2 Columns on Desktop) */}
        <div className="lg:col-span-2 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
              Episode Ingestion & Stage Matrix
            </h3>
            {episodes.length > 0 && (
              <span className="text-[10px] font-mono text-zinc-500">
                Total: {episodes.length} files
              </span>
            )}
          </div>

          {episodes.length === 0 ? (
            <div className="space-y-4">
              <LocalImportDropzone
                onImportSuccess={async () => {
                  if (onRefresh) await onRefresh()
                }}
                onStartProcessing={async () => {
                  if (onRefresh) await onRefresh()
                  if (onRunPipeline) await onRunPipeline()
                }}
                onAutoProduce={onAutoProduce}
              />
            </div>
          ) : (
            <div className="space-y-2">
              {episodes.map((ep) => {
                const isSelected = selectedStem === ep.stem
                const s = ep.status

                return (
                  <div
                    key={ep.stem}
                    onClick={() => handleSelectEpisode(ep.stem)}
                    className={`p-4 rounded-xl border transition-all cursor-pointer flex items-center justify-between gap-4 ${
                      isSelected
                        ? 'bg-indigo-600/10 border-indigo-500/50 shadow-md shadow-indigo-500/5'
                        : 'bg-zinc-900/40 border-zinc-800/80 hover:bg-zinc-900/70 hover:border-zinc-700'
                    }`}
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      <div className="w-8 h-8 rounded-lg bg-zinc-800/80 flex items-center justify-center font-mono text-xs font-bold text-zinc-300 shrink-0">
                        {ep.stem.replace('ep_', '')}
                      </div>

                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-semibold text-zinc-200 truncate">
                            {ep.filename}
                          </span>
                          <span className="text-[10px] font-mono text-zinc-500">
                            ({ep.raw_size_mb} MB)
                          </span>
                        </div>

                        {/* Status Badges */}
                        <div className="flex items-center gap-2 mt-1.5 flex-wrap">
                          <span
                            className={`text-[10px] font-mono px-1.5 py-0.5 rounded flex items-center gap-1 ${
                              s.separated
                                ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                                : 'bg-zinc-800 text-zinc-500'
                            }`}
                          >
                            {s.separated ? <CheckCircle2 className="w-2.5 h-2.5" /> : null}
                            Demucs
                          </span>

                          <span
                            className={`text-[10px] font-mono px-1.5 py-0.5 rounded flex items-center gap-1 ${
                              s.transcribed
                                ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                                : 'bg-zinc-800 text-zinc-500'
                            }`}
                          >
                            {s.transcribed ? <CheckCircle2 className="w-2.5 h-2.5" /> : null}
                            SenseVoice ({ep.segment_count})
                          </span>

                          <span
                            className={`text-[10px] font-mono px-1.5 py-0.5 rounded flex items-center gap-1 ${
                              s.recap_adapted
                                ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                                : 'bg-zinc-800 text-zinc-500'
                            }`}
                          >
                            {s.recap_adapted ? <CheckCircle2 className="w-2.5 h-2.5" /> : null}
                            Gemini Recap
                          </span>

                          <span
                            className={`text-[10px] font-mono px-1.5 py-0.5 rounded flex items-center gap-1 ${
                              s.voice_synthesized
                                ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                                : 'bg-zinc-800 text-zinc-500'
                            }`}
                          >
                            {s.voice_synthesized ? <CheckCircle2 className="w-2.5 h-2.5" /> : null}
                            F5-TTS
                          </span>

                          <span
                            className={`text-[10px] font-mono px-1.5 py-0.5 rounded flex items-center gap-1 ${
                              s.rendered
                                ? 'bg-indigo-500/15 text-indigo-300 border border-indigo-500/30'
                                : 'bg-zinc-800 text-zinc-500'
                            }`}
                          >
                            {s.rendered ? <CheckCircle2 className="w-2.5 h-2.5" /> : null}
                            Dubbed MP4
                          </span>
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center gap-2 text-zinc-400">
                      {s.rendered && (
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation()
                            openFolderInFileManager({
                              path: ep.processed_path || `storage/processed_episodes/${ep.stem}_dubbed.mp4`,
                            })
                          }}
                          className="p-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-300 hover:text-emerald-400 transition-colors"
                          title="Open dubbed video in Windows File Explorer"
                        >
                          <FolderOpen className="w-4 h-4" />
                        </button>
                      )}
                      <Eye className="w-4 h-4 hover:text-indigo-400" />
                      <ChevronRight className="w-4 h-4" />
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>

        {/* Right: Scene & Story Inspector */}
        <div className="space-y-3">
          <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
            Script & Dialogue Inspector
          </h3>

          <div className="p-4 rounded-2xl bg-zinc-900/60 border border-zinc-800/80 min-h-[400px]">
            {!selectedStem ? (
              <div className="h-full flex flex-col items-center justify-center text-center p-6 text-zinc-500 text-xs font-mono">
                <FileText className="w-8 h-8 mb-2 text-zinc-600" />
                Select an episode on the left to inspect Chinese dialogue transcription vs Hindi dramatic narration.
              </div>
            ) : isLoadingDetails ? (
              <div className="py-12 text-center text-xs font-mono text-indigo-400 animate-pulse">
                Loading transcript & story scripts...
              </div>
            ) : (
              <div className="space-y-4">
                <div className="flex items-center justify-between pb-3 border-b border-zinc-800">
                  <div className="font-mono text-xs font-bold text-zinc-200">
                    {selectedStem}
                  </div>
                  <span className="text-[10px] font-mono text-indigo-400">
                    {episodeDetails?.recap_script?.length || 0} Scene Cues
                  </span>
                </div>

                {/* Dubbed Video Preview (if rendered) */}
                {(() => {
                  const selEp = episodes.find((e) => e.stem === selectedStem)
                  if (!selEp?.status.rendered) return null
                  const streamUrl = `/api/video/stream/processed/${encodeURIComponent(selEp.stem)}_dubbed.mp4`

                  return (
                    <div className="rounded-xl overflow-hidden bg-black/90 border border-indigo-500/30 space-y-1">
                      <div className="flex items-center justify-between px-3 py-1.5 bg-zinc-950/80 border-b border-zinc-800/80 text-[11px] font-mono text-indigo-300">
                        <span className="flex items-center gap-1.5 font-semibold">
                          <Play className="w-3 h-3 text-emerald-400 fill-emerald-400" />
                          Dubbed Video Player
                        </span>
                        <button
                          type="button"
                          onClick={() =>
                            openFolderInFileManager({
                              path: selEp.processed_path || `storage/processed_episodes/${selEp.stem}_dubbed.mp4`,
                            })
                          }
                          className="hover:text-emerald-400 flex items-center gap-1 text-[10px] text-zinc-400 transition-colors"
                          title="Open in Windows Explorer"
                        >
                          <FolderOpen className="w-3 h-3" />
                          <span>Reveal File</span>
                        </button>
                      </div>
                      <video
                        controls
                        src={streamUrl}
                        className="w-full max-h-64 object-contain bg-black rounded-b-xl"
                        preload="metadata"
                      />
                    </div>
                  )
                })()}

                {/* Script Segments List */}
                <div className="space-y-3 max-h-[520px] overflow-y-auto pr-1">
                  {episodeDetails?.recap_script?.map((cue: any, idx: number) => {
                    const originalCue = episodeDetails?.transcript?.[idx]

                    return (
                      <div
                        key={idx}
                        className="p-3 rounded-xl bg-black/60 border border-zinc-800 text-xs space-y-1.5"
                      >
                        <div className="flex items-center justify-between text-[10px] font-mono text-zinc-500">
                          <span>Scene Cue #{idx + 1}</span>
                          <span>
                            {cue.start?.toFixed(1)}s - {cue.end?.toFixed(1)}s (
                            {((cue.end || 0) - (cue.start || 0)).toFixed(1)}s)
                          </span>
                        </div>

                        {originalCue && (
                          <div className="text-zinc-400 text-[11px] bg-zinc-900/60 p-1.5 rounded">
                            <span className="text-[9px] font-mono text-zinc-500 block uppercase">
                              Chinese Dialogue:
                            </span>
                            {originalCue.text}
                          </div>
                        )}

                        <div className="text-indigo-200 text-xs font-medium">
                          <span className="text-[9px] font-mono text-indigo-400 block uppercase">
                            Hindi Dramatic Recap (Gemini):
                          </span>
                          {cue.recap_text || cue.text}
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

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
                  if (onRefresh) await onRefresh()
                  if (onRunPipeline) await onRunPipeline()
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
