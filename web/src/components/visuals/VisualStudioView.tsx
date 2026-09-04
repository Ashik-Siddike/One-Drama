import { useState } from 'react'
import { Sparkles, Copy, Check, Image as ImageIcon, Sliders, Wand2, Download } from 'lucide-react'

const CLICKBAIT_HOOKS = [
  'MAX LEVEL REBIRTH!',
  'BETRAYED SOVEREIGN RETURNS!',
  'HE AWAKENED GOD FLAMES!',
  'IMMORTAL SWORD GOD!',
  'UNBEATABLE SYSTEM ACTIVATED!',
]

export const VisualStudioView: React.FC = () => {
  const [selectedHook, setSelectedHook] = useState(CLICKBAIT_HOOKS[0])
  const [character, setCharacter] = useState('Lin Feng (Protagonist)')
  const [action, setAction] = useState('holding glowing celestial flaming sword in high-speed battle stance')
  const [aspectRatio, setAspectRatio] = useState('16:9')
  const [stylePreset, setStylePreset] = useState('Cinematic 3D Manhua Anime')
  const [copied, setCopied] = useState(false)

  const masterPrompt = `Cinematic 3D donghua manhua style, dynamic low-angle wide shot, ${character} ${action}, dramatic volumetric golden lighting, glowing celestial fire particles, intricate celestial battle armor, hyper-detailed anime aesthetic, highly saturated vivid colors, 8k resolution, Unreal Engine 5 render style --ar ${aspectRatio} --v 6.0`

  const handleCopy = () => {
    navigator.clipboard.writeText(masterPrompt)
    setCopied(true)
    setTimeout(() => setCopied(false), 2500)
  }

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-5 rounded-2xl bg-zinc-900/60 border border-zinc-800/80 backdrop-blur-sm">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-pink-500/10 border border-pink-500/20 flex items-center justify-center text-pink-400">
            <Sparkles className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-base font-bold text-zinc-100">Visual Studio & AI Art Prompter</h2>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-pink-500/10 text-pink-400 border border-pink-500/20">
                MIDJOURNEY V6 & FLUX.1
              </span>
            </div>
            <p className="text-xs text-zinc-400 mt-0.5">
              Generates high-CTR viral thumbnail master prompts fusing character anchors with dramatic action scenes.
            </p>
          </div>
        </div>

        <button
          onClick={handleCopy}
          className="flex items-center gap-2 px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold tracking-wide transition-all shadow-md shadow-indigo-600/20"
        >
          {copied ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
          <span>{copied ? 'Prompt Copied!' : 'Copy Master Prompt'}</span>
        </button>
      </div>

      {/* Main Composer Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left: Controls & Builders (7 cols) */}
        <div className="lg:col-span-7 space-y-4">
          <div className="p-5 rounded-2xl bg-zinc-900/60 border border-zinc-800/80 space-y-4">
            <h3 className="text-xs font-semibold text-zinc-300 uppercase tracking-wider pb-2 border-b border-zinc-800 flex items-center gap-2">
              <Wand2 className="w-4 h-4 text-indigo-400" />
              Prompt Composition Parameters
            </h3>

            {/* Character Anchor */}
            <div>
              <label className="text-[11px] font-mono uppercase text-zinc-400 block mb-1">
                Character Anchor
              </label>
              <select
                value={character}
                onChange={(e) => setCharacter(e.target.value)}
                className="w-full px-4 py-2.5 rounded-xl bg-black/60 border border-zinc-800 text-xs text-zinc-200 focus:outline-none focus:border-indigo-500 font-mono"
              >
                <option>Lin Feng (Protagonist - Golden Eyes, Azure Battle Robe)</option>
                <option>Su Yan (Ice Lotus Empress - White Hair, Sapphire Eyes)</option>
                <option>Elder Gu (Sinister Demonic Elder - Onyx Eyes, Dark Mist)</option>
              </select>
            </div>

            {/* Action / Scene Description */}
            <div>
              <label className="text-[11px] font-mono uppercase text-zinc-400 block mb-1">
                Scene Action & Dynamic Camera
              </label>
              <input
                type="text"
                value={action}
                onChange={(e) => setAction(e.target.value)}
                className="w-full px-4 py-2.5 rounded-xl bg-black/60 border border-zinc-800 text-xs text-zinc-200 focus:outline-none focus:border-indigo-500 font-mono"
              />
            </div>

            {/* Style & Aspect Ratio */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-[11px] font-mono uppercase text-zinc-400 block mb-1">
                  Art Style Preset
                </label>
                <select
                  value={stylePreset}
                  onChange={(e) => setStylePreset(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl bg-black/60 border border-zinc-800 text-xs text-zinc-200 focus:outline-none"
                >
                  <option>Cinematic 3D Manhua Anime</option>
                  <option>Dynamic 2D Action Webtoon</option>
                  <option>Dark Fantasy Realistic Xianxia</option>
                </select>
              </div>

              <div>
                <label className="text-[11px] font-mono uppercase text-zinc-400 block mb-1">
                  Aspect Ratio
                </label>
                <select
                  value={aspectRatio}
                  onChange={(e) => setAspectRatio(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl bg-black/60 border border-zinc-800 text-xs text-zinc-200 focus:outline-none font-mono"
                >
                  <option value="16:9">16:9 (YouTube Full Video)</option>
                  <option value="9:16">9:16 (YouTube Shorts / TikTok)</option>
                  <option value="1:1">1:1 (Square Avatar)</option>
                </select>
              </div>
            </div>

            {/* Clickbait Hooks */}
            <div>
              <label className="text-[11px] font-mono uppercase text-zinc-400 block mb-1.5">
                Viral Thumbnail Hook Badge
              </label>
              <div className="flex flex-wrap gap-2">
                {CLICKBAIT_HOOKS.map((h, i) => (
                  <button
                    key={i}
                    onClick={() => setSelectedHook(h)}
                    className={`px-3 py-1.5 rounded-lg text-xs font-bold font-mono transition-all ${
                      selectedHook === h
                        ? 'bg-amber-500 text-black shadow-md shadow-amber-500/20 scale-105'
                        : 'bg-zinc-800 text-zinc-300 hover:bg-zinc-700'
                    }`}
                  >
                    {h}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Right: Master Output & Mockup (5 cols) */}
        <div className="lg:col-span-5 space-y-4">
          <div className="p-5 rounded-2xl bg-zinc-900/60 border border-zinc-800/80 space-y-4">
            <h3 className="text-xs font-semibold text-zinc-300 uppercase tracking-wider pb-2 border-b border-zinc-800">
              Live Prompt Inspector
            </h3>

            <div className="p-4 rounded-xl bg-black/80 border border-indigo-500/30 text-xs font-mono text-indigo-200 leading-relaxed select-all">
              {masterPrompt}
            </div>

            {/* Thumbnail Mockup Preview */}
            <div className="relative aspect-video rounded-xl bg-gradient-to-tr from-indigo-950 via-zinc-900 to-purple-950 border border-zinc-800 overflow-hidden flex items-end p-4 shadow-xl">
              <div className="absolute inset-0 bg-black/30" />
              {/* Floating Badge */}
              <div className="relative z-10 bg-amber-500 text-black font-black text-sm px-3 py-1 rounded-lg uppercase tracking-wider shadow-2xl border border-yellow-300 transform -rotate-2">
                {selectedHook}
              </div>

              <div className="absolute top-3 right-3 text-[10px] font-mono px-2 py-0.5 rounded bg-black/60 text-zinc-400 border border-zinc-800">
                1920x1080
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
