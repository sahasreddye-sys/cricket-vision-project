// Ball tracking from an uploaded video: optional four-point pitch calibration,
// the tracked path (observed and predicted points drawn differently), bounce and movement.
import { Upload } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { api } from '../lib/api'
import { fmt, pct, words } from '../lib/format'
import { Board, Button, Empty, Field, Legend, Notice, Section, Win, cx, useAsync, useToast } from './ui'

export interface Pitching { x: number; y: number; plausible: boolean; length: string | null; line: string | null; note: string }

export function BallTrack({ onResult, playerId }: { onResult?: (v: any) => void; playerId?: number | null }) {
  const toast = useToast()
  const [file, setFile] = useState<File | null>(null)
  const [url, setUrl] = useState<string | null>(null)
  const [colour, setColour] = useState('')
  const [labelText, setLabelText] = useState('')
  const [calibrating, setCalibrating] = useState(false)
  const [points, setPoints] = useState<number[][]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<any | null>(null)
  const video = useRef<HTMLVideoElement>(null)
  const targets = useAsync(() => api.get<any[]>('/video/calibration-targets'), [])

  useEffect(() => {
    if (!file) { setUrl(null); return }
    const u = URL.createObjectURL(file)
    setUrl(u); setPoints([]); setResult(null); setError(null)
    return () => URL.revokeObjectURL(u)
  }, [file])

  const mark = (e: React.MouseEvent) => {
    const v = video.current
    if (!calibrating || !v || points.length >= 4) return
    const r = v.getBoundingClientRect()
    setPoints([...points, [Math.round(((e.clientX - r.left) / r.width) * v.videoWidth), Math.round(((e.clientY - r.top) / r.height) * v.videoHeight)]])
  }

  const track = async () => {
    if (!file) return
    setBusy(true); setError(null)
    const form = new FormData()
    form.append('file', file); form.append('label', labelText)
    if (colour) form.append('colour', colour)
    if (playerId) form.append('player_id', String(playerId))
    if (points.length === 4) form.append('calibration', JSON.stringify(points))
    try {
      const v = await api.upload('/video/track', form)
      setResult(v); onResult?.(v)
      toast(v.result.status === 'ok' ? 'Ball tracked' : 'Too few ball positions were detected')
    } catch (e: any) { setError(e.message) }
    setBusy(false)
  }
  const vw = video.current?.videoWidth || 1, vh = video.current?.videoHeight || 1

  return (
    <div>
      <Section title="Track a delivery">
        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <div className="flex flex-col gap-3">
            <Field label="Video file" hint="One delivery per clip, fixed camera. 120 fps or more gives far better results than 30 fps.">
              <input className="field py-1.5" type="file" accept="video/*,.mp4,.mov,.avi,.webm,.mkv,.m4v" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
            </Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Ball colour" hint="Helps separate the ball from other moving things.">
                <select className="field" value={colour} onChange={(e) => setColour(e.target.value)}>
                  <option value="">Any (motion only)</option><option value="red">Red</option><option value="white">White</option><option value="pink">Pink</option>
                </select>
              </Field>
              <Field label="Label"><input className="field" value={labelText} maxLength={120} onChange={(e) => setLabelText(e.target.value)} /></Field>
            </div>
            {error && <Notice tone="error" title="The video could not be tracked">{error}</Notice>}
            <div className="flex flex-wrap gap-2">
              <Button variant="primary" busy={busy} disabled={!file} onClick={track}><Upload size={16} aria-hidden />{busy ? 'Tracking' : 'Track ball'}</Button>
              {url && <Button onClick={() => { setCalibrating(!calibrating); if (!calibrating) setPoints([]) }}>{calibrating ? 'Stop marking' : points.length === 4 ? 'Re-mark pitch corners' : 'Mark pitch corners (optional)'}</Button>}
            </div>
          </div>
          <div>
            {url ? (
              <div>
                <div className="relative" onClick={mark} style={{ cursor: calibrating && points.length < 4 ? 'crosshair' : 'default' }}>
                  <video ref={video} src={url} controls={!calibrating} muted playsInline className="block w-full rounded-plate bg-plate" onLoadedMetadata={() => setPoints([])} />
                  <svg viewBox={`0 0 ${vw} ${vh}`} className="pointer-events-none absolute inset-0 h-full w-full">
                    {points.length > 1 && <polygon points={points.map((p) => p.join(',')).join(' ')} fill="#f2c230" fillOpacity={0.15} stroke="#f2c230" strokeWidth={vw / 300} />}
                    {points.map((p, i) => <g key={i}><circle cx={p[0]} cy={p[1]} r={vw / 90} fill="#f2c230" stroke="#0d1310" strokeWidth={vw / 400} /><text x={p[0]} y={p[1] - vw / 60} textAnchor="middle" fontSize={vw / 40} fill="#f2c230" fontWeight={700}>{i + 1}</text></g>)}
                  </svg>
                </div>
                {calibrating && targets.data && (
                  <ol className="mt-2 flex flex-col gap-0.5 text-label">
                    {targets.data.map((t, i) => <li key={i} className={cx(i === points.length ? 'font-semibold text-ink' : 'text-ink-2')}>{i + 1}. Click the {t.label.toLowerCase()}{i < points.length ? ' (marked)' : ''}</li>)}
                  </ol>
                )}
                {!calibrating && <p className="mt-2 text-label text-ink-2">{points.length === 4 ? 'Pitch corners marked: the bounce point will be mapped to pitch metres.' : 'Without marked pitch corners, positions stay in image pixels and no pitching location in metres is given.'}</p>}
              </div>
            ) : (
              <Notice title="How tracking works">
                The server looks for a small, round, moving object in each frame and links the detections with a Kalman filter. Points it saw are marked observed; points it filled in while the ball was hidden are marked predicted. A single camera cannot measure depth, so positions are in image pixels unless you mark the four pitch corners, which lets the bounce point (and only the bounce point) be placed on the pitch.
              </Notice>
            )}
          </div>
        </div>
      </Section>
      {result && <TrackResult v={result} />}
    </div>
  )
}

export function TrackResult({ v }: { v: any }) {
  const r = v.result
  if (r.status !== 'ok') {
    return <Section title="Tracking result"><Notice tone="warn" title="Insufficient tracking data">{r.reason} {r.observed_count} position(s) were detected in {r.frames_processed} frames.</Notice></Section>
  }
  const W = r.info.width, H = r.info.height
  const pts: any[] = r.points
  const m = r.movement
  const unit = m?.units === 'm' ? 'm' : 'px'
  return (
    <Section title="Tracking result" aside={`${r.info.fps.toFixed(0)} fps${r.info.fps_assumed ? ' (assumed)' : ''} · ${W}×${H}`}>
      <Board cols={5}>
        <Win label="Observed points" value={r.observed_count} />
        <Win label="Predicted points" value={r.predicted_count} hint="filled in while hidden" />
        <Win label="Detection rate" value={pct(r.detection_rate * 100)} />
        <Win label="Tracking confidence" value={words(r.confidence_label)} tone={r.confidence_label === 'high' ? 'green' : r.confidence_label === 'low' ? 'red' : 'accent'} />
        <Win label="Position uncertainty" value={fmt(Math.max(...pts.map((p) => p.sigma_px)), 0)} unit="px" hint="largest, 1 sd" />
      </Board>
      <div className="mt-5 grid gap-6 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
        <div>
          <svg viewBox={`0 0 ${W} ${H}`} className="w-full rounded-plate bg-plate" role="img" aria-label="Tracked ball positions across the video frame">
            <polyline points={pts.map((p) => `${p.x},${p.y}`).join(' ')} fill="none" stroke="#f4f6f1" strokeOpacity={0.35} strokeWidth={W / 400} />
            {pts.map((p, i) => p.observed
              ? <circle key={i} cx={p.x} cy={p.y} r={W / 150} fill="#f4f6f1"><title>Observed, frame {p.frame}, confidence {(p.confidence * 100).toFixed(0)}%</title></circle>
              : <circle key={i} cx={p.x} cy={p.y} r={W / 150} fill="none" stroke="#f2c230" strokeWidth={W / 500} strokeDasharray={`${W / 300} ${W / 300}`}><title>Predicted, frame {p.frame} (ball not detected)</title></circle>)}
            {r.bounce?.found && <g><circle cx={r.bounce.x} cy={r.bounce.y} r={W / 70} fill="none" stroke="#f2c230" strokeWidth={W / 300} /><text x={r.bounce.x} y={r.bounce.y + W / 28} textAnchor="middle" fontSize={W / 45} fill="#f2c230" className="painted">Bounce</text></g>}
          </svg>
          <div className="mt-2"><Legend items={[
            { label: 'Observed position', swatch: <span className="inline-block h-2.5 w-2.5 rounded-full bg-ink" /> },
            { label: 'Predicted position (ball not detected)', swatch: <span className="inline-block h-2.5 w-2.5 rounded-full border border-dashed border-ink" /> },
          ]} /></div>
        </div>
        <div className="flex flex-col gap-3">
          <Fact title="Bounce" body={r.bounce?.found ? `Found at frame ${r.bounce.frame} (${(r.bounce.confidence * 100).toFixed(0)}% confidence).` : (r.bounce?.reason ?? 'Not found.')} />
          <Fact title="Pitching location" body={r.pitching ? (r.pitching.plausible
            ? `${words(r.pitching.length)} length, ${words(r.pitching.line)} line: ${r.pitching.y.toFixed(1)} m from the stumps, ${Math.abs(r.pitching.x * 100).toFixed(0)} cm ${r.pitching.x >= 0 ? 'to the off side' : 'to the leg side'} of middle. ${r.pitching.note}`
            : r.pitching.note) : r.calibration_error ? `Calibration failed: ${r.calibration_error}` : 'Not available: mark the four pitch corners and track again to place the bounce on the pitch.'} />
          <Fact title="Movement in the air (swing)" body={m?.swing?.status === 'measured'
            ? `${m.swing.label}. Deviation from the initial line ${fmt(m.swing.deviation, unit === 'm' ? 2 : 1)} ${unit} ± ${fmt(m.swing.std_error, unit === 'm' ? 2 : 1)} (${fmt(m.swing.z, 1)} standard errors; 3 or more is reported as movement).`
            : (m?.swing?.reason ?? 'Not measured.')} strong={m?.swing?.significant} />
          <Fact title="Movement off the pitch (seam)" body={m?.seam?.status === 'measured'
            ? `${m.seam.label}. Sideways speed changed by ${fmt(m.seam.change, 1)} ${unit}/s ± ${fmt(m.seam.std_error, 1)} (${fmt(m.seam.z, 1)} standard errors).`
            : (m?.seam?.reason ?? 'Not measured.')} strong={m?.seam?.significant} />
          {m?.warning && <p className="text-label text-ink-2">{m.warning}</p>}
        </div>
      </div>
    </Section>
  )
}

function Fact({ title, body, strong }: { title: string; body: string; strong?: boolean }) {
  return (
    <div className="border-b border-rule pb-2.5">
      <div className="painted text-label text-ink-2">{title}</div>
      <div className={cx(strong && 'font-semibold')}>{body}</div>
    </div>
  )
}

export function NoTracks() {
  return <Empty title="No deliveries tracked yet">Upload a clip above. Tracked deliveries are saved so their movement can be compared.</Empty>
}
