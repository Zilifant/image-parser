import { ReactNode, useEffect, useLayoutEffect, useRef, useState } from 'react'

import type { Point } from '../../api/types'
import { Tool, useEditorStore } from '../../state/editorStore'

export interface CanvasPointerEvent {
  kind: 'down' | 'move' | 'up'
  point: Point
  shiftKey: boolean
  altKey: boolean
  detail: number
  defaultPrevented: boolean
  preventDefault: () => void
}

/**
 * Zoom/pan viewport. The image and the SVG overlay share one transformed
 * container, so all children work in image-pixel coordinates.
 *
 * Panning: drag in select mode (unless a child claimed the event), or
 * space-drag / middle-drag in any mode. Wheel zooms toward the cursor.
 */
export default function PageCanvas({
  width,
  height,
  imageUrl,
  tool,
  onPointer,
  children,
}: {
  width: number
  height: number
  imageUrl: string
  tool: Tool
  onPointer: (event: CanvasPointerEvent) => void
  children: ReactNode
}) {
  const wrapRef = useRef<HTMLDivElement>(null)
  const transform = useEditorStore((state) => state.transform)
  const setTransform = useEditorStore((state) => state.setTransform)
  const [spaceHeld, setSpaceHeld] = useState(false)
  const panRef = useRef<{ startX: number; startY: number; originX: number; originY: number } | null>(null)

  // Fit the page into the viewport on first layout.
  const fittedFor = useRef<string | null>(null)
  useLayoutEffect(() => {
    const wrap = wrapRef.current
    if (!wrap || fittedFor.current === imageUrl) return
    fittedFor.current = imageUrl
    const scale = Math.min((wrap.clientWidth - 40) / width, (wrap.clientHeight - 40) / height, 4)
    setTransform({
      x: (wrap.clientWidth - width * scale) / 2,
      y: (wrap.clientHeight - height * scale) / 2,
      scale,
    })
  }, [imageUrl, width, height, setTransform])

  // Wheel zoom needs a non-passive listener so preventDefault works.
  useEffect(() => {
    const wrap = wrapRef.current
    if (!wrap) return
    const onWheel = (event: WheelEvent) => {
      event.preventDefault()
      const { transform: current } = useEditorStore.getState()
      const rect = wrap.getBoundingClientRect()
      const cursorX = event.clientX - rect.left
      const cursorY = event.clientY - rect.top
      const nextScale = Math.min(8, Math.max(0.05, current.scale * Math.exp(-event.deltaY * 0.0015)))
      const ratio = nextScale / current.scale
      useEditorStore.getState().setTransform({
        x: cursorX - (cursorX - current.x) * ratio,
        y: cursorY - (cursorY - current.y) * ratio,
        scale: nextScale,
      })
    }
    wrap.addEventListener('wheel', onWheel, { passive: false })
    return () => wrap.removeEventListener('wheel', onWheel)
  }, [])

  useEffect(() => {
    const down = (event: KeyboardEvent) => {
      if (event.code === 'Space' && !(event.target instanceof HTMLInputElement)) setSpaceHeld(true)
    }
    const up = (event: KeyboardEvent) => {
      if (event.code === 'Space') setSpaceHeld(false)
    }
    window.addEventListener('keydown', down)
    window.addEventListener('keyup', up)
    return () => {
      window.removeEventListener('keydown', down)
      window.removeEventListener('keyup', up)
    }
  }, [])

  const toImage = (clientX: number, clientY: number): Point => {
    const rect = wrapRef.current!.getBoundingClientRect()
    return [
      (clientX - rect.left - transform.x) / transform.scale,
      (clientY - rect.top - transform.y) / transform.scale,
    ]
  }

  const emit = (kind: CanvasPointerEvent['kind'], event: React.PointerEvent): boolean => {
    let prevented = false
    onPointer({
      kind,
      point: toImage(event.clientX, event.clientY),
      shiftKey: event.shiftKey,
      altKey: event.altKey,
      detail: event.detail,
      defaultPrevented: event.defaultPrevented,
      preventDefault: () => {
        prevented = true
      },
    })
    return prevented
  }

  const handlePointerDown = (event: React.PointerEvent) => {
    const wantsPan = spaceHeld || event.button === 1
    if (!wantsPan) {
      const claimed = emit('down', event)
      if (claimed || tool !== 'select' || event.defaultPrevented) return
    }
    if (event.button !== 0 && event.button !== 1) return
    panRef.current = {
      startX: event.clientX,
      startY: event.clientY,
      originX: transform.x,
      originY: transform.y,
    }
    wrapRef.current?.setPointerCapture(event.pointerId)
  }

  const handlePointerMove = (event: React.PointerEvent) => {
    if (panRef.current) {
      const pan = panRef.current
      setTransform({
        x: pan.originX + event.clientX - pan.startX,
        y: pan.originY + event.clientY - pan.startY,
        scale: transform.scale,
      })
      return
    }
    emit('move', event)
  }

  const handlePointerUp = (event: React.PointerEvent) => {
    if (panRef.current) {
      panRef.current = null
      wrapRef.current?.releasePointerCapture(event.pointerId)
      return
    }
    emit('up', event)
  }

  return (
    <div
      ref={wrapRef}
      className={`canvas-wrap tool-${tool}${panRef.current || spaceHeld ? ' panning' : ''}`}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
    >
      <div
        className="canvas-inner"
        style={{
          width,
          height,
          transform: `translate(${transform.x}px, ${transform.y}px) scale(${transform.scale})`,
        }}
      >
        <img src={imageUrl} width={width} height={height} alt="" draggable={false} />
        <svg
          viewBox={`0 0 ${width} ${height}`}
          width={width}
          height={height}
          style={spaceHeld ? { pointerEvents: 'none' } : undefined}
        >
          {children}
        </svg>
      </div>
    </div>
  )
}
