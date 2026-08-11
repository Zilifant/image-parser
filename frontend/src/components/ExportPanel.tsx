import { useState } from 'react'

import type { ExportOptions } from '../api/types'
import { useEditorStore } from '../state/editorStore'

export default function ExportPanel({
  onExport,
  exporting,
  exportUrls,
}: {
  onExport: (options: ExportOptions, regionIds?: string[]) => void
  exporting: boolean
  exportUrls: string[]
}) {
  const selectedIds = useEditorStore((state) => state.selectedIds)
  const [style, setStyle] = useState<ExportOptions['style']>('ink')
  const [rgb, setRgb] = useState<ExportOptions['rgb']>('original')
  const [padding, setPadding] = useState(4)

  const options: ExportOptions = { style, rgb, padding }

  return (
    <section>
      <h3>Export</h3>
      <div className="field">
        <label>Alpha style</label>
        <select value={style} onChange={(event) => setStyle(event.target.value as ExportOptions['style'])}>
          <option value="ink">ink (soft)</option>
          <option value="binary">binary (hard)</option>
        </select>
      </div>
      <div className="field">
        <label>Color</label>
        <select value={rgb} onChange={(event) => setRgb(event.target.value as ExportOptions['rgb'])}>
          <option value="original">original</option>
          <option value="pure_black">pure black</option>
        </select>
      </div>
      <div className="field">
        <label>Padding</label>
        <input
          type="number"
          min={0}
          max={64}
          value={padding}
          style={{ width: 64 }}
          onChange={(event) => setPadding(Number(event.target.value))}
        />
      </div>
      <div className="row">
        <button
          disabled={exporting || selectedIds.length === 0}
          onClick={() => onExport(options, selectedIds)}
        >
          Export selected ({selectedIds.length})
        </button>
        <button className="primary" disabled={exporting} onClick={() => onExport(options)}>
          {exporting ? 'Exporting…' : 'Export page'}
        </button>
      </div>
      {exportUrls.length > 0 ? (
        <div className="export-strip">
          {exportUrls.map((url) => (
            <a key={url} href={url} target="_blank" rel="noreferrer" title="Open full size">
              <img src={url} alt="" />
            </a>
          ))}
        </div>
      ) : null}
    </section>
  )
}
