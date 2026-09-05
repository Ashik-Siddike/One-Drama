import {
  LayoutDashboard,
  FolderKanban,
  Compass,
  BookOpen,
  Users,
  Clapperboard,
  Sparkles,
  Mic,
  Music,
  Clock,
  Film,
  CheckCircle2,
  Settings,
  ChevronLeft,
  ChevronRight,
  Flame,
} from 'lucide-react'

export type StudioTab =
  | 'dashboard'
  | 'projects'
  | 'discovery'
  | 'stories'
  | 'characters'
  | 'scenes'
  | 'visuals'
  | 'voice'
  | 'audio'
  | 'timeline'
  | 'render'
  | 'qc'
  | 'settings'

interface SidebarProps {
  currentTab: StudioTab
  onSelectTab: (tab: StudioTab) => void
  isCollapsed: boolean
  onToggleCollapse: () => void
  totalEpisodes?: number
  isPipelineRunning?: boolean
}

export const Sidebar: React.FC<SidebarProps> = ({
  currentTab,
  onSelectTab,
  isCollapsed,
  onToggleCollapse,
  totalEpisodes = 0,
  isPipelineRunning = false,
}) => {
  const navItems = [
    { id: 'dashboard' as StudioTab, label: 'Dashboard', icon: LayoutDashboard },
    {
      id: 'projects' as StudioTab,
      label: 'Projects',
      icon: FolderKanban,
      badge: totalEpisodes > 0 ? `${totalEpisodes} eps` : undefined,
    },
    { id: 'discovery' as StudioTab, label: 'Discovery', icon: Compass },
    { id: 'stories' as StudioTab, label: 'Stories', icon: BookOpen, sub: 'Story Bible' },
    { id: 'characters' as StudioTab, label: 'Characters', icon: Users },
    { id: 'scenes' as StudioTab, label: 'Scenes', icon: Clapperboard },
    { id: 'visuals' as StudioTab, label: 'Visuals', icon: Sparkles },
    { id: 'voice' as StudioTab, label: 'Voice Studio', icon: Mic },
    { id: 'audio' as StudioTab, label: 'Audio DAW', icon: Music },
    { id: 'timeline' as StudioTab, label: 'Timeline', icon: Clock },
    {
      id: 'render' as StudioTab,
      label: 'Render Center',
      icon: Film,
      badge: isPipelineRunning ? 'LIVE' : undefined,
      badgeColor: 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40',
    },
    { id: 'qc' as StudioTab, label: 'QC Audit', icon: CheckCircle2 },
    { id: 'settings' as StudioTab, label: 'Settings', icon: Settings },
  ]

  return (
    <aside
      className={`h-screen flex flex-col justify-between bg-zinc-950 border-r border-zinc-800/80 transition-all duration-300 select-none z-30 ${
        isCollapsed ? 'w-20' : 'w-64'
      }`}
    >
      {/* Brand Header */}
      <div>
        <div className="h-16 flex items-center justify-between px-4 border-b border-zinc-800/80">
          {!isCollapsed && (
            <div className="flex items-center gap-2.5 overflow-hidden">
              <img
                src="/logo.png"
                alt="OneDrama"
                className="w-9 h-9 rounded-xl object-contain shadow-lg shadow-indigo-500/20 border border-zinc-800/80"
              />
              <div className="flex flex-col">
                <span className="font-bold text-sm tracking-wide text-zinc-100 uppercase">
                  OneDrama
                </span>
                <span className="text-[10px] text-zinc-500 uppercase tracking-widest font-mono">
                  Production OS
                </span>
              </div>
            </div>
          )}

          {isCollapsed && (
            <img
              src="/logo.png"
              alt="OneDrama"
              className="mx-auto w-9 h-9 rounded-xl object-contain shadow-md border border-zinc-800/80"
            />
          )}

          <button
            onClick={onToggleCollapse}
            title={isCollapsed ? 'Expand Sidebar' : 'Collapse Sidebar'}
            className="p-1.5 rounded-md hover:bg-zinc-800/60 text-zinc-400 hover:text-zinc-200 transition-colors"
          >
            {isCollapsed ? (
              <ChevronRight className="w-4 h-4" />
            ) : (
              <ChevronLeft className="w-4 h-4" />
            )}
          </button>
        </div>

        {/* Navigation List */}
        <nav className="p-2 space-y-1 overflow-y-auto max-h-[calc(100vh-120px)]">
          {navItems.map((item) => {
            const Icon = item.icon
            const active = currentTab === item.id

            return (
              <button
                key={item.id}
                onClick={() => onSelectTab(item.id)}
                title={isCollapsed ? item.label : undefined}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-xs font-medium transition-all ${
                  active
                    ? 'bg-indigo-600/15 text-indigo-400 border border-indigo-500/30 shadow-sm'
                    : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900/60'
                } ${isCollapsed ? 'justify-center px-0' : ''}`}
              >
                <Icon
                  className={`w-4 h-4 shrink-0 ${
                    active ? 'text-indigo-400' : 'text-zinc-400'
                  }`}
                />

                {!isCollapsed && (
                  <div className="flex-1 flex items-center justify-between overflow-hidden text-left">
                    <span className="truncate">{item.label}</span>
                    {item.badge && (
                      <span
                        className={`text-[10px] font-mono px-1.5 py-0.5 rounded-full ${
                          item.badgeColor ||
                          'bg-zinc-800 text-zinc-400 border border-zinc-700/60'
                        }`}
                      >
                        {item.badge}
                      </span>
                    )}
                  </div>
                )}
              </button>
            )
          })}
        </nav>
      </div>

      {/* Engine Status Footprint */}
      <div className="p-3 border-t border-zinc-800/80 bg-zinc-900/40">
        {!isCollapsed ? (
          <div className="flex items-center justify-between text-[11px] text-zinc-400 font-mono">
            <div className="flex items-center gap-2">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
              </span>
              <span className="text-zinc-300">CUDA 12.4 Engine</span>
            </div>
            <span className="text-zinc-500 text-[10px]">v1.2.0</span>
          </div>
        ) : (
          <div className="flex justify-center">
            <span className="relative flex h-2 w-2">
              <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
            </span>
          </div>
        )}
      </div>
    </aside>
  )
}
