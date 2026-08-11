export type Point = [number, number]

export interface DetectParams {
  min_area_frac?: number
  max_area_frac?: number
  merge_radius?: number
  block_size?: number
  c?: number
  mode?: 'adaptive' | 'otsu'
}

export type RegionSource = 'auto' | 'manual' | 'sam' | 'merge'

export interface Region {
  id: string
  bbox: [number, number, number, number]
  polygon: Point[]
  source: RegionSource
  confidence: number
  enabled: boolean
  label: string
  has_mask: boolean
}

export interface PageSummary {
  id: string
  name: string
  width: number
  height: number
  region_count: number
  export_count: number
}

export interface Page extends PageSummary {
  regions: Region[]
  detect_params: DetectParams
  source_path: string | null
}

export interface Project {
  id: string
  name: string
  created_at: string
  pages: PageSummary[]
}

export interface FsEntry {
  name: string
  path: string
  is_dir: boolean
  is_image: boolean
}

export interface FsListing {
  path: string
  parent: string | null
  entries: FsEntry[]
}

export interface JobStatus {
  id: string
  kind: string
  status: 'running' | 'done' | 'error'
  done: number
  total: number
  error: string | null
}

export interface ExportOptions {
  style: 'ink' | 'binary'
  rgb: 'original' | 'pure_black'
  padding: number
}

export interface SamStatus {
  available: boolean
  model: string | null
}
