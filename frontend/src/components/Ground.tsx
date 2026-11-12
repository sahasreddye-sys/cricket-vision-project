// The cricket ground seen from above. Angle convention matches pitchvision/stats.py:
// 0 degrees = straight back past the bowler (up the screen); angles increase clockwise,
// toward the OFF side (right of the screen for a handedness-normalised batter).
import { useRef, useState } from 'react'
import { words } from '../lib/format'

export interface Shot { angle: number; runs: number; zone?: string; shot_type?: string | null }
export interface Fielder { name: string; angle: number; distance: number }
export interface Zone { zone: string; runs: number; shots: number; pct_of_runs: number; fours: number; sixes: number }

const S = 480
const C = S / 2
const R = 196
const ZONES = ['long_off', 'cover', 'point', 'third_man', 'fine_leg', 'square_leg', 'midwicket', 'long_on']

const polar = (angle: number, dist: number) => {
  const a = (angle * Math.PI) / 180
  return { x: C + Math.sin(a) * dist * R, y: C - Math.cos(a) * dist * R }
}
const reach = (runs: number) => (runs >= 4 ? 1 : runs === 3 ? 0.78 : runs === 2 ? 0.62 : runs === 1 ? 0.42 : 0.2)
const shotColour = (runs: number) => (runs === 6 ? '#f2c230' : runs === 4 ? '#f4f6f1' : runs === 0 ? 'rgba(244,246,241,0.25)' : 'rgba(244,246,241,0.6)')

export function Ground({ shots, zones, fielders, onMoveFielder, onPick, picked, highlightZone, onHoverZone, className }: {
  shots?: Shot[]; zones?: Zone[]; fielders?: Fielder[]
  onMoveFielder?: (index: number, angle: number, distance: number) => void
  onPick?: (angle: number) => void; picked?: number | null
  highlightZone?: string | null; onHoverZone?: (z: string | null) => void; className?: string
}) {
  const ref = useRef<SVGSVGElement>(null)
  const [drag, setDrag] = useState<number | null>(null)

  const toPolar = (e: { clientX: number; clientY: number }) => {
    const r = ref.current!.getBoundingClientRect()
    const x = ((e.clientX - r.left) / r.width) * S - C
    const y = ((e.clientY - r.top) / r.height) * S - C
    const angle = ((Math.atan2(x, -y) * 180) / Math.PI + 360) % 360
    return { angle: Math.round(angle), distance: Math.min(1, Math.max(0.08, Math.hypot(x, y) / R)) }
  }
  const maxRuns = Math.max(1, ...(zones ?? []).map((z) => z.runs))

  return (
    <svg ref={ref} viewBox={`0 0 ${S} ${S}`} className={className ?? 'w-full max-w-[440px]'} role="img" aria-label="Cricket ground seen from above"
      style={{ touchAction: 'none', cursor: onPick ? 'crosshair' : 'default' }}
      onPointerMove={(e) => { if (drag !== null && onMoveFielder) { const p = toPolar(e); onMoveFielder(drag, p.angle, Math.round(p.distance * 100) / 100) } }}
      onPointerUp={() => setDrag(null)} onPointerLeave={() => setDrag(null)}
      onClick={(e) => { if (onPick && drag === null) onPick(toPolar(e).angle) }}>
      <circle cx={C} cy={C} r={R + 10} fill="var(--turf)" />
      <circle cx={C} cy={C} r={R} fill="none" stroke="#f4f6f1" strokeWidth={2} />
      <circle cx={C} cy={C} r={R * 0.5} fill="none" stroke="#f4f6f1" strokeOpacity={0.45} strokeDasharray="5 5" />
      {/* zones */}
      {ZONES.map((z, i) => {
        const a0 = i * 45, a1 = a0 + 45
        const p0 = polar(a0, 1), p1 = polar(a1, 1)
        const zr = zones?.find((x) => x.zone === z)
        const on = highlightZone === z
        return (
          <g key={z} onMouseEnter={onHoverZone ? () => onHoverZone(z) : undefined} onMouseLeave={onHoverZone ? () => onHoverZone(null) : undefined}>
            <path d={`M${C} ${C}L${p0.x} ${p0.y}A${R} ${R} 0 0 1 ${p1.x} ${p1.y}Z`}
              fill={on ? '#f2c230' : '#f2c230'} fillOpacity={on ? 0.4 : zr ? 0.32 * (zr.runs / maxRuns) : 0} stroke="#f4f6f1" strokeOpacity={0.25} />
          </g>
        )
      })}
      {/* pitch: the striker stands at the centre, the bowler's end is up the screen */}
      <rect x={C - 7} y={C - 54} width={14} height={60} fill="var(--strip)" />
      {/* shots */}
      {shots?.map((s, i) => {
        const p = polar(s.angle, reach(s.runs))
        return <line key={i} x1={C} y1={C} x2={p.x} y2={p.y} stroke={shotColour(s.runs)} strokeWidth={s.runs >= 4 ? 2.2 : 1.3} strokeLinecap="round"><title>{s.runs} runs{s.shot_type ? `, ${words(s.shot_type)}` : ''}</title></line>
      })}
      {picked !== null && picked !== undefined && (() => { const p = polar(picked, 1); return <line x1={C} y1={C} x2={p.x} y2={p.y} stroke="#b3261e" strokeWidth={3} strokeLinecap="round" /> })()}
      {/* zone labels sit above the shot lines, with a dark edge so they stay readable */}
      {ZONES.map((z, i) => {
        const mid = polar(i * 45 + 22.5, 0.86)
        const zr = zones?.find((x) => x.zone === z)
        const halo = { paintOrder: 'stroke', stroke: 'var(--turf)', strokeWidth: 4, strokeLinejoin: 'round' as const, pointerEvents: 'none' as const }
        return (
          <g key={z}>
            <text x={mid.x} y={mid.y} textAnchor="middle" fontSize={12} className="painted" fill="#f4f6f1" style={halo}>{words(z)}</text>
            {zr && zr.runs > 0 && <text x={mid.x} y={mid.y + 14} textAnchor="middle" fontSize={12} className="num" fill="#f4f6f1" style={halo}>{zr.runs} ({zr.pct_of_runs.toFixed(0)}%)</text>}
          </g>
        )
      })}
      {/* batter, bowler, keeper */}
      <circle cx={C} cy={C} r={5} fill="#0d1310" stroke="#f2c230" strokeWidth={2}><title>Batter on strike</title></circle>
      {fielders && <>
        <circle cx={C} cy={C - 62} r={7} fill="#0d1310" stroke="#f4f6f1" strokeWidth={1.5}><title>Bowler</title></circle>
        <circle cx={C} cy={C + 20} r={7} fill="#0d1310" stroke="#f4f6f1" strokeWidth={1.5}><title>Wicket-keeper</title></circle>
      </>}
      {/* fielders */}
      {fielders?.map((f, i) => {
        const p = polar(f.angle, f.distance)
        return (
          <g key={i} transform={`translate(${p.x} ${p.y})`} style={{ cursor: onMoveFielder ? 'grab' : 'default' }}
            onPointerDown={(e) => { if (onMoveFielder) { e.stopPropagation(); (e.target as Element).setPointerCapture?.(e.pointerId); setDrag(i) } }}>
            <circle r={11} fill="#f2c230" stroke="#0d1310" strokeWidth={2} />
            <text textAnchor="middle" y={4} fontSize={12} fontWeight={700} fill="#0d1310" className="num" style={{ pointerEvents: 'none' }}>{i + 1}</text>
            <title>{words(f.name)}</title>
          </g>
        )
      })}
      <text x={C} y={18} textAnchor="middle" fontSize={12} className="painted" fill="var(--ink-2)">Bowler's end</text>
      <text x={S - 2} y={C + 4} textAnchor="end" fontSize={12} className="painted" fill="var(--ink-2)">Off</text>
      <text x={2} y={C + 4} fontSize={12} className="painted" fill="var(--ink-2)">Leg</text>
    </svg>
  )
}

/** Nearest named fielding position to an angle and distance. */
export function nearestPosition(angle: number, distance: number, positions: Fielder[]): string {
  let best = positions[0]?.name ?? 'fielder'
  let bd = Infinity
  for (const p of positions) {
    const da = Math.min(Math.abs(p.angle - angle), 360 - Math.abs(p.angle - angle)) / 180
    const d = Math.hypot(da * 2.2, p.distance - distance)
    if (d < bd) { bd = d; best = p.name }
  }
  return best
}
