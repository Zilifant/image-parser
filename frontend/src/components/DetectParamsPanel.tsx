import type { DetectParams } from '../api/types'
import { useEditorStore } from '../state/editorStore'

export default function DetectParamsPanel({
  onDetect,
  detecting,
}: {
  onDetect: (params: DetectParams) => void
  detecting: boolean
}) {
  const params = useEditorStore((state) => state.detectParamsDraft)
  const setParams = useEditorStore((state) => state.setDetectParamsDraft)

  const merge = params.merge_radius ?? 0
  const minArea = params.min_area_frac ?? 0.0002
  const blockSize = params.block_size ?? 51
  const c = params.c ?? 12

  return (
    <section>
      <h3>Auto-detect</h3>
      <div className="field">
        <label>Merge radius</label>
        <input
          type="range"
          min={0}
          max={40}
          value={merge}
          onChange={(event) => setParams({ ...params, merge_radius: Number(event.target.value) })}
        />
        <span className="value">{merge === 0 ? 'auto' : `${merge}px`}</span>
      </div>
      <div className="field">
        <label>Min size</label>
        <input
          type="range"
          min={-45}
          max={-25}
          value={Math.round(Math.log10(minArea) * 10)}
          onChange={(event) =>
            setParams({ ...params, min_area_frac: Number(Math.pow(10, Number(event.target.value) / 10).toPrecision(2)) })
          }
        />
        <span className="value">{(minArea * 100).toPrecision(2)}%</span>
      </div>
      <div className="field">
        <label>Threshold block</label>
        <input
          type="range"
          min={15}
          max={151}
          step={2}
          value={blockSize}
          onChange={(event) => setParams({ ...params, block_size: Number(event.target.value) })}
        />
        <span className="value">{blockSize}</span>
      </div>
      <div className="field">
        <label>Threshold C</label>
        <input
          type="range"
          min={0}
          max={30}
          value={c}
          onChange={(event) => setParams({ ...params, c: Number(event.target.value) })}
        />
        <span className="value">{c}</span>
      </div>
      <div className="field">
        <label>Mode</label>
        <select
          value={params.mode ?? 'adaptive'}
          onChange={(event) => setParams({ ...params, mode: event.target.value as 'adaptive' | 'otsu' })}
        >
          <option value="adaptive">adaptive</option>
          <option value="otsu">otsu</option>
        </select>
      </div>
      <button className="primary" style={{ width: '100%' }} disabled={detecting} onClick={() => onDetect(params)}>
        {detecting ? 'Detecting…' : 'Detect elements'}
      </button>
      <div className="hint" style={{ marginTop: 6 }}>
        Re-running replaces auto-detected regions; manual and SAM regions are kept.
      </div>
    </section>
  )
}
