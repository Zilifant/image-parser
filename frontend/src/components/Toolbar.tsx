import { Tool, useEditorStore } from '../state/editorStore'

const TOOLS: { id: Tool; label: string; title: string; sam?: boolean }[] = [
  { id: 'select', label: 'Select', title: 'Select/edit regions (V). Drag background to pan.' },
  { id: 'polygon', label: 'Polygon', title: 'Click vertices, double-click or Enter to close (P)' },
  { id: 'lasso', label: 'Lasso', title: 'Freehand-draw around an element (L)' },
  { id: 'sam-point', label: 'SAM point', title: 'Click an element to segment it with SAM', sam: true },
  { id: 'sam-box', label: 'SAM box', title: 'Drag a box around an element to segment it with SAM', sam: true },
]

export default function Toolbar({
  samAvailable,
  selectedCount,
  flaggedCount,
  onMerge,
  onSplit,
  onDelete,
  onApprove,
  onNextFlagged,
}: {
  samAvailable: boolean
  selectedCount: number
  flaggedCount: number
  onMerge: () => void
  onSplit: () => void
  onDelete: () => void
  onApprove: () => void
  onNextFlagged: () => void
}) {
  const tool = useEditorStore((state) => state.tool)
  const setTool = useEditorStore((state) => state.setTool)

  return (
    <div className="toolbar">
      {TOOLS.filter((entry) => !entry.sam || samAvailable).map((entry) => (
        <button
          key={entry.id}
          className={tool === entry.id ? 'active' : ''}
          title={entry.title}
          onClick={() => setTool(entry.id)}
        >
          {entry.label}
        </button>
      ))}
      <span style={{ width: 12 }} />
      <button disabled={selectedCount < 2} title="Merge selected regions into one" onClick={onMerge}>
        Merge
      </button>
      <button
        disabled={selectedCount !== 1}
        title="Re-detect inside the selected region with tighter settings"
        onClick={onSplit}
      >
        Split
      </button>
      <button disabled={selectedCount === 0} className="danger" title="Delete selected (⌫)" onClick={onDelete}>
        Delete
      </button>
      <span style={{ width: 12 }} />
      <button disabled={selectedCount === 0} title="Mark selected as approved (A)" onClick={onApprove}>
        Approve
      </button>
      <button disabled={flaggedCount === 0} title="Jump to the next flagged region (N)" onClick={onNextFlagged}>
        Next ⚑{flaggedCount > 0 ? ` (${flaggedCount})` : ''}
      </button>
    </div>
  )
}
