import { Check, Minus, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { BallTrack } from '../components/BallTrack'
import { DrsFront, DrsSide } from '../components/DrsView'
import { Pitch } from '../components/Pitch'
import { Async, Button, DataTable, Empty, Field, Notice, Page, Plate, Section, Seg, Tabs, cx, useAsync, useToast } from '../components/ui'
import { api } from '../lib/api'
import { day, fmt, pct } from '../lib/format'

interface Inputs {
  pitch_x: number | null; pitch_y: number | null; impact_x: number | null; impact_y: number | null; impact_z: number | null
  speed_kmh: number; position_sigma_m: number; speed_sigma_pct: number; no_ball: boolean; shot_offered: boolean; hit_bat_first: boolean; source: 'manual' | 'video'
}
const START: Inputs = { pitch_x: null, pitch_y: null, impact_x: null, impact_y: null, impact_z: 0.3, speed_kmh: 100, position_sigma_m: 0.03, speed_sigma_pct: 10, no_ball: false, shot_offered: true, hit_bat_first: false, source: 'manual' }

const DECISION: Record<string, { text: string; tone: 'red' | 'green' | 'accent' }> = {
  hitting: { text: 'Hitting', tone: 'red' }, missing: { text: 'Missing', tone: 'green' }, inconclusive: { text: 'Inconclusive', tone: 'accent' },
}

export default function DrsStudio() {
  const toast = useToast()
  const [tab, setTab] = useState<'review' | 'video' | 'saved'>('review')
  const [inp, setInp] = useState<Inputs>(START)
  const [placing, setPlacing] = useState<'pitch' | 'impact'>('pitch')
  const [res, setRes] = useState<any | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [labelText, setLabelText] = useState('')
  const saved = useAsync(() => api.get<any[]>('/drs/reviews'), [])
  const set = (patch: Partial<Inputs>) => setInp((i) => ({ ...i, ...patch }))

  // Recompute whenever an input moves: there is no Calculate button.
  useEffect(() => {
    const id = setTimeout(() => {
      api.post('/drs/simulate', inp).then((r) => { setRes(r); setError(null) }, (e) => setError(e.message))
    }, 120)
    return () => clearTimeout(id)
  }, [inp])

  const place = (x: number, y: number) => {
    if (placing === 'pitch') { set({ pitch_x: x, pitch_y: y }); setPlacing('impact') } else set({ impact_x: x, impact_y: y })
  }
  const save = async () => {
    try { await api.post('/drs/simulate', { ...inp, save: true, label: labelText }); toast('Review saved'); setLabelText(''); saved.reload() } catch (e: any) { toast(e.message, 'error') }
  }
  const marks = [
    ...(inp.pitch_x !== null && inp.pitch_y !== null ? [{ x: inp.pitch_x, y: inp.pitch_y, label: 'Pitching', tone: 'pitch' as const }] : []),
    ...(inp.impact_x !== null && inp.impact_y !== null ? [{ x: inp.impact_x, y: inp.impact_y, label: 'Impact', tone: 'impact' as const }] : []),
  ]
  const dec = res ? DECISION[res.decision] : null

  return (
    <Page title="DRS Studio" lead="An educational LBW simulation. Place where the ball pitched and where it struck the pad, and see whether the projected path would hit the stumps, with the uncertainty shown.">
      <div className="mb-5">
        <Notice tone="warn" title="A training simulation, not an official DRS">
          This does not have Hawk-Eye accuracy. Professional systems triangulate the ball from six or more calibrated high-speed cameras. Here the path is projected from two points you enter, using a simple physical model, so the result is only as good as those two points.
        </Notice>
      </div>
      <Tabs value={tab} onChange={setTab} tabs={[{ id: 'review', label: 'Review' }, { id: 'video', label: 'Track from video' }, { id: 'saved', label: 'Saved reviews' }]} />

      {tab === 'review' && (
        <div className="grid gap-8 lg:grid-cols-[400px_minmax(0,1fr)]">
          <div>
            <div className="mb-2"><Seg label="Point to place" value={placing} onChange={setPlacing} options={[{ id: 'pitch', label: 'Place pitching point' }, { id: 'impact', label: 'Place impact point' }]} /></div>
            <Pitch yMax={12} marks={marks} corridor onAdd={place} />
            <p className="mt-1 text-label text-ink-2">Click the map to place the {placing === 'pitch' ? 'pitching' : 'impact'} point. The pale strip is the line between wicket and wicket.</p>

            <div className="mt-4 grid grid-cols-2 gap-3">
              <Num label="Pitching: across (m)" value={inp.pitch_x} step={0.01} onChange={(v) => set({ pitch_x: v })} hint="+ off, − leg" />
              <Num label="Pitching: from stumps (m)" value={inp.pitch_y} step={0.1} onChange={(v) => set({ pitch_y: v })} />
              <Num label="Impact: across (m)" value={inp.impact_x} step={0.01} onChange={(v) => set({ impact_x: v })} />
              <Num label="Impact: from stumps (m)" value={inp.impact_y} step={0.1} onChange={(v) => set({ impact_y: v })} />
            </div>
            <div className="mt-4 flex flex-col gap-3">
              <Slider label="Impact height" value={inp.impact_z ?? 0} min={0} max={1.2} step={0.01} unit="m" onChange={(v) => set({ impact_z: v })} hint="Knee roll is about 0.45 m; top of the stumps is 0.71 m." />
              <Slider label="Ball speed after the bounce" value={inp.speed_kmh} min={40} max={150} step={1} unit="km/h" onChange={(v) => set({ speed_kmh: v })} />
              <Slider label="How uncertain each position is" value={inp.position_sigma_m * 100} min={1} max={20} step={1} unit="cm" onChange={(v) => set({ position_sigma_m: v / 100 })} hint="About 3 cm for careful manual entry; 8 cm or more for positions taken from video." />
            </div>
            <div className="mt-4 flex flex-col gap-2">
              <Check2 label="No-ball" checked={inp.no_ball} onChange={(v) => set({ no_ball: v })} />
              <Check2 label="Batter offered a shot" checked={inp.shot_offered} onChange={(v) => set({ shot_offered: v })} />
              <Check2 label="Ball hit the bat first" checked={inp.hit_bat_first} onChange={(v) => set({ hit_bat_first: v })} />
            </div>
            <div className="mt-4"><Button variant="quiet" onClick={() => { setInp(START); setPlacing('pitch') }}>Clear review</Button></div>
          </div>

          <div className="min-w-0">
            {error && <Notice tone="error">{error}</Notice>}
            {res && dec && (
              <>
                <div className="flex flex-wrap items-end gap-x-6 gap-y-3 border-y border-rule-strong py-4">
                  <div>
                    <div className="painted mb-1.5 text-label text-ink-2">Ball tracking: wickets</div>
                    <Plate value={dec.text} tone={dec.tone} wide />
                  </div>
                  <div>
                    <div className="painted mb-1.5 text-label text-ink-2">Simulated LBW decision</div>
                    <Plate value={res.lbw === 'out' ? 'Out' : res.lbw === 'not_out' ? 'Not out' : res.lbw ? 'Inconclusive' : '–'} tone={res.lbw === 'out' ? 'red' : res.lbw === 'not_out' ? 'green' : 'accent'} wide />
                  </div>
                  <div>
                    <div className="painted mb-1.5 text-label text-ink-2">Simulated paths hitting</div>
                    <Plate value={res.projection ? pct(res.projection.hit_probability * 100) : null} />
                  </div>
                </div>
                <p className="mt-2 font-semibold">{res.reason}</p>

                {res.projection && (
                  <>
                    <Section title="Projected path">
                      <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_240px]">
                        <div>
                          <DrsSide path={res.path} decision={res.decision} />
                          <p className="mt-1 text-label text-ink-2">Solid line: between the points you entered. Dashed line: predicted beyond the impact.</p>
                        </div>
                        <div>
                          <DrsFront projection={res.projection} decision={res.decision} />
                          <p className="mt-1 text-label text-ink-2">Shaded area: where 95% of simulated paths arrive at the stumps.</p>
                        </div>
                      </div>
                      <p className="mt-2 text-ink-2">
                        Point of intersection with the stumps' plane: {Math.abs(res.projection.x * 100).toFixed(0)} cm {res.projection.x >= 0 ? 'to the off side' : 'to the leg side'} of middle stump at {fmt(Math.max(res.projection.z, 0) * 100, 0)} cm high. 95% range: {fmt(res.projection.x_low * 100, 0)} to {fmt(res.projection.x_high * 100, 0)} cm across, {fmt(Math.max(res.projection.z_low, 0) * 100, 0)} to {fmt(res.projection.z_high * 100, 0)} cm high. The stumps are 22.9 cm wide and 71.1 cm tall.
                      </p>
                    </Section>
                    <Section title="LBW conditions (Law 36)">
                      <ul className="flex flex-col">
                        {res.conditions.map((c: any) => (
                          <li key={c.name} className="flex items-start gap-2.5 border-b border-rule py-2">
                            <span className={cx('mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-plate', c.pass === true ? 'bg-green text-bg' : c.pass === false ? 'bg-red text-bg' : 'bg-accent text-accent-ink')}>
                              {c.pass === true ? <Check size={14} aria-label="Met" /> : c.pass === false ? <X size={14} aria-label="Not met" /> : <Minus size={14} aria-label="Undetermined" />}
                            </span>
                            <div><b>{c.name}.</b> {c.detail} <span className="text-label text-ink-2">{c.law}</span></div>
                          </li>
                        ))}
                      </ul>
                    </Section>
                  </>
                )}
                {!res.projection && <div className="mt-4"><Empty title="Place both points to run the review">Mark where the ball pitched, then where it hit the pad. If you only have video, track it first and bring the pitching point across.</Empty></div>}

                <Section title="Assumptions behind this result">
                  <ul className="list-disc space-y-1 pl-5 text-ink-2">{res.assumptions.map((a: string) => <li key={a}>{a}</li>)}</ul>
                </Section>
                <Section title="Limitations">
                  <ul className="list-disc space-y-1 pl-5 text-ink-2">{res.limitations.map((a: string) => <li key={a}>{a}</li>)}</ul>
                </Section>
                {res.projection && (
                  <Section title="Save this review">
                    <div className="flex flex-wrap items-end gap-2">
                      <Field label="Label" className="w-full max-w-[320px]"><input className="field" value={labelText} maxLength={120} placeholder="e.g. Nets, Imran to Arun" onChange={(e) => setLabelText(e.target.value)} /></Field>
                      <Button variant="primary" onClick={save}>Save review</Button>
                    </div>
                  </Section>
                )}
              </>
            )}
          </div>
        </div>
      )}

      {tab === 'video' && (
        <div>
          <BallTrack onResult={(v) => {
            const p = v.result.pitching
            if (p?.plausible) { set({ pitch_x: Math.round(p.x * 100) / 100, pitch_y: Math.round(p.y * 10) / 10, source: 'video', position_sigma_m: 0.08 }); toast('Pitching point copied to the review, with video-level uncertainty') }
          }} />
          <div className="mt-6"><Notice title="What video can and cannot supply">
            With the four pitch corners marked, the bounce point lies on the ground and can be placed on the pitch. The impact point is above the ground, and one camera cannot tell how far away or how high it is, so enter the impact position and height yourself on the Review tab. Positions taken from video are given a wider uncertainty (8 cm).
          </Notice></div>
          {inp.source === 'video' && <div className="mt-3"><Button variant="primary" onClick={() => { setTab('review'); setPlacing('impact') }}>Continue to the review</Button></div>}
        </div>
      )}

      {tab === 'saved' && (
        <Async state={saved} empty={<Empty title="No saved reviews">Run a review and save it to keep a record for team discussion.</Empty>}>
          {(rows) => (
            <DataTable rows={rows} rowKey={(r) => r.id} cols={[
              { key: 'd', label: 'Date', render: (r) => day(r.created_at) },
              { key: 'l', label: 'Label', render: (r) => r.label || '–' },
              { key: 'p', label: 'Pitched', render: (r) => `${fmt(r.inputs.pitch_y)} m, ${fmt(r.inputs.pitch_x * 100, 0)} cm across` },
              { key: 'w', label: 'Wickets', render: (r) => DECISION[r.decision]?.text },
              { key: 'o', label: 'Decision', render: (r) => (r.lbw === 'out' ? 'Out' : r.lbw === 'not_out' ? 'Not out' : 'Inconclusive') },
              { key: 'a', label: '', render: (r) => <div className="flex justify-end gap-1"><Button small variant="quiet" onClick={() => { setInp({ ...START, ...r.inputs }); setTab('review') }}>Open</Button><Button small variant="quiet" onClick={async () => { await api.del(`/drs/reviews/${r.id}`); saved.reload() }}>Delete</Button></div> },
            ]} />
          )}
        </Async>
      )}
    </Page>
  )
}

function Num({ label, value, onChange, step, hint }: { label: string; value: number | null; onChange: (v: number | null) => void; step: number; hint?: string }) {
  return (
    <Field label={label} hint={hint}>
      <input className="field num" type="number" step={step} value={value ?? ''} onChange={(e) => onChange(e.target.value === '' ? null : parseFloat(e.target.value))} />
    </Field>
  )
}

function Slider({ label, value, min, max, step, unit, onChange, hint }: { label: string; value: number; min: number; max: number; step: number; unit: string; onChange: (v: number) => void; hint?: string }) {
  return (
    <label className="flex flex-col gap-1">
      <span className="flex items-baseline justify-between"><span className="painted text-label text-ink-2">{label}</span><span className="num font-semibold">{step < 1 ? value.toFixed(2) : value.toFixed(0)} {unit}</span></span>
      <input type="range" min={min} max={max} step={step} value={value} onChange={(e) => onChange(parseFloat(e.target.value))} />
      {hint && <span className="text-label text-ink-2">{hint}</span>}
    </label>
  )
}

function Check2({ label, checked, onChange }: { label: string; checked: boolean; onChange: (v: boolean) => void }) {
  return <label className="flex items-center gap-2"><input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />{label}</label>
}
