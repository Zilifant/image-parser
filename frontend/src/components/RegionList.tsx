import { useState } from 'react'

import type { Region } from '../api/types'
import { useEditorStore } from '../state/editorStore'

export default function RegionList({
  regions,
  onToggleEnabled,
  onRename,
}: {
  regions: Region[]
  onToggleEnabled: (region: Region) => void
  onRename: (region: Region, label: string) => void
}) {
  const selectedIds = useEditorStore((state) => state.selectedIds)
  const setSelected = useEditorStore((state) => state.setSelected)
  const toggleSelected = useEditorStore((state) => state.toggleSelected)
  const setHovered = useEditorStore((state) => state.setHovered)
  const [editing, setEditing] = useState<string | null>(null)
  const [sort, setSort] = useState<'position' | 'confidence' | 'area'>('position')

  const sorted = [...regions]
  if (sort === 'confidence') sorted.sort((a, b) => a.confidence - b.confidence)
  if (sort === 'area') sorted.sort((a, b) => b.bbox[2] * b.bbox[3] - a.bbox[2] * a.bbox[3])

  return (
    <section style={{ flex: 1 }}>
      <div className="row" style={{ marginBottom: 6 }}>
        <h3 style={{ margin: 0, flex: 1 }}>Regions ({regions.length})</h3>
        <select value={sort} onChange={(event) => setSort(event.target.value as typeof sort)}>
          <option value="position">position</option>
          <option value="confidence">confidence ↑</option>
          <option value="area">area ↓</option>
        </select>
      </div>
      <ul className="region-list">
        {sorted.map((region) => (
          <li
            key={region.id}
            className={`${selectedIds.includes(region.id) ? 'selected' : ''} ${region.enabled ? '' : 'disabled'}`}
            onPointerEnter={() => setHovered(region.id)}
            onPointerLeave={() => setHovered(null)}
          >
            <input
              type="checkbox"
              checked={region.enabled}
              title="Include in export"
              onChange={() => onToggleEnabled(region)}
            />
            {editing === region.id ? (
              <input
                type="text"
                autoFocus
                defaultValue={region.label}
                style={{ flex: 1, padding: '2px 4px' }}
                onBlur={(event) => {
                  onRename(region, event.target.value.trim() || region.label)
                  setEditing(null)
                }}
                onKeyDown={(event) => {
                  if (event.key === 'Enter') (event.target as HTMLInputElement).blur()
                  if (event.key === 'Escape') setEditing(null)
                }}
              />
            ) : (
              <span
                className="label"
                title={`${region.label} (${region.source}) — double-click to rename`}
                onClick={(event) => {
                  if (event.shiftKey) toggleSelected(region.id)
                  else setSelected([region.id])
                }}
                onDoubleClick={() => setEditing(region.id)}
              >
                {region.label}
              </span>
            )}
            <span className="conf">{region.confidence.toFixed(2)}</span>
          </li>
        ))}
      </ul>
    </section>
  )
}
