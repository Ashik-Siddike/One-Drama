import { useState, useEffect } from 'react'
import { BookOpen, Save, Sparkles, Layers, Shield, ScrollText, Check } from 'lucide-react'
import { fetchStoryBible, saveStoryBible } from '../../services/api'

export const StoryBibleView: React.FC = () => {
  const [bible, setBible] = useState<any>(null)
  const [isSaving, setIsSaving] = useState(false)
  const [savedMsg, setSavedMsg] = useState(false)

  useEffect(() => {
    fetchStoryBible().then((data) => setBible(data)).catch(console.error)
  }, [])

  const handleSave = async () => {
    if (!bible) return
    setIsSaving(true)
    try {
      await saveStoryBible(bible)
      setSavedMsg(true)
      setTimeout(() => setSavedMsg(false), 3000)
    } finally {
      setIsSaving(false)
    }
  }

  if (!bible) {
    return (
      <div className="py-20 text-center text-xs font-mono text-indigo-400 animate-pulse">
        Loading Story Bible context...
      </div>
    )
  }

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-5 rounded-2xl bg-zinc-900/60 border border-zinc-800/80 backdrop-blur-sm">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-purple-500/10 border border-purple-500/20 flex items-center justify-center text-purple-400">
            <BookOpen className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-base font-bold text-zinc-100">Story Bible & World Lore</h2>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-purple-500/10 text-purple-400 border border-purple-500/20">
                GEMINI CONTEXT ENGINE
              </span>
            </div>
            <p className="text-xs text-zinc-400 mt-0.5">
              Defines multi-episode lore, cultivation realm hierarchies, and sect power dynamics.
            </p>
          </div>
        </div>

        <button
          onClick={handleSave}
          disabled={isSaving}
          className="flex items-center gap-2 px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:bg-zinc-800 text-white text-xs font-semibold tracking-wide transition-all shadow-md shadow-indigo-600/20"
        >
          {savedMsg ? <Check className="w-4 h-4 text-emerald-400" /> : <Save className="w-4 h-4" />}
          <span>{savedMsg ? 'Saved to Engine!' : 'Save Story Bible'}</span>
        </button>
      </div>

      {/* Series Title & Premise */}
      <div className="p-5 rounded-2xl bg-zinc-900/40 border border-zinc-800/80 space-y-4">
        <div>
          <label className="block text-[11px] font-mono uppercase tracking-wider text-zinc-400 mb-1">
            Series Title (Manhua / Short Drama)
          </label>
          <input
            type="text"
            value={bible.title || ''}
            onChange={(e) => setBible({ ...bible, title: e.target.value })}
            className="w-full px-4 py-2.5 rounded-xl bg-black/60 border border-zinc-800 text-sm font-semibold text-zinc-100 focus:outline-none focus:border-indigo-500"
          />
        </div>

        <div>
          <label className="block text-[11px] font-mono uppercase tracking-wider text-zinc-400 mb-1">
            Core Story Premise (Provided to Gemini for Dramatic Recap Context)
          </label>
          <textarea
            rows={3}
            value={bible.premise || ''}
            onChange={(e) => setBible({ ...bible, premise: e.target.value })}
            className="w-full px-4 py-2.5 rounded-xl bg-black/60 border border-zinc-800 text-xs text-zinc-200 focus:outline-none focus:border-indigo-500 leading-relaxed font-sans"
          />
        </div>
      </div>

      {/* Two Column Grid: Cultivation Realms & Story Arcs */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Cultivation Realms Ladder */}
        <div className="p-5 rounded-2xl bg-zinc-900/40 border border-zinc-800/80 space-y-3">
          <div className="flex items-center gap-2 pb-2 border-b border-zinc-800 text-xs font-semibold text-zinc-300">
            <Layers className="w-4 h-4 text-amber-400" />
            <span>Cultivation Power Realms (境界体系)</span>
          </div>

          <div className="space-y-2">
            {bible.realms?.map((realm: any, idx: number) => (
              <div
                key={idx}
                className="p-3 rounded-xl bg-black/40 border border-zinc-800/80 text-xs flex items-center justify-between gap-3"
              >
                <div>
                  <div className="font-bold text-zinc-200">{realm.name}</div>
                  <div className="text-[11px] text-zinc-400">{realm.desc}</div>
                </div>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20 shrink-0">
                  {realm.level}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Story Arcs Progress */}
        <div className="p-5 rounded-2xl bg-zinc-900/40 border border-zinc-800/80 space-y-3">
          <div className="flex items-center gap-2 pb-2 border-b border-zinc-800 text-xs font-semibold text-zinc-300">
            <ScrollText className="w-4 h-4 text-indigo-400" />
            <span>Story Arcs & Episodes Timeline</span>
          </div>

          <div className="space-y-2">
            {bible.arcs?.map((arc: any, idx: number) => (
              <div
                key={idx}
                className="p-3 rounded-xl bg-black/40 border border-zinc-800/80 text-xs flex items-center justify-between gap-3"
              >
                <div>
                  <div className="font-bold text-zinc-200">{arc.name}</div>
                  <div className="text-[10px] font-mono text-zinc-500">{arc.episodes}</div>
                </div>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 shrink-0">
                  {arc.status}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Sects & Clan Factions */}
      <div className="p-5 rounded-2xl bg-zinc-900/40 border border-zinc-800/80 space-y-3">
        <div className="flex items-center gap-2 pb-2 border-b border-zinc-800 text-xs font-semibold text-zinc-300">
          <Shield className="w-4 h-4 text-emerald-400" />
          <span>Major Sects & Factions (宗门势力)</span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {bible.sects?.map((sect: any, idx: number) => (
            <div
              key={idx}
              className="p-3 rounded-xl bg-black/40 border border-zinc-800/80 text-xs space-y-1"
            >
              <div className="flex items-center justify-between">
                <span className="font-bold text-zinc-200">{sect.name}</span>
                <span className="text-[10px] font-mono text-emerald-400">{sect.alignment}</span>
              </div>
              <div className="text-[11px] text-zinc-400 font-mono">Leader: {sect.leader}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
