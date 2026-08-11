import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { api } from '../api/client'
import FolderPicker from '../components/FolderPicker'
import JobProgress from '../components/JobProgress'

export default function LibraryPage() {
  const { projectId } = useParams()
  return projectId ? <ProjectView projectId={projectId} /> : <ProjectList />
}

function ProjectList() {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [name, setName] = useState('')

  const { data: projects } = useQuery({ queryKey: ['projects'], queryFn: api.listProjects })

  const create = useMutation({
    mutationFn: api.createProject,
    onSuccess: (project) => {
      queryClient.invalidateQueries({ queryKey: ['projects'] })
      navigate(`/projects/${project.id}`)
    },
  })

  return (
    <div>
      <div className="topbar">
        <h1>image-parser</h1>
      </div>
      <div className="library">
        <div className="row">
          <input
            type="text"
            placeholder="New project name"
            value={name}
            onChange={(event) => setName(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && name.trim()) create.mutate(name.trim())
            }}
          />
          <button className="primary" disabled={!name.trim()} onClick={() => create.mutate(name.trim())}>
            Create project
          </button>
        </div>
        <h2>Projects</h2>
        <div className="card-grid">
          {projects?.map((project) => (
            <div key={project.id} className="card" onClick={() => navigate(`/projects/${project.id}`)}>
              <div style={{ fontWeight: 600 }}>{project.name}</div>
              <div className="meta">
                <span>{project.pages.length} page{project.pages.length === 1 ? '' : 's'}</span>
              </div>
            </div>
          ))}
          {projects && projects.length === 0 ? (
            <span className="hint">No projects yet — create one to get started.</span>
          ) : null}
        </div>
      </div>
    </div>
  )
}

function ProjectView({ projectId }: { projectId: string }) {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const fileInput = useRef<HTMLInputElement>(null)
  const [pickerMode, setPickerMode] = useState<'ingest' | 'export' | null>(null)
  const [job, setJob] = useState<{ id: string; label: string } | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)

  const { data: project } = useQuery({
    queryKey: ['project', projectId],
    queryFn: () => api.getProject(projectId),
  })

  const invalidate = useCallback(
    () => queryClient.invalidateQueries({ queryKey: ['project', projectId] }),
    [queryClient, projectId],
  )

  const onError = (error: Error) => setActionError(error.message)

  const upload = useMutation({
    mutationFn: (files: File[]) => api.uploadPages(projectId, files),
    onSuccess: invalidate,
    onError,
  })
  const ingestDir = useMutation({
    mutationFn: (dir: string) => api.pagesFromDir(projectId, dir),
    onSuccess: invalidate,
    onError,
  })
  const detectAll = useMutation({
    mutationFn: () => api.detectAll(projectId),
    onSuccess: (started) => setJob({ id: started.id, label: 'Detecting' }),
    onError,
  })
  const exportAll = useMutation({
    mutationFn: (outDir?: string) => api.exportAll(projectId, { style: 'ink', rgb: 'original', padding: 4 }, outDir),
    onSuccess: (started) => setJob({ id: started.id, label: 'Exporting' }),
    onError,
  })
  const deletePage = useMutation({
    mutationFn: (pageId: string) => api.deletePage(projectId, pageId),
    onSuccess: invalidate,
    onError,
  })

  const jobDone = useCallback(() => {
    invalidate()
  }, [invalidate])

  return (
    <div>
      <div className="topbar">
        <Link to="/">image-parser</Link>
        <h1>{project?.name ?? '…'}</h1>
        <span className="spacer" />
        {job ? <JobProgress key={job.id} jobId={job.id} label={job.label} onDone={jobDone} /> : null}
      </div>
      <div className="library">
        {actionError ? (
          <div className="row" style={{ marginBottom: 10 }}>
            <span className="error-text">{actionError}</span>
            <button onClick={() => setActionError(null)}>×</button>
          </div>
        ) : null}
        <div className="row">
          <input
            ref={fileInput}
            type="file"
            accept="image/*"
            multiple
            style={{ display: 'none' }}
            onChange={(event) => {
              const files = Array.from(event.target.files ?? [])
              if (files.length) upload.mutate(files)
              event.target.value = ''
            }}
          />
          <button onClick={() => fileInput.current?.click()}>Add images…</button>
          <button onClick={() => setPickerMode('ingest')}>Add folder…</button>
          <span className="spacer" />
          <button disabled={!project?.pages.length || detectAll.isPending} onClick={() => detectAll.mutate()}>
            Detect all
          </button>
          <button
            disabled={!project?.pages.some((page) => page.region_count > 0)}
            onClick={() => setPickerMode('export')}
          >
            Export all…
          </button>
        </div>
        <h2>Pages</h2>
        <div className="card-grid">
          {project?.pages.map((page) => (
            <div key={page.id} className="card" onClick={() => navigate(`/projects/${projectId}/pages/${page.id}`)}>
              <img className="thumb" src={api.pageThumbUrl(projectId, page.id)} alt={page.name} />
              <div style={{ marginTop: 8, fontWeight: 600, fontSize: 13 }}>{page.name}</div>
              <div className="meta">
                <span>
                  {page.region_count > 0 ? (
                    <span className={`badge ${page.export_count > 0 ? 'ok' : ''}`}>
                      {page.region_count} regions{page.export_count > 0 ? ` · ${page.export_count} exported` : ''}
                    </span>
                  ) : (
                    <span className="badge">not detected</span>
                  )}
                </span>
                <button
                  className="danger"
                  style={{ padding: '2px 8px' }}
                  onClick={(event) => {
                    event.stopPropagation()
                    if (confirm(`Delete page "${page.name}"?`)) deletePage.mutate(page.id)
                  }}
                >
                  ×
                </button>
              </div>
            </div>
          ))}
          {project && project.pages.length === 0 ? (
            <span className="hint">No pages yet — add scans via upload or a local folder.</span>
          ) : null}
        </div>
      </div>
      {pickerMode ? (
        <FolderPicker
          pickLabel={pickerMode === 'ingest' ? 'Ingest images from this folder' : 'Export all here'}
          onClose={() => setPickerMode(null)}
          onPick={(path) => {
            if (pickerMode === 'ingest') ingestDir.mutate(path)
            else exportAll.mutate(path)
            setPickerMode(null)
          }}
        />
      ) : null}
    </div>
  )
}
