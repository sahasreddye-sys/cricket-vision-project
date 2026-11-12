import { Trash2 } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { useApp } from '../context'
import { BallTrack, NoTracks } from '../components/BallTrack'
import { Bars, LineTrend, SeriesKey } from '../components/Chart'
import { Pitch } from '../components/Pitch'
import type { Band } from '../components/Pitch'
import { VideoPose } from '../components/VideoPose'
import { Async, Board, Button, DataTable, Empty, Field, Notice, Page, PlayerSelect, Section, Seg, Tabs, Win, useAsync, useToast } from '../components/ui'
import { api, qs } from '../lib/api'
import { cap, day, fmt, pct, today, words } from '../lib/format'
import { averageSpeed, kmhToMph } from '../lib/units'
import type { DistanceUnit, TimeUnit } from '../lib/units'

type Tab = 'speed' | 'accuracy' | 'action' | 'tracking' | 'movement'

export default function BowlingLab() {
  const [tab, setTab] = useState<Tab>('speed')
  return (
    <Page title="Bowling Lab" lead="Time deliveries, map line and length, and measure a bowling action or a ball's flight from video.">
      <Tabs value={tab} onChange={setTab} tabs={[
        { id: 'speed', label: 'Speed and radar' }, { id: 'accuracy', label: 'Line and length' }, { id: 'action', label: 'Action analyzer' },
        { id: 'tracking', label: 'Ball tracking' }, { id: 'movement', label: 'Swing and seam' },
      ]} />
      {tab === 'speed' && <Speed />}
      {tab === 'accuracy' && <Accuracy />}
      {tab === 'action' && <VideoPose mode="bowling" />}
      {tab === 'tracking' && <Tracking />}
      {tab === 'movement' && <Movement />}
    </Page>
  )
}

function NeedPlayers() {
  return <Empty title="Add a player first">Readings and sessions are saved against a player. Add the squad in the Team Hub.</Empty>
}

/* ---------------------------------------------------------------- speed */

function Speed() {
  const { players, user, canEdit, team } = useApp()
  const toast = useToast()
  const [distance, setDistance] = useState('18.9')
  const [time, setTime] = useState('')
  const [du, setDu] = useState<DistanceUnit>('m')
  const [tu, setTu] = useState<TimeUnit>('s')
  const [playerId, setPlayerId] = useState<number | null>(user.player_id ?? players[0]?.id ?? null)
  const [date, setDate] = useState(today())
  const [radar, setRadar] = useState('')
  const [busy, setBusy] = useState(false)
  const history = useAsync(() => (playerId ? api.get(`/speed/history${qs({ player_id: playerId })}`) : Promise.resolve(null)), [playerId])
  const mph = team.speed_unit === 'mph'

  const d = parseFloat(distance), t = parseFloat(time)
  const result = distance !== '' && time !== '' ? averageSpeed(d, t, du, tu) : null
  const ok = result && typeof result !== 'string' ? result : null
  const err = typeof result === 'string' ? result : ok && ok.kmh > 200 ? 'That is faster than any recorded delivery. Check the distance and time.' : null

  const save = async (body: Record<string, unknown>) => {
    setBusy(true)
    try { await api.post('/speed/readings', { player_id: playerId, date, ...body }); toast('Reading saved'); history.reload() } catch (e: any) { toast(e.message, 'error') }
    setBusy(false)
  }
  const remove = async (id: number) => { try { await api.del(`/speed/readings/${id}`); history.reload() } catch (e: any) { toast(e.message, 'error') } }
  const show = (kmh: number | null | undefined) => (kmh == null ? null : fmt(mph ? kmhToMph(kmh) : kmh))
  const unit = mph ? 'mph' : 'km/h'

  return (
    <div>
      <Section title="Speed calculator">
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
          <div className="flex flex-col gap-3">
            <div className="grid grid-cols-[minmax(0,1fr)_auto] items-start gap-2 [&>div[role=radiogroup]]:mt-5">
              <Field label="Distance the ball travelled" hint="Release point to where timing stopped. 18.9 m is popping crease to the far stumps.">
                <input className="field num" inputMode="decimal" value={distance} onChange={(e) => setDistance(e.target.value)} />
              </Field>
              <Seg label="Distance unit" value={du} onChange={setDu} options={[{ id: 'm', label: 'm' }, { id: 'ft', label: 'ft' }, { id: 'yd', label: 'yd' }]} />
            </div>
            <div className="grid grid-cols-[minmax(0,1fr)_auto] items-start gap-2 [&>div[role=radiogroup]]:mt-5">
              <Field label="Time taken" error={err}>
                <input className="field num" inputMode="decimal" value={time} placeholder={tu === 's' ? 'e.g. 0.62' : 'e.g. 620'} onChange={(e) => setTime(e.target.value)} />
              </Field>
              <Seg label="Time unit" value={tu} onChange={setTu} options={[{ id: 's', label: 's' }, { id: 'ms', label: 'ms' }]} />
            </div>
          </div>
          <div>
            <Board cols={3}>
              <Win label="Metres per second" value={ok && !err ? fmt(ok.ms, 2) : null} />
              <Win label="Kilometres per hour" value={ok && !err ? fmt(ok.kmh) : null} tone="accent" />
              <Win label="Miles per hour" value={ok && !err ? fmt(ok.mph) : null} />
            </Board>
            <p className="mt-2 text-label text-ink-2">
              {ok && !err ? `${fmt(ok.distanceM, 2)} m in ${fmt(ok.timeS, 3)} s. ` : ''}This is the ball's <b>average speed</b> over the measured distance. A ball slows through the air and at the bounce, so its release speed is higher than this figure; a radar gun reads close to release speed.
            </p>
          </div>
        </div>
      </Section>

      <Section title="Save a reading">
        {players.length === 0 ? <NeedPlayers /> : (
          <div className="grid items-end gap-3 sm:grid-cols-2 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)_auto_minmax(0,1fr)_auto]">
            <PlayerSelect players={players} value={playerId} onChange={setPlayerId} label="Bowler" />
            <Field label="Date"><input className="field" type="date" value={date} max={today()} onChange={(e) => setDate(e.target.value)} /></Field>
            <Button variant="primary" busy={busy} disabled={!ok || !!err || !playerId || !canEdit(playerId)} onClick={() => save({ source: 'stopwatch', distance: d, time: t, distance_unit: du, time_unit: tu })}>Save calculated speed</Button>
            <Field label="Radar gun reading (km/h)"><input className="field num" inputMode="decimal" value={radar} placeholder="e.g. 118.5" onChange={(e) => setRadar(e.target.value)} /></Field>
            <Button busy={busy} disabled={!(parseFloat(radar) > 0 && parseFloat(radar) < 200) || !playerId || !canEdit(playerId)} onClick={() => save({ source: 'radar', kmh: parseFloat(radar) }).then(() => setRadar(''))}>Save radar reading</Button>
          </div>
        )}
        {playerId !== null && !canEdit(playerId) && <p className="mt-2 text-label text-ink-2">You can save readings only for your own player profile.</p>}
      </Section>

      {playerId && (
        <Async state={history}>
          {(h: any) => h && (
            <>
              <Section title="Speed history" aside="Calculated readings are average speeds; radar readings are near release speed">
                {h.readings.length === 0 ? <Empty title="No readings for this bowler yet">Save a calculated speed or a radar reading above.</Empty> : (
                  <>
                    <Board cols={5}>
                      <Win label="Average" value={show(h.average_speed.average)} unit={unit} hint={`${h.average_speed.count} calculated`} />
                      <Win label="Fastest" value={show(h.average_speed.max)} unit={unit} tone="accent" />
                      <Win label="Slowest" value={show(h.average_speed.min)} unit={unit} />
                      <Win label="Most recent" value={show(h.average_speed.recent)} unit={unit} />
                      <Win label="Radar best" value={show(h.radar.max)} unit={unit} hint={`${h.radar.count} radar`} />
                    </Board>
                    <div className="mt-4">
                      <SpeedChart readings={h.readings} mph={mph} />
                    </div>
                    {h.comparison && (
                      <p className="mt-3 text-ink-2">
                        On days with both kinds of reading, radar read <b className="text-ink">{fmt(h.comparison.mean_difference_kmh)} km/h higher</b> on average than the calculated speed. {h.comparison.note}
                      </p>
                    )}
                    {h.average_speed.trend.slope_per_reading != null && (
                      <p className="mt-1 text-ink-2">Trend across calculated readings: {h.average_speed.trend.change_first_to_last_third >= 0 ? '+' : ''}{fmt(h.average_speed.trend.change_first_to_last_third)} km/h between the first and last third of readings.</p>
                    )}
                  </>
                )}
              </Section>
              {h.readings.length > 0 && (
                <Section title="Readings">
                  <DataTable rows={[...h.readings].reverse()} rowKey={(r: any) => r.id} dense cols={[
                    { key: 'd', label: 'Date', render: (r: any) => day(r.date) },
                    { key: 's', label: 'Method', render: (r: any) => (r.source === 'radar' ? 'Radar (near release)' : r.source === 'video' ? 'Video (average)' : 'Distance / time (average)') },
                    { key: 'm', label: 'Distance', num: true, render: (r: any) => (r.distance_m ? `${fmt(r.distance_m, 2)} m` : '–') },
                    { key: 't', label: 'Time', num: true, render: (r: any) => (r.time_s ? `${fmt(r.time_s, 3)} s` : '–') },
                    { key: 'k', label: 'km/h', num: true, render: (r: any) => <b>{fmt(r.kmh)}</b> },
                    { key: 'p', label: 'mph', num: true, render: (r: any) => fmt(kmhToMph(r.kmh)) },
                    { key: 'x', label: '', render: (r: any) => canEdit(playerId) && <button aria-label="Delete reading" className="text-ink-2 hover:text-red" onClick={() => remove(r.id)}><Trash2 size={15} /></button> },
                  ]} />
                </Section>
              )}
            </>
          )}
        </Async>
      )}
    </div>
  )
}

function SpeedChart({ readings, mph }: { readings: any[]; mph: boolean }) {
  const conv = (v: number) => (mph ? kmhToMph(v) : v)
  const data = readings.map((r, i) => ({ n: `${i + 1}`, date: r.date, calculated: r.source !== 'radar' ? conv(r.kmh) : null, radar: r.source === 'radar' ? conv(r.kmh) : null }))
  const series = [{ key: 'calculated', label: 'Calculated (average speed)' }, { key: 'radar', label: 'Radar (near release)', colour: 'var(--red)' }]
  return <><LineTrend data={data} x="n" series={series} unit={mph ? 'mph' : 'km/h'} /><SeriesKey series={series} /><p className="text-label text-ink-2">Readings in the order they were taken.</p></>
}

/* ---------------------------------------------------------------- line and length */

function Accuracy() {
  const { players, user, canEdit } = useApp()
  const toast = useToast()
  const [playerId, setPlayerId] = useState<number | null>(user.player_id ?? players[0]?.id ?? null)
  const [sid, setSid] = useState<number | null>(null)
  const [cmpId, setCmpId] = useState<number | null>(null)
  const [hover, setHover] = useState<number | string | null>(null)
  const [view, setView] = useState<'dots' | 'heat'>('dots')
  const [settingTarget, setSettingTarget] = useState(false)
  const geometry = useAsync(() => api.get('/pitch/geometry'), [])
  const sessions = useAsync(() => api.get<any[]>(`/bowling/sessions${qs({ player_id: playerId })}`), [playerId])
  const session = useAsync(() => (sid ? api.get(`/bowling/sessions/${sid}`) : Promise.resolve(null)), [sid])
  const other = useAsync(() => (cmpId && sid ? api.get(`/bowling/compare${qs({ a: sid, b: cmpId })}`) : Promise.resolve(null)), [cmpId, sid, session.data?.count])
  const otherSession = useAsync(() => (cmpId ? api.get(`/bowling/sessions/${cmpId}`) : Promise.resolve(null)), [cmpId])
  const trend = useAsync(() => (playerId ? api.get<any[]>(`/bowling/accuracy-trend${qs({ player_id: playerId })}`) : Promise.resolve([])), [playerId, session.data?.count])

  useEffect(() => { setSid(null); setCmpId(null) }, [playerId])
  useEffect(() => { if (sid === null && sessions.data?.length) setSid(sessions.data[0].id) }, [sessions.data, sid])

  const bands: Band[] | undefined = geometry.data?.length_bands
  const editable = canEdit(playerId)
  const s = session.data

  const create = async () => {
    try {
      const made = await api.post('/bowling/sessions', { player_id: playerId, date: today(), name: '' })
      await sessions.reload(); setSid(made.id)
    } catch (e: any) { toast(e.message, 'error') }
  }
  const add = async (x: number, y: number) => {
    if (!s) return
    if (settingTarget) {
      try { session.setData(await api.put(`/bowling/sessions/${s.id}`, { player_id: s.player_id, date: s.date, name: s.name, target_x: x, target_y: y, tol_x: s.target.tol_x, tol_y: s.target.tol_y })) } catch (e: any) { toast(e.message, 'error') }
      setSettingTarget(false)
      return
    }
    try { session.setData(await api.post(`/bowling/sessions/${s.id}/deliveries`, { x, y })) } catch (e: any) { toast(e.message, 'error') }
  }
  const removeDelivery = async (id: number) => { try { session.setData(await api.del(`/bowling/deliveries/${id}`)) } catch (e: any) { toast(e.message, 'error') } }
  const updateTarget = async (patch: Record<string, number | string>) => {
    if (!s) return
    const body = { player_id: s.player_id, date: s.date, name: s.name, target_x: s.target.x, target_y: s.target.y, tol_x: s.target.tol_x, tol_y: s.target.tol_y, ...patch }
    try { session.setData(await api.put(`/bowling/sessions/${s.id}`, body)); sessions.reload() } catch (e: any) { toast(e.message, 'error') }
  }
  const removeSession = async () => {
    if (!s || !window.confirm(`Delete this session and its ${s.count} deliveries? This cannot be undone.`)) return
    try { await api.del(`/bowling/sessions/${s.id}`); setSid(null); sessions.reload() } catch (e: any) { toast(e.message, 'error') }
  }

  const dots = useMemo(() => {
    const a = (s?.deliveries ?? []).map((d: any, i: number) => ({ id: d.id, x: d.x, y: d.y, tone: 'a' as const, title: `Ball ${i + 1}: ${words(d.length)} length, ${words(d.line)} line` }))
    const b = (otherSession.data?.deliveries ?? []).map((d: any) => ({ id: `b${d.id}`, x: d.x, y: d.y, tone: 'b' as const }))
    return cmpId ? [...b, ...a] : a
  }, [s, otherSession.data, cmpId])

  if (players.length === 0) return <NeedPlayers />
  return (
    <div>
      <div className="mb-5 grid items-end gap-3 sm:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)_auto]">
        <PlayerSelect players={players} value={playerId} onChange={setPlayerId} label="Bowler" />
        <Field label="Session">
          <select className="field" value={sid ?? ''} onChange={(e) => setSid(e.target.value ? Number(e.target.value) : null)} disabled={!sessions.data?.length}>
            {!sessions.data?.length && <option value="">No sessions yet</option>}
            {sessions.data?.map((x) => <option key={x.id} value={x.id}>{day(x.date)}{x.name ? ` · ${x.name}` : ''} · {x.count} balls</option>)}
          </select>
        </Field>
        <Button variant="primary" disabled={!playerId || !editable} onClick={create}>New session</Button>
      </div>

      {!s ? (
        <Empty title="No line-and-length session selected">Start a session, then click the pitch map where each delivery lands. Accuracy is measured against the target box you set.</Empty>
      ) : (
        <div className="grid gap-8 lg:grid-cols-[400px_minmax(0,1fr)]">
          <div>
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
              <Seg label="Map view" value={view} onChange={setView} options={[{ id: 'dots', label: 'Deliveries' }, { id: 'heat', label: 'Heatmap' }]} />
              {editable && <Button small variant={settingTarget ? 'primary' : 'default'} onClick={() => setSettingTarget(!settingTarget)}>{settingTarget ? 'Click the pitch to place the target' : 'Move target'}</Button>}
            </div>
            <Pitch dots={view === 'dots' ? dots : []} heat={view === 'heat' ? s.heatmap : null} bands={bands} target={s.target} onAdd={editable ? add : undefined}
              highlight={hover} onHover={setHover} />
            <p className="mt-1 text-label text-ink-2">{editable ? 'Click where a ball pitched to record it. ' : ''}The map is widened across the pitch so differences in line are readable; it is not to scale.{cmpId ? ' Green dots are the comparison session.' : ''}</p>
          </div>
          <div className="min-w-0">
            <Board cols={4}>
              <Win label="Deliveries" value={s.accuracy.total || null} />
              <Win label="In target zone" value={s.accuracy.total ? pct(s.accuracy.hit_pct) : null} tone="accent" hint={s.accuracy.total ? `${s.accuracy.hits} of ${s.accuracy.total}` : 'Click the map'} />
              <Win label="Average miss" value={s.accuracy.total ? fmt(s.accuracy.mean_error_m, 2) : null} unit="m" />
              <Win label="Consistency" value={s.accuracy.consistency_index != null ? fmt(s.accuracy.consistency_index, 0) : null} hint="0–100, grouping tightness" />
            </Board>
            {s.accuracy.total >= 2 && (
              <p className="mt-2 text-ink-2">
                The group is centred {Math.abs(s.accuracy.bias_x * 100).toFixed(0)} cm {s.accuracy.bias_x >= 0 ? 'to the off side' : 'to the leg side'} of the target and {Math.abs(s.accuracy.bias_y).toFixed(1)} m {s.accuracy.bias_y >= 0 ? 'shorter' : 'fuller'}. Spread (standard deviation): {(s.accuracy.spread_x * 100).toFixed(0)} cm in line, {s.accuracy.spread_y.toFixed(1)} m in length.
              </p>
            )}

            <Section title="Target line and length">
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                <NumField label="Line (m from middle)" value={s.target.x} step={0.05} min={-1.5} max={1.5} disabled={!editable} onCommit={(v) => updateTarget({ target_x: v })} hint="+ is off side" />
                <NumField label="Length (m from stumps)" value={s.target.y} step={0.5} min={0} max={20} disabled={!editable} onCommit={(v) => updateTarget({ target_y: v })} />
                <NumField label="Line tolerance (m)" value={s.target.tol_x} step={0.05} min={0.05} max={1.5} disabled={!editable} onCommit={(v) => updateTarget({ tol_x: v })} />
                <NumField label="Length tolerance (m)" value={s.target.tol_y} step={0.25} min={0.25} max={10} disabled={!editable} onCommit={(v) => updateTarget({ tol_y: v })} />
              </div>
            </Section>

            <Section title="Delivery distribution">
              {s.distribution.total === 0 ? <p className="text-ink-2">No deliveries recorded in this session yet.</p> : (
                <div className="grid gap-6 md:grid-cols-2">
                  <Bars data={s.distribution.length.map((r: any) => ({ band: cap(r.band), Deliveries: r.count }))} x="band" series={[{ key: 'Deliveries', label: 'By length' }]} height={180} />
                  <Bars data={s.distribution.line.map((r: any) => ({ band: cap(r.band), Deliveries: r.count }))} x="band" series={[{ key: 'Deliveries', label: 'By line', colour: 'var(--green)' }]} height={180} />
                </div>
              )}
            </Section>

            <Section title="Compare with another session" aside="Both measured against this session's target">
              <Field label="Comparison session" className="max-w-[360px]">
                <select className="field" value={cmpId ?? ''} onChange={(e) => setCmpId(e.target.value ? Number(e.target.value) : null)}>
                  <option value="">None</option>
                  {sessions.data?.filter((x) => x.id !== s.id).map((x) => <option key={x.id} value={x.id}>{day(x.date)}{x.name ? ` · ${x.name}` : ''} · {x.count} balls</option>)}
                </select>
              </Field>
              {other.data && (
                <div className="mt-3">
                  <DataTable dense rowKey={(r: any) => r.k} rows={[
                    { k: 'In target zone', a: pct(other.data.a.hit_pct), b: pct(other.data.b.hit_pct), d: other.data.change.hit_pct, u: ' pts', good: 1 },
                    { k: 'Average miss (m)', a: fmt(other.data.a.mean_error_m, 2), b: fmt(other.data.b.mean_error_m, 2), d: other.data.change.mean_error_m, u: ' m', good: -1 },
                    { k: 'Line spread (cm)', a: fmt(other.data.a.spread_x * 100, 0), b: fmt(other.data.b.spread_x * 100, 0), d: other.data.change.spread_x * 100, u: ' cm', good: -1 },
                    { k: 'Length spread (m)', a: fmt(other.data.a.spread_y, 2), b: fmt(other.data.b.spread_y, 2), d: other.data.change.spread_y, u: ' m', good: -1 },
                  ]} cols={[
                    { key: 'k', label: 'Measure', render: (r: any) => r.k },
                    { key: 'a', label: 'This session', num: true, render: (r: any) => r.a },
                    { key: 'b', label: 'Comparison', num: true, render: (r: any) => r.b },
                    { key: 'd', label: 'Comparison minus this', num: true, render: (r: any) => (r.d == null || Number.isNaN(r.d) ? '–' : <span className={r.d * r.good > 0 ? 'text-green' : r.d * r.good < 0 ? 'text-red' : ''}>{r.d > 0 ? '+' : ''}{fmt(r.d, 2)}{r.u}</span>) },
                  ]} />
                </div>
              )}
            </Section>

            {(trend.data?.length ?? 0) > 1 && (
              <Section title="Accuracy across sessions">
                <LineTrend data={trend.data!.map((x) => ({ date: day(x.date), 'In target zone': x.hit_pct }))} x="date" series={[{ key: 'In target zone', label: 'In target zone (%)' }]} unit="%" domain={[0, 100]} height={180} />
              </Section>
            )}

            <Section title="Deliveries" aside={editable && s.count > 0 ? <Button small variant="danger" onClick={removeSession}>Delete session</Button> : undefined}>
              {s.deliveries.length === 0 ? <p className="text-ink-2">Click the pitch map to record the first delivery.</p> : (
                <div className="max-h-[320px] overflow-y-auto">
                  <DataTable rows={s.deliveries} rowKey={(r: any) => r.id} dense onHover={(r: any) => setHover(r ? r.id : null)} active={(r: any) => r.id === hover} cols={[
                    { key: 'n', label: 'Ball', num: true, render: (_: any, i) => i + 1 },
                    { key: 'l', label: 'Length', render: (r: any) => cap(r.length) },
                    { key: 'i', label: 'Line', render: (r: any) => cap(r.line) },
                    { key: 'y', label: 'From stumps', num: true, render: (r: any) => `${fmt(r.y)} m` },
                    { key: 'x', label: 'Across', num: true, render: (r: any) => `${r.x >= 0 ? '+' : ''}${fmt(r.x * 100, 0)} cm` },
                    { key: 'd', label: '', render: (r: any) => editable && <button aria-label="Remove delivery" className="text-ink-2 hover:text-red" onClick={() => removeDelivery(r.id)}><Trash2 size={15} /></button> },
                  ]} />
                </div>
              )}
            </Section>
          </div>
        </div>
      )}
    </div>
  )
}

function NumField({ label, value, onCommit, step, min, max, disabled, hint }: { label: string; value: number; onCommit: (v: number) => void; step: number; min: number; max: number; disabled?: boolean; hint?: string }) {
  const [text, setText] = useState(String(value))
  useEffect(() => setText(String(value)), [value])
  const commit = () => { const v = parseFloat(text); if (Number.isFinite(v) && v >= min && v <= max && v !== value) onCommit(v); else setText(String(value)) }
  return (
    <Field label={label} hint={hint}>
      <input className="field num" type="number" step={step} min={min} max={max} value={text} disabled={disabled}
        onChange={(e) => setText(e.target.value)} onBlur={commit} onKeyDown={(e) => { if (e.key === 'Enter') (e.target as HTMLInputElement).blur() }} />
    </Field>
  )
}

/* ---------------------------------------------------------------- tracking and movement */

function Tracking() {
  const { players, user } = useApp()
  const [playerId, setPlayerId] = useState<number | null>(user.player_id)
  return (
    <div>
      <div className="mb-5 max-w-[320px]"><PlayerSelect players={players} value={playerId} onChange={setPlayerId} label="Bowler" allowEmpty="Not linked to a player" /></div>
      <BallTrack playerId={playerId} />
      <div className="mt-6"><Notice title="Limits of single-camera ball tracking">
        At 30 frames per second a 100 km/h ball moves almost a metre between frames and blurs into a streak. The ball is a few pixels wide and is often hidden by the bowler or batter. Each estimate here carries a confidence level. Use it as a training aid.
      </Notice></div>
    </div>
  )
}

function Movement() {
  const [cmp, setCmp] = useState<{ a: number | null; b: number | null }>({ a: null, b: null })
  const list = useAsync(() => api.get<any[]>('/video/analyses?kind=tracking'), [])
  const full = useAsync(async () => {
    const rows = list.data ?? []
    return Promise.all(rows.slice(0, 30).map((r) => api.get(`/video/analyses/${r.id}`)))
  }, [list.data])
  const comparison = useAsync(() => (cmp.a && cmp.b && cmp.a !== cmp.b ? api.get(`/video/compare${qs({ a: cmp.a, b: cmp.b })}`) : Promise.resolve(null)), [cmp.a, cmp.b])
  const measured = (full.data ?? []).filter((v: any) => v.result.status === 'ok' && v.result.movement?.swing?.status === 'measured')
  return (
    <div>
      <Notice title="How movement is separated from noise">
        Swing is the gap between where the ball was just before it bounced and where its initial line pointed. Seam is the change in sideways speed across the bounce. Each is compared with the scatter of the tracked points: only a movement at least three times its own standard error is reported as movement. Anything smaller is labelled within tracking noise.
      </Notice>
      <Section title="Tracked deliveries" aside={measured.length ? 'Choose A and B to compare two deliveries' : undefined}>
        <Async state={full}>
          {(rows: any[]) => rows.length === 0 ? <NoTracks /> : (
            <DataTable rows={rows} rowKey={(r: any) => r.id} dense cols={[
              { key: 'd', label: 'Date', render: (r: any) => day(r.created_at) },
              { key: 'p', label: 'Bowler', render: (r: any) => r.player ?? '–' },
              { key: 'l', label: 'Label', render: (r: any) => r.label || r.filename },
              { key: 's', label: 'Swing', render: (r: any) => r.result.movement?.swing?.label ?? (r.result.status === 'ok' ? 'Too few points' : 'Not tracked') },
              { key: 'sd', label: 'Deviation', num: true, render: (r: any) => (r.result.movement?.swing?.deviation != null ? `${fmt(r.result.movement.swing.deviation)} ${r.result.movement.units}` : '–') },
              { key: 'm', label: 'Seam', render: (r: any) => r.result.movement?.seam?.label ?? '–' },
              { key: 'c', label: 'Confidence', render: (r: any) => cap(r.result.confidence_label) },
              { key: 'a', label: 'A', render: (r: any) => <input type="radio" name="mv-a" aria-label="Use as delivery A" checked={cmp.a === r.id} onChange={() => setCmp({ ...cmp, a: r.id })} /> },
              { key: 'b', label: 'B', render: (r: any) => <input type="radio" name="mv-b" aria-label="Use as delivery B" checked={cmp.b === r.id} onChange={() => setCmp({ ...cmp, b: r.id })} /> },
            ]} />
          )}
        </Async>
      </Section>
      {comparison.data && (
        <Section title="Delivery A against delivery B">
          <DataTable rows={comparison.data.rows} rowKey={(r: any) => r.metric} dense cols={[
            { key: 'm', label: 'Measurement', render: (r: any) => cap(r.metric.replace(' z', ' (standard errors)')) },
            { key: 'a', label: 'A', num: true, render: (r: any) => fmt(r.a, 2) },
            { key: 'b', label: 'B', num: true, render: (r: any) => fmt(r.b, 2) },
            { key: 'd', label: 'B minus A', num: true, render: (r: any) => fmt(r.difference, 2) },
          ]} />
          <p className="mt-2 text-label text-ink-2">{comparison.data.note}</p>
        </Section>
      )}
      {measured.length > 1 && (
        <Section title="Movement across tracked deliveries" aside="Oldest first">
          <LineTrend data={[...measured].reverse().map((v: any, i: number) => ({ n: `${i + 1}`, Swing: Math.abs(v.result.movement.swing.deviation), Noise: v.result.movement.swing.std_error * 3 }))} x="n"
            series={[{ key: 'Swing', label: 'Swing deviation (absolute)' }, { key: 'Noise', label: 'Reporting threshold (3 standard errors)', colour: 'var(--ink-2)', dashed: true }]} height={200} />
          <SeriesKey series={[{ key: 'Swing', label: 'Swing deviation (absolute)' }, { key: 'Noise', label: 'Reporting threshold (3 standard errors)', colour: 'var(--ink-2)' }]} />
          <p className="text-label text-ink-2">Values are comparable only between clips filmed from the same fixed camera position.</p>
        </Section>
      )}
    </div>
  )
}
