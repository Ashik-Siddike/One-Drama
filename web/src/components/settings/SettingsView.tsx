import { useState, useEffect } from 'react'
import { Settings, Save, Check, Key, Eye, Sliders, HardDrive } from 'lucide-react'
import { fetchSettings, saveSettings } from '../../services/api'

export const SettingsView: React.FC = () => {
  const [cfg, setCfg] = useState<any>(null)
  const [isSaving, setIsSaving] = useState(false)
  const [savedMsg, setSavedMsg] = useState(false)

  useEffect(() => {
    fetchSettings().then((data) => setCfg(data)).catch(console.error)
  }, [])

  const handleSave = async () => {
    if (!cfg) return
    setIsSaving(true)
    try {
      await saveSettings(cfg)
      setSavedMsg(true)
      setTimeout(() => setSavedMsg(false), 3000)
    } finally {
      setIsSaving(false)
    }
  }

  if (!cfg) {
    return (
      <div className="py-20 text-center text-xs font-mono text-indigo-400 animate-pulse">
        Loading studio settings...
      </div>
    )
  }

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-5 rounded-2xl bg-zinc-900/60 border border-zinc-800/80 backdrop-blur-sm">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-zinc-800 border border-zinc-700/60 flex items-center justify-center text-zinc-300">
            <Settings className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-base font-bold text-zinc-100">Engine Settings & Preferences</h2>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-zinc-800 text-zinc-400">
                CONFIG / SETTINGS.JSON
              </span>
            </div>
            <p className="text-xs text-zinc-400 mt-0.5">
              Control AI model backends, API credentials, visual anti-copyright filters, and audio mixing levels.
            </p>
          </div>
        </div>

        <button
          onClick={handleSave}
          disabled={isSaving}
          className="flex items-center gap-2 px-5 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:bg-zinc-800 text-white text-xs font-semibold tracking-wide transition-all shadow-md shadow-indigo-600/20"
        >
          {savedMsg ? <Check className="w-4 h-4 text-emerald-400" /> : <Save className="w-4 h-4" />}
          <span>{savedMsg ? 'Saved to settings.json!' : 'Save Changes'}</span>
        </button>
      </div>

      {/* Settings Grid */}
      <div className="space-y-4">
        {/* Core Language & TTS Engine */}
        <div className="p-5 rounded-2xl bg-zinc-900/40 border border-zinc-800/80 space-y-4">
          <h3 className="text-xs font-semibold text-zinc-300 uppercase tracking-wider pb-2 border-b border-zinc-800">
            AI Speech & Language Engine
          </h3>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="text-[11px] font-mono uppercase text-zinc-400 block mb-1">
                Target Language
              </label>
              <select
                value={cfg.target_language || 'hi'}
                onChange={(e) => setCfg({ ...cfg, target_language: e.target.value })}
                className="w-full px-3 py-2 rounded-xl bg-black/60 border border-zinc-800 text-xs text-zinc-200 focus:outline-none"
              >
                <option value="hi">Hindi (हिन्दी - Dramatic Narration)</option>
                <option value="bn">Bengali (বাংলা)</option>
                <option value="en">English (Cinematic Story)</option>
                <option value="es">Spanish (Español)</option>
              </select>
            </div>

            <div>
              <label className="text-[11px] font-mono uppercase text-zinc-400 block mb-1">
                Primary Voice Synthesis Backend
              </label>
              <select
                value={cfg.tts_engine || 'f5-tts'}
                onChange={(e) => setCfg({ ...cfg, tts_engine: e.target.value })}
                className="w-full px-3 py-2 rounded-xl bg-black/60 border border-zinc-800 text-xs text-zinc-200 focus:outline-none font-mono"
              >
                <option value="f5-tts">F5-TTS (Diffusion Flow Matching on RTX 4060 GPU)</option>
                <option value="edge-tts">Edge-TTS (Cloud Neural Voice - Hi-IN-Madhur)</option>
              </select>
            </div>
          </div>
        </div>

        {/* Visual Filters & Watermark Inpainting */}
        <div className="p-5 rounded-2xl bg-zinc-900/40 border border-zinc-800/80 space-y-4">
          <h3 className="text-xs font-semibold text-zinc-300 uppercase tracking-wider pb-2 border-b border-zinc-800">
            Visual Remastering & Watermark Inpainting (FFmpeg)
          </h3>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="text-[11px] font-mono uppercase text-zinc-400 block mb-1">
                Subtitle Bottom Crop (Pixels)
              </label>
              <input
                type="number"
                value={cfg.visual_filters?.crop_bottom ?? 80}
                onChange={(e) =>
                  setCfg({
                    ...cfg,
                    visual_filters: {
                      ...cfg.visual_filters,
                      crop_bottom: parseInt(e.target.value, 10) || 0,
                    },
                  })
                }
                className="w-full px-3 py-2 rounded-xl bg-black/60 border border-zinc-800 text-xs text-zinc-200 focus:outline-none font-mono"
              />
            </div>

            <div>
              <label className="text-[11px] font-mono uppercase text-zinc-400 block mb-1">
                Anti-Fingerprint Zoom Percent
              </label>
              <input
                type="number"
                step="0.01"
                value={cfg.visual_filters?.zoom_percent ?? 1.04}
                onChange={(e) =>
                  setCfg({
                    ...cfg,
                    visual_filters: {
                      ...cfg.visual_filters,
                      zoom_percent: parseFloat(e.target.value) || 1.0,
                    },
                  })
                }
                className="w-full px-3 py-2 rounded-xl bg-black/60 border border-zinc-800 text-xs text-zinc-200 focus:outline-none font-mono"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
            <label className="flex items-center gap-3 p-3 rounded-xl bg-black/40 border border-zinc-800/60 cursor-pointer">
              <input
                type="checkbox"
                checked={cfg.visual_filters?.remove_watermark ?? false}
                onChange={(e) =>
                  setCfg({
                    ...cfg,
                    visual_filters: {
                      ...cfg.visual_filters,
                      remove_watermark: e.target.checked,
                    },
                  })
                }
                className="w-4 h-4 accent-indigo-500 rounded"
              />
              <span className="text-xs text-zinc-300">
                Auto Delogo Top-Left Watermark (Bilibili / UP Tag)
              </span>
            </label>

            <label className="flex items-center gap-3 p-3 rounded-xl bg-black/40 border border-zinc-800/60 cursor-pointer">
              <input
                type="checkbox"
                checked={cfg.visual_filters?.remove_right_disclaimer ?? false}
                onChange={(e) =>
                  setCfg({
                    ...cfg,
                    visual_filters: {
                      ...cfg.visual_filters,
                      remove_right_disclaimer: e.target.checked,
                    },
                  })
                }
                className="w-4 h-4 accent-indigo-500 rounded"
              />
              <span className="text-xs text-zinc-300">
                Auto Inpaint Right Vertical Disclaimer Text
              </span>
            </label>
          </div>
        </div>

        {/* Audio Mixing Levels */}
        <div className="p-5 rounded-2xl bg-zinc-900/40 border border-zinc-800/80 space-y-4">
          <h3 className="text-xs font-semibold text-zinc-300 uppercase tracking-wider pb-2 border-b border-zinc-800">
            Audio Levels & Ducking
          </h3>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <div className="flex justify-between text-xs font-mono text-zinc-400 mb-1">
                <span>BGM Ducking Level</span>
                <span className="text-purple-400 font-bold">
                  {Math.round((cfg.audio_mixing?.bgm_volume ?? 0.35) * 100)}%
                </span>
              </div>
              <input
                type="range"
                min="0.10"
                max="0.80"
                step="0.05"
                value={cfg.audio_mixing?.bgm_volume ?? 0.35}
                onChange={(e) =>
                  setCfg({
                    ...cfg,
                    audio_mixing: {
                      ...cfg.audio_mixing,
                      bgm_volume: parseFloat(e.target.value),
                    },
                  })
                }
                className="w-full accent-purple-500"
              />
            </div>

            <div>
              <div className="flex justify-between text-xs font-mono text-zinc-400 mb-1">
                <span>Narration Voiceover Volume</span>
                <span className="text-indigo-400 font-bold">
                  {Math.round((cfg.audio_mixing?.voice_volume ?? 1.0) * 100)}%
                </span>
              </div>
              <input
                type="range"
                min="0.5"
                max="1.5"
                step="0.05"
                value={cfg.audio_mixing?.voice_volume ?? 1.0}
                onChange={(e) =>
                  setCfg({
                    ...cfg,
                    audio_mixing: {
                      ...cfg.audio_mixing,
                      voice_volume: parseFloat(e.target.value),
                    },
                  })
                }
                className="w-full accent-indigo-500"
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
