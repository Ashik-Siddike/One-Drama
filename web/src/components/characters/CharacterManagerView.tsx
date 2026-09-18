import { useState, useEffect } from 'react'
import {
  Users,
  Sparkles,
  RefreshCw,
  Save,
  Check,
  Mic,
  Volume2,
  Sliders,
  Shield,
  UserCheck,
  Layers,
  Image as ImageIcon,
  ExternalLink,
} from 'lucide-react'
import {
  fetchCharacterCast,
  saveCharacterRegistry,
  triggerCharacterScan,
  type DramaCharacter,
  type CharacterCastResponse,
} from '../../services/api'

export const CharacterManagerView: React.FC = () => {
  const [castData, setCastData] = useState<CharacterCastResponse | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isScanning, setIsScanning] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [savedMsg, setSavedMsg] = useState(false)
  const [selectedRole, setSelectedRole] = useState<string | null>('hero')

  const loadCast = async () => {
    try {
      setIsLoading(true)
      const data = await fetchCharacterCast()
      setCastData(data)
      const firstRole = Object.keys(data.registry?.roles || {})[0]
      if (firstRole) setSelectedRole(firstRole)
    } catch (err) {
      console.error('Failed to load character cast:', err)
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    loadCast()
  }, [])

  const handleScanCharacters = async () => {
    setIsScanning(true)
    try {
      await triggerCharacterScan()
      await loadCast()
    } catch (err: any) {
      alert(err.message || 'Character scan failed')
    } finally {
      setIsScanning(false)
    }
  }

  const handleSaveRegistry = async () => {
    if (!castData?.registry) return
    setIsSaving(true)
    try {
      await saveCharacterRegistry(castData.registry)
      setSavedMsg(true)
      setTimeout(() => setSavedMsg(false), 3000)
    } catch (err: any) {
      alert(err.message || 'Failed to save voice registry')
    } finally {
      setIsSaving(false)
    }
  }

  const updateRoleField = (roleKey: string, field: string, value: any) => {
    if (!castData?.registry?.roles) return
    setCastData({
      ...castData,
      registry: {
        ...castData.registry,
        roles: {
          ...castData.registry.roles,
          [roleKey]: {
            ...castData.registry.roles[roleKey],
            [field]: value,
          },
        },
      },
    })
  }

  const toggleDubbingMode = (mode: string) => {
    if (!castData?.registry) return
    setCastData({
      ...castData,
      registry: {
        ...castData.registry,
        dubbing_mode: mode,
      },
    })
  }

  if (isLoading) {
    return (
      <div className="py-24 text-center text-xs font-mono text-indigo-400 animate-pulse">
        Loading Drama Cast & Multi-Voice Studio...
      </div>
    )
  }

  const characters = castData?.lineup?.characters || []
  const roles = castData?.registry?.roles || {}
  const dubbingMode = castData?.registry?.dubbing_mode || 'multi_character'

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-5 rounded-2xl bg-zinc-900/60 border border-zinc-800/80 backdrop-blur-sm">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-purple-500/10 border border-purple-500/20 flex items-center justify-center text-purple-400">
            <Users className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-base font-bold text-zinc-100">
                Drama Cast & Multi-Voice Studio
              </h2>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-purple-500/10 text-purple-300 border border-purple-500/20">
                AI VISION DIARIZATION & DUBBING
              </span>
            </div>
            <p className="text-xs text-zinc-400 mt-0.5">
              নায়ক, নায়িকা, ভিলেন ও বাবা-মায়ের জন্য আলাদা আলাদা স্বর ও ভয়েস মডেল কনফিগার করুন।
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={handleScanCharacters}
            disabled={isScanning}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-zinc-800 hover:bg-zinc-700 disabled:opacity-50 text-zinc-200 text-xs font-medium border border-zinc-700/60 transition-all shadow-sm"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isScanning ? 'animate-spin text-purple-400' : ''}`} />
            <span>{isScanning ? 'স্ক্যান হচ্ছে...' : 'AI ক্যারেক্টার রি-স্ক্যান'}</span>
          </button>

          <button
            onClick={handleSaveRegistry}
            disabled={isSaving}
            className="flex items-center gap-2 px-5 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:bg-zinc-800 text-white text-xs font-semibold tracking-wide transition-all shadow-md shadow-indigo-600/20"
          >
            {savedMsg ? <Check className="w-4 h-4 text-emerald-400" /> : <Save className="w-4 h-4" />}
            <span>{savedMsg ? 'সংরক্ষিত!' : 'ভয়েস সেট করুন'}</span>
          </button>
        </div>
      </div>

      {/* Dubbing Mode Switcher */}
      <div className="p-4 rounded-2xl bg-zinc-900/40 border border-zinc-800/80 flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-indigo-500/10 flex items-center justify-center text-indigo-400">
            <Layers className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-xs font-semibold text-zinc-200">ডাবিং স্টাইল মোড (Dubbing Mode)</h3>
            <p className="text-[11px] text-zinc-400">
              চরিত্রভিত্তিক আসল কথোপকথন (ডাবিং) নাকি শুধু নায়কের প্রথম পুরুষ বয়ান?
            </p>
          </div>
        </div>

        <div className="flex items-center p-1 rounded-xl bg-black/50 border border-zinc-800">
          <button
            onClick={() => toggleDubbingMode('multi_character')}
            className={`px-4 py-1.5 rounded-lg text-xs font-medium transition-all ${
              dubbingMode === 'multi_character'
                ? 'bg-indigo-600 text-white shadow-sm'
                : 'text-zinc-400 hover:text-zinc-200'
            }`}
          >
            🎭 সম্পূর্ণ ডাবিং স্টাইল (Multi-Character)
          </button>
          <button
            onClick={() => toggleDubbingMode('protagonist_pov')}
            className={`px-4 py-1.5 rounded-lg text-xs font-medium transition-all ${
              dubbingMode === 'protagonist_pov'
                ? 'bg-indigo-600 text-white shadow-sm'
                : 'text-zinc-400 hover:text-zinc-200'
            }`}
          >
            🎙️ ১ম পুরুষ বয়ান (Protagonist POV)
          </button>
        </div>
      </div>

      {/* Cast Reference Sheet Banner */}
      {castData?.has_sheet_image && (
        <div className="p-5 rounded-2xl bg-zinc-900/40 border border-zinc-800/80 space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <ImageIcon className="w-4 h-4 text-purple-400" />
              <h3 className="text-xs font-semibold text-zinc-200 uppercase tracking-wider">
                Drama Cast Reference Sheet (স্বয়ংক্রিয় ফেস লাইনআপ গ্রিড)
              </h3>
            </div>
            <a
              href="/api/characters/lineup_image"
              target="_blank"
              rel="noreferrer"
              className="text-[11px] font-mono text-indigo-400 hover:text-indigo-300 flex items-center gap-1"
            >
              <span>ফুল সাইজ দেখুন</span>
              <ExternalLink className="w-3 h-3" />
            </a>
          </div>

          <div className="rounded-xl overflow-hidden border border-zinc-800/80 bg-black/60 max-h-72 flex items-center justify-center">
            <img
              src="/api/characters/lineup_image"
              alt="Character Cast Lineup Sheet"
              className="max-h-72 w-auto object-contain mx-auto"
            />
          </div>
          <p className="text-[11px] text-zinc-500 font-mono">
            * এই একটি রেফারেন্স শিট দেখেই Gemini Vision প্রতি ডায়ালগে নায়ক, নায়িকা ও ভিলেনের মুখ চেনে।
          </p>
        </div>
      )}

      {/* Discovered Characters in Drama */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <UserCheck className="w-4 h-4 text-emerald-400" />
            <h3 className="text-xs font-semibold text-zinc-200 uppercase tracking-wider">
              ডিটেক্টেড চরিত্রসমূহ ({characters.length} জন)
            </h3>
          </div>
          <span className="text-[10px] font-mono text-zinc-500">
            {characters.length > 0 ? 'স্বয়ংক্রিয়ভাবে ট্র্যাক করা হয়েছে' : 'কোনো চরিত্র পাওয়া যায়নি'}
          </span>
        </div>

        {characters.length === 0 ? (
          <div className="p-8 rounded-2xl bg-zinc-900/30 border border-zinc-800/60 text-center space-y-2">
            <Users className="w-8 h-8 text-zinc-600 mx-auto" />
            <p className="text-xs text-zinc-400">
              ভিডিওর চরিত্রগুলোকে স্বয়ংক্রিয়ভাবে চিহ্নিত করতে উপরের &quot;AI ক্যারেক্টার রি-স্ক্যান&quot; বাটনে ক্লিক করুন।
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {characters.map((char) => {
              const isFemale = char.gender === 'female'
              return (
                <div
                  key={char.id}
                  className="p-4 rounded-2xl bg-zinc-900/60 border border-zinc-800/80 hover:border-zinc-700 transition-all flex flex-col justify-between gap-3"
                >
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-zinc-800 text-zinc-300">
                        {char.id}
                      </span>
                      <span
                        className={`text-[10px] font-mono font-semibold px-2 py-0.5 rounded border ${
                          isFemale
                            ? 'bg-pink-500/10 text-pink-400 border-pink-500/30'
                            : 'bg-blue-500/10 text-blue-400 border-blue-500/30'
                        }`}
                      >
                        {char.role.toUpperCase()} ({char.gender.toUpperCase()})
                      </span>
                    </div>

                    <div>
                      <h4 className="text-sm font-bold text-zinc-100 flex items-center gap-2">
                        <span>{char.name}</span>
                        {char.hindi_name && (
                          <span className="text-xs font-normal text-purple-300">
                            ({char.hindi_name})
                          </span>
                        )}
                      </h4>
                      <p className="text-[11px] text-zinc-400 mt-1 line-clamp-2">
                        {char.visual_summary}
                      </p>
                    </div>
                  </div>

                  <div className="pt-2 border-t border-zinc-800/60 flex items-center justify-between text-[11px] text-zinc-400 font-mono">
                    <span>এসাইন করা রোল:</span>
                    <span className="text-indigo-400 font-bold capitalize">{char.role}</span>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* Voice Roles Registry & Custom Voice Assignment */}
      <div className="p-5 rounded-2xl bg-zinc-900/60 border border-zinc-800/80 space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-zinc-800">
          <div className="flex items-center gap-2">
            <Mic className="w-4 h-4 text-indigo-400" />
            <h3 className="text-xs font-semibold text-zinc-200 uppercase tracking-wider">
              ভয়েস রোল কনফিগারেশন (Voice Roles & Neural Models)
            </h3>
          </div>
          <span className="text-[10px] font-mono text-zinc-400">
            F5-TTS & Microsoft Edge-TTS
          </span>
        </div>

        {/* Role Tabs */}
        <div className="flex flex-wrap gap-2">
          {Object.entries(roles).map(([key, role]) => {
            const isSelected = selectedRole === key
            return (
              <button
                key={key}
                onClick={() => setSelectedRole(key)}
                className={`px-3.5 py-2 rounded-xl text-xs font-medium border transition-all flex items-center gap-2 ${
                  isSelected
                    ? 'bg-indigo-600/20 border-indigo-500 text-indigo-200 shadow-sm'
                    : 'bg-zinc-800/60 border-zinc-700/60 text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800'
                }`}
              >
                <span>{role.display_name}</span>
              </button>
            )
          })}
        </div>

        {/* Selected Role Detail Box */}
        {selectedRole && roles[selectedRole] && (
          <div className="p-4 rounded-xl bg-black/40 border border-zinc-800/80 space-y-4 mt-2">
            <div className="flex items-center justify-between">
              <div>
                <h4 className="text-sm font-bold text-zinc-100">
                  {roles[selectedRole].display_name}
                </h4>
                <p className="text-xs text-zinc-400 mt-0.5">
                  {roles[selectedRole].description}
                </p>
              </div>

              <span
                className={`text-[10px] font-mono px-2 py-0.5 rounded border ${
                  roles[selectedRole].gender === 'female'
                    ? 'bg-pink-500/10 text-pink-400 border-pink-500/30'
                    : 'bg-blue-500/10 text-blue-400 border-blue-500/30'
                }`}
              >
                {roles[selectedRole].gender.toUpperCase()}
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-1">
              {/* Edge-TTS Neural Voice Choice */}
              <div>
                <label className="text-[11px] font-mono uppercase text-zinc-400 block mb-1">
                  Edge-TTS Neural Voice
                </label>
                <select
                  value={roles[selectedRole].edge_voice || 'hi-IN-MadhurNeural'}
                  onChange={(e) => updateRoleField(selectedRole, 'edge_voice', e.target.value)}
                  className="w-full px-3 py-2 rounded-xl bg-black/60 border border-zinc-800 text-xs text-zinc-200 focus:outline-none font-mono"
                >
                  <option value="hi-IN-MadhurNeural">Madhur (হিন্দি মেল - তরুণ/নায়ক)</option>
                  <option value="hi-IN-SwaraNeural">Swara (হিন্দি ফিমেল - মিষ্টি/নায়িকা)</option>
                  <option value="hi-IN-KavyaNeural">Kavya (হিন্দি ফিমেল - পরিপক্ক/মা)</option>
                  <option value="bn-IN-BashkarNeural">Bashkar (বাংলা মেল)</option>
                  <option value="bn-IN-TanishaaNeural">Tanishaa (বাংলা ফিমেল)</option>
                  <option value="en-US-GuyNeural">Guy (ইংরেজি মেল)</option>
                  <option value="en-US-AriaNeural">Aria (ইংরেজি ফিমেল)</option>
                </select>
              </div>

              {/* Pitch Shift */}
              <div>
                <label className="text-[11px] font-mono uppercase text-zinc-400 block mb-1">
                  গলার স্বর পিচ (Pitch Offset)
                </label>
                <select
                  value={roles[selectedRole].edge_pitch || '+0Hz'}
                  onChange={(e) => updateRoleField(selectedRole, 'edge_pitch', e.target.value)}
                  className="w-full px-3 py-2 rounded-xl bg-black/60 border border-zinc-800 text-xs text-zinc-200 focus:outline-none font-mono"
                >
                  <option value="-40Hz">-40Hz (ভীষণ গম্ভীর / ভারী দানব)</option>
                  <option value="-25Hz">-25Hz (ভারী ভিলেন / বৃদ্ধ বাবা)</option>
                  <option value="-10Hz">-10Hz (পরিপক্ক স্বর)</option>
                  <option value="+0Hz">+0Hz (স্বাভাবিক কণ্ঠ)</option>
                  <option value="+15Hz">+15Hz (উত্তেজিত / বন্ধু)</option>
                  <option value="+25Hz">+25Hz (মিষ্টি / কম বয়সী বোন)</option>
                </select>
              </div>

              {/* Speed Rate */}
              <div>
                <label className="text-[11px] font-mono uppercase text-zinc-400 block mb-1">
                  কথা বলার গতি (Speaking Rate)
                </label>
                <select
                  value={roles[selectedRole].edge_rate || '+0%'}
                  onChange={(e) => updateRoleField(selectedRole, 'edge_rate', e.target.value)}
                  className="w-full px-3 py-2 rounded-xl bg-black/60 border border-zinc-800 text-xs text-zinc-200 focus:outline-none font-mono"
                >
                  <option value="-10%">-10% (ধীরস্থির / গম্ভীর)</option>
                  <option value="-5%">-5% (ধীর)</option>
                  <option value="+0%">+0% (স্বাভাবিক গতি)</option>
                  <option value="+5%">+5% (উত্তেজনাপূর্ণ / দ্রুত)</option>
                  <option value="+10%">+10% (খুব দ্রুত)</option>
                </select>
              </div>
            </div>

            {/* F5-TTS Reference Audio Path */}
            <div className="pt-2 border-t border-zinc-800/60">
              <label className="text-[11px] font-mono uppercase text-zinc-400 block mb-1">
                F5-TTS কাস্টম ভয়েস ক্লোন রেফারেন্স (ঐচ্ছিক WAV ফাইল)
              </label>
              <input
                type="text"
                placeholder="যেমন: storage/voice_reference/heroine_hindi.wav (ফাঁকা রাখলে Edge-TTS চলবে)"
                value={roles[selectedRole].f5_ref_audio || ''}
                onChange={(e) => updateRoleField(selectedRole, 'f5_ref_audio', e.target.value)}
                className="w-full px-3 py-2 rounded-xl bg-black/60 border border-zinc-800 text-xs text-zinc-200 focus:outline-none font-mono placeholder:text-zinc-600"
              />
              <p className="text-[10px] text-zinc-500 font-mono mt-1">
                * যদি নির্দিষ্ট ক্যারেক্টারের জন্য কোনো F5-TTS ফাইল না থাকে, তবে সিস্টেম স্বয়ংক্রিয়ভাবে তার নির্ধারিত Edge-TTS মডেলে কথা বলাবে।
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
