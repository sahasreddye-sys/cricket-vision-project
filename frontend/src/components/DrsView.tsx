// DRS graphics: a side-on view of the ball path and a front-on view of the stumps
// with the projected point and its uncertainty. Observed and predicted are drawn differently.
const STUMP_H = 0.711
const HALF = 0.1143
const BALL = 0.036

export interface DrsPath { x: number; y: number; z: number; predicted: boolean }
export interface Projection { x: number; z: number; x_low: number; x_high: number; z_low: number; z_high: number; hit_probability: number }

export function DrsSide({ path, decision }: { path: DrsPath[]; decision: string }) {
  const W = 560, H = 190, PL = 34, PB = 26
  const yMax = Math.max(8, ...path.map((p) => p.y)) + 0.5
  const zMax = Math.max(1.2, ...path.map((p) => p.z)) + 0.2
  const sx = (W - PL - 10) / yMax
  const sz = (H - PB - 10) / zMax
  const px = (y: number) => PL + y * sx
  const pz = (z: number) => H - PB - z * sz
  const obs = path.filter((p) => !p.predicted)
  const pred = path.filter((p) => p.predicted)
  const join = obs.length && pred.length ? [obs[obs.length - 1], ...pred] : pred
  const line = (pts: DrsPath[]) => pts.map((p, i) => `${i ? 'L' : 'M'}${px(p.y).toFixed(1)} ${pz(p.z).toFixed(1)}`).join('')
  const tone = decision === 'hitting' ? '#b3261e' : decision === 'missing' ? '#1f6b45' : '#f2c230'
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="Side view of the ball's path from pitching to the stumps">
      <rect x={PL} y={10} width={W - PL - 10} height={H - PB - 10} fill="var(--plate)" />
      <line x1={PL} x2={W - 10} y1={pz(0)} y2={pz(0)} stroke="var(--strip)" strokeWidth={4} />
      {[0, 2, 4, 6, 8, 10, 12].filter((v) => v < yMax).map((v) => (
        <g key={v}><line x1={px(v)} x2={px(v)} y1={pz(0)} y2={pz(0) + 5} stroke="var(--ink-2)" />
          <text x={px(v)} y={H - 6} textAnchor="middle" fontSize={12} className="num" fill="var(--ink-2)">{v} m</text></g>
      ))}
      <rect x={px(0) - 3} y={pz(STUMP_H)} width={6} height={STUMP_H * sz} fill="#f2c230" />
      <text x={px(0) + 8} y={pz(STUMP_H) - 4} fontSize={12} className="painted" fill="#f4f6f1">Stumps</text>
      {obs.length > 1 && <path d={line(obs)} fill="none" stroke="#f4f6f1" strokeWidth={3} strokeLinecap="round" />}
      {join.length > 1 && <path d={line(join)} fill="none" stroke={tone} strokeWidth={3} strokeDasharray="7 5" strokeLinecap="round" />}
      {obs.length > 0 && <>
        <circle cx={px(obs[0].y)} cy={pz(obs[0].z)} r={6} fill="#f2c230" stroke="#0d1310" strokeWidth={2} />
        <text x={px(obs[0].y)} y={pz(obs[0].z) - 12} textAnchor="middle" fontSize={12} className="painted" fill="#f4f6f1">Pitching</text>
        <circle cx={px(obs[obs.length - 1].y)} cy={pz(obs[obs.length - 1].z)} r={6} fill="#b3261e" stroke="#f4f6f1" strokeWidth={2} />
        <text x={px(obs[obs.length - 1].y)} y={pz(obs[obs.length - 1].z) - 12} textAnchor="middle" fontSize={12} className="painted" fill="#f4f6f1">Impact</text>
      </>}
    </svg>
  )
}

export function DrsFront({ projection, decision }: { projection: Projection | null; decision: string }) {
  const W = 260, H = 260
  const scale = 240          // px per metre
  const cx = W / 2
  const ground = H - 28
  const px = (x: number) => cx + x * scale
  const pz = (z: number) => ground - z * scale
  const tone = decision === 'hitting' ? '#b3261e' : decision === 'missing' ? '#4fae78' : '#f2c230'
  const p = projection
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full max-w-[280px]" role="img" aria-label="Front view of the stumps with the projected ball position">
      <rect width={W} height={H} fill="var(--plate)" />
      <line x1={0} x2={W} y1={ground} y2={ground} stroke="var(--strip)" strokeWidth={4} />
      {/* the zone in which the ball's centre makes contact */}
      <rect x={px(-HALF - BALL)} y={pz(STUMP_H + BALL)} width={(2 * HALF + 2 * BALL) * scale} height={(STUMP_H + BALL) * scale}
        fill="#f4f6f1" opacity={0.08} stroke="#f4f6f1" strokeOpacity={0.3} strokeDasharray="4 4" />
      {[-HALF, 0, HALF].map((s) => <rect key={s} x={px(s) - 4} y={pz(STUMP_H)} width={8} height={STUMP_H * scale} fill="#f2c230" />)}
      <rect x={px(-HALF) - 4} y={pz(STUMP_H) - 4} width={2 * HALF * scale + 8} height={4} fill="#f4f6f1" />
      {p && (
        <g>
          <ellipse cx={px((p.x_low + p.x_high) / 2)} cy={pz((p.z_low + p.z_high) / 2)} rx={Math.max(4, ((p.x_high - p.x_low) / 2) * scale)}
            ry={Math.max(4, ((p.z_high - p.z_low) / 2) * scale)} fill={tone} fillOpacity={0.22} stroke={tone} strokeDasharray="4 3" />
          <circle cx={px(p.x)} cy={pz(Math.max(p.z, -0.05))} r={BALL * scale} fill={tone} stroke="#f4f6f1" strokeWidth={1.5} />
        </g>
      )}
      <text x={6} y={H - 8} fontSize={12} className="painted" fill="var(--ink-2)">Leg</text>
      <text x={W - 6} y={H - 8} fontSize={12} textAnchor="end" className="painted" fill="var(--ink-2)">Off</text>
    </svg>
  )
}

/** Stick figure from MediaPipe landmarks [[x, y, visibility], ...] (normalised 0-1). */
export function Skeleton({ landmarks, className }: { landmarks: number[][] | null; className?: string }) {
  if (!landmarks) return null
  const bones = [[11, 12], [11, 13], [13, 15], [12, 14], [14, 16], [11, 23], [12, 24], [23, 24], [23, 25], [25, 27], [24, 26], [26, 28], [27, 31], [28, 32], [0, 11], [0, 12]]
  const xs = landmarks.filter((l) => l[2] >= 0.5).map((l) => l[0]), ys = landmarks.filter((l) => l[2] >= 0.5).map((l) => l[1])
  if (!xs.length) return null
  const minX = Math.min(...xs), maxX = Math.max(...xs), minY = Math.min(...ys), maxY = Math.max(...ys)
  const span = Math.max(maxX - minX, maxY - minY, 0.01)
  const tx = (x: number) => 20 + ((x - minX) / span) * 200 + (200 - ((maxX - minX) / span) * 200) / 2
  const ty = (y: number) => 20 + ((y - minY) / span) * 200 + (200 - ((maxY - minY) / span) * 200) / 2
  const ok = (i: number) => landmarks[i] && landmarks[i][2] >= 0.5
  return (
    <svg viewBox="0 0 240 240" className={className ?? 'w-full max-w-[240px]'} role="img" aria-label="Body landmarks at the key frame">
      <rect width={240} height={240} fill="var(--plate)" />
      {bones.map(([a, b]) => ok(a) && ok(b) && <line key={`${a}-${b}`} x1={tx(landmarks[a][0])} y1={ty(landmarks[a][1])} x2={tx(landmarks[b][0])} y2={ty(landmarks[b][1])} stroke="#f4f6f1" strokeWidth={3} strokeLinecap="round" />)}
      {[0, 11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28].map((i) => ok(i) && <circle key={i} cx={tx(landmarks[i][0])} cy={ty(landmarks[i][1])} r={i === 0 ? 9 : 4.5} fill="#f2c230" stroke="#0d1310" strokeWidth={1.5} />)}
    </svg>
  )
}
