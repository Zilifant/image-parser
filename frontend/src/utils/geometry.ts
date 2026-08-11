import type { Point } from '../api/types'

function perpendicularDistance(point: Point, a: Point, b: Point): number {
  const dx = b[0] - a[0]
  const dy = b[1] - a[1]
  const lengthSquared = dx * dx + dy * dy
  if (lengthSquared === 0) return Math.hypot(point[0] - a[0], point[1] - a[1])
  const t = Math.max(0, Math.min(1, ((point[0] - a[0]) * dx + (point[1] - a[1]) * dy) / lengthSquared))
  return Math.hypot(point[0] - (a[0] + t * dx), point[1] - (a[1] + t * dy))
}

/** Ramer–Douglas–Peucker simplification, used to slim down freehand lassos. */
export function simplifyPolyline(points: Point[], epsilon: number): Point[] {
  if (points.length < 3) return points
  let maxDistance = 0
  let index = 0
  const last = points.length - 1
  for (let i = 1; i < last; i++) {
    const distance = perpendicularDistance(points[i], points[0], points[last])
    if (distance > maxDistance) {
      maxDistance = distance
      index = i
    }
  }
  if (maxDistance > epsilon) {
    const left = simplifyPolyline(points.slice(0, index + 1), epsilon)
    const right = simplifyPolyline(points.slice(index), epsilon)
    return [...left.slice(0, -1), ...right]
  }
  return [points[0], points[last]]
}

export function polygonToSvgPoints(points: Point[]): string {
  return points.map(([x, y]) => `${x},${y}`).join(' ')
}
