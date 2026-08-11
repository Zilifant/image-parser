import { create } from 'zustand'

import type { DetectParams, ExportOptions, Point } from '../api/types'

export type Tool = 'select' | 'polygon' | 'lasso' | 'sam-point' | 'sam-box'

interface Transform {
  x: number
  y: number
  scale: number
}

interface EditorState {
  tool: Tool
  transform: Transform
  selectedIds: string[]
  hoveredId: string | null
  draftPoints: Point[]
  detectParamsDraft: DetectParams
  exportOptions: ExportOptions
  setTool: (tool: Tool) => void
  setTransform: (transform: Transform) => void
  setSelected: (ids: string[]) => void
  toggleSelected: (id: string) => void
  setHovered: (id: string | null) => void
  setDraftPoints: (points: Point[]) => void
  appendDraftPoint: (point: Point) => void
  clearDraft: () => void
  setDetectParamsDraft: (params: DetectParams) => void
  setExportOptions: (options: ExportOptions) => void
  reset: () => void
}

const DEFAULT_EXPORT: ExportOptions = { style: 'ink', rgb: 'pure_white', padding: 4 }

export const useEditorStore = create<EditorState>((set) => ({
  tool: 'select',
  transform: { x: 0, y: 0, scale: 1 },
  selectedIds: [],
  hoveredId: null,
  draftPoints: [],
  detectParamsDraft: {},
  exportOptions: DEFAULT_EXPORT,
  setTool: (tool) => set({ tool, draftPoints: [] }),
  setTransform: (transform) => set({ transform }),
  setSelected: (selectedIds) => set({ selectedIds }),
  toggleSelected: (id) =>
    set((state) => ({
      selectedIds: state.selectedIds.includes(id)
        ? state.selectedIds.filter((existing) => existing !== id)
        : [...state.selectedIds, id],
    })),
  setHovered: (hoveredId) => set({ hoveredId }),
  setDraftPoints: (draftPoints) => set({ draftPoints }),
  appendDraftPoint: (point) => set((state) => ({ draftPoints: [...state.draftPoints, point] })),
  clearDraft: () => set({ draftPoints: [] }),
  setDetectParamsDraft: (detectParamsDraft) => set({ detectParamsDraft }),
  setExportOptions: (exportOptions) => set({ exportOptions }),
  reset: () =>
    set({ tool: 'select', transform: { x: 0, y: 0, scale: 1 }, selectedIds: [], hoveredId: null, draftPoints: [] }),
}))
