import type {
  SystemStats,
  ProjectData,
  PipelineStatus,
  Recommendation,
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

export async function fetchDaily3DSuggestions(): Promise<{
  status: string
  suggestions: Array<{
    id: string
    title: string
    chinese_title: string
    query: string
    hook: string
    category: string
    target_audience: string
    icon: string
  }>
}> {
  const res = await fetch(`${API_BASE}/discovery/daily_suggestions`)
  if (!res.ok) throw new Error('Failed to fetch daily 3D suggestions')
  return res.json()
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

export async function triggerDownload(query_or_url: string, limit?: number) {
  const res = await fetch(`${API_BASE}/pipeline/download`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query_or_url, limit }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Download request failed' }))
    throw new Error(err.detail || 'Download request failed')
  }
  return res.json()
}

export async function triggerPipelineRun(opts: {
  limit?: number
  force?: boolean
  carry_context?: boolean
  split_compilations?: boolean
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

export async function fetchCharacters() {
  const res = await fetch(`${API_BASE}/characters`)
  if (!res.ok) throw new Error('Failed to fetch characters')
  return res.json()
}

export async function saveCharacters(chars: any[]) {
  const res = await fetch(`${API_BASE}/characters`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(chars),
  })
  if (!res.ok) throw new Error('Failed to save characters')
  return res.json()
}

// --------------------------------------------------------------------------- //
// Voice Studio API
// --------------------------------------------------------------------------- //
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

