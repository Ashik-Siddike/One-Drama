import { useState, useEffect } from 'react'
import { Users, Plus, Shield, Sword, Sparkles, Copy, Check } from 'lucide-react'
import { fetchCharacters, saveCharacters } from '../../services/api'

export const CharacterManagerView: React.FC = () => {
  const [characters, setCharacters] = useState<any[]>([])
  const [copiedId, setCopiedId] = useState<string | null>(null)
  const [selectedChar, setSelectedChar] = useState<any | null>(null)

  useEffect(() => {
    fetchCharacters().then((data) => {
      setCharacters(data)
      if (data.length > 0) setSelectedChar(data[0])
    }).catch(console.error)
  }, [])

  const handleCopyPrompt = (prompt: string, id: string) => {
    navigator.clipboard.writeText(prompt)
    setCopiedId(id)
    setTimeout(() => setCopiedId(null), 2500)
  }

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-5 rounded-2xl bg-zinc-900/60 border border-zinc-800/80 backdrop-blur-sm">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400">
            <Users className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-base font-bold text-zinc-100">Character Consistency Studio</h2>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                LORA & VISUAL PROFILES
              </span>
            </div>
            <p className="text-xs text-zinc-400 mt-0.5">
              Reusable character bibles for consistent facial features, weapons, and Midjourney/Flux art prompts.
            </p>
          </div>
        </div>
      </div>

      {/* Grid: Character Cards & Selected Detail Drawer */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 2 Cols: Character Grid */}
        <div className="lg:col-span-2 grid grid-cols-1 md:grid-cols-2 gap-4">
          {characters.map((char) => {
            const isSelected = selectedChar?.id === char.id

            return (
              <div
                key={char.id}
                onClick={() => setSelectedChar(char)}
                className={`p-5 rounded-2xl border transition-all cursor-pointer flex flex-col justify-between gap-4 ${
                  isSelected
                    ? 'bg-indigo-600/10 border-indigo-500/60 shadow-lg shadow-indigo-500/10'
                    : 'bg-zinc-900/40 border-zinc-800/80 hover:bg-zinc-900/70 hover:border-zinc-700'
                }`}
              >
                <div>
                  <div className="flex items-center justify-between gap-2 mb-2">
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-zinc-800 text-zinc-400">
                      {char.id}
                    </span>
                    <span
                      className={`text-[10px] font-mono px-2 py-0.5 rounded ${
                        char.role === 'Protagonist'
                          ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                          : char.role === 'Female Lead'
                          ? 'bg-purple-500/10 text-purple-400 border border-purple-500/20'
                          : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                      }`}
                    >
                      {char.role}
                    </span>
                  </div>

                  <h3 className="text-sm font-bold text-zinc-100">{char.name}</h3>
                  <p className="text-xs text-zinc-400 mt-1 line-clamp-2">{char.personality}</p>
                </div>

                <div className="pt-3 border-t border-zinc-800/60 text-xs space-y-1 font-mono text-zinc-400">
                  <div className="flex justify-between">
                    <span>Power Realm:</span>
                    <span className="text-amber-400">{char.power_realm}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Signature:</span>
                    <span className="text-zinc-300 truncate max-w-[160px]">{char.weapon}</span>
                  </div>
                </div>
              </div>
            )
          })}
        </div>

        {/* Right Col: Selected Character Profile & Prompt Generator */}
        <div className="p-5 rounded-2xl bg-zinc-900/60 border border-zinc-800/80 space-y-4">
          {selectedChar ? (
            <>
              <div className="flex items-center justify-between pb-3 border-b border-zinc-800">
                <div>
                  <h3 className="text-sm font-bold text-zinc-100">{selectedChar.name}</h3>
                  <span className="text-[10px] font-mono text-zinc-500">
                    ID: {selectedChar.id} • Age: {selectedChar.age}
                  </span>
                </div>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-indigo-500/10 text-indigo-400">
                  {selectedChar.role}
                </span>
              </div>

              <div className="space-y-3 text-xs">
                <div>
                  <span className="text-[10px] font-mono uppercase text-zinc-500 block">Hair & Eyes</span>
                  <p className="text-zinc-300">{selectedChar.hair} • {selectedChar.eyes}</p>
                </div>

                <div>
                  <span className="text-[10px] font-mono uppercase text-zinc-500 block">Battle Attire</span>
                  <p className="text-zinc-300">{selectedChar.clothing}</p>
                </div>

                <div>
                  <span className="text-[10px] font-mono uppercase text-zinc-500 block">Weapon</span>
                  <p className="text-zinc-300 flex items-center gap-1.5 mt-0.5">
                    <Sword className="w-3.5 h-3.5 text-indigo-400" />
                    {selectedChar.weapon}
                  </p>
                </div>

                <div className="pt-2">
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-[10px] font-mono uppercase text-indigo-400 flex items-center gap-1">
                      <Sparkles className="w-3 h-3" />
                      Midjourney / Flux Anchor Prompt
                    </span>
                    <button
                      onClick={() => handleCopyPrompt(selectedChar.consistency_prompt, selectedChar.id)}
                      className="text-[10px] font-mono px-2 py-0.5 rounded bg-zinc-800 hover:bg-zinc-700 text-zinc-300 flex items-center gap-1"
                    >
                      {copiedId === selectedChar.id ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                      {copiedId === selectedChar.id ? 'Copied' : 'Copy'}
                    </button>
                  </div>
                  <div className="p-2.5 rounded-xl bg-black/60 border border-zinc-800 font-mono text-[11px] text-indigo-200 leading-relaxed select-all">
                    {selectedChar.consistency_prompt}
                  </div>
                </div>
              </div>
            </>
          ) : (
            <div className="py-12 text-center text-xs text-zinc-500 font-mono italic">
              Select a character to view their detailed profile.
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
