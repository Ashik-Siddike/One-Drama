import { useState, useEffect } from 'react'
import { Sidebar, type StudioTab } from './components/layout/Sidebar'
import { TopBar } from './components/layout/TopBar'
import { HardwareMetrics } from './components/dashboard/HardwareMetrics'
import { ActivePipelineCard } from './components/dashboard/ActivePipelineCard'
import { QuickActionCenter } from './components/dashboard/QuickActionCenter'
import { MasterMoviesTable } from './components/dashboard/MasterMoviesTable'
import { ProjectWorkspace } from './components/projects/ProjectWorkspace'
import { DiscoveryView } from './components/discovery/DiscoveryView'
import { StoryBibleView } from './components/stories/StoryBibleView'
import { CharacterManagerView } from './components/characters/CharacterManagerView'
import { SceneEditorView } from './components/scenes/SceneEditorView'
import { VisualStudioView } from './components/visuals/VisualStudioView'
import { VoiceStudioView } from './components/voice/VoiceStudioView'
import { AudioStudioView } from './components/audio/AudioStudioView'
import { TimelineView } from './components/timeline/TimelineView'
import { RenderCenterView } from './components/render/RenderCenterView'
import { QCAuditView } from './components/qc/QCAuditView'
import { SettingsView } from './components/settings/SettingsView'
import type { SystemStats, ProjectData, PipelineStatus } from './types'
import {
  fetchSystemStats,
  fetchProjects,
  fetchPipelineStatus,
  triggerDownload,
  triggerPipelineRun,
} from './services/api'

export function App() {
  const [currentTab, setCurrentTab] = useState<StudioTab>('dashboard')
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false)

  // State
  const [stats, setStats] = useState<SystemStats | null>(null)
  const [projectData, setProjectData] = useState<ProjectData | null>(null)
  const [pipelineStatus, setPipelineStatus] = useState<PipelineStatus | null>(null)
  const [isLoading, setIsLoading] = useState(false)

  // Initial load & Polling loop
  useEffect(() => {
    loadAllData()
    const interval = setInterval(loadStatusOnly, 3000)
    return () => clearInterval(interval)
  }, [])

  const loadAllData = async () => {
    setIsLoading(true)
    try {
      const [s, p, st] = await Promise.all([
        fetchSystemStats().catch(() => null),
        fetchProjects().catch(() => null),
        fetchPipelineStatus().catch(() => null),
      ])
      if (s) setStats(s)
      if (p) setProjectData(p)
      if (st) setPipelineStatus(st)
    } finally {
      setIsLoading(false)
    }
  }

  const loadStatusOnly = async () => {
    try {
      const [s, st] = await Promise.all([
        fetchSystemStats().catch(() => null),
        fetchPipelineStatus().catch(() => null),
      ])
      if (s) setStats(s)
      if (st) setPipelineStatus(st)
    } catch {
      // ignore transient poll errors
    }
  }

  const handleDownload = async (queryOrUrl: string, limit?: number) => {
    await triggerDownload(queryOrUrl, limit)
    await loadAllData()
  }

  const handleRunPipeline = async (opts?: {
    limit?: number
    force?: boolean
    carry_context?: boolean
    split_compilations?: boolean
    enable_filler_trim?: boolean
    generate_shorts?: boolean
  }) => {
    await triggerPipelineRun(opts || {})
    await loadAllData()
  }

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-zinc-950 text-zinc-100 font-sans">
      {/* Studio Sidebar */}
      <Sidebar
        currentTab={currentTab}
        onSelectTab={setCurrentTab}
        isCollapsed={isSidebarCollapsed}
        onToggleCollapse={() => setIsSidebarCollapsed(!isSidebarCollapsed)}
        totalEpisodes={projectData?.total_raw_episodes || 0}
        isPipelineRunning={pipelineStatus?.is_running || false}
      />

      {/* Main Studio Frame */}
      <div className="flex-1 flex flex-col h-screen overflow-hidden">
        {/* Global TopBar */}
        <TopBar
          stats={stats}
          pipelineStatus={pipelineStatus}
          activeProjectName={projectData?.active_project || 'Martial Peak (Season 1)'}
          onTriggerPipeline={() => handleRunPipeline()}
          onRefresh={loadAllData}
          isLoading={isLoading}
        />

        {/* Dynamic Workspace Body */}
        <main className="flex-1 overflow-y-auto p-6 space-y-6">
          {currentTab === 'dashboard' && (
            <>
              <HardwareMetrics stats={stats} />
              <ActivePipelineCard status={pipelineStatus} />
              <QuickActionCenter
                onDownload={handleDownload}
                onRunPipeline={() => handleRunPipeline()}
                isBusy={pipelineStatus?.is_running || false}
              />
              <MasterMoviesTable projectData={projectData} />
            </>
          )}

          {currentTab === 'projects' && (
            <ProjectWorkspace projectData={projectData} />
          )}

          {currentTab === 'discovery' && (
            <DiscoveryView onIngestSeries={handleDownload} />
          )}

          {currentTab === 'stories' && <StoryBibleView />}

          {currentTab === 'characters' && <CharacterManagerView />}

          {currentTab === 'scenes' && <SceneEditorView />}

          {currentTab === 'visuals' && <VisualStudioView />}

          {currentTab === 'voice' && <VoiceStudioView />}

          {currentTab === 'audio' && <AudioStudioView />}

          {currentTab === 'timeline' && <TimelineView />}

          {currentTab === 'render' && (
            <RenderCenterView
              pipelineStatus={pipelineStatus}
              onStartRender={handleRunPipeline}
            />
          )}

          {currentTab === 'qc' && <QCAuditView />}

          {currentTab === 'settings' && <SettingsView />}
        </main>
      </div>
    </div>
  )
}

export default App
