import type { ExportOptions, RegionExport } from '../api/types'
import { useEditorStore } from '../state/editorStore'

export default function ExportPanel({
  onExport,
  onExportCleanPage,
  onExportSvg,
  exporting,
  exports,
  cleanPageUrl,
  contactSheetUrl,
  hasExports,
  potraceAvailable,
}: {
  onExport: (options: ExportOptions, regionIds?: string[]) => void
  onExportCleanPage: (options: ExportOptions) => void
  onExportSvg: (regionId: string, options: ExportOptions) => void
  exporting: boolean
  exports: RegionExport[]
  cleanPageUrl: string | null
  contactSheetUrl: string
  hasExports: boolean
  potraceAvailable: boolean
}) {
  const selectedIds = useEditorStore((state) => state.selectedIds)
  const options = useEditorStore((state) => state.exportOptions)
  const setOptions = useEditorStore((state) => state.setExportOptions)

  return (
    <section>
      <h3>Export</h3>
      <div className="field">
        <label>Alpha style</label>
        <select
          value={options.style}
          onChange={(event) => setOptions({ ...options, style: event.target.value as ExportOptions['style'] })}
        >
          <option value="ink">ink (soft)</option>
          <option value="binary">binary (hard)</option>
        </select>
      </div>
      <div className="field">
        <label>Color</label>
        <select
          value={options.rgb}
          onChange={(event) => setOptions({ ...options, rgb: event.target.value as ExportOptions['rgb'] })}
        >
          <option value="pure_white">pure white</option>
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
          value={options.padding}
          style={{ width: 64 }}
          onChange={(event) => setOptions({ ...options, padding: Number(event.target.value) })}
        />
      </div>
      <div className="row">
        <button disabled={exporting || selectedIds.length === 0} onClick={() => onExport(options, selectedIds)}>
          Export selected ({selectedIds.length})
        </button>
        <button className="primary" disabled={exporting} onClick={() => onExport(options)}>
          {exporting ? 'Exporting…' : 'Export page'}
        </button>
      </div>
      <div className="row" style={{ marginTop: 8 }}>
        <button title="Whole page cleaned: all ink kept, background transparent" onClick={() => onExportCleanPage(options)}>
          Clean full page
        </button>
        {potraceAvailable ? (
          <button
            disabled={selectedIds.length !== 1}
            title="Vectorize the selected region with potrace"
            onClick={() => onExportSvg(selectedIds[0], options)}
          >
            Export SVG
          </button>
        ) : null}
        {hasExports ? (
          <a href={contactSheetUrl} target="_blank" rel="noreferrer" style={{ color: 'var(--accent)', fontSize: 13 }}>
            Contact sheet ↗
          </a>
        ) : null}
      </div>
      {cleanPageUrl ? (
        <div className="hint" style={{ marginTop: 6 }}>
          Cleaned page:{' '}
          <a href={cleanPageUrl} target="_blank" rel="noreferrer" style={{ color: 'var(--accent)' }}>
            open ↗
          </a>
        </div>
      ) : null}
      {exports.length > 0 ? (
        <div className="export-strip">
          {exports.map((entry) => (
            <a
              key={entry.url}
              href={entry.url}
              target="_blank"
              rel="noreferrer"
              title={entry.qc_issues.length ? `QC: ${entry.qc_issues.join(', ')}` : 'Open full size'}
            >
              <img src={entry.url} alt="" style={entry.qc_issues.length ? { borderColor: 'var(--danger)', borderWidth: 2 } : undefined} />
            </a>
          ))}
        </div>
      ) : null}
    </section>
  )
}
