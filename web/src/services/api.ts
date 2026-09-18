import type {
  SystemStats,
  ProjectData,
  PipelineStatus,
  Recommendation,
  LocalScanResult,
  ImportLocalResult,
} from '../types'

const API_BASE = '/api'

export async function fetchHealth(): Promise<{ status: string }> {
  const res = await fetch(`${API_BASE}/health`)
  if (!res.ok) throw new Error('Backend offline')
  return res.json()
}

export async function fetchSystemStats(): Promise<SystemStats> {
  const res = await fetch(`${API_BASE}/system/stats`)
  if (!res.ok) throw new Error('Failed to fetch system stats')
  return res.json()
}

export async function fetchProjects(): Promise<ProjectData> {
  const res = await fetch(`${API_BASE}/projects`)
  if (!res.ok) throw new Error('Failed to fetch project data')
  return res.json()
}

export async function fetchEpisodeDetails(stem: string) {
  const res = await fetch(`${API_BASE}/projects/episodes/${encodeURIComponent(stem)}`)
  if (!res.ok) throw new Error('Failed to fetch episode details')
  return res.json()
}

export async function scanLocalPath(path: string): Promise<LocalScanResult> {
  const res = await fetch(`${API_BASE}/projects/scan_local_path`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to scan path' }))
    throw new Error(err.detail || 'Failed to scan path')
  }
  return res.json()
}

export async function importLocalPath(opts: {
  path: string
  archive_previous?: boolean
  copy_or_move?: 'copy' | 'move'
  rename_to_standard?: boolean
  selected_files?: string[]
}): Promise<ImportLocalResult> {
  const res = await fetch(`${API_BASE}/projects/import_local_path`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      path: opts.path,
      archive_previous: opts.archive_previous ?? false,
      copy_or_move: opts.copy_or_move ?? 'copy',
      rename_to_standard: opts.rename_to_standard ?? true,
      selected_files: opts.selected_files,
    }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to import local path' }))
    throw new Error(err.detail || 'Failed to import local path')
  }
  return res.json()
}

export async function uploadEpisodeFiles(
  files: File[],
  archive_previous = false,
  rename_to_standard = true
): Promise<ImportLocalResult> {
  const formData = new FormData()
  for (const file of files) {
    formData.append('files', file)
  }
  formData.append('archive_previous', String(archive_previous))
  formData.append('rename_to_standard', String(rename_to_standard))

  const res = await fetch(`${API_BASE}/projects/upload_episodes`, {
    method: 'POST',
    body: formData,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to upload episodes' }))
    throw new Error(err.detail || 'Failed to upload episodes')
  }
  return res.json()
}

export async function fetchTrending(
  genre = 'cultivation',
  limit = 6
): Promise<{ count: number; recommendations: Recommendation[] }> {
  const res = await fetch(
    `${API_BASE}/discovery/trending?genre=${encodeURIComponent(genre)}&limit=${limit}`
  )
  if (!res.ok) throw new Error('Failed to fetch trending manhua')
  return res.json()
}

export async function searchManhua(
  query: string,
  limit = 6
): Promise<{ count: number; results: Recommendation[] }> {
  const res = await fetch(
    `${API_BASE}/discovery/search?q=${encodeURIComponent(query)}&max_results=${limit}`
  )
  if (!res.ok) throw new Error('Failed to search manhua')
  return res.json()
}

export async function fetchDaily3DSuggestions(
  genre?: string,
  refresh = false
): Promise<{
  status: string
  suggestions: Array<{
    id: string
    title: string
    bengali_title?: string
    chinese_title?: string
    query: string
    url?: string
    thumbnail?: string
    genre?: string
    hook: string
    bengali_hook?: string
    category: string
    target_audience: string
    episodes_est?: string
    icon: string
  }>
}> {
  const params = new URLSearchParams()
  if (genre && genre !== 'all') params.set('genre', genre)
  if (refresh) params.set('refresh', 'true')
  const qs = params.toString() ? `?${params.toString()}` : ''
  const res = await fetch(`${API_BASE}/discovery/daily_suggestions${qs}`)
  if (!res.ok) throw new Error('Failed to fetch daily 3D suggestions')
  return res.json()
}

export async function autoScanShortSeries(
  genre?: string,
  count = 6
): Promise<{
  status: string
  count: number
  suggestions: Array<{
    id: string
    title: string
    bengali_title?: string
    chinese_title?: string
    query: string
    url?: string
    thumbnail?: string
    genre?: string
    hook: string
    bengali_hook?: string
    category: string
    target_audience: string
    episodes_est?: string
    icon: string
    is_short_series?: boolean
  }>
}> {
  const params = new URLSearchParams()
  if (genre && genre !== 'all') params.set('genre', genre)
  params.set('count', String(count))
  const qs = params.toString() ? `?${params.toString()}` : ''
  const res = await fetch(`${API_BASE}/discovery/auto_scan_short_series${qs}`, {
    method: 'POST',
  })
  if (!res.ok) throw new Error('Failed to auto-scan short series')
  return res.json()
}


export async function fetchCustomSeries(): Promise<{ status: string; series: any[] }> {
  const res = await fetch(`${API_BASE}/discovery/custom_series`)
  if (!res.ok) throw new Error('Failed to fetch custom series')
  return res.json()
}

export async function addCustomSeries(data: {
  title: string
  url: string
  category?: string
  hook?: string
  genre?: string
}) {
  const res = await fetch(`${API_BASE}/discovery/custom_series`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!res.ok) throw new Error('Failed to add custom series')
  return res.json()
}

export function getProxiedImageUrl(url?: string): string {
  if (!url) return ''
  if (url.startsWith('http://') || url.startsWith('https://')) {
    return `${API_BASE}/media/image_proxy?url=${encodeURIComponent(url)}`
  }
  return url
}

export async function search3DManhua(
  query: string,
  max_candidates = 5,
  screen_watermarks = true
): Promise<{ count: number; results: any[] }> {
  const res = await fetch(`${API_BASE}/discovery/search_3d`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, max_candidates, screen_watermarks }),
  })
  if (!res.ok) throw new Error('Failed to search 3D manhua')
  return res.json()
}

export async function fetchWorkspaceStatus(): Promise<{
  has_active_assets: boolean
  raw_episodes_count: number
  raw_files: string[]
  processed_episodes_count: number
  master_movies_count: number
}> {
  const res = await fetch(`${API_BASE}/projects/workspace_status`)
  if (!res.ok) throw new Error('Failed to fetch workspace status')
  return res.json()
}

export async function archiveWorkspace(projectName?: string): Promise<{
  archived: boolean
  message: string
  archive_path: string | null
  total_files: number
}> {
  const url = projectName
    ? `${API_BASE}/projects/archive?project_name=${encodeURIComponent(projectName)}`
    : `${API_BASE}/projects/archive`
  const res = await fetch(url, { method: 'POST' })
  if (!res.ok) throw new Error('Failed to archive workspace')
  return res.json()
}

export async function fetchArchives(): Promise<any[]> {
  const res = await fetch(`${API_BASE}/projects/archives`)
  if (!res.ok) throw new Error('Failed to fetch archives')
  return res.json()
}

export async function triggerDownload(
  query_or_url: string,
  limit?: number,
  archive_previous = false
) {
  const res = await fetch(`${API_BASE}/pipeline/download`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query_or_url, limit, archive_previous }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Download request failed' }))
    throw new Error(err.detail || 'Download request failed')
  }
  return res.json()
}

export async function triggerAutoProduce(opts: {
  query_or_url: string
  limit?: number
  enable_filler_trim?: boolean
  generate_shorts?: boolean
  archive_previous?: boolean
}) {
  try {
    const res = await fetch(`${API_BASE}/pipeline/autopilot`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query_or_url: opts.query_or_url,
        limit: opts.limit ?? 25,
        enable_filler_trim: opts.enable_filler_trim ?? false,
        generate_shorts: opts.generate_shorts ?? true,
        archive_previous: opts.archive_previous ?? true,
      }),
    })
    if (res.ok) {
      return await res.json()
    }
  } catch {
    // fallback to download
  }

  return triggerDownload(opts.query_or_url, opts.limit ?? 25, opts.archive_previous ?? true)
}

export async function triggerPipelineRun(opts: {
  limit?: number
  force?: boolean
  carry_context?: boolean
  split_compilations?: boolean
  enable_filler_trim?: boolean
  generate_shorts?: boolean
}) {
  const res = await fetch(`${API_BASE}/pipeline/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(opts),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Pipeline run request failed' }))
    throw new Error(err.detail || 'Pipeline run request failed')
  }
  return res.json()
}

export async function fetchPipelineStatus(): Promise<PipelineStatus> {
  const res = await fetch(`${API_BASE}/pipeline/status`)
  if (!res.ok) throw new Error('Failed to fetch pipeline status')
  return res.json()
}

export async function stopPipeline(): Promise<{ status: string }> {
  const res = await fetch(`${API_BASE}/pipeline/stop`, {
    method: 'POST',
  })
  if (!res.ok) throw new Error('Failed to stop pipeline')
  return res.json()
}

// --------------------------------------------------------------------------- //
// Story Bible & Characters API
// --------------------------------------------------------------------------- //
export async function fetchStoryBible() {
  const res = await fetch(`${API_BASE}/story/bible`)
  if (!res.ok) throw new Error('Failed to fetch story bible')
  return res.json()
}

export async function saveStoryBible(bible: any) {
  const res = await fetch(`${API_BASE}/story/bible`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(bible),
  })
  if (!res.ok) throw new Error('Failed to save story bible')
  return res.json()
}

export interface DramaCharacter {
  id: string
  role: string
  name: string
  hindi_name: string
  gender: string
  frame_index: number
  box_ymin: number
  box_xmin: number
  box_ymax: number
  box_xmax: number
  visual_summary: string
}

export interface CharacterRoleConfig {
  display_name: string
  gender: string
  age_group: string
  f5_ref_audio: string
  f5_ref_text: string
  edge_voice: string
  edge_pitch: string
  edge_rate: string
  description: string
}

export interface CharacterCastResponse {
  lineup: {
    drama_title?: string
    sheet_image?: string
    characters?: DramaCharacter[]
    total_characters?: number
  }
  registry: {
    dubbing_mode: string
    roles: Record<string, CharacterRoleConfig>
  }
  has_sheet_image: boolean
  sheet_image_url: string | null
}

export async function fetchCharacterCast(): Promise<CharacterCastResponse> {
  const res = await fetch(`${API_BASE}/characters`)
  if (!res.ok) throw new Error('Failed to fetch character cast')
  return res.json()
}

export async function saveCharacterRegistry(registry: any): Promise<any> {
  const res = await fetch(`${API_BASE}/characters/registry`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(registry),
  })
  if (!res.ok) throw new Error('Failed to save character registry')
  return res.json()
}

export async function triggerCharacterScan(): Promise<any> {
  const res = await fetch(`${API_BASE}/characters/detect`, {
    method: 'POST',
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to scan characters' }))
    throw new Error(err.detail || 'Failed to scan characters')
  }
  return res.json()
}

export async function fetchCharacters() {
  return fetchCharacterCast().then((res) => res.lineup.characters || [])
}

export async function saveCharacters(chars: any[]) {
  return Promise.resolve({ status: 'ok' })
}

// --------------------------------------------------------------------------- //
// Voice Studio API & Zero-Shot Reference Management
// --------------------------------------------------------------------------- //
export interface VoiceProfile {
  id: string
  name: string
  filename: string
  ref_text: string
  duration_sec: number
  is_default: boolean
  audio_url: string
  created_at: string
}

export async function fetchVoiceProfiles(): Promise<{
  count: number
  active_voice_id: string
  voices: VoiceProfile[]
}> {
  const res = await fetch(`${API_BASE}/voice/profiles`)
  if (!res.ok) throw new Error('Failed to fetch voice profiles')
  return res.json()
}

export async function uploadVoiceSample(formData: FormData): Promise<{
  status: string
  voice: VoiceProfile
  is_default: boolean
}> {
  const res = await fetch(`${API_BASE}/voice/upload`, {
    method: 'POST',
    body: formData,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to upload voice sample' }))
    throw new Error(err.detail || 'Failed to upload voice sample')
  }
  return res.json()
}

export async function setDefaultVoice(voiceId: string): Promise<{
  status: string
  active_voice: VoiceProfile
}> {
  const res = await fetch(`${API_BASE}/voice/select_default`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ voice_id: voiceId }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to set default voice' }))
    throw new Error(err.detail || 'Failed to set default voice')
  }
  return res.json()
}

export async function updateVoiceTranscript(voiceId: string, refText: string, name?: string): Promise<{
  status: string
  voice: VoiceProfile
}> {
  const res = await fetch(`${API_BASE}/voice/update_transcript`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ voice_id: voiceId, ref_text: refText, name }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to update transcript' }))
    throw new Error(err.detail || 'Failed to update transcript')
  }
  return res.json()
}

export async function deleteVoiceProfile(voiceId: string): Promise<{
  status: string
  deleted_id: string
}> {
  const res = await fetch(`${API_BASE}/voice/profiles/${encodeURIComponent(voiceId)}`, {
    method: 'DELETE',
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to delete voice profile' }))
    throw new Error(err.detail || 'Failed to delete voice profile')
  }
  return res.json()
}

export async function synthesizeVoicePreview(req: {
  text: string
  engine?: string
  emotion?: string
  speed?: number
}) {
  const res = await fetch(`${API_BASE}/voice/synthesize`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Voice synthesis failed' }))
    throw new Error(err.detail || 'Voice synthesis failed')
  }
  return res.json()
}

// --------------------------------------------------------------------------- //
// QC Audit API
// --------------------------------------------------------------------------- //
export async function fetchQCAudit() {
  const res = await fetch(`${API_BASE}/qc/audit`)
  if (!res.ok) throw new Error('Failed to fetch QC audit report')
  return res.json()
}

// --------------------------------------------------------------------------- //
// Settings API
// --------------------------------------------------------------------------- //
export async function fetchSettings() {
  const res = await fetch(`${API_BASE}/settings`)
  if (!res.ok) throw new Error('Failed to fetch settings')
  return res.json()
}

export async function saveSettings(settings: any) {
  const res = await fetch(`${API_BASE}/settings`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(settings),
  })
  if (!res.ok) throw new Error('Failed to save settings')
  return res.json()
}

// --------------------------------------------------------------------------- //
// Google Drive Sync API
// --------------------------------------------------------------------------- //
export async function syncToGoogleDrive() {
  const res = await fetch(`${API_BASE}/drive/sync_latest`, {
    method: 'POST',
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Google Drive sync failed' }))
    throw new Error(err.detail || 'Google Drive sync failed')
  }
  return res.json()
}

// --------------------------------------------------------------------------- //
// Safe Creators & Production History (Autonomous Brain)
// --------------------------------------------------------------------------- //
export async function fetchSafeCreators(): Promise<{
  count: number
  creators: any[]
  all_creators: any[]
}> {
  const res = await fetch(`${API_BASE}/scout/safe_creators`)
  if (!res.ok) throw new Error('Failed to fetch safe creators')
  return res.json()
}

export async function auditCreatorChannel(urlOrMid: string): Promise<any> {
  const res = await fetch(`${API_BASE}/scout/audit_creator`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url_or_mid: urlOrMid, max_videos: 5 }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Audit failed' }))
    throw new Error(err.detail || 'Audit failed')
  }
  return res.json()
}

export async function fetchProductionHistory(): Promise<{
  count: number
  history: any[]
}> {
  const res = await fetch(`${API_BASE}/scout/history`)
  if (!res.ok) throw new Error('Failed to fetch production history')
  return res.json()
}

export async function fetchNextCleanSeries(): Promise<{
  candidate: any
}> {
  const res = await fetch(`${API_BASE}/scout/next_clean`)
  if (!res.ok) throw new Error('Failed to query next clean series')
  return res.json()
}

// --------------------------------------------------------------------------- //
// High-CTR YouTube Shorts API
// --------------------------------------------------------------------------- //
export async function generateShort(opts?: {
  video_path?: string
  start_sec?: number
  duration_sec?: number
  top_hook?: string
  bottom_cta?: string
}): Promise<{
  status: string
  short_path: string
  filename: string
  size_mb: number
}> {
  const res = await fetch(`${API_BASE}/pipeline/shorts/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(opts || {}),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Shorts generation failed' }))
    throw new Error(err.detail || 'Shorts generation failed')
  }
  return res.json()
}

// --------------------------------------------------------------------------- //
// Video Catalog & Scene Directing API
// --------------------------------------------------------------------------- //
export interface PlayableVideo {
  id: string
  category: 'processed' | 'raw' | 'master' | 'shorts'
  category_label: string
  filename: string
  title: string
  stem: string
  duration: number
  size_mb: number
  url: string
}

export async function fetchVideoList(): Promise<{ count: number; videos: PlayableVideo[] }> {
  const res = await fetch(`${API_BASE}/video/list`)
  if (!res.ok) throw new Error('Failed to fetch video catalog')
  return res.json()
}

export interface SceneCue {
  id: string
  index: number
  status: 'done' | 'pending'
  start: number
  end: number
  duration: number
  chinese: string
  hindi: string
  camera: string
  motion: string
  bgm: string
  sfx: string
  characters: string[]
}

export async function fetchEpisodeScenes(stem: string): Promise<{ stem: string; count: number; scenes: SceneCue[] }> {
  const res = await fetch(`${API_BASE}/scenes/episode/${encodeURIComponent(stem)}`)
  if (!res.ok) throw new Error('Failed to fetch episode scenes')
  return res.json()
}

export async function saveEpisodeScenes(stem: string, scenes: SceneCue[]): Promise<any> {
  const res = await fetch(`${API_BASE}/scenes/episode/${encodeURIComponent(stem)}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ scenes }),
  })
  if (!res.ok) throw new Error('Failed to save episode scenes')
  return res.json()
}

// --------------------------------------------------------------------------- //
// Smart Intro & Outro Guard API
// --------------------------------------------------------------------------- //
export interface IntroOutroAudit {
  stem: string
  video_filename: string
  total_duration: number
  clean_start_sec: number
  clean_end_sec: number
  clean_duration_sec: number
  intro_cut_duration: number
  outro_cut_duration: number
  cta_detected: string[]
  intro_detected: string[]
  has_chinese_cta: boolean
  confidence: number
}

export async function fetchIntroOutroAudit(stem: string): Promise<IntroOutroAudit> {
  const res = await fetch(`${API_BASE}/qc/intro_outro/${encodeURIComponent(stem)}`)
  if (!res.ok) throw new Error('Failed to audit intro/outro boundaries')
  return res.json()
}

export async function trimIntroOutro(
  stem: string,
  clean_start_sec: number,
  clean_end_sec: number,
  reencode = true
): Promise<{
  status: string
  output_path: string
  filename: string
  clean_duration_sec: number
  stream_url: string
}> {
  const res = await fetch(`${API_BASE}/qc/trim_intro_outro/${encodeURIComponent(stem)}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ clean_start_sec, clean_end_sec, reencode }),
  })
  if (!res.ok) throw new Error('Failed to trim intro/outro')
  return res.json()
}

// --------------------------------------------------------------------------- //
// Local File Manager Integration (1-Click Reveal)
// --------------------------------------------------------------------------- //
export async function openFolderInFileManager(opts: {
  category?: 'master' | 'processed' | 'raw' | 'shorts' | 'tts' | 'drive' | 'workspace' | string
  path?: string
  select_file?: string
}): Promise<{ status: string; message: string; path: string; is_file: boolean }> {
  const res = await fetch(`${API_BASE}/system/open_folder`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(opts),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to open in File Manager' }))
    throw new Error(err.detail || 'Failed to open in File Manager')
  }
  return res.json()
}



