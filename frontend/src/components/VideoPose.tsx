// Upload a clip, run pose estimation on the server, and read the measurements.
// Used by the Bowling Lab (action), Batting Lab (action) and Fielding Lab (catching).
import { Check, Target, Upload } from 'lucide-react'
import { useState } from 'react'
import { useApp } from '../context'
import { api, qs } from '../lib/api'
import { cap, day, fmt, words } from '../lib/format'
import { LineTrend, SeriesKey } from './Chart'
import { Skeleton } from './DrsView'
import { Async, Board, Button, DataTable, Empty, Field, Notice, PlayerSelect, Section, Win, useAsync, useToast } from './ui'

type Mode = 'bowling' | 'batting' | 'catching'

const COPY: Record<Mode, { what: string; film: string }> = {
  bowling: { what: 'run-up, alignment, head position, front arm, shoulders, trunk, balance, delivery stride and follow-through', film: 'Film side-on from square of the wicket, whole body in shot from the last few strides to the follow-through.' },
  batting: { what: 'stance, head position, balance, footwork, the shot and the follow-through', film: 'Film side-on (from point or square leg), whole body in shot, from the stance to the end of the shot.' },
  catching: { what: 'positioning, movement to the ball, hand placement and balance', film: 'Film from in front or side-on with the whole body in shot, one person only.' },
}

const METRIC_LABEL: Record<string, string> = {
  trunk_lean: 'Trunk lean (deg)', shoulder_tilt: 'Shoulder tilt (deg)', head_offset: 'Head offset (torso lengths)', stride_ratio: 'Stride (torso lengths)',
  bowling_elbow_angle: 'Bowling elbow (deg)', front_knee_angle: 'Front knee (deg)', front_arm_angle: 'Front arm from trunk (deg)',
  wrist_gap_ratio: 'Hands apart (torso lengths)', hands_height: 'Hands above hips (torso lengths)', left_knee_angle: 'Left knee (deg)', right_knee_angle: 'Right knee (deg)',
  stance_width_ratio: 'Stance width (shoulder widths)', head_tilt: 'Head tilt (deg)', speed_cv: 'Run-up speed variation', weight_transfer: 'Weight transfer (frame widths)',
  peak_hand_speed: 'Peak hand speed (frame/s)',
}
const label = (k: string) => METRIC_LABEL[k.split('.').pop()!] ?? cap(k.split('.').pop()!)

export function VideoPose({ mode }: { mode: Mode }) {
  const { players, canEdit, user } = useApp()
  const toast = useToast()
  const [file, setFile] = useState<File | null>(null)
  const [playerId, setPlayerId] = useState<number | null>(user.player_id)
  const [labelText, setLabelText] = useState('')
  const [arm, setArm] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [current, setCurrent] = useState<any | null>(null)
  const [cmp, setCmp] = useState<{ a: number | null; b: number | null }>({ a: null, b: null })
  const history = useAsync(() => api.get<any[]>(`/video/analyses${qs({ kind: mode })}`), [mode])
  const comparison = useAsync(() => (cmp.a && cmp.b && cmp.a !== cmp.b ? api.get(`/video/compare${qs({ a: cmp.a, b: cmp.b })}`) : Promise.resolve(null)), [cmp.a, cmp.b])

  const analyse = async () => {
    if (!file) return
    setBusy(true); setError(null)
    const form = new FormData()
    form.append('file', file); form.append('mode', mode); form.append('label', labelText)
    if (playerId) form.append('player_id', String(playerId))
    if (arm) form.append('arm', arm)
    try {
      const res = await api.upload('/video/pose', form)
      setCurrent(res); history.reload()
      toast(res.status === 'ok' ? 'Analysis saved' : 'Analysis saved, but too little was detected')
    } catch (e: any) { setError(e.message) }
    setBusy(false)
  }
  const open = async (id: number) => { try { setCurrent(await api.get(`/video/analyses/${id}`)) } catch (e: any) { toast(e.message, 'error') } }

  return (
    <div>
      <Section title="Analyse a clip">
        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <div className="flex flex-col gap-3">
            <Field label="Video file" hint="MP4, MOV, AVI or WebM. The video is analysed and then deleted; only the measurements are kept.">
              <input className="field py-1.5" type="file" accept="video/*,.mp4,.mov,.avi,.webm,.mkv,.m4v" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
            </Field>
            <div className="grid grid-cols-2 gap-3">
              <PlayerSelect players={players} value={playerId} onChange={setPlayerId} allowEmpty="Not linked to a player" />
              <Field label="Label"><input className="field" value={labelText} maxLength={120} placeholder="e.g. Nets, 12 May, ball 3" onChange={(e) => setLabelText(e.target.value)} /></Field>
              {mode === 'bowling' && (
                <Field label="Bowling arm" hint="Leave on detect unless it picks the wrong arm.">
                  <select className="field" value={arm} onChange={(e) => setArm(e.target.value)}><option value="">Detect</option><option value="right">Right</option><option value="left">Left</option></select>
                </Field>
              )}
            </div>
            {error && <Notice tone="error" title="The clip could not be analysed">{error}</Notice>}
            <div><Button variant="primary" busy={busy} disabled={!file || (playerId !== null && !canEdit(playerId))} onClick={analyse}><Upload size={16} aria-hidden />{busy ? 'Analysing' : 'Analyse clip'}</Button></div>
          </div>
          <Notice title="What this measures">
            Pose estimation finds body landmarks in each frame and measures {COPY[mode].what} as 2-D angles and distances. {COPY[mode].film} It cannot diagnose injury risk, say whether an action is medically safe, or judge whether a bowling action is legal.
          </Notice>
        </div>
      </Section>

      {current && <Result v={current} />}

      <Section title="Saved analyses" aside={history.data?.length ? 'Choose A and B to compare two clips' : undefined}>
        <Async state={history} empty={<Empty title="No clips analysed yet">Upload a clip above. Each analysis is saved here so attempts can be compared.</Empty>}>
          {(rows) => (
            <DataTable rows={rows} rowKey={(r) => r.id} dense cols={[
              { key: 'd', label: 'Date', render: (r) => day(r.created_at) },
              { key: 'p', label: 'Player', render: (r) => r.player ?? '–' },
              { key: 'l', label: 'Label', render: (r) => r.label || r.filename },
              { key: 's', label: 'Result', render: (r) => (r.status === 'ok' ? 'Measured' : 'Too little detected') },
              { key: 'o', label: '', render: (r) => <Button small variant="quiet" onClick={() => open(r.id)}>Open</Button> },
              { key: 'a', label: 'A', render: (r) => <input type="radio" name={`a-${mode}`} aria-label="Use as clip A" checked={cmp.a === r.id} onChange={() => setCmp({ ...cmp, a: r.id })} /> },
              { key: 'b', label: 'B', render: (r) => <input type="radio" name={`b-${mode}`} aria-label="Use as clip B" checked={cmp.b === r.id} onChange={() => setCmp({ ...cmp, b: r.id })} /> },
            ]} />
          )}
        </Async>
      </Section>

      {comparison.data && (
        <Section title="Clip A against clip B">
          {comparison.data.rows.length === 0
            ? <Empty title="Nothing to compare">The two clips have no measurements in common. One of them may have had too few frames with a visible person.</Empty>
            : <DataTable rows={comparison.data.rows} rowKey={(r: any) => r.metric} dense cols={[
              { key: 'm', label: 'Measurement', render: (r: any) => `${cap(r.metric.split('.')[0])}: ${label(r.metric)}` },
              { key: 'a', label: 'Clip A', num: true, render: (r: any) => fmt(r.a, 2) },
              { key: 'b', label: 'Clip B', num: true, render: (r: any) => fmt(r.b, 2) },
              { key: 'd', label: 'B minus A', num: true, render: (r: any) => (r.difference > 0 ? '+' : '') + fmt(r.difference, 2) },
            ]} />}
          <p className="mt-2 text-label text-ink-2">{comparison.data.note}</p>
        </Section>
      )}
    </div>
  )
}

function Result({ v }: { v: any }) {
  const r = v.result
  if (r.status !== 'ok') {
    return (
      <Section title="Result">
        <Notice tone="warn" title="Not enough was detected to measure this clip">{r.reason}</Notice>
      </Section>
    )
  }
  const ind = r.indicators ?? {}
  const key: Record<string, number | null> = { ...(ind.release ?? {}), ...(ind.catch ?? {}) }
  if (ind.runup?.speed_cv != null) key.speed_cv = ind.runup.speed_cv
  if (typeof ind.weight_transfer === 'number') key.weight_transfer = ind.weight_transfer
  if (ind.stance) for (const [k, s] of Object.entries<any>(ind.stance)) if (s) key[k] = s.mean
  const shown = Object.entries(key).filter(([k, val]) => typeof val === 'number' && METRIC_LABEL[k]).slice(0, 8)
  const series = [{ key: 'trunk_lean', label: 'Trunk lean (deg)' }, { key: 'shoulder_tilt', label: 'Shoulder tilt (deg)' }]
  return (
    <Section title={`Result${v.label ? ': ' + v.label : ''}`} aside={`${r.frames_with_pose} of ${r.frames_processed} sampled frames had a visible person`}>
      <Board cols={4}>
        {shown.map(([k, val]) => <Win key={k} label={label(k)} value={fmt(val as number, Math.abs(val as number) < 10 ? 2 : 0)} />)}
      </Board>
      <div className="mt-5 grid gap-6 lg:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]">
        <div>
          <h3 className="painted mb-2 text-label text-ink-2">Coaching observations</h3>
          <ul className="flex flex-col">
            {r.observations.map((o: any, i: number) => (
              <li key={i} className="flex gap-2.5 border-b border-rule py-2">
                {o.kind === 'strength' ? <Check size={17} className="mt-0.5 shrink-0 text-green" aria-label="Strength" /> : o.kind === 'focus' ? <Target size={17} className="mt-0.5 shrink-0 text-accent [html[data-theme=light]_&]:text-red" aria-label="Focus area" /> : <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-ink-2" aria-hidden />}
                <div><div>{o.text}</div><div className="text-label text-ink-2">Measured: {o.evidence}</div></div>
              </li>
            ))}
            {r.observations.length === 0 && <li className="py-2 text-ink-2">No observation thresholds were crossed in this clip.</li>}
          </ul>
          {r.series?.length > 2 && (
            <div className="mt-5">
              <h3 className="painted mb-1 text-label text-ink-2">Through the clip</h3>
              <LineTrend data={r.series.map((s: any) => ({ ...s, t: s.t.toFixed(2) }))} x="t" series={series} height={180} />
              <SeriesKey series={series} />
            </div>
          )}
        </div>
        <div>
          <h3 className="painted mb-2 text-label text-ink-2">Landmarks at the key frame{r.key_frame != null ? ` (frame ${r.key_frame})` : ''}</h3>
          <Skeleton landmarks={r.key_landmarks} />
        </div>
      </div>
      {r.annotated_frames?.length > 0 && (
        <div className="mt-5">
          <h3 className="painted mb-2 text-label text-ink-2">Annotated frames</h3>
          <div className="grid grid-cols-2 gap-2 md:grid-cols-3">
            {r.annotated_frames.map((f: any) => (
              <figure key={f.frame} className="m-0">
                <img src={f.image} alt={`Frame ${f.frame} with body landmarks drawn`} className="w-full rounded-plate" />
                <figcaption className="mt-1 text-label text-ink-2">Frame {f.frame}{f.key ? ` · key frame (${words(r.mode === 'bowling' ? 'release' : r.mode === 'batting' ? 'fastest hands' : 'hands together')})` : ''}</figcaption>
              </figure>
            ))}
          </div>
        </div>
      )}
      <p className="mt-4 text-label text-ink-2">{r.disclaimer}</p>
    </Section>
  )
}
