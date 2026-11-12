import { ArrowLeft } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, Route, Routes, useNavigate, useParams } from 'react-router-dom'
import { useApp } from '../context'
import type { Player } from '../context'
import { LineTrend } from '../components/Chart'
import { Ground } from '../components/Ground'
import { Async, Board, Button, DataTable, Empty, Field, Notice, Page, PlayerSelect, Section, Tabs, Win, useAsync, useToast } from '../components/ui'
import { api, qs } from '../lib/api'
import { ROLE_LABEL, STYLE_LABEL, cap, day, fmt, pct } from '../lib/format'

export default function TeamHub() {
  return (
    <Routes>
      <Route path="/" element={<Hub />} />
      <Route path="player/:id" element={<Profile />} />
    </Routes>
  )
}

type Tab = 'players' | 'selection' | 'opposition' | 'leaderboards'

function Hub() {
  const [tab, setTab] = useState<Tab>('players')
  return (
    <Page title="Team Hub" lead="The squad, each player's record, team selection, opposition scouting and leaderboards.">
      <Tabs value={tab} onChange={setTab} tabs={[{ id: 'players', label: 'Players' }, { id: 'selection', label: 'Selection assistant' }, { id: 'opposition', label: 'Opposition' }, { id: 'leaderboards', label: 'Leaderboards' }]} />
      {tab === 'players' && <Players />}
      {tab === 'selection' && <Selection />}
      {tab === 'opposition' && <Opposition />}
      {tab === 'leaderboards' && <Leaderboards />}
    </Page>
  )
}

/* ---------------------------------------------------------------- filters */

function SeasonFilter({ season, format, onChange }: { season: string; format: string; onChange: (s: string, f: string) => void }) {
  const { team } = useApp()
  return (
    <div className="mb-4 flex flex-wrap gap-3">
      <Field label="Season" className="w-40"><select className="field" value={season} onChange={(e) => onChange(e.target.value, format)}><option value="">All seasons</option>{team.seasons.map((s) => <option key={s}>{s}</option>)}</select></Field>
      <Field label="Format" className="w-40"><select className="field" value={format} onChange={(e) => onChange(season, e.target.value)}><option value="">All formats</option>{team.formats.map((s) => <option key={s}>{s}</option>)}</select></Field>
    </div>
  )
}

/* ---------------------------------------------------------------- players */

const BLANK = { name: '', role: 'batter', batting_hand: 'right', bowl_style: '', active: true, notes: '' }

function Players() {
  const { players, isCoach, reloadPlayers } = useApp()
  const toast = useToast()
  const nav = useNavigate()
  const [form, setForm] = useState<any>(BLANK)
  const [editing, setEditing] = useState<number | null>(null)
  const [season, setSeason] = useState('')
  const [format, setFormat] = useState('')
  const tables = useAsync(() => api.get(`/stats/tables${qs({ season, format })}`), [season, format, players.length])

  const save = async (e: React.FormEvent) => {
    e.preventDefault()
    const body = { ...form, side: 'us', bowl_style: form.bowl_style || null }
    try {
      if (editing) await api.put(`/players/${editing}`, body); else await api.post('/players', body)
      toast(editing ? 'Player updated' : 'Player added'); setForm(BLANK); setEditing(null); await reloadPlayers()
    } catch (err: any) { toast(err.message, 'error') }
  }
  const remove = async (p: Player) => {
    if (!window.confirm(`Delete ${p.name}? Their speed readings, sessions and goals are deleted too. This cannot be undone.`)) return
    try { await api.del(`/players/${p.id}`); toast('Player deleted'); await reloadPlayers() } catch (err: any) { toast(err.message, 'error') }
  }
  const bat = (id: number) => tables.data?.batting.find((r: any) => r.player === id)
  const bowl = (id: number) => tables.data?.bowling.find((r: any) => r.player === id)

  return (
    <div>
      {isCoach && (
        <Section title={editing ? 'Edit player' : 'Add a player'}>
          <form onSubmit={save} className="grid items-end gap-3 sm:grid-cols-2 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)_120px_minmax(0,1fr)_auto]">
            <Field label="Name"><input className="field" required maxLength={120} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></Field>
            <Field label="Role"><select className="field" value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>{Object.entries(ROLE_LABEL).map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></Field>
            <Field label="Bats"><select className="field" value={form.batting_hand} onChange={(e) => setForm({ ...form, batting_hand: e.target.value })}><option value="right">Right hand</option><option value="left">Left hand</option></select></Field>
            <Field label="Bowling"><select className="field" value={form.bowl_style ?? ''} onChange={(e) => setForm({ ...form, bowl_style: e.target.value })}><option value="">Does not bowl</option>{Object.entries(STYLE_LABEL).map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></Field>
            <div className="flex gap-2">
              <Button variant="primary" type="submit">{editing ? 'Save changes' : 'Add player'}</Button>
              {editing && <Button type="button" onClick={() => { setEditing(null); setForm(BLANK) }}>Cancel</Button>}
            </div>
          </form>
        </Section>
      )}
      <Section title={`Squad (${players.length})`}>
        {players.length === 0 ? <Empty title="No players yet">{isCoach ? 'Add each squad member above. Statistics are built from the matches and sessions you record for them.' : 'Your coach has not added the squad yet.'}</Empty> : (
          <>
            <SeasonFilter season={season} format={format} onChange={(s, f) => { setSeason(s); setFormat(f) }} />
            <DataTable rows={players} rowKey={(p) => p.id} onRow={(p) => nav(`/team/player/${p.id}`)} cols={[
              { key: 'n', label: 'Player', render: (p) => <span className="font-semibold">{p.name}{p.is_sample && <span className="painted ml-2 text-label text-ink-2">Sample</span>}{!p.active && <span className="painted ml-2 text-label text-ink-2">Inactive</span>}</span> },
              { key: 'r', label: 'Role', render: (p) => ROLE_LABEL[p.role] },
              { key: 'b', label: 'Bowling', render: (p) => (p.bowl_style ? STYLE_LABEL[p.bowl_style] : '–') },
              { key: 'i', label: 'Inns', num: true, render: (p) => bat(p.id)?.innings ?? '–' },
              { key: 'ru', label: 'Runs', num: true, render: (p) => bat(p.id)?.runs ?? '–' },
              { key: 'av', label: 'Avg', num: true, render: (p) => fmt(bat(p.id)?.average) },
              { key: 'sr', label: 'SR', num: true, render: (p) => fmt(bat(p.id)?.strike_rate, 0) },
              { key: 'w', label: 'Wkts', num: true, render: (p) => bowl(p.id)?.wickets ?? '–' },
              { key: 'e', label: 'Econ', num: true, render: (p) => fmt(bowl(p.id)?.economy, 2) },
              ...(isCoach ? [{ key: 'x', label: '', render: (p: Player) => (
                <div className="flex justify-end gap-1" onClick={(e) => e.stopPropagation()}>
                  <Button small variant="quiet" onClick={() => { setEditing(p.id); setForm({ ...p, bowl_style: p.bowl_style ?? '' }); window.scrollTo({ top: 0, behavior: 'smooth' }) }}>Edit</Button>
                  <Button small variant="quiet" onClick={() => remove(p)}>Delete</Button>
                </div>
              ) }] : []),
            ]} />
          </>
        )}
      </Section>
    </div>
  )
}

/* ---------------------------------------------------------------- profile */

function Profile() {
  const { id } = useParams()
  const state = useAsync(() => api.get(`/players/${id}/profile`), [id])
  return (
    <Async state={state}>
      {(p: any) => {
        const b = p.batting, w = p.bowling, f = p.fielding
        const scores = b?.scores.map((s: any, i: number) => ({ n: `${i + 1}`, Runs: s.runs })) ?? []
        const speeds = p.speeds.map((s: any, i: number) => ({ n: `${i + 1}`, Speed: s.kmh }))
        return (
          <Page title={p.player.name} lead={`${ROLE_LABEL[p.player.role]} · bats ${p.player.batting_hand}-handed${p.player.bowl_style ? ` · ${STYLE_LABEL[p.player.bowl_style]}` : ''}${p.player.side !== 'us' ? ` · ${p.player.side}` : ''}`}
            actions={<Link to="/team"><Button><ArrowLeft size={16} aria-hidden />Team Hub</Button></Link>}>
            {p.player.is_sample && <div className="mb-4"><Notice tone="warn">This is a synthetic sample player. The figures below are computer-generated, not real performance.</Notice></div>}
            <Section title="Batting">
              {b ? (
                <Board cols={6}>
                  <Win label="Innings" value={b.innings} hint={`${b.not_outs} not out`} />
                  <Win label="Runs" value={b.runs} tone="accent" />
                  <Win label="Average" value={fmt(b.average)} hint={b.average == null ? 'never dismissed' : undefined} />
                  <Win label="Strike rate" value={fmt(b.strike_rate, 0)} />
                  <Win label="Highest score" value={b.highest_text} />
                  <Win label="Fours / sixes" value={`${b.fours}/${b.sixes}`} />
                </Board>
              ) : <p className="text-ink-2">No innings recorded.</p>}
            </Section>
            <Section title="Bowling">
              {w ? (
                <Board cols={6}>
                  <Win label="Overs" value={w.overs} />
                  <Win label="Runs conceded" value={w.runs} />
                  <Win label="Wickets" value={w.wickets} tone="accent" />
                  <Win label="Average" value={fmt(w.average)} hint={w.average == null ? 'no wickets yet' : undefined} />
                  <Win label="Economy" value={fmt(w.economy, 2)} />
                  <Win label="Strike rate" value={fmt(w.strike_rate)} hint="balls per wicket" />
                </Board>
              ) : <p className="text-ink-2">No overs recorded.</p>}
              {p.speed_summary.count > 0 && (
                <div className="mt-4"><Board cols={4}>
                  <Win label="Fastest recorded" value={fmt(p.speed_summary.max)} unit="km/h" />
                  <Win label="Average recorded" value={fmt(p.speed_summary.average)} unit="km/h" />
                  <Win label="Readings" value={p.speed_summary.count} />
                  <Win label="Practice accuracy" value={p.accuracy?.total ? pct(p.accuracy.hit_pct) : null} hint={p.accuracy?.total ? `${p.accuracy.total} deliveries` : undefined} />
                </Board></div>
              )}
            </Section>
            <Section title="Fielding">
              {f ? (
                <Board cols={5}>
                  <Win label="Catches" value={f.catch} tone="accent" />
                  <Win label="Catch success" value={pct(f.catch_pct)} hint={`${f.catch_chances} chances`} />
                  <Win label="Run-outs" value={f.run_outs_total} />
                  <Win label="Stumpings" value={f.stumping} />
                  <Win label="Ground fielding" value={pct(f.ground_pct)} hint="clean stops" />
                </Board>
              ) : <p className="text-ink-2">No fielding recorded.</p>}
            </Section>
            <div className="mt-8 grid gap-x-10 gap-y-8 lg:grid-cols-2">
              {scores.length > 1 && <Section title="Runs by innings" aside="Oldest first"><LineTrend data={scores} x="n" series={[{ key: 'Runs', label: 'Runs' }]} height={180} /></Section>}
              {speeds.length > 1 && <Section title="Recorded speeds" aside="Oldest first"><LineTrend data={speeds} x="n" series={[{ key: 'Speed', label: 'Speed' }]} unit="km/h" height={180} /></Section>}
            </div>
            {p.wagon_wheel.total_runs > 0 && (
              <Section title="Where the runs come from">
                <div className="grid gap-6 md:grid-cols-[minmax(0,360px)_minmax(0,1fr)]">
                  <Ground shots={p.wagon_wheel.shots} zones={p.wagon_wheel.zones} />
                  <SplitMini splits={p.splits} />
                </div>
              </Section>
            )}
            <Section title="Coaching recommendations" aside="Each is triggered by a recorded figure">
              {p.recommendations.length ? (
                <ul className="flex flex-col">
                  {p.recommendations.map((r: any) => (
                    <li key={r.area} className="border-b border-rule py-2.5">
                      <div><b>{r.area}.</b> {r.recommendation}</div>
                      <div className="text-ink-2">Drill: {r.drill}</div>
                      <div className="text-label text-ink-2">Evidence: {r.evidence}</div>
                    </li>
                  ))}
                </ul>
              ) : <p className="text-ink-2">Nothing in this player's record crosses a coaching threshold yet. That usually means there is too little recorded data.</p>}
            </Section>
            <div className="mt-8 grid gap-x-10 gap-y-8 lg:grid-cols-2">
              <Section title="Goals" aside={<Link className="underline" to="/coach">Manage in AI Coach</Link>}>
                {p.goals.length ? <DataTable dense rows={p.goals} rowKey={(g: any) => g.id} cols={[
                  { key: 't', label: 'Goal', render: (g: any) => g.title },
                  { key: 'd', label: 'Due', render: (g: any) => day(g.due_date) },
                  { key: 's', label: 'Status', render: (g: any) => cap(g.status) },
                ]} /> : <p className="text-ink-2">No goals set.</p>}
              </Section>
              <Section title="Training sessions">
                {p.training.length ? <DataTable dense rows={p.training.slice(0, 8)} rowKey={(g: any) => g.id} cols={[
                  { key: 'd', label: 'Date', render: (g: any) => day(g.date) },
                  { key: 'k', label: 'Type', render: (g: any) => cap(g.kind) },
                  { key: 'm', label: 'Minutes', num: true, render: (g: any) => g.duration_min },
                ]} /> : <p className="text-ink-2">No training logged.</p>}
              </Section>
            </div>
          </Page>
        )
      }}
    </Async>
  )
}

function SplitMini({ splits }: { splits: any }) {
  const rows = [...Object.entries<any>(splits.bowl_type ?? {}).map(([k, v]) => ({ k: `Against ${k}`, ...v })), ...Object.entries<any>(splits.length ?? {}).map(([k, v]) => ({ k: `${cap(k)} length`, ...v }))]
  if (!rows.length) return <p className="text-ink-2">No bowling detail was recorded for the balls this batter faced.</p>
  return <DataTable dense rows={rows} rowKey={(r: any) => r.k} cols={[
    { key: 'k', label: '', render: (r: any) => r.k },
    { key: 'b', label: 'Balls', num: true, render: (r: any) => r.balls },
    { key: 'r', label: 'Runs', num: true, render: (r: any) => r.runs },
    { key: 'o', label: 'Outs', num: true, render: (r: any) => r.dismissals },
    { key: 's', label: 'SR', num: true, render: (r: any) => fmt(r.strike_rate, 0) },
  ]} />
}

/* ---------------------------------------------------------------- selection */

function Selection() {
  const { players, team } = useApp()
  const toast = useToast()
  const active = players.filter((p) => p.active)
  const [avail, setAvail] = useState<Set<number>>(new Set(active.map((p) => p.id)))
  const [overs, setOvers] = useState(String(team.default_overs))
  const [res, setRes] = useState<any | null>(null)
  const [alt, setAlt] = useState<number[] | null>(null)
  const [cmp, setCmp] = useState<any | null>(null)
  useEffect(() => { setAvail(new Set(active.map((p) => p.id))) /* eslint-disable-next-line */ }, [players.length])

  const run = async () => {
    try { const r = await api.post('/team/select', { available: [...avail], overs: parseInt(overs, 10) || 20 }); setRes(r); setAlt(r.xi.map((p: any) => p.id)); setCmp(null) } catch (e: any) { toast(e.message, 'error') }
  }
  const compare = async (ids: number[]) => {
    setAlt(ids)
    if (!res) return
    try { setCmp(await api.post('/team/compare', { a: res.xi.map((p: any) => p.id), b: ids, overs: parseInt(overs, 10) || 20 })) } catch (e: any) { toast(e.message, 'error') }
  }
  const toggle = (id: number) => { const s = new Set(avail); s.has(id) ? s.delete(id) : s.add(id); setAvail(s) }

  if (active.length === 0) return <Empty title="Add the squad first">The selection assistant picks from players marked available. Add players on the Players tab.</Empty>
  return (
    <div className="grid gap-8 lg:grid-cols-[300px_minmax(0,1fr)]">
      <div>
        <Section title={`Available (${avail.size} of ${active.length})`}>
          <ul className="flex flex-col">
            {active.map((p) => (
              <li key={p.id} className="border-b border-rule"><label className="flex cursor-pointer items-center gap-2.5 py-1.5"><input type="checkbox" checked={avail.has(p.id)} onChange={() => toggle(p.id)} /><span className="min-w-0 flex-1 truncate">{p.name}</span><span className="text-label text-ink-2">{ROLE_LABEL[p.role]}</span></label></li>
            ))}
          </ul>
          <div className="mt-3 flex items-end gap-2">
            <Field label="Match overs" className="w-28"><input className="field num" type="number" min={1} max={100} value={overs} onChange={(e) => setOvers(e.target.value)} /></Field>
            <Button variant="primary" onClick={run}>Suggest an XI</Button>
          </div>
        </Section>
      </div>
      <div className="min-w-0">
        {!res && <Empty title="No suggestion yet">Tick who is available and ask for an XI. Each pick is listed with the statistics behind it.</Empty>}
        {res && !res.enough_players && <Notice tone="warn" title="Not enough players">{res.note}</Notice>}
        {res?.enough_players && (
          <>
            <Section title="Suggested XI in batting order">
              <DataTable rows={res.xi} rowKey={(r: any) => r.id} cols={[
                { key: 'n', label: 'No.', num: true, render: (r: any) => r.position },
                { key: 'p', label: 'Player', render: (r: any) => <b>{r.name}</b> },
                { key: 'r', label: 'Role', render: (r: any) => ROLE_LABEL[r.role] },
                { key: 'w', label: 'Why', render: (r: any) => <span className="text-ink-2">{res.reasons.find((x: any) => x.player === r.name)?.reason}</span> },
              ]} />
            </Section>
            <Analysis a={res.analysis} />
            {res.left_out.length > 0 && (
              <Section title="Left out">
                <DataTable dense rows={res.left_out} rowKey={(r: any) => r.player} cols={[
                  { key: 'p', label: 'Player', render: (r: any) => r.player },
                  { key: 'r', label: 'Role', render: (r: any) => ROLE_LABEL[r.role] },
                  { key: 'w', label: 'Why', render: (r: any) => <span className="text-ink-2">{r.reason}</span> },
                ]} />
              </Section>
            )}
            <Section title="Try an alternative" aside="Swap one player for another and compare">
              <Swap res={res} players={active.filter((p) => avail.has(p.id))} alt={alt ?? []} onChange={compare} />
              {cmp && (
                <div className="mt-3">
                  <DataTable dense rowKey={(r: any) => r.k} rows={[
                    { k: 'Batting depth', a: cmp.a.batting_depth, b: cmp.b.batting_depth },
                    { k: 'Bowling options', a: cmp.a.bowling_options, b: cmp.b.bowling_options },
                    { k: 'Overs covered', a: cmp.a.overs_covered, b: cmp.b.overs_covered },
                    { k: 'Sum of runs per innings', a: fmt(cmp.a.runs_per_innings_sum), b: fmt(cmp.b.runs_per_innings_sum) },
                    { k: 'Spin options', a: cmp.a.spin_options.length, b: cmp.b.spin_options.length },
                  ]} cols={[
                    { key: 'k', label: 'Measure', render: (r: any) => r.k },
                    { key: 'a', label: 'Suggested XI', num: true, render: (r: any) => r.a },
                    { key: 'b', label: 'Alternative', num: true, render: (r: any) => r.b },
                  ]} />
                  {cmp.b.warnings.length > 0 && <p className="mt-2 text-ink-2">Alternative: {cmp.b.warnings.join(' ')}</p>}
                </div>
              )}
            </Section>
            <Section title="Assumptions">
              <ul className="list-disc space-y-1 pl-5 text-ink-2">{res.assumptions.map((a: string) => <li key={a}>{a}</li>)}</ul>
            </Section>
          </>
        )}
      </div>
    </div>
  )
}

function Analysis({ a }: { a: any }) {
  return (
    <Section title="Balance of the side">
      <Board cols={4}>
        <Win label="Batting depth" value={a.batting_depth} hint="from the top, averaging 15+" />
        <Win label="Bowling options" value={a.bowling_options} />
        <Win label="Pace / spin" value={`${a.pace_options.length}/${a.spin_options.length}`} />
        <Win label="Overs covered" value={a.overs_covered} hint={`${a.overs_per_bowler_cap} per bowler`} />
      </Board>
      {a.warnings.length > 0 && <div className="mt-3"><Notice tone="warn">{a.warnings.join(' ')}</Notice></div>}
    </Section>
  )
}

function Swap({ res, players, alt, onChange }: { res: any; players: Player[]; alt: number[]; onChange: (ids: number[]) => void }) {
  const [out, setOut] = useState<number | null>(null)
  const [inn, setInn] = useState<number | null>(null)
  const xi = res.xi.map((p: any) => ({ id: p.id, name: p.name }))
  const bench = players.filter((p) => !res.xi.some((x: any) => x.id === p.id))
  if (bench.length === 0) return <p className="text-ink-2">Everyone available is already in the XI, so there is no alternative to compare.</p>
  return (
    <div className="flex flex-wrap items-end gap-2">
      <PlayerSelect players={xi} value={out} onChange={setOut} label="Take out" className="w-52" />
      <PlayerSelect players={bench} value={inn} onChange={setInn} label="Bring in" className="w-52" />
      <Button disabled={!out || !inn} onClick={() => onChange(res.xi.map((p: any) => (p.id === out ? inn! : p.id)))}>Compare</Button>
      {alt.length > 0 && <span className="text-label text-ink-2" />}
    </div>
  )
}

/* ---------------------------------------------------------------- opposition */

function Opposition() {
  const { isCoach, reloadPlayers } = useApp()
  const toast = useToast()
  const teams = useAsync(() => api.get<any[]>('/opposition/teams'), [])
  const [pid, setPid] = useState<number | null>(null)
  const [form, setForm] = useState({ name: '', side: '', role: 'batter', bowl_style: '' })
  const report = useAsync(() => (pid ? api.get(`/opposition/report${qs({ player_id: pid })}`) : Promise.resolve(null)), [pid])

  const add = async (e: React.FormEvent) => {
    e.preventDefault()
    try { await api.post('/players', { ...form, bowl_style: form.bowl_style || null }); toast('Opposition player added'); setForm({ ...form, name: '' }); teams.reload(); reloadPlayers() } catch (err: any) { toast(err.message, 'error') }
  }
  return (
    <div>
      {isCoach && (
        <Section title="Record an opposition player">
          <form onSubmit={add} className="grid items-end gap-3 sm:grid-cols-2 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_minmax(0,0.8fr)_minmax(0,0.8fr)_auto]">
            <Field label="Player name"><input className="field" required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></Field>
            <Field label="Their team"><input className="field" required value={form.side} placeholder="e.g. Northfield School" onChange={(e) => setForm({ ...form, side: e.target.value })} /></Field>
            <Field label="Role"><select className="field" value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>{Object.entries(ROLE_LABEL).map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></Field>
            <Field label="Bowling"><select className="field" value={form.bowl_style} onChange={(e) => setForm({ ...form, bowl_style: e.target.value })}><option value="">Does not bowl</option>{Object.entries(STYLE_LABEL).map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></Field>
            <Button variant="primary" type="submit" disabled={form.side.trim().toLowerCase() === 'us'}>Add</Button>
          </form>
          <p className="mt-2 text-label text-ink-2">Their batting and bowling records build up when you score matches against them ball by ball, including where each ball pitched and where it was hit.</p>
        </Section>
      )}
      <Section title="Scouting reports">
        <Async state={teams} empty={<Empty title="No opposition recorded">Add opposition players above, or score a match against a team: players named while scoring are added automatically.</Empty>}>
          {(ts) => (
            <div className="grid gap-8 lg:grid-cols-[280px_minmax(0,1fr)]">
              <div>
                {ts.map((t) => (
                  <div key={t.team} className="mb-4">
                    <h3 className="painted mb-1 text-label text-ink-2">{t.team}</h3>
                    <ul>{t.players.map((p: any) => (
                      <li key={p.id}><button onClick={() => setPid(p.id)} className={`flex w-full items-center justify-between border-b border-rule px-1 py-1.5 text-left hover:bg-surface ${pid === p.id ? 'bg-accent/20 font-semibold' : ''}`}><span className="truncate">{p.name}</span><span className="num text-label text-ink-2">{p.balls_faced} balls</span></button></li>
                    ))}</ul>
                  </div>
                ))}
              </div>
              <div className="min-w-0">
                {!pid && <Empty title="Choose a player">Pick an opposition batter to see how they score, how they get out, and which lines and lengths have worked against them.</Empty>}
                {pid && <Async state={report}>{(r: any) => r && <Report r={r} />}</Async>}
              </div>
            </div>
          )}
        </Async>
      </Section>
    </div>
  )
}

function Report({ r }: { r: any }) {
  return (
    <div>
      <h3 className="font-board text-fig font-bold uppercase">{r.name}</h3>
      <p className="mb-3 text-ink-2">{r.side} · {r.balls_recorded} balls recorded</p>
      {!r.enough_data ? <Notice tone="warn" title="Too little data for a report">{r.balls_recorded} balls faced are recorded. {r.note}</Notice> : (
        <>
          <Board cols={4}>
            <Win label="Runs" value={r.overall.runs} />
            <Win label="Dismissals" value={r.overall.dismissals} />
            <Win label="Strike rate" value={fmt(r.overall.strike_rate, 0)} />
            <Win label="Dot balls" value={pct(r.overall.dot_pct)} />
          </Board>
          <Section title="Findings" aside={r.note}>
            <ul className="flex flex-col">{r.findings.map((f: any) => <li key={f.finding} className="border-b border-rule py-2"><div className="font-semibold">{f.finding}</div><div className="text-label text-ink-2">{f.evidence}</div></li>)}</ul>
          </Section>
          <Section title="Scoring areas">
            <div className="grid gap-6 md:grid-cols-[minmax(0,340px)_minmax(0,1fr)]">
              <Ground shots={r.wagon_wheel.shots} zones={r.wagon_wheel.zones} />
              <SplitMini splits={r.splits} />
            </div>
          </Section>
        </>
      )}
    </div>
  )
}

/* ---------------------------------------------------------------- leaderboards */

function Leaderboards() {
  const [season, setSeason] = useState('')
  const [format, setFormat] = useState('')
  const state = useAsync(() => api.get(`/stats/leaderboards${qs({ season, format })}`), [season, format])
  return (
    <div>
      <SeasonFilter season={season} format={format} onChange={(s, f) => { setSeason(s); setFormat(f) }} />
      <Async state={state}>
        {(d: any) => d.boards.every((b: any) => b.rows.length === 0)
          ? <Empty title="No rankings yet">Leaderboards fill in as matches are scored and speeds, practice deliveries and fielding are recorded. Some rankings need a minimum number of innings or balls before a player qualifies.</Empty>
          : (
            <div className="grid gap-x-10 gap-y-2 md:grid-cols-2 xl:grid-cols-3">
              {d.boards.map((b: any) => (
                <Section key={b.key} title={b.title}>
                  {b.rows.length === 0 ? <p className="text-ink-2">Nobody qualifies yet.</p> : (
                    <DataTable dense rows={b.rows.slice(0, 5)} rowKey={(r: any) => r.player} cols={[
                      { key: 'r', label: '', num: true, render: (r: any) => r.rank },
                      { key: 'n', label: 'Player', render: (r: any) => <Link className="draw" to={`/team/player/${r.player}`}>{r.name}</Link> },
                      { key: 'v', label: b.unit || 'Value', num: true, render: (r: any) => <b>{(r.value > 0 && b.key === 'improvement' ? '+' : '') + fmt(r.value, b.digits)}</b> },
                    ]} />
                  )}
                  {b.rule && <p className="mt-1.5 text-label text-ink-2">{b.rule}</p>}
                </Section>
              ))}
            </div>
          )}
      </Async>
    </div>
  )
}
