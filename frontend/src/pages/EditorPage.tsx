import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { api } from '../api/client'
import type { DetectParams, ExportOptions, Page, Point, Region } from '../api/types'
import DetectParamsPanel from '../components/DetectParamsPanel'
import ExportPanel from '../components/ExportPanel'
import RegionList from '../components/RegionList'
import Toolbar from '../components/Toolbar'
import PageCanvas, { CanvasPointerEvent } from '../components/canvas/PageCanvas'
import PolygonTool from '../components/canvas/PolygonTool'
import RegionOverlay from '../components/canvas/RegionOverlay'
import { useEditorStore } from '../state/editorStore'
import { simplifyPolyline } from '../utils/geometry'

export default function EditorPage() {
  const { projectId, pageId } = useParams() as { projectId: string; pageId: string }
  const queryClient = useQueryClient()
  const pageKey = ['page', projectId, pageId]

  const tool = useEditorStore((state) => state.tool)
  const scale = useEditorStore((state) => state.transform.scale)
  const selectedIds = useEditorStore((state) => state.selectedIds)
  const draftPoints = useEditorStore((state) => state.draftPoints)

  const [cursor, setCursor] = useState<Point | null>(null)
  const [exportUrls, setExportUrls] = useState<string[]>([])
  const [actionError, setActionError] = useState<string | null>(null)
  const drawingRef = useRef(false)

  const { data: page } = useQuery({ queryKey: pageKey, queryFn: () => api.getPage(projectId, pageId) })
  const { data: samStatus } = useQuery({ queryKey: ['sam-status'], queryFn: api.samStatus, staleTime: Infinity })

  // Fresh editor state per page; seed the params panel from the page's params.
  useEffect(() => {
    const store = useEditorStore.getState()
    store.reset()
    return () => useEditorStore.getState().reset()
  }, [pageId])
  const seededFor = useRef<string | null>(null)
  useEffect(() => {
    if (page && seededFor.current !== page.id) {
      seededFor.current = page.id
      useEditorStore.getState().setDetectParamsDraft(page.detect_params ?? {})
    }
  }, [page])

  const invalidate = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: pageKey })
    queryClient.invalidateQueries({ queryKey: ['project', projectId] })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [queryClient, projectId, pageId])

  const onError = (error: Error) => setActionError(error.message)

  const detect = useMutation({
    mutationFn: (params: DetectParams) => api.detect(projectId, pageId, params),
    onSuccess: invalidate,
    onError,
  })
  const createRegion = useMutation({
    mutationFn: (polygon: Point[]) => api.createRegion(projectId, pageId, polygon),
    onSuccess: (region) => {
      invalidate()
      useEditorStore.getState().setSelected([region.id])
    },
    onError,
  })
  const patchRegion = useMutation({
    mutationFn: (input: { regionId: string; patch: Partial<Pick<Region, 'polygon' | 'enabled' | 'label'>> }) =>
      api.patchRegion(projectId, pageId, input.regionId, input.patch),
    onMutate: async (input) => {
      await queryClient.cancelQueries({ queryKey: pageKey })
      const previous = queryClient.getQueryData<Page>(pageKey)
      queryClient.setQueryData<Page>(pageKey, (old) =>
        old
          ? {
              ...old,
              regions: old.regions.map((region) =>
                region.id === input.regionId ? { ...region, ...input.patch } : region,
              ),
            }
          : old,
      )
      return { previous }
    },
    onError: (error: Error, _input, context) => {
      if (context?.previous) queryClient.setQueryData(pageKey, context.previous)
      onError(error)
    },
    onSettled: invalidate,
  })
  const deleteRegion = useMutation({
    mutationFn: (regionId: string) => api.deleteRegion(projectId, pageId, regionId),
    onSuccess: invalidate,
    onError,
  })
  const mergeRegions = useMutation({
    mutationFn: (regionIds: string[]) => api.mergeRegions(projectId, pageId, regionIds),
    onSuccess: (region) => {
      invalidate()
      useEditorStore.getState().setSelected([region.id])
    },
    onError,
  })
  const splitRegion = useMutation({
    mutationFn: (regionId: string) => api.splitRegion(projectId, pageId, regionId),
    onSuccess: () => {
      invalidate()
      useEditorStore.getState().setSelected([])
    },
    onError,
  })
  const exportPage = useMutation({
    mutationFn: (input: { options: ExportOptions; regionIds?: string[] }) =>
      api.exportPage(projectId, pageId, input.options, input.regionIds),
    onSuccess: (result) => {
      invalidate()
      const stamp = Date.now()
      setExportUrls(result.exports.map((entry) => `${entry.url}?t=${stamp}`))
    },
    onError,
  })
  const samPredict = useMutation({
    mutationFn: (body: Parameters<typeof api.samPredict>[2]) => api.samPredict(projectId, pageId, body),
    onSuccess: (region) => {
      invalidate()
      useEditorStore.getState().setSelected([region.id])
    },
    onError,
  })

  const finishDraft = useCallback(() => {
    const store = useEditorStore.getState()
    const points =
      store.tool === 'lasso'
        ? simplifyPolyline(store.draftPoints, 1.5)
        : store.draftPoints
    store.clearDraft()
    if (points.length >= 3) createRegion.mutate(points)
  }, [createRegion])

  // Keyboard shortcuts.
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.target instanceof HTMLInputElement || event.target instanceof HTMLSelectElement) return
      const store = useEditorStore.getState()
      if (event.key === 'Escape') {
        store.clearDraft()
        store.setSelected([])
        drawingRef.current = false
      } else if (event.key === 'Enter' && store.tool === 'polygon' && store.draftPoints.length >= 3) {
        finishDraft()
      } else if ((event.key === 'Delete' || event.key === 'Backspace') && store.selectedIds.length > 0) {
        event.preventDefault()
        store.selectedIds.forEach((id) => deleteRegion.mutate(id))
        store.setSelected([])
      } else if (event.key === 'v') store.setTool('select')
      else if (event.key === 'p') store.setTool('polygon')
      else if (event.key === 'l') store.setTool('lasso')
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [deleteRegion, finishDraft])

  const handleCanvasPointer = (event: CanvasPointerEvent) => {
    const store = useEditorStore.getState()
    switch (store.tool) {
      case 'select':
        // A click that no polygon claimed clears the selection.
        if (event.kind === 'down' && !event.defaultPrevented) store.setSelected([])
        break

      case 'polygon':
        if (event.kind === 'down') {
          event.preventDefault()
          const points = store.draftPoints
          const closeEnough =
            points.length >= 3 &&
            Math.hypot(event.point[0] - points[0][0], event.point[1] - points[0][1]) < 8 / scale
          if ((event.detail >= 2 || closeEnough) && points.length >= 3) finishDraft()
          else store.appendDraftPoint(event.point)
        } else if (event.kind === 'move') {
          setCursor(event.point)
        }
        break

      case 'lasso':
        if (event.kind === 'down') {
          event.preventDefault()
          drawingRef.current = true
          store.setDraftPoints([event.point])
        } else if (event.kind === 'move' && drawingRef.current) {
          const last = store.draftPoints[store.draftPoints.length - 1]
          if (!last || Math.hypot(event.point[0] - last[0], event.point[1] - last[1]) > 2 / scale) {
            store.appendDraftPoint(event.point)
          }
        } else if (event.kind === 'up' && drawingRef.current) {
          drawingRef.current = false
          finishDraft()
        }
        break

      case 'sam-point':
        if (event.kind === 'down') {
          event.preventDefault()
          samPredict.mutate({ points: [{ x: event.point[0], y: event.point[1], label: 1 }] })
        }
        break

      case 'sam-box':
        if (event.kind === 'down') {
          event.preventDefault()
          drawingRef.current = true
          store.setDraftPoints([event.point])
        } else if (event.kind === 'move' && drawingRef.current) {
          setCursor(event.point)
        } else if (event.kind === 'up' && drawingRef.current) {
          drawingRef.current = false
          const [start] = store.draftPoints
          store.clearDraft()
          if (start) {
            const x = Math.min(start[0], event.point[0])
            const y = Math.min(start[1], event.point[1])
            const width = Math.abs(event.point[0] - start[0])
            const height = Math.abs(event.point[1] - start[1])
            if (width > 4 && height > 4) samPredict.mutate({ box: [x, y, width, height] })
          }
        }
        break
    }
  }

  if (!page) return <div style={{ padding: 20 }}>Loading…</div>

  return (
    <div className="editor">
      <div className="topbar">
        <Link to={`/projects/${projectId}`}>← {page.name}</Link>
        <Toolbar
          samAvailable={samStatus?.available ?? false}
          selectedCount={selectedIds.length}
          onMerge={() => mergeRegions.mutate(selectedIds)}
          onSplit={() => splitRegion.mutate(selectedIds[0])}
          onDelete={() => {
            selectedIds.forEach((id) => deleteRegion.mutate(id))
            useEditorStore.getState().setSelected([])
          }}
        />
        <span className="spacer" />
        {samPredict.isPending ? <span className="hint">SAM…</span> : null}
        {actionError ? (
          <span className="row">
            <span className="error-text">{actionError}</span>
            <button onClick={() => setActionError(null)}>×</button>
          </span>
        ) : null}
      </div>
      <PageCanvas
        width={page.width}
        height={page.height}
        imageUrl={api.pageImageUrl(projectId, pageId)}
        tool={tool}
        onPointer={handleCanvasPointer}
      >
        <RegionOverlay
          regions={page.regions}
          onPatchPolygon={(regionId, polygon) => patchRegion.mutate({ regionId, patch: { polygon } })}
        />
        <PolygonTool cursor={draftPoints.length > 0 ? cursor : null} />
      </PageCanvas>
      <div className="sidebar">
        <DetectParamsPanel detecting={detect.isPending} onDetect={(params) => detect.mutate(params)} />
        <RegionList
          regions={page.regions}
          onToggleEnabled={(region) =>
            patchRegion.mutate({ regionId: region.id, patch: { enabled: !region.enabled } })
          }
          onRename={(region, label) => patchRegion.mutate({ regionId: region.id, patch: { label } })}
        />
        <ExportPanel
          exporting={exportPage.isPending}
          exportUrls={exportUrls}
          onExport={(options, regionIds) => exportPage.mutate({ options, regionIds })}
        />
      </div>
    </div>
  )
}
