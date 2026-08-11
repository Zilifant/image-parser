import type {
  DetectParams,
  ExportOptions,
  FsListing,
  JobStatus,
  Page,
  PageSummary,
  Point,
  Profile,
  Project,
  Region,
  RegionExport,
  SamStatus,
  ToolsStatus,
} from './types'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, {
    headers: init?.body instanceof FormData ? undefined : { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!response.ok) {
    let detail = response.statusText
    try {
      const body = await response.json()
      if (body.detail) detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
    } catch {
      /* keep statusText */
    }
    throw new Error(detail)
  }
  return response.json() as Promise<T>
}

export const api = {
  listProjects: () => request<Project[]>('/projects'),
  createProject: (name: string) =>
    request<Project>('/projects', { method: 'POST', body: JSON.stringify({ name }) }),
  getProject: (projectId: string) => request<Project>(`/projects/${projectId}`),
  deleteProject: (projectId: string) => request(`/projects/${projectId}`, { method: 'DELETE' }),

  uploadPages: (projectId: string, files: File[]) => {
    const form = new FormData()
    files.forEach((file) => form.append('files', file))
    return request<PageSummary[]>(`/projects/${projectId}/pages`, { method: 'POST', body: form })
  },
  pagesFromDir: (projectId: string, dir: string) =>
    request<PageSummary[]>(`/projects/${projectId}/pages/from-paths`, {
      method: 'POST',
      body: JSON.stringify({ dir }),
    }),

  getPage: (projectId: string, pageId: string) =>
    request<Page>(`/projects/${projectId}/pages/${pageId}`),
  deletePage: (projectId: string, pageId: string) =>
    request(`/projects/${projectId}/pages/${pageId}`, { method: 'DELETE' }),
  pageImageUrl: (projectId: string, pageId: string) =>
    `/api/projects/${projectId}/pages/${pageId}/image`,
  pageThumbUrl: (projectId: string, pageId: string) =>
    `/api/projects/${projectId}/pages/${pageId}/thumb`,

  detect: (projectId: string, pageId: string, params?: DetectParams) =>
    request<Region[]>(`/projects/${projectId}/pages/${pageId}/detect`, {
      method: 'POST',
      body: JSON.stringify({ params: params ?? null }),
    }),

  createRegion: (projectId: string, pageId: string, polygon: Point[]) =>
    request<Region>(`/projects/${projectId}/pages/${pageId}/regions`, {
      method: 'POST',
      body: JSON.stringify({ polygon }),
    }),
  patchRegion: (
    projectId: string,
    pageId: string,
    regionId: string,
    patch: Partial<Pick<Region, 'polygon' | 'enabled' | 'label' | 'status'>>,
  ) =>
    request<Region>(`/projects/${projectId}/pages/${pageId}/regions/${regionId}`, {
      method: 'PATCH',
      body: JSON.stringify(patch),
    }),
  deleteRegion: (projectId: string, pageId: string, regionId: string) =>
    request(`/projects/${projectId}/pages/${pageId}/regions/${regionId}`, { method: 'DELETE' }),
  setEnabled: (projectId: string, pageId: string, enabled: boolean, regionIds?: string[]) =>
    request<Region[]>(`/projects/${projectId}/pages/${pageId}/regions/set-enabled`, {
      method: 'POST',
      body: JSON.stringify({ enabled, region_ids: regionIds ?? null }),
    }),
  brush: (
    projectId: string,
    pageId: string,
    body: { region_id?: string; points: Point[]; radius: number; mode: 'add' | 'subtract' },
  ) =>
    request<Region>(`/projects/${projectId}/pages/${pageId}/regions/brush`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  mergeRegions: (projectId: string, pageId: string, regionIds: string[]) =>
    request<Region>(`/projects/${projectId}/pages/${pageId}/regions/merge`, {
      method: 'POST',
      body: JSON.stringify({ region_ids: regionIds }),
    }),
  splitRegion: (projectId: string, pageId: string, regionId: string) =>
    request<Region[]>(`/projects/${projectId}/pages/${pageId}/regions/${regionId}/split`, {
      method: 'POST',
      body: JSON.stringify({}),
    }),

  exportPage: (projectId: string, pageId: string, options: ExportOptions, regionIds?: string[]) =>
    request<{ exports: RegionExport[] }>(`/projects/${projectId}/pages/${pageId}/export`, {
      method: 'POST',
      body: JSON.stringify({ ...options, region_ids: regionIds ?? null }),
    }),
  exportCleanPage: (projectId: string, pageId: string, options: ExportOptions) =>
    request<{ url: string }>(`/projects/${projectId}/pages/${pageId}/export-clean-page`, {
      method: 'POST',
      body: JSON.stringify(options),
    }),
  exportSvg: (projectId: string, pageId: string, regionId: string, options: ExportOptions) =>
    request<{ export_url: string }>(
      `/projects/${projectId}/pages/${pageId}/regions/${regionId}/export-svg`,
      { method: 'POST', body: JSON.stringify(options) },
    ),
  contactSheetUrl: (projectId: string, pageId: string) =>
    `/api/projects/${projectId}/pages/${pageId}/contact-sheet.png`,

  listProfiles: () => request<Profile[]>('/profiles'),
  saveProfile: (profile: Profile) =>
    request<Profile>('/profiles', { method: 'PUT', body: JSON.stringify(profile) }),

  toolsStatus: () => request<ToolsStatus>('/tools/status'),

  detectAll: (projectId: string, params?: DetectParams) =>
    request<JobStatus>(`/projects/${projectId}/detect-all`, {
      method: 'POST',
      body: JSON.stringify({ params: params ?? null }),
    }),
  exportAll: (projectId: string, options: ExportOptions, outDir?: string) =>
    request<JobStatus>(`/projects/${projectId}/export-all`, {
      method: 'POST',
      body: JSON.stringify({ ...options, out_dir: outDir ?? null }),
    }),
  getJob: (jobId: string) => request<JobStatus>(`/jobs/${jobId}`),

  fsList: (path?: string) =>
    request<FsListing>(`/fs/list${path ? `?path=${encodeURIComponent(path)}` : ''}`),

  samStatus: () => request<SamStatus>('/sam/status'),
  samPredict: (
    projectId: string,
    pageId: string,
    body: { points?: { x: number; y: number; label: number }[]; box?: [number, number, number, number] },
  ) =>
    request<Region>(`/projects/${projectId}/pages/${pageId}/sam/predict`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),
}
