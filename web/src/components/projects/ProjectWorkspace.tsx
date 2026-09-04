import { useState } from 'react'
import {
  FolderKanban,
  CheckCircle2,
  FileText,
  ChevronRight,
  Eye,
} from 'lucide-react'
import type { ProjectData } from '../../types'
import { fetchEpisodeDetails } from '../../services/api'

interface ProjectWorkspaceProps {
  projectData: ProjectData | null
}

export const ProjectWorkspace: React.FC<ProjectWorkspaceProps> = ({ projectData }) => {
  const [selectedStem, setSelectedStem] = useState<string | null>(null)
  const [episodeDetails, setEpisodeDetails] = useState<any>(null)
  const [isLoadingDetails, setIsLoadingDetails] = useState(false)

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
    <div className="space-y-6">
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
      </div>

      {/* Main Grid & Inspector Split */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: Episodes List (2 Columns on Desktop) */}
        <div className="lg:col-span-2 space-y-3">
          <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
            Episode Ingestion & Stage Matrix
          </h3>

          {episodes.length === 0 ? (
            <div className="py-12 text-center text-xs text-zinc-500 font-mono italic border border-dashed border-zinc-800 rounded-2xl">
              No episodes in storage/raw_episodes yet. Use the Quick Action bar or Discovery to download episodes.
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
    </div>
  )
}
