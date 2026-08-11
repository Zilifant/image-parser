import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '../api/client'
import type { DetectParams, Profile } from '../api/types'
import { useEditorStore } from '../state/editorStore'

function Tip({ text }: { text: string }) {
  return (
    <span className="tip" title={text}>
      ⓘ
    </span>
  )
}

export default function DetectParamsPanel({
  onDetect,
  detecting,
}: {
  onDetect: (params: DetectParams) => void
  detecting: boolean
}) {
  const queryClient = useQueryClient()
  const params = useEditorStore((state) => state.detectParamsDraft)
  const setParams = useEditorStore((state) => state.setDetectParamsDraft)

  const { data: profiles } = useQuery({ queryKey: ['profiles'], queryFn: api.listProfiles })
  const saveProfile = useMutation({
    mutationFn: (profile: Profile) => api.saveProfile(profile),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['profiles'] }),
  })

  const applyProfile = (name: string) => {
    const profile = profiles?.find((entry) => entry.name === name)
    if (!profile) return
    setParams(profile.detect)
    useEditorStore.getState().setExportOptions(profile.export)
  }

  const merge = params.merge_radius ?? 0
  const minArea = params.min_area_frac ?? 0.0002
  const blockSize = params.block_size ?? 51
  const c = params.c ?? 12

  return (
    <section>
      <h3>Auto-detect</h3>
      <div className="field">
        <label>
          Profile
          <Tip text="Preset bundles of detection + export settings tuned for different kinds of scans (clean photocopies, yellowed magazines, dense collages…). Applying one fills in the sliders below; Save… stores your current settings as a new profile." />
        </label>
        <select defaultValue="" onChange={(event) => applyProfile(event.target.value)}>
          <option value="" disabled>
            apply a profile…
          </option>
          {profiles?.map((profile) => (
            <option key={profile.name} value={profile.name}>
              {profile.name}
            </option>
          ))}
        </select>
        <button
          title="Save current detect + export settings as a named profile"
          onClick={() => {
            const name = prompt('Profile name?')?.trim()
            if (name)
              saveProfile.mutate({
                name,
                builtin: false,
                detect: params,
                export: useEditorStore.getState().exportOptions,
              })
          }}
        >
          Save…
        </button>
      </div>
      <div className="field">
        <label>
          Merge radius
          <Tip text="How close two bits of ink can be and still count as one element. Bigger groups nearby pieces together (fewer, larger regions); smaller keeps them separate (more, smaller regions). 'auto' picks a sensible value from the image size." />
        </label>
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
        <label>
          Min size
          <Tip text="Ignore anything smaller than this fraction of the page. Filters out dust, specks, and stray marks — raise it if you're getting lots of tiny junk regions, lower it if small real elements are being missed." />
        </label>
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
        <label>
          Threshold block
          <Tip text="Size of the neighborhood each pixel is compared against when deciding ink vs. paper. Bigger copes with gradual lighting/stain changes across the page; smaller reacts to fine local detail." />
        </label>
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
        <label>
          Threshold C
          <Tip text="How strict the ink test is. Higher = pickier (faint marks are treated as paper); lower = more sensitive (picks up fainter marks, but also more noise)." />
        </label>
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
        <label>
          Mode
          <Tip text="adaptive: compares each pixel to its local neighborhood — best for uneven, stained, or yellowed paper. otsu: one global cutoff for the whole page — best for clean, evenly-lit scans." />
        </label>
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
