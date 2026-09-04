export interface GpuStats {
  available: boolean;
  name: string;
  vram_used_gb: number;
  vram_total_gb: number;
  vram_percent: number;
  device_count: number;
  error?: string;
}

export interface StorageBreakdown {
  raw_episodes_mb: number;
  audio_separated_mb: number;
  tts_output_mb: number;
  processed_episodes_mb: number;
  master_export_mb: number;
}

export interface SystemStats {
  gpu: GpuStats;
  cpu_percent: number;
  ram_used_gb: number;
  ram_total_gb: number;
  ram_percent: number;
  storage_breakdown: StorageBreakdown;
  total_storage_mb: number;
  target_language: string;
  tts_engine: string;
  asr_engine: string;
  google_drive?: {
    connected: boolean;
    path: string;
    sync_folder?: string;
  };
}

export interface EpisodeStatus {
  separated: boolean;
  transcribed: boolean;
  recap_adapted: boolean;
  voice_synthesized: boolean;
  rendered: boolean;
}

export interface Episode {
  filename: string;
  stem: string;
  raw_size_mb: number;
  status: EpisodeStatus;
  segment_count: number;
}

export interface MasterMovie {
  filename: string;
  size_mb: number;
  path: string;
}

export interface ProjectData {
  active_project: string;
  total_raw_episodes: number;
  episodes: Episode[];
  master_movies: MasterMovie[];
  has_publish_guide: boolean;
  youtube_package: Record<string, any>;
  last_run_report: Record<string, any>;
}

export interface PipelineStatus {
  is_running: boolean;
  job_type: string;
  progress_percent: number;
  current_episode: string | null;
  current_stage: string | null;
  total_episodes: number;
  processed_episodes: number;
  started_at: number | null;
  last_error: string | null;
  logs: string[];
}

export interface Recommendation {
  title: string;
  url: string;
  play_count?: number;
  duration?: string;
  author?: string;
  safe: boolean;
  safety_flags?: string[];
  reason?: string;
}
