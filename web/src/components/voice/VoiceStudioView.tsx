import { useState, useEffect, useRef } from 'react'
import {
  Mic,
  Play,
  Pause,
  Volume2,
  Sparkles,
  Sliders,
  CheckCircle2,
  Radio,
  UploadCloud,
  Star,
  Trash2,
  Edit3,
  Save,
  X,
  RefreshCw,
  FileAudio,
  AlertCircle,
} from 'lucide-react'
import {
  fetchVoiceProfiles,
  uploadVoiceSample,
  setDefaultVoice,
  updateVoiceTranscript,
  deleteVoiceProfile,
  synthesizeVoicePreview,
  type VoiceProfile,
} from '../../services/api'

export const VoiceStudioView: React.FC = () => {
  // Voice Profiles State
  const [profiles, setProfiles] = useState<VoiceProfile[]>([])
  const [activeVoiceId, setActiveVoiceId] = useState<string>('')
  const [isLoadingProfiles, setIsLoadingProfiles] = useState(false)
  const [currentlyPlayingAudio, setCurrentlyPlayingAudio] = useState<string | null>(null)
  const audioPlayerRef = useRef<HTMLAudioElement | null>(null)

  // Drag & Drop Upload State
  const [isDragging, setIsDragging] = useState(false)
  const [droppedFile, setDroppedFile] = useState<File | null>(null)
  const [droppedPreviewUrl, setDroppedPreviewUrl] = useState<string | null>(null)
  const [newVoiceName, setNewVoiceName] = useState('')
  const [newVoiceRefText, setNewVoiceRefText] = useState('')
  const [setAsDefaultImmediately, setSetAsDefaultImmediately] = useState(true)
  const [isUploading, setIsUploading] = useState(false)
  const fileInputRef = useRef<HTMLInputElement | null>(null)

  // Inline Transcript Editing State
  const [editingVoiceId, setEditingVoiceId] = useState<string | null>(null)
  const [editingText, setEditingText] = useState('')
  const [editingName, setEditingName] = useState('')
  const [isSavingEdit, setIsSavingEdit] = useState(false)

  // Live Synthesis Preview State
  const [text, setText] = useState(
    'इस दुनिया में कमजोर की कोई जगह नहीं है, ताकत ही सब कुछ तय करती है।'
  )
  const [engine, setEngine] = useState('f5-tts')
  const [speed, setSpeed] = useState(1.05)
  const [emotion, setEmotion] = useState('Dramatic Xianxia')
  const [isSynthesizing, setIsSynthesizing] = useState(false)
  const [synthAudioUrl, setSynthAudioUrl] = useState<string | null>(null)
  const [statusMsg, setStatusMsg] = useState<string | null>(null)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  useEffect(() => {
    loadProfiles()
  }, [])

  const loadProfiles = async () => {
    setIsLoadingProfiles(true)
    try {
      const res = await fetchVoiceProfiles()
      setProfiles(res.voices || [])
      setActiveVoiceId(res.active_voice_id || '')
    } catch (err: any) {
      setErrorMsg(`Failed to load voice profiles: ${err.message}`)
    } finally {
      setIsLoadingProfiles(false)
    }
  }

  // Handle Drag and Drop
  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(true)
  }

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleSelectedAudioFile(e.dataTransfer.files[0])
    }
  }

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      handleSelectedAudioFile(e.target.files[0])
    }
  }

  const handleSelectedAudioFile = (file: File) => {
    setDroppedFile(file)
    const url = URL.createObjectURL(file)
    setDroppedPreviewUrl(url)

    // Suggest clean name based on file
    if (!newVoiceName) {
      const baseName = file.name.replace(/\.[^/.]+$/, '').replace(/[_-]/g, ' ')
      setNewVoiceName(baseName.charAt(0).toUpperCase() + baseName.slice(1))
    }
  }

  // Handle Upload
  const handleUploadVoice = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!droppedFile) {
      setErrorMsg('Please select or drop an audio file first.')
      return
    }
    if (!newVoiceRefText.trim()) {
      setErrorMsg('Please type or paste the exact spoken transcript for this voice sample.')
      return
    }

    setIsUploading(true)
    setErrorMsg(null)
    setStatusMsg('Normalizing audio to 24kHz and registering voice profile...')

    const formData = new FormData()
    formData.append('file', droppedFile)
    formData.append('name', newVoiceName.trim() || 'Custom Voice')
    formData.append('ref_text', newVoiceRefText.trim())
    formData.append('set_as_default', String(setAsDefaultImmediately))

    try {
      const res = await uploadVoiceSample(formData)
      setStatusMsg(`Voice profile '${res.voice.name}' saved and registered!`)
      setDroppedFile(null)
      setDroppedPreviewUrl(null)
      setNewVoiceName('')
      setNewVoiceRefText('')
      await loadProfiles()
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to upload voice sample.')
    } finally {
      setIsUploading(false)
    }
  }

  // Handle Set Default
  const handleSetDefault = async (voiceId: string) => {
    try {
      setStatusMsg('Updating default voice in settings.json...')
      await setDefaultVoice(voiceId)
      setActiveVoiceId(voiceId)
      setStatusMsg('Active default voice updated successfully!')
      await loadProfiles()
    } catch (err: any) {
      setErrorMsg(`Failed to set default voice: ${err.message}`)
    }
  }

  // Handle Edit Transcript
  const startEditing = (v: VoiceProfile) => {
    setEditingVoiceId(v.id)
    setEditingName(v.name)
    setEditingText(v.ref_text)
  }

  const saveEditedTranscript = async () => {
    if (!editingVoiceId) return
    setIsSavingEdit(true)
    try {
      await updateVoiceTranscript(editingVoiceId, editingText, editingName)
      setStatusMsg('Transcript updated successfully!')
      setEditingVoiceId(null)
      await loadProfiles()
    } catch (err: any) {
      setErrorMsg(`Failed to save edit: ${err.message}`)
    } finally {
      setIsSavingEdit(false)
    }
  }

  // Handle Delete
  const handleDeleteVoice = async (voiceId: string) => {
    if (!window.confirm('Are you sure you want to delete this voice profile?')) return
    try {
      await deleteVoiceProfile(voiceId)
      setStatusMsg('Voice profile removed.')
      await loadProfiles()
    } catch (err: any) {
      setErrorMsg(`Failed to delete voice: ${err.message}`)
    }
  }

  // Audio Playback
  const togglePlayAudio = (url: string) => {
    if (currentlyPlayingAudio === url) {
      audioPlayerRef.current?.pause()
      setCurrentlyPlayingAudio(null)
    } else {
      setCurrentlyPlayingAudio(url)
      if (audioPlayerRef.current) {
        audioPlayerRef.current.src = url
        audioPlayerRef.current.play()
      }
    }
  }

  // Synthesis Preview
  const handleSynthesize = async () => {
    if (!text.trim()) return
    setIsSynthesizing(true)
    setStatusMsg('Synthesizing speech on engine...')
    setErrorMsg(null)
    try {
      const res = await synthesizeVoicePreview({
        text,
        engine,
        speed,
        emotion,
      })
      setSynthAudioUrl(`${res.audio_url}?t=${Date.now()}`)
      setStatusMsg('Synthesis complete! Ready to playback.')
    } catch (err: any) {
      setErrorMsg(`Synthesis failed: ${err.message}`)
    } finally {
      setIsSynthesizing(false)
    }
  }

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      {/* Hidden Audio Player for list previews */}
      <audio
        ref={audioPlayerRef}
        onEnded={() => setCurrentlyPlayingAudio(null)}
        className="hidden"
      />

      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-5 rounded-2xl bg-zinc-900/60 border border-zinc-800/80 backdrop-blur-sm">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400">
            <Mic className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-base font-bold text-zinc-100">Voice Reference & Zero-Shot Cloning Studio</h2>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                {profiles.length} VOICES REGISTERED
              </span>
            </div>
            <p className="text-xs text-zinc-400 mt-0.5">
              Drag & drop reference audio, customize transcripts, and select the active default voice for F5-TTS dubbing.
            </p>
          </div>
        </div>

        <button
          onClick={loadProfiles}
          className="flex items-center gap-2 px-3.5 py-2 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-zinc-300 text-xs font-mono transition-colors"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isLoadingProfiles ? 'animate-spin' : ''}`} />
          <span>Refresh Library</span>
        </button>
      </div>

      {/* Feedback Alerts */}
      {statusMsg && (
        <div className="p-3 rounded-xl bg-emerald-950/40 border border-emerald-500/30 text-xs text-emerald-300 flex items-center justify-between">
          <span className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
            {statusMsg}
          </span>
          <button onClick={() => setStatusMsg(null)} className="text-emerald-400 hover:text-white">
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {errorMsg && (
        <div className="p-3 rounded-xl bg-rose-950/40 border border-rose-500/30 text-xs text-rose-300 flex items-center justify-between">
          <span className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
            {errorMsg}
          </span>
          <button onClick={() => setErrorMsg(null)} className="text-rose-400 hover:text-white">
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* Main 2-Column Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Voice Profiles Library (7 cols) */}
        <div className="lg:col-span-7 space-y-4">
          <div className="p-5 rounded-2xl bg-zinc-900/60 border border-zinc-800/80 space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-zinc-800">
              <div className="flex items-center gap-2">
                <Volume2 className="w-4 h-4 text-indigo-400" />
                <h3 className="text-xs font-bold text-zinc-100 uppercase tracking-wider">
                  Voice Reference Library
                </h3>
              </div>
              <span className="text-[11px] font-mono text-zinc-500">
                Active Default Voice is used across all dubbing pipelines
              </span>
            </div>

            {/* Voices List */}
            <div className="space-y-3">
              {profiles.map((v) => {
                const isDefault = v.id === activeVoiceId || v.is_default
                const isPlaying = currentlyPlayingAudio === v.audio_url
                const isEditingThis = editingVoiceId === v.id

                return (
                  <div
                    key={v.id}
                    className={`p-4 rounded-xl border transition-all space-y-3 ${
                      isDefault
                        ? 'bg-gradient-to-r from-emerald-950/20 via-zinc-900/80 to-zinc-900/80 border-emerald-500/40 shadow-lg shadow-emerald-500/5'
                        : 'bg-black/40 border-zinc-800/80 hover:border-zinc-700'
                    }`}
                  >
                    {/* Top Row: Title, Badges & Audio Player */}
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex items-center gap-3">
                        <button
                          onClick={() => togglePlayAudio(v.audio_url)}
                          className={`w-9 h-9 rounded-xl flex items-center justify-center transition-all ${
                            isPlaying
                              ? 'bg-emerald-500 text-black shadow-lg shadow-emerald-500/30'
                              : 'bg-zinc-800 hover:bg-zinc-700 text-zinc-200'
                          }`}
                          title="Preview Reference Audio"
                        >
                          {isPlaying ? (
                            <Pause className="w-4 h-4 fill-current" />
                          ) : (
                            <Play className="w-4 h-4 fill-current ml-0.5" />
                          )}
                        </button>

                        <div>
                          <div className="flex items-center gap-2">
                            <h4 className="text-xs font-bold text-zinc-100">
                              {v.name}
                            </h4>
                            {isDefault && (
                              <span className="px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 text-[9px] font-mono font-bold flex items-center gap-1">
                                <Star className="w-2.5 h-2.5 fill-current" />
                                ACTIVE DEFAULT
                              </span>
                            )}
                          </div>
                          <div className="flex items-center gap-2 text-[10px] font-mono text-zinc-500 mt-0.5">
                            <span>{v.filename}</span>
                            <span>•</span>
                            <span>{v.duration_sec}s PCM 24kHz</span>
                          </div>
                        </div>
                      </div>

                      {/* Right Action Buttons */}
                      <div className="flex items-center gap-1.5 shrink-0">
                        {!isDefault && (
                          <button
                            onClick={() => handleSetDefault(v.id)}
                            className="px-2.5 py-1 rounded-lg bg-zinc-800 hover:bg-emerald-600 hover:text-white text-zinc-300 text-[11px] font-mono transition-colors"
                          >
                            Set as Default
                          </button>
                        )}

                        <button
                          onClick={() => (isEditingThis ? setEditingVoiceId(null) : startEditing(v))}
                          className="p-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-400 hover:text-zinc-200 transition-colors"
                          title="Edit Transcript Text"
                        >
                          <Edit3 className="w-3.5 h-3.5" />
                        </button>

                        {!isDefault && profiles.length > 1 && (
                          <button
                            onClick={() => handleDeleteVoice(v.id)}
                            className="p-1.5 rounded-lg bg-zinc-800 hover:bg-rose-900/60 hover:text-rose-300 text-zinc-500 transition-colors"
                            title="Delete Voice"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        )}
                      </div>
                    </div>

                    {/* Spoken Transcript Box */}
                    {isEditingThis ? (
                      <div className="p-3 rounded-xl bg-zinc-950 border border-indigo-500/40 space-y-2">
                        <div className="flex items-center justify-between text-[11px] font-mono text-zinc-400">
                          <span>Edit Voice Name & Spoken Transcript:</span>
                        </div>
                        <input
                          type="text"
                          value={editingName}
                          onChange={(e) => setEditingName(e.target.value)}
                          className="w-full px-2.5 py-1.5 rounded-lg bg-black/60 border border-zinc-800 text-xs text-zinc-200 focus:outline-none"
                          placeholder="Voice Name"
                        />
                        <textarea
                          rows={2}
                          value={editingText}
                          onChange={(e) => setEditingText(e.target.value)}
                          className="w-full p-2.5 rounded-lg bg-black/60 border border-zinc-800 text-xs text-indigo-200 font-sans focus:outline-none"
                          placeholder="Type or paste exact spoken transcript..."
                        />
                        <div className="flex justify-end gap-2">
                          <button
                            onClick={() => setEditingVoiceId(null)}
                            className="px-3 py-1 rounded-lg bg-zinc-800 text-zinc-300 text-xs"
                          >
                            Cancel
                          </button>
                          <button
                            onClick={saveEditedTranscript}
                            disabled={isSavingEdit}
                            className="flex items-center gap-1.5 px-3 py-1 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold"
                          >
                            <Save className="w-3.5 h-3.5" />
                            <span>{isSavingEdit ? 'Saving...' : 'Save Transcript'}</span>
                          </button>
                        </div>
                      </div>
                    ) : (
                      <div className="p-2.5 rounded-lg bg-black/50 border border-zinc-800/80 text-xs text-zinc-300 font-sans leading-relaxed">
                        <span className="text-zinc-500 font-mono text-[10px] uppercase block mb-0.5">
                          Spoken Transcript (Reference Prompt):
                        </span>
                        <p className="italic text-zinc-200">
                          "{v.ref_text}"
                        </p>
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        </div>

        {/* Right Column: Drag & Drop Uploader + Live Preview (5 cols) */}
        <div className="lg:col-span-5 space-y-6">
          {/* Drag & Drop Audio File Uploader Card */}
          <div className="p-5 rounded-2xl bg-zinc-900/60 border border-zinc-800/80 space-y-4">
            <div className="flex items-center justify-between pb-2 border-b border-zinc-800">
              <h3 className="text-xs font-semibold text-zinc-300 uppercase tracking-wider flex items-center gap-2">
                <UploadCloud className="w-4 h-4 text-emerald-400" />
                Add New Voice Sample
              </h3>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-zinc-800 text-zinc-400">
                WAV / MP3 / M4A
              </span>
            </div>

            <form onSubmit={handleUploadVoice} className="space-y-4">
              {/* Drag & Drop Zone */}
              <div
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current?.click()}
                className={`p-6 rounded-2xl border-2 border-dashed transition-all cursor-pointer flex flex-col items-center justify-center text-center gap-2 ${
                  isDragging
                    ? 'border-emerald-500 bg-emerald-500/10'
                    : droppedFile
                    ? 'border-emerald-500/40 bg-black/40'
                    : 'border-zinc-800 hover:border-zinc-700 bg-black/30'
                }`}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="audio/*,.wav,.mp3,.m4a,.aac,.ogg"
                  onChange={handleFileInputChange}
                  className="hidden"
                />

                <div className="w-12 h-12 rounded-xl bg-zinc-800/80 border border-zinc-700 flex items-center justify-center text-zinc-400">
                  {droppedFile ? (
                    <FileAudio className="w-6 h-6 text-emerald-400" />
                  ) : (
                    <UploadCloud className="w-6 h-6 text-zinc-400" />
                  )}
                </div>

                {droppedFile ? (
                  <div className="space-y-1">
                    <p className="text-xs font-bold text-zinc-200">
                      {droppedFile.name}
                    </p>
                    <p className="text-[10px] font-mono text-emerald-400">
                      {(droppedFile.size / (1024 * 1024)).toFixed(2)} MB • Ready for conversion
                    </p>
                  </div>
                ) : (
                  <div className="space-y-1">
                    <p className="text-xs font-semibold text-zinc-200">
                      Drag & drop your voice sample audio here
                    </p>
                    <p className="text-[11px] text-zinc-500">
                      or click to browse from your computer (5–10s clear clip)
                    </p>
                  </div>
                )}
              </div>

              {/* Audio preview of dropped file */}
              {droppedPreviewUrl && (
                <div className="p-2.5 rounded-xl bg-black/60 border border-zinc-800">
                  <span className="text-[10px] font-mono text-zinc-400 block mb-1">
                    Audio Preview:
                  </span>
                  <audio controls src={droppedPreviewUrl} className="w-full h-8" />
                </div>
              )}

              {/* Voice Name Input */}
              <div>
                <label className="text-[11px] font-mono uppercase text-zinc-400 block mb-1">
                  Voice Name / Character
                </label>
                <input
                  type="text"
                  value={newVoiceName}
                  onChange={(e) => setNewVoiceName(e.target.value)}
                  placeholder="e.g. Cold Cultivator Narrator"
                  className="w-full px-3 py-2 rounded-xl bg-black/60 border border-zinc-800 text-xs text-zinc-200 focus:outline-none focus:border-indigo-500"
                />
              </div>

              {/* Spoken Transcript Input */}
              <div>
                <label className="text-[11px] font-mono uppercase text-zinc-400 block mb-1">
                  Spoken Dialogue Transcript (Exact Words) *
                </label>
                <textarea
                  rows={3}
                  value={newVoiceRefText}
                  onChange={(e) => setNewVoiceRefText(e.target.value)}
                  placeholder="Type or paste the exact spoken words from this audio clip (e.g. 'इस दुनिया में कमजोर की कोई जगह नहीं है, ताकत ही सब कुछ तय करती है।')"
                  className="w-full p-3 rounded-xl bg-black/60 border border-zinc-800 text-xs text-zinc-200 font-sans focus:outline-none focus:border-indigo-500 leading-relaxed"
                />
                <p className="text-[10px] text-zinc-500 mt-1">
                  💡 <strong>Crucial for F5-TTS:</strong> The transcript must match the audio clip word-for-word for flawless voice cloning.
                </p>
              </div>

              {/* Set as Default Checkbox */}
              <label className="flex items-center gap-2.5 cursor-pointer text-xs text-zinc-300">
                <input
                  type="checkbox"
                  checked={setAsDefaultImmediately}
                  onChange={(e) => setSetAsDefaultImmediately(e.target.checked)}
                  className="w-4 h-4 accent-emerald-500 rounded cursor-pointer"
                />
                <span className="font-medium">Set as active default voice for all dubbing</span>
              </label>

              {/* Upload Button */}
              <button
                type="submit"
                disabled={isUploading || !droppedFile}
                className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:bg-zinc-800 text-white text-xs font-bold tracking-wide transition-all shadow-md shadow-emerald-600/20"
              >
                {isUploading ? (
                  <>
                    <Radio className="w-4 h-4 animate-spin text-white" />
                    <span>Processing & Converting with FFmpeg...</span>
                  </>
                ) : (
                  <>
                    <Sparkles className="w-4 h-4 text-amber-300" />
                    <span>SAVE & REGISTER VOICE SAMPLE</span>
                  </>
                )}
              </button>
            </form>
          </div>

          {/* Test Voice Synthesis on Active Voice Card */}
          <div className="p-5 rounded-2xl bg-zinc-900/60 border border-zinc-800/80 space-y-4">
            <div className="flex items-center justify-between pb-2 border-b border-zinc-800">
              <h3 className="text-xs font-semibold text-zinc-300 uppercase tracking-wider flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-indigo-400" />
                Test Voice Synthesis Preview
              </h3>
              <span className="text-[10px] font-mono text-zinc-400">
                Active: {profiles.find((v) => v.id === activeVoiceId)?.name || 'Default'}
              </span>
            </div>

            <div>
              <label className="text-[11px] font-mono uppercase text-zinc-400 block mb-1">
                Test Dialogue Line
              </label>
              <textarea
                rows={2}
                value={text}
                onChange={(e) => setText(e.target.value)}
                className="w-full p-2.5 rounded-xl bg-black/60 border border-zinc-800 text-xs text-indigo-200 focus:outline-none"
              />
            </div>

            <button
              onClick={handleSynthesize}
              disabled={isSynthesizing}
              className="w-full py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:bg-zinc-800 text-white text-xs font-semibold transition-all shadow"
            >
              {isSynthesizing ? 'Synthesizing...' : 'Synthesize Test Phrase'}
            </button>

            {synthAudioUrl && (
              <div className="pt-2 border-t border-zinc-800 space-y-2">
                <audio controls src={synthAudioUrl} className="w-full h-8" autoPlay />
                <span className="text-[10px] font-mono text-emerald-400 flex items-center gap-1">
                  <CheckCircle2 className="w-3 h-3" /> Synthesis generated using active voice settings!
                </span>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

