import { useState } from 'react'
import {
  Clapperboard,
  Camera,
  Move,
  Music,
  Zap,
  Play,
  Save,
  CheckCircle2,
  Clock,
  UserCheck,
} from 'lucide-react'

const MOCK_SCENES = [
  {
    id: '001',
    status: 'done',
    duration: 18.4,
    chinese: '林枫！今日你勾结外道，罪不容诛！受死吧！',
    hindi: 'उस रात लिन फेंग को पहली बार अपनी ही सेक्ट के गद्दार एल्डर्स के असली चेहरे का एहसास हुआ...',
    camera: 'Close Up',
    motion: 'Slow Zoom',
    bgm: 'Dark Tension',
    sfx: 'Thunder Strike',
    characters: ['Lin Feng', 'Elder Gu'],
  },
  {
    id: '002',
    status: 'done',
    duration: 14.2,
    chinese: '哈哈哈！既然你们不仁，就休怪我九霄剑煞无情！',
    hindi: 'लेकिन उसने घुटने टेकने से इनकार कर दिया। अपनी तलवार को हवा में लहराते हुए उसने अंतिम शक्ति को जगाया!',
    camera: 'Low Angle Dynamic',
    motion: 'Parallax Pan',
    bgm: 'Epic Climax',
    sfx: 'Sword Slash',
    characters: ['Lin Feng'],
  },
  {
    id: '003',
    status: 'pending',
    duration: 16.8,
    chinese: '这股力量...难道是传说中的太古九霄炎？！不可能！',
    hindi: 'एल्डर गू की आंखें खौफ से फटी की फटी रह गईं। वह नीली आग साधारण आग नहीं, बल्कि अमर लोक की दिव्य ज्वाला थी!',
    camera: 'Wide Shot',
    motion: 'Camera Shake',
    bgm: 'High Stakes Cultivation',
    sfx: 'Energy Blast',
    characters: ['Elder Gu'],
  },
]

export const SceneEditorView: React.FC = () => {
  const [scenes, setScenes] = useState(MOCK_SCENES)
  const [selectedIdx, setSelectedIdx] = useState(0)
  const [isSaved, setIsSaved] = useState(false)

  const activeScene = scenes[selectedIdx]

  const handleUpdate = (field: string, val: any) => {
    const updated = [...scenes]
    updated[selectedIdx] = { ...updated[selectedIdx], [field]: val }
    setScenes(updated)
  }

  const handleSave = () => {
    setIsSaved(true)
    setTimeout(() => setIsSaved(false), 2500)
  }

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-5 rounded-2xl bg-zinc-900/60 border border-zinc-800/80 backdrop-blur-sm">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-400">
            <Clapperboard className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-base font-bold text-zinc-100">Scene Director & Storyboard Editor</h2>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20">
                SCENE COMPOSER
              </span>
            </div>
            <p className="text-xs text-zinc-400 mt-0.5">
              Direct camera motion, character presence, dramatic pacing, and audio cues per scene.
            </p>
          </div>
        </div>

        <button
          onClick={handleSave}
          className="flex items-center gap-2 px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold tracking-wide transition-all shadow-md shadow-indigo-600/20"
        >
          <Save className="w-4 h-4" />
          <span>{isSaved ? 'Changes Saved!' : 'Save Directing Cues'}</span>
        </button>
      </div>

      {/* 3-Column Studio Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Col: Scene Cues List (3 cols) */}
        <div className="lg:col-span-3 space-y-2">
          <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-2">
            Scenes Timeline ({scenes.length})
          </h3>

          <div className="space-y-2">
            {scenes.map((sc, idx) => {
              const isSelected = selectedIdx === idx
              return (
                <div
                  key={sc.id}
                  onClick={() => setSelectedIdx(idx)}
                  className={`p-3 rounded-xl border transition-all cursor-pointer flex items-center justify-between ${
                    isSelected
                      ? 'bg-indigo-600/15 border-indigo-500/60 shadow-sm'
                      : 'bg-zinc-900/40 border-zinc-800/80 hover:bg-zinc-900/70 hover:border-zinc-700'
                  }`}
                >
                  <div className="flex items-center gap-2.5">
                    <span className="font-mono text-xs font-bold text-zinc-300">
                      Scene {sc.id}
                    </span>
                    <span className="text-[10px] font-mono text-zinc-500 flex items-center gap-1">
                      <Clock className="w-2.5 h-2.5" />
                      {sc.duration}s
                    </span>
                  </div>

                  <span
                    className={`text-[10px] font-mono px-1.5 py-0.5 rounded ${
                      sc.status === 'done'
                        ? 'bg-emerald-500/10 text-emerald-400'
                        : 'bg-amber-500/10 text-amber-400'
                    }`}
                  >
                    {sc.status === 'done' ? 'Ready' : 'Pending'}
                  </span>
                </div>
              )
            })}
          </div>
        </div>

        {/* Center Col: Scene Preview & Script Editor (6 cols) */}
        <div className="lg:col-span-6 space-y-4">
          {/* Mockup Preview Monitor */}
          <div className="relative aspect-video rounded-2xl bg-black border border-zinc-800 overflow-hidden flex items-center justify-center group shadow-2xl">
            <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-black/40 z-10" />

            <div className="text-center z-20 space-y-2">
              <div className="w-12 h-12 rounded-full bg-indigo-600/80 text-white flex items-center justify-center mx-auto shadow-lg group-hover:scale-110 transition-transform">
                <Play className="w-5 h-5 fill-current ml-0.5" />
              </div>
              <span className="text-xs font-mono text-zinc-400 block">
                Scene {activeScene.id} • {activeScene.duration}s Preview
              </span>
            </div>

            {/* Directing Overlays */}
            <div className="absolute top-3 left-3 z-20 flex gap-2">
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-black/60 border border-zinc-700 text-zinc-300">
                Cam: {activeScene.camera}
              </span>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-black/60 border border-zinc-700 text-indigo-300">
                Motion: {activeScene.motion}
              </span>
            </div>
          </div>

          {/* Dialogue Editors */}
          <div className="p-4 rounded-2xl bg-zinc-900/60 border border-zinc-800/80 space-y-3">
            <div>
              <span className="text-[10px] font-mono uppercase text-zinc-500 block mb-1">
                Original Chinese Dialogue (SenseVoice ASR)
              </span>
              <div className="p-2.5 rounded-xl bg-black/50 border border-zinc-800 text-xs font-sans text-zinc-400">
                {activeScene.chinese}
              </div>
            </div>

            <div>
              <span className="text-[10px] font-mono uppercase text-indigo-400 block mb-1">
                Hindi Dramatic Narration (Editable Gemini Script)
              </span>
              <textarea
                rows={2}
                value={activeScene.hindi}
                onChange={(e) => handleUpdate('hindi', e.target.value)}
                className="w-full p-2.5 rounded-xl bg-black/80 border border-zinc-800 text-xs font-sans text-indigo-100 focus:outline-none focus:border-indigo-500 leading-relaxed"
              />
            </div>
          </div>
        </div>

        {/* Right Col: Directing Controls (3 cols) */}
        <div className="lg:col-span-3 space-y-4">
          <div className="p-4 rounded-2xl bg-zinc-900/60 border border-zinc-800/80 space-y-3">
            <h4 className="text-xs font-semibold text-zinc-300 uppercase tracking-wider pb-2 border-b border-zinc-800">
              Directing Parameters
            </h4>

            {/* Camera */}
            <div>
              <label className="text-[10px] font-mono uppercase text-zinc-400 flex items-center gap-1.5 mb-1">
                <Camera className="w-3 h-3 text-indigo-400" /> Camera Shot
              </label>
              <select
                value={activeScene.camera}
                onChange={(e) => handleUpdate('camera', e.target.value)}
                className="w-full px-3 py-2 rounded-xl bg-black/60 border border-zinc-800 text-xs text-zinc-200 focus:outline-none"
              >
                <option>Close Up</option>
                <option>Wide Shot</option>
                <option>Low Angle Dynamic</option>
                <option>Tracking Shot</option>
              </select>
            </div>

            {/* Motion */}
            <div>
              <label className="text-[10px] font-mono uppercase text-zinc-400 flex items-center gap-1.5 mb-1">
                <Move className="w-3 h-3 text-emerald-400" /> Motion Curve
              </label>
              <select
                value={activeScene.motion}
                onChange={(e) => handleUpdate('motion', e.target.value)}
                className="w-full px-3 py-2 rounded-xl bg-black/60 border border-zinc-800 text-xs text-zinc-200 focus:outline-none"
              >
                <option>Slow Zoom</option>
                <option>Parallax Pan</option>
                <option>Camera Shake</option>
                <option>Static Focus</option>
              </select>
            </div>

            {/* BGM Mood */}
            <div>
              <label className="text-[10px] font-mono uppercase text-zinc-400 flex items-center gap-1.5 mb-1">
                <Music className="w-3 h-3 text-purple-400" /> BGM Mood
              </label>
              <select
                value={activeScene.bgm}
                onChange={(e) => handleUpdate('bgm', e.target.value)}
                className="w-full px-3 py-2 rounded-xl bg-black/60 border border-zinc-800 text-xs text-zinc-200 focus:outline-none"
              >
                <option>Dark Tension</option>
                <option>Epic Climax</option>
                <option>High Stakes Cultivation</option>
                <option>Tragic Sentiment</option>
              </select>
            </div>

            {/* SFX Hit */}
            <div>
              <label className="text-[10px] font-mono uppercase text-zinc-400 flex items-center gap-1.5 mb-1">
                <Zap className="w-3 h-3 text-amber-400" /> SFX Impact
              </label>
              <select
                value={activeScene.sfx}
                onChange={(e) => handleUpdate('sfx', e.target.value)}
                className="w-full px-3 py-2 rounded-xl bg-black/60 border border-zinc-800 text-xs text-zinc-200 focus:outline-none"
              >
                <option>Thunder Strike</option>
                <option>Sword Slash</option>
                <option>Energy Blast</option>
                <option>None</option>
              </select>
            </div>

            {/* Tagged Characters */}
            <div className="pt-2 border-t border-zinc-800">
              <span className="text-[10px] font-mono uppercase text-zinc-400 block mb-1.5">
                Tagged Characters
              </span>
              <div className="flex flex-wrap gap-1.5">
                {activeScene.characters.map((c, i) => (
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
