import type { Point } from '../../api/types'
import { useEditorStore } from '../../state/editorStore'
import { polygonToSvgPoints } from '../../utils/geometry'

/** Renders the in-progress polygon/lasso/SAM-box draft. Input handling lives
 * in EditorPage via PageCanvas's pointer callback. */
export default function PolygonTool({ cursor }: { cursor: Point | null }) {
  const tool = useEditorStore((state) => state.tool)
  const scale = useEditorStore((state) => state.transform.scale)
  const draftPoints = useEditorStore((state) => state.draftPoints)

  if (draftPoints.length === 0) return null

  if (tool === 'sam-box') {
    const [start] = draftPoints
    const end = cursor ?? draftPoints[draftPoints.length - 1]
    const x = Math.min(start[0], end[0])
    const y = Math.min(start[1], end[1])
    return (
      <rect
        x={x}
        y={y}
        width={Math.abs(end[0] - start[0])}
        height={Math.abs(end[1] - start[1])}
        fill="#c678dd"
        fillOpacity={0.15}
        stroke="#c678dd"
        strokeWidth={2}
        strokeDasharray="6 4"
        vectorEffect="non-scaling-stroke"
        pointerEvents="none"
      />
    )
  }

  const preview = tool === 'polygon' && cursor ? [...draftPoints, cursor] : draftPoints
  return (
    <>
      <polyline
        points={polygonToSvgPoints(preview)}
        fill="#7bc96f"
        fillOpacity={0.12}
        stroke="#7bc96f"
        strokeWidth={2}
        strokeDasharray={tool === 'polygon' ? '6 4' : undefined}
        vectorEffect="non-scaling-stroke"
        pointerEvents="none"
      />
      {tool === 'polygon'
        ? draftPoints.map((point, index) => (
            <circle
              key={index}
              cx={point[0]}
              cy={point[1]}
              r={(index === 0 ? 6 : 4) / scale}
              fill={index === 0 ? '#ffb454' : '#7bc96f'}
              pointerEvents="none"
            />
          ))
        : null}
    </>
  )
}
