// Top-down pitch map. Coordinates match pitchvision/constants.py:
//   x = metres from middle stump, + = off side (drawn to the right, bowler at the top)
//   y = metres from the striker's stumps toward the bowler
import { useRef } from 'react'
import { words } from '../lib/format'

export interface Dot { id?: number | string; x: number; y: number; tone?: 'a' | 'b' | 'wicket' | 'muted'; title?: string }
export interface Band { name: string; min: number; max: number }

const X_HALF = 1.6
const SX = 92       // px per metre across (widened so line differences are readable)
const SY = 36       // px per metre along
const PAD_L = 74
const PAD_R = 16
const PAD_T = 10
const PAD_B = 34
const STUMP_HALF = 0.1143

export const DEFAULT_BANDS: Band[] = [
  { name: 'yorker', min: 0, max: 2 }, { name: 'full', min: 2, max: 6 }, { name: 'good', min: 6, max: 8 },
  { name: 'short', min: 8, max: 10 }, { name: 'bouncer', min: 10, max: 20.12 },
]

export function Pitch({ dots = [], bands = DEFAULT_BANDS, yMax = 13, target, onAdd, highlight, onHover, heat, marks, corridor, className }: {
  dots?: Dot[]; bands?: Band[]; yMax?: number
  target?: { x: number; y: number; tol_x: number; tol_y: number } | null
  onAdd?: (x: number, y: number) => void
  highlight?: number | string | null; onHover?: (id: number | string | null) => void
  heat?: { counts: number[][]; x_edges: number[]; y_edges: number[]; max: number } | null
  marks?: { x: number; y: number; label: string; tone: 'pitch' | 'impact' }[]
  corridor?: boolean; className?: string
}) {
  const ref = useRef<SVGSVGElement>(null)
  const W = PAD_L + 2 * X_HALF * SX + PAD_R
  const H = PAD_T + yMax * SY + PAD_B
  const px = (x: number) => PAD_L + (x + X_HALF) * SX
  const py = (y: number) => PAD_T + (yMax - y) * SY
  const edge = 1.525

  const toPitch = (e: { clientX: number; clientY: number }) => {
    const svg = ref.current!
    const r = svg.getBoundingClientRect()
    const u = ((e.clientX - r.left) / r.width) * W
    const v = ((e.clientY - r.top) / r.height) * H
    return { x: (u - PAD_L) / SX - X_HALF, y: yMax - (v - PAD_T) / SY }
  }
  const click = (e: React.MouseEvent) => {
    if (!onAdd) return
    const p = toPitch(e)
    if (Math.abs(p.x) <= edge && p.y >= 0 && p.y <= yMax) onAdd(Math.round(p.x * 100) / 100, Math.round(p.y * 100) / 100)
  }

  return (
    <svg ref={ref} viewBox={`0 0 ${W} ${H}`} className={className ?? 'w-full max-w-[400px]'} role="img"
      aria-label={`Pitch map with ${dots.length} deliveries`} onClick={click} style={{ cursor: onAdd ? 'crosshair' : 'default', touchAction: 'manipulation' }}>
      {/* the strip */}
      <rect x={px(-edge)} y={py(yMax)} width={2 * edge * SX} height={yMax * SY} fill="var(--strip)" />
      {bands.filter((b) => b.min < yMax).map((b, i) => {
        const top = Math.min(b.max, yMax)
        return (
          <g key={b.name}>
            {i % 2 === 1 && <rect x={px(-edge)} y={py(top)} width={2 * edge * SX} height={(top - b.min) * SY} fill="#000" opacity={0.07} />}
            <line x1={px(-edge)} x2={px(edge)} y1={py(top)} y2={py(top)} stroke="#0d1310" strokeOpacity={0.28} strokeDasharray="3 4" />
            <text x={PAD_L - 8} y={py((b.min + top) / 2) + 4} textAnchor="end" className="painted" fontSize={12} fill="var(--ink-2)">{words(b.name)}</text>
            <text x={PAD_L - 8} y={py(top) + 4} textAnchor="end" fontSize={12} fill="var(--ink-2)" opacity={0.7} className="num">{top} m</text>
          </g>
        )
      })}
      {/* heat cells */}
      {heat && heat.max > 0 && heat.counts.map((row, yi) => row.map((c, xi) => c > 0 && (
        <rect key={`${yi}-${xi}`} x={px(heat.x_edges[xi])} y={py(heat.y_edges[yi + 1])} width={(heat.x_edges[xi + 1] - heat.x_edges[xi]) * SX}
          height={(heat.y_edges[yi + 1] - heat.y_edges[yi]) * SY} fill="#b3261e" opacity={0.12 + 0.7 * (c / heat.max)}>
          <title>{c} deliveries</title>
        </rect>
      )))}
      {/* stump-to-stump corridor */}
      {corridor && <rect x={px(-STUMP_HALF)} y={py(yMax)} width={2 * STUMP_HALF * SX} height={yMax * SY} fill="#f4f6f1" opacity={0.35} />}
      {/* creases and stumps */}
      <line x1={px(-edge)} x2={px(edge)} y1={py(1.22)} y2={py(1.22)} stroke="#f4f6f1" strokeWidth={2.5} />
      <line x1={px(-1.32)} x2={px(1.32)} y1={py(0)} y2={py(0)} stroke="#f4f6f1" strokeWidth={2.5} />
      {[-STUMP_HALF, 0, STUMP_HALF].map((s) => <circle key={s} cx={px(s)} cy={py(0)} r={3.2} fill="#0d1310" stroke="#f2c230" strokeWidth={1.5} />)}
      {/* target box */}
      {target && (
        <g>
          <rect x={px(target.x - target.tol_x)} y={py(target.y + target.tol_y)} width={2 * target.tol_x * SX} height={2 * target.tol_y * SY}
            fill="#f2c230" fillOpacity={0.22} stroke="#0d1310" strokeWidth={1.5} strokeDasharray="5 3" />
          <path d={`M${px(target.x) - 6} ${py(target.y)}h12M${px(target.x)} ${py(target.y) - 6}v12`} stroke="#0d1310" strokeWidth={1.5} />
        </g>
      )}
      {/* deliveries */}
      {dots.map((d, i) => {
        const on = highlight !== null && highlight !== undefined && d.id === highlight
        const fill = d.tone === 'wicket' ? '#b3261e' : d.tone === 'b' ? '#1f6b45' : d.tone === 'muted' ? '#5c665f' : '#0d1310'
        return (
          <circle key={d.id ?? i} cx={px(Math.max(-edge, Math.min(edge, d.x)))} cy={py(Math.max(0, Math.min(yMax, d.y)))} r={on ? 8 : 4.6}
            fill={on ? '#f2c230' : fill} stroke={on ? '#0d1310' : '#f4f6f1'} strokeWidth={on ? 2 : 1}
            onMouseEnter={onHover ? () => onHover(d.id ?? null) : undefined} onMouseLeave={onHover ? () => onHover(null) : undefined}
            onClick={(e) => e.stopPropagation()} style={{ transition: 'r 120ms' }}>
            <title>{d.title ?? `${d.x.toFixed(2)} m across, ${d.y.toFixed(1)} m from the stumps`}</title>
          </circle>
        )
      })}
      {/* DRS marks */}
      {marks?.map((m) => (
        <g key={m.label}>
          <circle cx={px(m.x)} cy={py(m.y)} r={8} fill={m.tone === 'pitch' ? '#f2c230' : '#b3261e'} stroke="#0d1310" strokeWidth={2} />
          <text x={px(m.x) + 12} y={py(m.y) + 4} fontSize={12} className="painted" fill="#0d1310">{m.label}</text>
        </g>
      ))}
      {/* axis labels */}
      <text x={px(-edge)} y={H - 12} fontSize={12} className="painted" fill="var(--ink-2)">Leg side</text>
      <text x={px(edge)} y={H - 12} fontSize={12} textAnchor="end" className="painted" fill="var(--ink-2)">Off side</text>
      <text x={px(0)} y={H - 12} fontSize={12} textAnchor="middle" className="painted" fill="var(--ink-2)">Stumps</text>
    </svg>
  )
}
