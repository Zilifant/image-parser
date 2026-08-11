import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'

import { api } from '../api/client'

export default function FolderPicker({
  onPick,
  onClose,
  pickLabel = 'Use this folder',
}: {
  onPick: (path: string) => void
  onClose: () => void
  pickLabel?: string
}) {
  const [path, setPath] = useState<string | undefined>(undefined)
  const [typed, setTyped] = useState('')

  const { data: listing, error } = useQuery({
    queryKey: ['fs', path ?? '~'],
    queryFn: () => api.fsList(path),
  })

  const imageCount = listing?.entries.filter((entry) => entry.is_image).length ?? 0

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(event) => event.stopPropagation()}>
        <div className="row">
          <input
            type="text"
            style={{ flex: 1 }}
            placeholder="/absolute/path — or browse below"
            value={typed}
            onChange={(event) => setTyped(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && typed.trim()) setPath(typed.trim())
            }}
          />
          <button onClick={() => typed.trim() && setPath(typed.trim())}>Go</button>
        </div>
        <div className="path">{listing?.path ?? '…'}</div>
        {error ? <div className="error-text">{(error as Error).message}</div> : null}
        <div className="fs-list">
          {listing?.parent ? (
            <button onClick={() => setPath(listing.parent!)}>
              <span className="dim">⬑ ..</span>
            </button>
          ) : null}
          {listing?.entries.map((entry) =>
            entry.is_dir ? (
              <button key={entry.path} onClick={() => setPath(entry.path)}>
                📁 {entry.name}
              </button>
            ) : (
              <button key={entry.path} disabled>
                <span className="dim">🖼 {entry.name}</span>
              </button>
            ),
          )}
        </div>
        <div className="row">
          <span className="hint">{imageCount} image{imageCount === 1 ? '' : 's'} here</span>
          <span className="spacer" />
          <button onClick={onClose}>Cancel</button>
          <button className="primary" disabled={!listing} onClick={() => listing && onPick(listing.path)}>
            {pickLabel}
          </button>
        </div>
      </div>
    </div>
  )
}
