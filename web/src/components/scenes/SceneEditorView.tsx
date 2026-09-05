import { useState, useEffect, useRef } from 'react'
import {
  Clapperboard,
  Camera,
  Move,
  Music,
  Zap,
  Play,
  Pause,
  Save,
  Clock,
  UserCheck,
  RotateCcw,
  RotateCw,
  Volume2,
  VolumeX,
  Maximize2,
  Eye,
  EyeOff,
  Video,
  ShieldCheck,
  Scissors,
  CheckCircle2,
  AlertTriangle,
} from 'lucide-react'
import {
  fetchVideoList,
  fetchEpisodeScenes,
  saveEpisodeScenes,
  fetchIntroOutroAudit,
  trimIntroOutro,
  type PlayableVideo,
  type SceneCue,
  type IntroOutroAudit,
} from '../../services/api'

export const SceneEditorView: React.FC = () => {
  // Video catalog state
  const [videoList, setVideoList] = useState<PlayableVideo[]>([])
  const [selectedVideo, setSelectedVideo] = useState<PlayableVideo | null>(null)
  const [loadingVideos, setLoadingVideos] = useState(true)

  // Scenes state
  const [scenes, setScenes] = useState<SceneCue[]>([])
  const [selectedIdx, setSelectedIdx] = useState(0)
  const [loadingScenes, setLoadingScenes] = useState(false)
  const [isSaved, setIsSaved] = useState(false)

  // Intro/Outro Guard state
  const [introOutro, setIntroOutro] = useState<IntroOutroAudit | null>(null)
  const [isTrimming, setIsTrimming] = useState(false)
  const [trimSuccessMsg, setTrimSuccessMsg] = useState<string | null>(null)

  // Player state
  const videoRef = useRef<HTMLVideoElement>(null)
  const [isPlaying, setIsPlaying] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const [volume, setVolume] = useState(1)
  const [isMuted, setIsMuted] = useState(false)
  const [playbackRate, setPlaybackRate] = useState(1)
  const [showHUD, setShowHUD] = useState(true)

  // Load video list on mount
  useEffect(() => {
    loadVideos()
  }, [])

  const loadVideos = async () => {
    try {
      setLoadingVideos(true)
      const data = await fetchVideoList()
      setVideoList(data.videos)
      if (data.videos.length > 0) {
        // Default to first processed dubbed video or first item
        const defaultVid = data.videos.find((v) => v.category === 'processed') || data.videos[0]
        setSelectedVideo(defaultVid)
      }
    } catch (err) {
      console.error('Failed to load videos:', err)
    } finally {
      setLoadingVideos(false)
    }
  }

  // Load scenes and intro/outro audit when selected video changes
  useEffect(() => {
    if (!selectedVideo) return
    const stem = selectedVideo.stem && selectedVideo.stem !== 'master' && selectedVideo.stem !== 'shorts'
      ? selectedVideo.stem
      : 'ep_001'

    loadScenesForStem(stem)
    loadIntroOutroAudit(stem)
  }, [selectedVideo])

  const loadScenesForStem = async (stem: string) => {
    try {
      setLoadingScenes(true)
      const res = await fetchEpisodeScenes(stem)
      setScenes(res.scenes)
      setSelectedIdx(0)
    } catch (err) {
      console.error('Failed to load episode scenes:', err)
    } finally {
      setLoadingScenes(false)
    }
  }

  const loadIntroOutroAudit = async (stem: string) => {
    try {
      const audit = await fetchIntroOutroAudit(stem)
      setIntroOutro(audit)
    } catch (err) {
      console.error('Failed to load intro/outro audit:', err)
      setIntroOutro(null)
    }
  }

  // Active scene
  const activeScene = scenes[selectedIdx] || scenes[0]

  // Track active scene based on video currentTime
  useEffect(() => {
    if (!scenes.length || !isPlaying) return
    const currentSceneIndex = scenes.findIndex(
      (sc) => currentTime >= sc.start && currentTime < sc.end
    )
    if (currentSceneIndex !== -1 && currentSceneIndex !== selectedIdx) {
      setSelectedIdx(currentSceneIndex)
    }
  }, [currentTime, scenes, isPlaying, selectedIdx])

  // Video Controls
  const togglePlay = () => {
    if (!videoRef.current) return
    if (isPlaying) {
      videoRef.current.pause()
    } else {
      videoRef.current.play()
    }
  }

  const handleTimeUpdate = () => {
    if (!videoRef.current) return
    setCurrentTime(videoRef.current.currentTime)
  }

  const handleLoadedMetadata = () => {
    if (!videoRef.current) return
    setDuration(videoRef.current.duration)
  }

  const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
    const time = parseFloat(e.target.value)
    if (videoRef.current) {
      videoRef.current.currentTime = time
      setCurrentTime(time)
    }
  }

  const jumpSeconds = (secs: number) => {
    if (!videoRef.current) return
    videoRef.current.currentTime = Math.max(0, Math.min(duration, videoRef.current.currentTime + secs))
  }

  const jumpToScene = (sc: SceneCue, idx: number) => {
    setSelectedIdx(idx)
    if (videoRef.current) {
      videoRef.current.currentTime = sc.start
      setCurrentTime(sc.start)
      if (!isPlaying) {
        videoRef.current.play().catch(() => {})
      }
    }
  }

  const toggleMute = () => {
    if (!videoRef.current) return
    const newMute = !isMuted
    videoRef.current.muted = newMute
    setIsMuted(newMute)
  }

  const handleVolumeChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = parseFloat(e.target.value)
    setVolume(val)
    if (videoRef.current) {
      videoRef.current.volume = val
      videoRef.current.muted = val === 0
      setIsMuted(val === 0)
    }
  }

  const handleSpeedChange = (rate: number) => {
    setPlaybackRate(rate)
    if (videoRef.current) {
      videoRef.current.playbackRate = rate
    }
  }

  const toggleFullscreen = () => {
    if (!videoRef.current) return
    if (!document.fullscreenElement) {
      videoRef.current.requestFullscreen().catch(() => {})
    } else {
      document.exitFullscreen().catch(() => {})
    }
  }

  const formatTime = (secs: number) => {
    if (isNaN(secs) || secs < 0) return '00:00'
    const m = Math.floor(secs / 60)
    const s = Math.floor(secs % 60)
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
  }

  const handleUpdate = (field: string, val: any) => {
    const updated = [...scenes]
    updated[selectedIdx] = { ...updated[selectedIdx], [field]: val }
    setScenes(updated)
  }

  const handleSave = async () => {
    if (!selectedVideo) return
    const stem = selectedVideo.stem || 'ep_001'
    try {
      await saveEpisodeScenes(stem, scenes)
      setIsSaved(true)
      setTimeout(() => setIsSaved(false), 2500)
    } catch (err) {
      console.error('Failed to save scenes:', err)
      alert('Failed to save scenes.')
    }
  }

  // Intro/Outro preview and trim
  const handlePreviewCleanStory = () => {
    if (!introOutro || !videoRef.current) return
    videoRef.current.currentTime = introOutro.clean_start_sec
    if (!isPlaying) {
      videoRef.current.play().catch(() => {})
    }
  }

  const handleTrimIntroOutro = async () => {
    if (!introOutro || !selectedVideo) return
    const stem = selectedVideo.stem || 'ep_001'
    try {
      setIsTrimming(true)
      const res = await trimIntroOutro(
        stem,
        introOutro.clean_start_sec,
        introOutro.clean_end_sec,
        false // fast lossless trim
      )
      setTrimSuccessMsg(`Clean trimmed video created! (${res.clean_duration_sec}s)`)
      await loadVideos()
      setTimeout(() => setTrimSuccessMsg(null), 4000)
    } catch (err: any) {
      alert(err.message || 'Trim failed')
    } finally {
      setIsTrimming(false)
    }
  }

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header & Video Selector */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-5 rounded-2xl bg-zinc-900/60 border border-zinc-800/80 backdrop-blur-sm">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-400 shadow-inner">
            <Clapperboard className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-base font-bold text-zinc-100">Scene Director & Video Player Studio</h2>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20">
                DIRECTOR SUITE
              </span>
            </div>
            <p className="text-xs text-zinc-400 mt-0.5">
              Interactive timeline playback, timestamp jumping, cinematic directing HUD, and intro/outro trimmer.
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          {/* Video Selector Dropdown */}
          <div className="flex items-center gap-2 bg-black/60 border border-zinc-800 rounded-xl px-3 py-1.5">
            <Video className="w-4 h-4 text-indigo-400" />
            <select
              value={selectedVideo?.id || ''}
              onChange={(e) => {
                const found = videoList.find((v) => v.id === e.target.value)
                if (found) setSelectedVideo(found)
              }}
              className="bg-transparent text-xs text-zinc-200 font-medium focus:outline-none cursor-pointer max-w-[240px] truncate"
            >
              {videoList.map((v) => (
                <option key={v.id} value={v.id} className="bg-zinc-900 text-zinc-200">
                  [{v.category_label}] {v.title} ({v.size_mb} MB)
                </option>
              ))}
            </select>
          </div>

          <button
            onClick={handleSave}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold tracking-wide transition-all shadow-md shadow-indigo-600/20"
          >
            <Save className="w-4 h-4" />
            <span>{isSaved ? 'Changes Saved!' : 'Save Directing Cues'}</span>
          </button>
        </div>
      </div>

      {/* Smart Intro & Outro Guard Notification Banner */}
      {introOutro && (
        <div className="p-4 rounded-2xl bg-zinc-900/70 border border-emerald-500/30 flex flex-col md:flex-row md:items-center justify-between gap-4 backdrop-blur-md">
          <div className="flex items-start gap-3">
            <div className="w-8 h-8 rounded-lg bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400 shrink-0 mt-0.5">
              <ShieldCheck className="w-4 h-4" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xs font-bold text-zinc-200">Smart Intro & Outro Eliminator</span>
                <span className="text-[10px] font-mono px-2 py-0.2 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                  {introOutro.has_chinese_cta ? 'Chinese CTA Detected' : 'Clean Audio Boundaries'}
                </span>
              </div>
              <p className="text-xs text-zinc-400 mt-0.5">
                Head Bumper Cut: <span className="text-amber-400 font-mono">0.0s - {introOutro.clean_start_sec}s</span> ({introOutro.intro_cut_duration}s) • Clean Story Window: <span className="text-emerald-400 font-mono">{introOutro.clean_start_sec}s - {introOutro.clean_end_sec}s</span> ({introOutro.clean_duration_sec}s) • Tail Outro Cut: <span className="text-red-400 font-mono">{introOutro.clean_end_sec}s - {introOutro.total_duration}s</span> ({introOutro.outro_cut_duration}s)
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <button
              onClick={handlePreviewCleanStory}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs font-medium transition-all"
            >
              <Play className="w-3.5 h-3.5 fill-current text-indigo-400" />
              <span>Preview Clean Story</span>
            </button>
            <button
              onClick={handleTrimIntroOutro}
              disabled={isTrimming}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold tracking-wide transition-all shadow-sm"
            >
              <Scissors className="w-3.5 h-3.5" />
              <span>{isTrimming ? 'Trimming...' : 'Execute Clean Trim'}</span>
            </button>
          </div>
        </div>
      )}

      {trimSuccessMsg && (
        <div className="p-3 rounded-xl bg-emerald-500/15 border border-emerald-500/40 text-emerald-300 text-xs flex items-center gap-2 animate-fade-in">
          <CheckCircle2 className="w-4 h-4 shrink-0" />
          <span>{trimSuccessMsg}</span>
        </div>
      )}

      {/* 3-Column Studio Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Col: Scene Cues List (3 cols) */}
        <div className="lg:col-span-3 space-y-2">
          <div className="flex items-center justify-between pb-1">
            <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
              Scenes Timeline ({scenes.length})
            </h3>
            <span className="text-[10px] font-mono text-zinc-500">Click to Seek Video</span>
          </div>

          <div className="space-y-2 max-h-[620px] overflow-y-auto pr-1 custom-scrollbar">
            {scenes.map((sc, idx) => {
              const isSelected = selectedIdx === idx
              const isCurrentlyPlaying = currentTime >= sc.start && currentTime < sc.end

              return (
                <div
                  key={sc.id}
                  onClick={() => jumpToScene(sc, idx)}
                  className={`p-3 rounded-xl border transition-all cursor-pointer relative group ${
                    isSelected
                      ? 'bg-indigo-600/15 border-indigo-500/80 shadow-md ring-1 ring-indigo-500/30'
                      : isCurrentlyPlaying
                      ? 'bg-emerald-600/10 border-emerald-500/60'
                      : 'bg-zinc-900/40 border-zinc-800/80 hover:bg-zinc-900/70 hover:border-zinc-700'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          jumpToScene(sc, idx)
                        }}
                        className={`w-6 h-6 rounded-lg flex items-center justify-center transition-colors ${
                          isSelected ? 'bg-indigo-600 text-white' : 'bg-zinc-800 text-zinc-400 group-hover:bg-indigo-600/80 group-hover:text-white'
                        }`}
                      >
                        <Play className="w-3 h-3 fill-current ml-0.5" />
                      </button>
                      <span className="font-mono text-xs font-bold text-zinc-200">
                        Scene {sc.id}
                      </span>
                    </div>

                    <span
                      className={`text-[10px] font-mono px-1.5 py-0.5 rounded ${
                        sc.status === 'done'
                          ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                          : 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                      }`}
                    >
                      {sc.status === 'done' ? 'Rendered' : 'Ready'}
                    </span>
                  </div>

                  <div className="flex items-center justify-between text-[11px] font-mono text-zinc-400 mt-2 pt-2 border-t border-zinc-800/60">
                    <span className="flex items-center gap-1 text-zinc-300">
                      <Clock className="w-3 h-3 text-indigo-400" />
                      {formatTime(sc.start)} - {formatTime(sc.end)}
                    </span>
                    <span className="text-zinc-500">{sc.duration}s</span>
                  </div>

                  {/* Directing tags snapshot */}
                  <div className="flex items-center gap-1 mt-1.5">
                    <span className="text-[9px] font-mono px-1.5 py-0.2 rounded bg-zinc-800/80 text-zinc-400">
                      {sc.camera}
                    </span>
                    <span className="text-[9px] font-mono px-1.5 py-0.2 rounded bg-zinc-800/80 text-zinc-400">
                      {sc.motion}
                    </span>
                  </div>

                  {/* Live Beacon Indicator */}
                  {isCurrentlyPlaying && isPlaying && (
                    <div className="absolute top-2 right-2 flex items-center gap-1 text-[9px] font-mono text-emerald-400 font-bold bg-emerald-500/20 px-1.5 py-0.5 rounded animate-pulse">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                      PLAYING
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </div>

        {/* Center Col: Real Playable Video & Script Editor (6 cols) */}
        <div className="lg:col-span-6 space-y-4">
          {/* Genuine HTML5 Video Player Container */}
          <div className="relative aspect-video rounded-2xl bg-black border border-zinc-800 overflow-hidden shadow-2xl flex flex-col justify-end group">
            {selectedVideo?.url ? (
              <video
                ref={videoRef}
                src={selectedVideo.url}
                onPlay={() => setIsPlaying(true)}
                onPause={() => setIsPlaying(false)}
                onTimeUpdate={handleTimeUpdate}
                onLoadedMetadata={handleLoadedMetadata}
                onClick={togglePlay}
                className="w-full h-full object-contain cursor-pointer"
              />
            ) : (
              <div className="w-full h-full flex items-center justify-center text-zinc-500 text-xs">
                No video loaded. Select a video from the top menu.
              </div>
            )}

            {/* Directing HUD Overlays (Top Floating Badges) */}
            {showHUD && activeScene && (
              <div className="absolute top-3 left-3 right-3 z-20 flex items-center justify-between pointer-events-none">
                <div className="flex flex-wrap gap-2 pointer-events-auto">
                  <span className="text-[10px] font-mono px-2.5 py-1 rounded-lg bg-black/80 border border-zinc-700/80 text-amber-300 font-semibold backdrop-blur-md shadow-lg">
                    SCENE {activeScene.id} • {formatTime(activeScene.start)} - {formatTime(activeScene.end)}
                  </span>
                  <span className="text-[10px] font-mono px-2 py-1 rounded-lg bg-black/80 border border-zinc-700/80 text-indigo-300 backdrop-blur-md">
                    Cam: {activeScene.camera}
                  </span>
                  <span className="text-[10px] font-mono px-2 py-1 rounded-lg bg-black/80 border border-zinc-700/80 text-emerald-300 backdrop-blur-md">
                    Motion: {activeScene.motion}
                  </span>
                </div>

                <button
                  onClick={() => setShowHUD(false)}
                  className="pointer-events-auto p-1.5 rounded-lg bg-black/80 border border-zinc-700/80 text-zinc-400 hover:text-zinc-200 transition-colors backdrop-blur-md"
                  title="Hide HUD"
                >
                  <EyeOff className="w-3.5 h-3.5" />
                </button>
              </div>
            )}

            {!showHUD && (
              <button
                onClick={() => setShowHUD(true)}
                className="absolute top-3 right-3 z-20 p-1.5 rounded-lg bg-black/80 border border-zinc-700/80 text-zinc-400 hover:text-zinc-200 transition-colors backdrop-blur-md"
                title="Show HUD Overlays"
              >
                <Eye className="w-3.5 h-3.5" />
              </button>
            )}

            {/* Centered Play Button when paused */}
            {!isPlaying && selectedVideo?.url && (
              <button
                onClick={togglePlay}
                className="absolute inset-0 m-auto w-16 h-16 rounded-full bg-indigo-600/90 hover:bg-indigo-500 text-white flex items-center justify-center shadow-2xl transition-transform hover:scale-110 z-10"
              >
                <Play className="w-7 h-7 fill-current ml-1" />
              </button>
            )}

            {/* Custom Sleek Video Controls Bar */}
            <div className="absolute bottom-0 inset-x-0 bg-gradient-to-t from-black/95 via-black/80 to-transparent p-3 pt-6 z-20 flex flex-col gap-2 transition-opacity duration-200">
              {/* Timeline Scrubber Slider */}
              <div className="flex items-center gap-2 group/seek">
                <input
                  type="range"
                  min={0}
                  max={duration || 100}
                  step={0.1}
                  value={currentTime}
                  onChange={handleSeek}
                  className="w-full h-1.5 bg-zinc-700 rounded-lg appearance-none cursor-pointer accent-indigo-500 hover:h-2 transition-all"
                />
              </div>

              {/* Bottom Actions Row */}
              <div className="flex items-center justify-between text-xs text-zinc-300">
                <div className="flex items-center gap-3">
                  {/* Play/Pause */}
                  <button
                    onClick={togglePlay}
                    className="p-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-white transition-colors"
                  >
                    {isPlaying ? <Pause className="w-4 h-4 fill-current" /> : <Play className="w-4 h-4 fill-current" />}
                  </button>

                  {/* Jump Backward 5s */}
                  <button
                    onClick={() => jumpSeconds(-5)}
                    className="p-1.5 rounded-lg hover:bg-zinc-800 text-zinc-300 transition-colors"
                    title="Rewind 5s"
                  >
                    <RotateCcw className="w-3.5 h-3.5" />
                  </button>

                  {/* Jump Forward 5s */}
                  <button
                    onClick={() => jumpSeconds(5)}
                    className="p-1.5 rounded-lg hover:bg-zinc-800 text-zinc-300 transition-colors"
                    title="Forward 5s"
                  >
                    <RotateCw className="w-3.5 h-3.5" />
                  </button>

                  {/* Time Stamp */}
                  <span className="font-mono text-xs text-zinc-300">
                    {formatTime(currentTime)} / {formatTime(duration)}
                  </span>
                </div>

                <div className="flex items-center gap-3">
                  {/* Volume Control */}
                  <div className="flex items-center gap-1.5">
                    <button onClick={toggleMute} className="text-zinc-400 hover:text-zinc-200">
                      {isMuted || volume === 0 ? <VolumeX className="w-4 h-4" /> : <Volume2 className="w-4 h-4" />}
                    </button>
                    <input
                      type="range"
                      min={0}
                      max={1}
                      step={0.05}
                      value={isMuted ? 0 : volume}
                      onChange={handleVolumeChange}
                      className="w-16 h-1 bg-zinc-700 rounded-lg appearance-none cursor-pointer accent-indigo-500"
                    />
                  </div>

                  {/* Playback Speed Selector */}
                  <div className="flex items-center gap-1 bg-zinc-800/80 px-2 py-0.5 rounded-lg text-[11px] font-mono">
                    {[1, 1.25, 1.5, 2].map((rate) => (
                      <button
                        key={rate}
                        onClick={() => handleSpeedChange(rate)}
                        className={`px-1 rounded ${
                          playbackRate === rate ? 'text-indigo-400 font-bold bg-indigo-500/20' : 'text-zinc-400 hover:text-zinc-200'
                        }`}
                      >
                        {rate}x
                      </button>
                    ))}
                  </div>

                  {/* Fullscreen Button */}
                  <button
                    onClick={toggleFullscreen}
                    className="p-1.5 rounded-lg hover:bg-zinc-800 text-zinc-400 hover:text-white transition-colors"
                    title="Fullscreen"
                  >
                    <Maximize2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            </div>
          </div>

          {/* Dialogue & Script Editors */}
          <div className="p-4 rounded-2xl bg-zinc-900/60 border border-zinc-800/80 space-y-3">
            <div>
              <div className="flex items-center justify-between mb-1">
                <span className="text-[10px] font-mono uppercase text-zinc-500">
                  Original Chinese Dialogue (SenseVoice ASR)
                </span>
                <span className="text-[10px] font-mono text-zinc-500">
                  {activeScene?.chinese?.length || 0} chars
                </span>
              </div>
              <div className="p-3 rounded-xl bg-black/50 border border-zinc-800 text-xs font-sans text-zinc-300 leading-relaxed select-all">
                {activeScene?.chinese || 'No dialogue detected in this scene.'}
              </div>
            </div>

            <div>
              <div className="flex items-center justify-between mb-1">
                <span className="text-[10px] font-mono uppercase text-indigo-400 font-semibold">
                  Hindi Dramatic Narration (Editable Gemini Script)
                </span>
                <span className="text-[10px] font-mono text-indigo-300">
                  {activeScene?.hindi?.split(' ').filter(Boolean).length || 0} words
                </span>
              </div>
              <textarea
                rows={3}
                value={activeScene?.hindi || ''}
                onChange={(e) => handleUpdate('hindi', e.target.value)}
                placeholder="Enter Hindi narrative adaptation..."
                className="w-full p-3 rounded-xl bg-black/80 border border-zinc-800 text-xs font-sans text-indigo-100 focus:outline-none focus:border-indigo-500 leading-relaxed"
              />
            </div>
          </div>
        </div>

        {/* Right Col: Directing Controls (3 cols) */}
        <div className="lg:col-span-3 space-y-4">
          <div className="p-4 rounded-2xl bg-zinc-900/60 border border-zinc-800/80 space-y-3">
            <h4 className="text-xs font-semibold text-zinc-300 uppercase tracking-wider pb-2 border-b border-zinc-800 flex items-center justify-between">
              <span>Directing Parameters</span>
              <span className="text-[10px] font-mono text-zinc-500">Scene #{activeScene?.id}</span>
            </h4>

            {/* Camera */}
            <div>
              <label className="text-[10px] font-mono uppercase text-zinc-400 flex items-center gap-1.5 mb-1">
                <Camera className="w-3 h-3 text-indigo-400" /> Camera Shot
              </label>
              <select
                value={activeScene?.camera || 'Close Up'}
                onChange={(e) => handleUpdate('camera', e.target.value)}
                className="w-full px-3 py-2 rounded-xl bg-black/60 border border-zinc-800 text-xs text-zinc-200 focus:outline-none"
              >
                <option>Close Up</option>
                <option>Wide Shot</option>
                <option>Low Angle Dynamic</option>
                <option>Tracking Shot</option>
                <option>Extreme Close Up</option>
                <option>Birds Eye View</option>
              </select>
            </div>

            {/* Motion */}
            <div>
              <label className="text-[10px] font-mono uppercase text-zinc-400 flex items-center gap-1.5 mb-1">
                <Move className="w-3 h-3 text-emerald-400" /> Motion Curve
              </label>
              <select
                value={activeScene?.motion || 'Slow Zoom'}
                onChange={(e) => handleUpdate('motion', e.target.value)}
                className="w-full px-3 py-2 rounded-xl bg-black/60 border border-zinc-800 text-xs text-zinc-200 focus:outline-none"
              >
                <option>Slow Zoom</option>
                <option>Parallax Pan</option>
                <option>Camera Shake</option>
                <option>Static Focus</option>
                <option>Fast Push In</option>
              </select>
            </div>

            {/* BGM Mood */}
            <div>
              <label className="text-[10px] font-mono uppercase text-zinc-400 flex items-center gap-1.5 mb-1">
                <Music className="w-3 h-3 text-purple-400" /> BGM Mood
              </label>
              <select
                value={activeScene?.bgm || 'Dark Tension'}
                onChange={(e) => handleUpdate('bgm', e.target.value)}
                className="w-full px-3 py-2 rounded-xl bg-black/60 border border-zinc-800 text-xs text-zinc-200 focus:outline-none"
              >
                <option>Dark Tension</option>
                <option>Epic Climax</option>
                <option>High Stakes Cultivation</option>
                <option>Tragic Sentiment</option>
                <option>Triumphant Revenge</option>
              </select>
            </div>

            {/* SFX Hit */}
            <div>
              <label className="text-[10px] font-mono uppercase text-zinc-400 flex items-center gap-1.5 mb-1">
                <Zap className="w-3 h-3 text-amber-400" /> SFX Impact
              </label>
              <select
                value={activeScene?.sfx || 'Thunder Strike'}
                onChange={(e) => handleUpdate('sfx', e.target.value)}
                className="w-full px-3 py-2 rounded-xl bg-black/60 border border-zinc-800 text-xs text-zinc-200 focus:outline-none"
              >
                <option>Thunder Strike</option>
                <option>Sword Slash</option>
                <option>Energy Blast</option>
                <option>Heavy Impact</option>
                <option>None</option>
              </select>
            </div>

            {/* Tagged Characters */}
            <div className="pt-2 border-t border-zinc-800">
              <span className="text-[10px] font-mono uppercase text-zinc-400 block mb-1.5">
                Tagged Characters
              </span>
              <div className="flex flex-wrap gap-1.5">
                {(activeScene?.characters || ['Lin Feng']).map((c, i) => (
                  <span
                    key={i}
                    className="text-[10px] font-mono px-2 py-0.5 rounded bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 flex items-center gap-1"
                  >
                    <UserCheck className="w-2.5 h-2.5" />
                    {c}
                  </span>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
