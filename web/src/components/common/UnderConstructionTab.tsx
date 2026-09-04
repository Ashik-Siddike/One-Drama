import { Layers, CheckCircle2 } from 'lucide-react'
import type { StudioTab } from '../layout/Sidebar'

interface UnderConstructionTabProps {
  tab: StudioTab
}

const TAB_DESCRIPTIONS: Record<string, { title: string; phase: string; desc: string; features: string[] }> = {
  stories: {
    title: 'Story Bible & World Building',
    phase: 'Phase 4',
    desc: 'Deep multi-episode story context manager with world rules, power hierarchies, and sect lore.',
    features: ['Multi-Arc Story Lore', 'Power System Tracker', 'Context Memory for Gemini'],
  },
  characters: {
    title: 'Character Consistency & Profile Studio',
    phase: 'Phase 5',
    desc: 'Visual face consistency profiles, clothing presets, and persona dialogue bibles.',
    features: ['LoRA / Consistency Anchors', 'Signature Weapons & Attire', 'Relationship Graphs'],
  },
  scenes: {
    title: 'Scene Visual Editor & Cut Builder',
    phase: 'Phase 6',
    desc: 'Fine-grained scene composition with camera zoom, pan-and-scan curves, and parallax.',
    features: ['Dynamic Camera Shake', 'Motion Pan Presets', 'Visual FX Overlay'],
  },
  visuals: {
    title: 'Visual Studio & Flux/Midjourney Prompter',
    phase: 'Phase 7',
    desc: 'AI image generation bridge for automated clickbait thumbnails and hero frames.',
    features: ['Midjourney v6 Integration', 'Flux.1 Schnell Direct Render', 'Automatic Lighting Fixes'],
  },
  voice: {
    title: 'Voice Studio (F5-TTS & Edge-TTS)',
    phase: 'Phase 7',
    desc: 'Zero-shot voice cloning workbench with emotional tone sliders and pitch controls.',
    features: ['Custom Narrator Reference Upload', 'Dramatic Hindi Emotional Flow', 'Phonetic Devanagari Warping'],
  },
  audio: {
    title: 'Audio Studio & Dynamic DAW',
    phase: 'Phase 7',
    desc: 'Multi-stem volume automation, dynamic BGM ducking under speech, and SFX impact triggers.',
    features: ['Smart Dialogue Ducking (-18dB)', 'Cinematic Whoosh SFX Placer', 'Loudness Normalization (LUFS)'],
  },
  timeline: {
    title: 'Multi-Track Production Timeline',
    phase: 'Phase 8',
    desc: 'Non-linear video and audio track layout with frame-accurate scrubbing and markers.',
    features: ['Real-Time Waveform Display', 'Cut Transition Snapping', 'Chapter Marker Generator'],
  },
  render: {
    title: 'Render Center & Cloud Dispatcher',
    phase: 'Phase 9',
    desc: 'GPU batch encoding queue (NVENC / libx264) with bitrate profiling and multi-resolution export.',
    features: ['4K & 1080p Master Movie Render', 'Lossless Direct Stream Copy', 'YouTube Chapter Metadata Burn'],
  },
  qc: {
    title: 'Automated QC & Compliance Audit',
    phase: 'Phase 9',
    desc: 'Pre-flight automated check verifying subtitle sync, audio clipping, and Content ID safety.',
    features: ['Zero Dialogue Drop Audit', 'Audio Peak Detection', 'Fair Use Transformation Score'],
  },
  settings: {
    title: 'Engine Preferences & Hardware Configuration',
    phase: 'Phase 10',
    desc: 'Configure API keys (Gemini), CUDA device indices, default vocal volumes, and download paths.',
    features: ['Gemini API Key Setup', 'Visual Zoom & Delogo Margins', 'Default Target Language'],
  },
}

export const UnderConstructionTab: React.FC<UnderConstructionTabProps> = ({ tab }) => {
  const info = TAB_DESCRIPTIONS[tab] || {
    title: tab.toUpperCase(),
    phase: 'Upcoming Phase',
    desc: 'This module is scheduled for implementation in the next phase.',
    features: [],
  }

  return (
    <div className="p-8 rounded-2xl bg-zinc-900/40 border border-zinc-800/80 backdrop-blur-sm max-w-3xl mx-auto my-8">
      <div className="flex items-center gap-3 mb-4">
        <div className="p-2.5 rounded-xl bg-indigo-500/10 border border-indigo-500/20 text-indigo-400">
          <Layers className="w-6 h-6" />
        </div>
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-bold text-zinc-100">{info.title}</h2>
            <span className="text-xs font-mono px-2 py-0.5 rounded bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
              {info.phase}
            </span>
          </div>
          <p className="text-xs text-zinc-400 mt-1">{info.desc}</p>
        </div>
      </div>

      <div className="mt-6 pt-6 border-t border-zinc-800 space-y-3">
        <h4 className="text-xs font-semibold text-zinc-300 uppercase tracking-wider">
          Planned Module Features
        </h4>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
          {info.features.map((feat, idx) => (
            <div
              key={idx}
              className="p-3 rounded-xl bg-black/40 border border-zinc-800/80 text-xs font-mono text-zinc-300 flex items-center gap-2"
            >
              <CheckCircle2 className="w-3.5 h-3.5 text-indigo-400 shrink-0" />
              <span>{feat}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
