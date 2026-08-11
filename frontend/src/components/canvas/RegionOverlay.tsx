import { useState } from 'react'

import type { Point, Region } from '../../api/types'
import { useEditorStore } from '../../state/editorStore'
import { polygonToSvgPoints } from '../../utils/geometry'

const SOURCE_COLORS: Record<Region['source'], string> = {
  auto: '#4d9fff',
  manual: '#7bc96f',
  sam: '#c678dd',
  merge: '#e5c07b',
}

export default function RegionOverlay({
  regions,
  onPatchPolygon,
}: {
  regions: Region[]
  onPatchPolygon: (regionId: string, polygon: Point[]) => void
}) {
  const tool = useEditorStore((state) => state.tool)
  const scale = useEditorStore((state) => state.transform.scale)
  const selectedIds = useEditorStore((state) => state.selectedIds)
  const hoveredId = useEditorStore((state) => state.hoveredId)
  const setSelected = useEditorStore((state) => state.setSelected)
  const toggleSelected = useEditorStore((state) => state.toggleSelected)
  const setHovered = useEditorStore((state) => state.setHovered)

  // Local override while a vertex is being dragged; committed on pointer-up.
  const [drag, setDrag] = useState<{ regionId: string; index: number; polygon: Point[] } | null>(null)

  const selectable = tool === 'select'
  const singleSelected = selectedIds.length === 1 ? selectedIds[0] : null
  const handleRadius = 5 / scale

  return (
    <>
      {regions.map((region) => {
        const polygon = drag?.regionId === region.id ? drag.polygon : region.polygon
        const color = SOURCE_COLORS[region.source]
        const isSelected = selectedIds.includes(region.id)
        const isHovered = hoveredId === region.id
        return (
          <polygon
            key={region.id}
            points={polygonToSvgPoints(polygon)}
            fill={region.enabled ? color : '#888888'}
            fillOpacity={isSelected ? 0.28 : isHovered ? 0.22 : region.enabled ? 0.12 : 0.05}
            stroke={isSelected ? '#ffb454' : region.enabled ? color : '#888888'}
            strokeWidth={isSelected ? 2.5 : 1.5}
            vectorEffect="non-scaling-stroke"
            style={{ pointerEvents: selectable ? 'auto' : 'none', cursor: 'pointer' }}
            onPointerDown={(event) => {
              if (!selectable || event.button !== 0) return
              event.preventDefault() // keep the canvas from panning
              if (event.shiftKey) toggleSelected(region.id)
              else setSelected([region.id])
            }}
            onPointerEnter={() => setHovered(region.id)}
            onPointerLeave={() => setHovered(null)}
          />
        )
      })}
      {selectable && singleSelected
        ? regions
            .filter((region) => region.id === singleSelected)
            .map((region) => {
              const polygon = drag?.regionId === region.id ? drag.polygon : region.polygon
              return polygon.map((point, index) => (
                <circle
                  key={`${region.id}-${index}`}
                  cx={point[0]}
                  cy={point[1]}
                  r={handleRadius}
                  fill="#ffb454"
                  stroke="#1f232b"
                  strokeWidth={1.5 / scale}
                  style={{ cursor: 'move' }}
                  onPointerDown={(event) => {
                    if (event.button !== 0) return
                    event.stopPropagation()
                    event.preventDefault()
                    event.currentTarget.setPointerCapture(event.pointerId)
                    setDrag({ regionId: region.id, index, polygon: [...region.polygon] })
                  }}
                  onPointerMove={(event) => {
                    if (!drag || drag.index !== index) return
                    const svg = event.currentTarget.ownerSVGElement!
                    const rect = svg.getBoundingClientRect()
                    const x = ((event.clientX - rect.left) / rect.width) * svg.viewBox.baseVal.width
                    const y = ((event.clientY - rect.top) / rect.height) * svg.viewBox.baseVal.height
                    const polygon = [...drag.polygon]
                    polygon[index] = [x, y]
                    setDrag({ ...drag, polygon })
                  }}
                  onPointerUp={(event) => {
                    if (!drag || drag.index !== index) return
                    event.currentTarget.releasePointerCapture(event.pointerId)
                    onPatchPolygon(drag.regionId, drag.polygon)
                    setDrag(null)
                  }}
                />
              ))
            })
        : null}
    </>
  )
}
