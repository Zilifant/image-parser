import { Tool, useEditorStore } from '../state/editorStore'

const TOOLS: { id: Tool; label: string; title: string; sam?: boolean }[] = [
  { id: 'select', label: 'Select', title: 'Select/edit regions (V). Drag background to pan.' },
  { id: 'polygon', label: 'Polygon', title: 'Click vertices, double-click or Enter to close (P)' },
  { id: 'lasso', label: 'Lasso', title: 'Freehand-draw around an element (L)' },
  { id: 'brush', label: 'Brush', title: 'Paint a region with a circular brush (B). [ and ] change size; hold Alt to subtract.' },
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
  const brushSize = useEditorStore((state) => state.brushSize)
  const setBrushSize = useEditorStore((state) => state.setBrushSize)
  const brushMode = useEditorStore((state) => state.brushMode)
  const setBrushMode = useEditorStore((state) => state.setBrushMode)
  const dimBackground = useEditorStore((state) => state.dimBackground)
  const toggleDimBackground = useEditorStore((state) => state.toggleDimBackground)

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
      {tool === 'brush' ? (
        <span className="row brush-controls">
          <button
            className={brushMode === 'add' ? 'active' : ''}
            title="Painting adds to the selected region (or starts a new one)"
            onClick={() => setBrushMode('add')}
          >
            +
          </button>
          <button
            className={brushMode === 'subtract' ? 'active' : ''}
            title="Painting removes area from the selected region (or hold Alt while painting)"
            onClick={() => setBrushMode('subtract')}
          >
            −
          </button>
          <input
            type="range"
            min={4}
            max={150}
            step={2}
            value={brushSize}
            title="Brush size ( [ smaller, ] bigger )"
            style={{ width: 90 }}
            onChange={(event) => setBrushSize(Number(event.target.value))}
          />
          <span className="hint">{brushSize}px</span>
        </span>
      ) : null}
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
      <span style={{ width: 12 }} />
      <button
        className={dimBackground ? 'active' : ''}
        title="Dim everything that is NOT part of a detected region, to make detections stand out (D)"
        onClick={toggleDimBackground}
      >
        Dim
      </button>
    </div>
  )
}
