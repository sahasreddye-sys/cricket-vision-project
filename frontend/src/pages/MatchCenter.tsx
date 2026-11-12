import { ArrowLeft, Undo2 } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Link, Route, Routes, useNavigate, useParams } from 'react-router-dom'
import { useApp } from '../context'
import { Bars, LineTrend, SeriesKey } from '../components/Chart'
import { Ground } from '../components/Ground'
import { Pitch } from '../components/Pitch'
import { Async, Board, Button, DataTable, Empty, Field, Notice, OverStrip, Page, PlayerSelect, Section, Seg, Tabs, Win, useAsync, useToast } from '../components/ui'
import { api } from '../lib/api'
import { cap, day, fmt, today, words } from '../lib/format'

export default function MatchCenter() {
  return (
    <Routes>
      <Route path="/" element={<List />} />
      <Route path=":id" element={<Detail />} />
    </Routes>
  )
}

/* ---------------------------------------------------------------- list */

function List() {
  const { isCoach, team, reloadTeam } = useApp()
  const toast = useToast()
  const nav = useNavigate()
  const matches = useAsync(() => api.get<any[]>('/matches'), [])
  const [form, setForm] = useState({ date: today(), opponent: '', venue: '', format: `T${team.default_overs}`, overs: String(team.default_overs), season: team.season })

  const add = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      const m = await api.post('/matches', { ...form, overs: parseInt(form.overs, 10) })
      toast('Match added'); await reloadTeam(); nav(`/matches/${m.id}`)
    } catch (err: any) { toast(err.message, 'error') }
  }
  const score = (m: any, side: string) => { const i = m.innings?.find((x: any) => x.batting_side === side); return i ? `${i.total}/${i.wickets} (${i.overs})` : '–' }
  return (
    <Page title="Match Center" lead="Fixtures, live ball-by-ball scoring, scorecards and match analytics.">
      {isCoach && (
        <Section title="Add a match or fixture">
          <form onSubmit={add} className="grid items-end gap-3 sm:grid-cols-2 lg:grid-cols-[150px_minmax(0,1.3fr)_minmax(0,1fr)_100px_90px_100px_auto]">
            <Field label="Date"><input className="field" type="date" required value={form.date} onChange={(e) => setForm({ ...form, date: e.target.value })} /></Field>
            <Field label="Opponent"><input className="field" required maxLength={120} value={form.opponent} onChange={(e) => setForm({ ...form, opponent: e.target.value })} /></Field>
            <Field label="Venue"><input className="field" maxLength={120} value={form.venue} onChange={(e) => setForm({ ...form, venue: e.target.value })} /></Field>
            <Field label="Format"><input className="field" required maxLength={20} value={form.format} onChange={(e) => setForm({ ...form, format: e.target.value })} /></Field>
            <Field label="Overs"><input className="field num" type="number" min={1} max={100} required value={form.overs} onChange={(e) => setForm({ ...form, overs: e.target.value, format: /^T\d+$/.test(form.format) ? `T${e.target.value}` : form.format })} /></Field>
            <Field label="Season"><input className="field" maxLength={20} value={form.season} onChange={(e) => setForm({ ...form, season: e.target.value })} /></Field>
            <Button variant="primary" type="submit">Add match</Button>
          </form>
        </Section>
      )}
      <Section title="Matches">
        <Async state={matches} empty={<Empty title="No matches yet">{isCoach ? 'Add a fixture above. On match day, open it to score ball by ball, or enter the finished scorecard afterwards.' : 'Your coach has not added any matches yet.'}</Empty>}>
          {(rows) => (
            <DataTable rows={rows} rowKey={(m) => m.id} onRow={(m) => nav(`/matches/${m.id}`)} cols={[
              { key: 'd', label: 'Date', render: (m) => day(m.date) },
              { key: 'o', label: 'Opponent', render: (m) => <span className="font-semibold">{m.opponent}{m.is_sample && <span className="painted ml-2 text-label text-ink-2">Sample</span>}</span> },
              { key: 'f', label: 'Format', render: (m) => m.format },
              { key: 'u', label: 'Us', num: true, render: (m) => score(m, 'us') },
              { key: 't', label: 'Them', num: true, render: (m) => score(m, 'them') },
              { key: 's', label: 'Status', render: (m) => (m.status === 'completed' ? <span className={m.outcome === 'won' ? 'text-green' : m.outcome === 'lost' ? 'text-red' : ''}>{m.outcome ? cap(m.outcome) : 'Completed'}</span> : cap(m.status)) },
            ]} />
          )}
        </Async>
      </Section>
    </Page>
  )
}

/* ---------------------------------------------------------------- detail */

type Tab = 'scorecard' | 'live' | 'analytics' | 'entry'

function Detail() {
  const { id } = useParams()
  const { isCoach, reloadPlayers } = useApp()
  const toast = useToast()
  const nav = useNavigate()
  const state = useAsync(() => api.get(`/matches/${id}`), [id])
  // Players may have been added elsewhere (a CSV import, another device) since the app opened.
  useEffect(() => { reloadPlayers() }, [id, reloadPlayers])
  const [tab, setTab] = useState<Tab>('scorecard')
  const m = state.data
  useEffect(() => { if (m && m.status !== 'completed' && isCoach && m.cards.every((c: any) => c.source !== 'scorecard')) setTab('live') /* eslint-disable-next-line */ }, [m?.id])

  const update = async (patch: Record<string, unknown>) => {
    if (!m) return
    const body = { date: m.date, opponent: m.opponent, venue: m.venue, format: m.format, overs: m.overs, season: m.season, status: m.status, result: m.result, outcome: m.outcome, notes: m.notes, ...patch }
    try { await api.put(`/matches/${m.id}`, body); state.reload() } catch (e: any) { toast(e.message, 'error') }
  }
  const remove = async () => {
    if (!m || !window.confirm(`Delete the match against ${m.opponent} and every ball recorded in it? This cannot be undone.`)) return
    try { await api.del(`/matches/${m.id}`); toast('Match deleted'); nav('/matches') } catch (e: any) { toast(e.message, 'error') }
  }

  return (
    <Async state={state}>
      {(m: any) => (
        <Page title={`v ${m.opponent}`} lead={`${day(m.date)}${m.venue ? ` · ${m.venue}` : ''} · ${m.format}, ${m.overs} overs a side${m.season ? ` · ${m.season} season` : ''}`}
          actions={<Link to="/matches"><Button><ArrowLeft size={16} aria-hidden />All matches</Button></Link>}>
          {m.is_sample && <div className="mb-4"><Notice tone="warn">This is a synthetic sample match. The scores are computer-generated.</Notice></div>}
          <Board cols={4}>
            {m.cards.map((c: any) => <Win key={c.number} wide label={`${c.batting_side === 'us' ? 'Us' : m.opponent} · innings ${c.number}`} value={`${c.total}/${c.wickets}`} tone={c.batting_side === 'us' ? 'accent' : 'plain'} hint={`${c.overs} overs · run rate ${fmt(c.run_rate, 2)}`} />)}
            {m.cards.length === 0 && <Win label="Score" value={null} hint="No innings started" />}
            <Win wide label="Result" value={m.outcome ? cap(m.outcome) : m.status === 'live' ? 'Live' : null} tone={m.outcome === 'won' ? 'green' : m.outcome === 'lost' ? 'red' : 'plain'} hint={m.result || m.computed_result || cap(m.status)} />
          </Board>
          <div className="mt-6">
            <Tabs value={tab} onChange={setTab} tabs={[{ id: 'scorecard', label: 'Scorecard' }, ...(isCoach ? [{ id: 'live' as Tab, label: 'Live scoring' }] : []), { id: 'analytics', label: 'Analytics' }, ...(isCoach ? [{ id: 'entry' as Tab, label: 'Enter or import' }] : [])]} />
          </div>
          {tab === 'scorecard' && <Scorecard m={m} />}
          {tab === 'live' && isCoach && <Live m={m} reload={state.reload} />}
          {tab === 'analytics' && <Analytics m={m} />}
          {tab === 'entry' && isCoach && <Entry m={m} reload={state.reload} />}
          {isCoach && (
            <Section title="Match status">
              <div className="flex flex-wrap items-end gap-3">
                <Field label="Status" className="w-40"><select className="field" value={m.status} onChange={(e) => update({ status: e.target.value })}><option value="scheduled">Scheduled</option><option value="live">Live</option><option value="completed">Completed</option></select></Field>
                <Field label="Outcome for us" className="w-40"><select className="field" value={m.outcome ?? ''} onChange={(e) => update({ outcome: e.target.value || null, status: e.target.value ? 'completed' : m.status })}><option value="">Not decided</option><option value="won">Won</option><option value="lost">Lost</option><option value="tied">Tied</option><option value="no_result">No result</option></select></Field>
                <ResultText value={m.result} suggestion={m.computed_result} onSave={(v) => update({ result: v })} />
                <Button variant="danger" onClick={remove}>Delete match</Button>
              </div>
            </Section>
          )}
        </Page>
      )}
    </Async>
  )
}

function ResultText({ value, suggestion, onSave }: { value: string; suggestion: string | null; onSave: (v: string) => void }) {
  const [text, setText] = useState(value)
  useEffect(() => setText(value), [value])
  return (
    <div className="flex min-w-[260px] flex-1 items-end gap-2">
      <Field label="Result text" className="flex-1" hint={suggestion && suggestion !== 'In progress' && suggestion !== text ? `Calculated from the scores: ${suggestion}` : undefined}>
        <input className="field" value={text} maxLength={200} onChange={(e) => setText(e.target.value)} />
      </Field>
      {suggestion && suggestion !== 'In progress' && suggestion !== text && <Button onClick={() => onSave(suggestion)}>Use calculated</Button>}
      <Button disabled={text === value} onClick={() => onSave(text)}>Save</Button>
    </div>
  )
}

/* ---------------------------------------------------------------- scorecard */

const HOW: Record<string, string> = { bowled: 'b', caught: 'c', lbw: 'lbw', stumped: 'st', run_out: 'run out', hit_wicket: 'hit wicket', caught_and_bowled: 'c & b', retired_hurt: 'retired hurt', retired_out: 'retired out' }
const dismissal = (b: any) => {
  if (!b.out && !b.how_out) return 'not out'
  if (!b.how_out) return 'out'
  const k = b.how_out
  if (k === 'bowled' || k === 'lbw') return `${HOW[k]} ${b.bowler_name ?? ''}`.trim()
  if (k === 'caught') return `c ${b.fielder_name ?? '?'} b ${b.bowler_name ?? '?'}`
  if (k === 'stumped') return `st ${b.fielder_name ?? '?'} b ${b.bowler_name ?? '?'}`
  if (k === 'run_out') return `run out${b.fielder_name ? ` (${b.fielder_name})` : ''}`
  return HOW[k] ?? words(k)
}

function Scorecard({ m }: { m: any }) {
  if (m.cards.length === 0 || m.cards.every((c: any) => c.source === 'empty')) return <Empty title="No scorecard yet">Score this match ball by ball on the Live scoring tab, or enter the finished scorecard on the Enter or import tab.</Empty>
  return (
    <div>
      {m.cards.map((c: any) => c.source !== 'empty' && (
        <div key={c.number} className="mb-10">
          <Section title={`${c.batting_side === 'us' ? 'Our' : `${m.opponent}'s`} innings: ${c.total}/${c.wickets} in ${c.overs} overs`} aside={c.source === 'scorecard' ? 'Entered as a scorecard' : `Run rate ${fmt(c.run_rate, 2)}${c.target ? ` · target ${c.target}` : ''}`}>
            <DataTable dense rows={c.batting} rowKey={(b: any) => b.player} cols={[
              { key: 'n', label: 'Batter', render: (b: any) => <b>{b.name}</b> },
              { key: 'h', label: '', render: (b: any) => <span className="text-ink-2">{dismissal(b)}</span> },
              { key: 'r', label: 'Runs', num: true, render: (b: any) => <b>{b.runs}</b> },
              { key: 'b', label: 'Balls', num: true, render: (b: any) => b.balls },
              { key: '4', label: '4s', num: true, render: (b: any) => b.fours },
              { key: '6', label: '6s', num: true, render: (b: any) => b.sixes },
              { key: 's', label: 'SR', num: true, render: (b: any) => fmt(b.strike_rate, 0) },
            ]} />
            <p className="mt-2 text-ink-2">
              Extras <b className="text-ink">{c.extras.total}</b>
              {c.extras.wides !== undefined && ` (wides ${c.extras.wides}, no-balls ${c.extras.no_balls}, byes ${c.extras.byes}, leg-byes ${c.extras.leg_byes}${c.extras.penalty ? `, penalty ${c.extras.penalty}` : ''})`}
              {c.source === 'scorecard' && ' (total minus runs off the bat)'}
            </p>
            {c.fall_of_wickets.length > 0 && <p className="mt-1 text-ink-2">Fall of wickets: {c.fall_of_wickets.map((f: any) => `${f.wicket}-${f.score} (${f.name}, ${f.over} ov)`).join(', ')}</p>}
          </Section>
          <Section title="Bowling">
            <DataTable dense rows={c.bowling} rowKey={(b: any) => b.player} cols={[
              { key: 'n', label: 'Bowler', render: (b: any) => <b>{b.name}</b> },
              { key: 'o', label: 'Overs', num: true, render: (b: any) => b.overs },
              { key: 'm', label: 'Mdns', num: true, render: (b: any) => b.maidens },
              { key: 'r', label: 'Runs', num: true, render: (b: any) => b.runs },
              { key: 'w', label: 'Wkts', num: true, render: (b: any) => <b>{b.wickets}</b> },
              { key: 'e', label: 'Econ', num: true, render: (b: any) => fmt(b.economy, 2) },
              { key: 'wd', label: 'Wd', num: true, render: (b: any) => b.wides },
              { key: 'nb', label: 'NB', num: true, render: (b: any) => b.no_balls },
            ]} />
          </Section>
        </div>
      ))}
    </div>
  )
}

/* ---------------------------------------------------------------- analytics */

function Analytics({ m }: { m: any }) {
  const byBall = m.cards.filter((c: any) => c.source === 'ball_by_ball')
  if (byBall.length === 0) return <Empty title="Over-by-over analytics need ball-by-ball data">Partnerships, run rates by over and the run chase are calculated from balls scored on the Live scoring tab or imported from CSV. A scorecard entered as totals does not contain them.</Empty>
  const maxOvers = Math.max(...byBall.map((c: any) => c.over_by_over.filter((o: any) => !o.in_progress).length))
  const worm = Array.from({ length: maxOvers }, (_, i) => {
    const row: any = { over: `${i + 1}` }
    for (const c of byBall) { const o = c.over_by_over.find((x: any) => x.over === i + 1 && !x.in_progress); if (o) { row[`t${c.number}`] = o.total; row[`r${c.number}`] = o.runs } }
    return row
  })
  const name = (c: any) => (c.batting_side === 'us' ? 'Us' : m.opponent)
  const tSeries = byBall.map((c: any, i: number) => ({ key: `t${c.number}`, label: `${name(c)} total`, colour: i ? 'var(--green)' : 'var(--ink)' }))
  const rSeries = byBall.map((c: any, i: number) => ({ key: `r${c.number}`, label: `${name(c)} runs in the over`, colour: i ? 'var(--green)' : 'var(--ink)' }))
  const chase = byBall.find((c: any) => c.number === 2 && c.target)
  return (
    <div>
      {chase && (
        <Section title="The chase">
          <Board cols={4}>
            <Win label="Target" value={chase.target} />
            <Win label="Runs required" value={chase.runs_required} tone="accent" />
            <Win label="Balls remaining" value={chase.balls_remaining} />
            <Win label="Required run rate" value={fmt(chase.required_run_rate, 2)} hint={`current ${fmt(chase.run_rate, 2)}`} />
          </Board>
        </Section>
      )}
      <div className="mt-8 grid gap-x-10 gap-y-8 lg:grid-cols-2">
        <Section title="Score by over"><LineTrend data={worm} x="over" series={tSeries} height={220} /><SeriesKey series={tSeries} /></Section>
        <Section title="Runs in each over"><Bars data={worm} x="over" series={rSeries} height={220} /><SeriesKey series={rSeries} /></Section>
      </div>
      {byBall.map((c: any) => (
        <div key={c.number}>
          <Section title={`Partnerships: ${name(c)}`}>
            <DataTable dense rows={c.partnerships} rowKey={(_: any, i) => i} cols={[
              { key: 'w', label: 'Wkt', num: true, render: (p: any) => p.wicket },
              { key: 'b', label: 'Batters', render: (p: any) => p.contrib.map((x: any) => `${x.name} ${x.runs}`).join(' and ') },
              { key: 'r', label: 'Runs', num: true, render: (p: any) => <b>{p.runs}</b> },
              { key: 'l', label: 'Balls', num: true, render: (p: any) => p.balls },
              { key: 'rr', label: 'Run rate', num: true, render: (p: any) => fmt(p.run_rate, 2) },
              { key: 'u', label: '', render: (p: any) => (p.unbroken ? 'unbroken' : '') },
            ]} />
            <p className="mt-1 text-label text-ink-2">Partnership runs include extras scored while the pair were together.</p>
          </Section>
          <Section title={`Over by over: ${name(c)}`}>
            <div className="flex flex-col gap-1.5">
              {c.over_by_over.map((o: any) => (
                <div key={o.over} className="flex flex-wrap items-center gap-x-4 gap-y-1">
                  <OverStrip balls={o.balls} label={`Over ${o.over}`} />
                  <span className="text-label text-ink-2">{o.bowler_name} · {o.runs} run{o.runs === 1 ? '' : 's'}{o.wickets ? `, ${o.wickets} wkt` : ''} · {o.total}/{o.total_wickets}</span>
                </div>
              ))}
            </div>
          </Section>
        </div>
      ))}
    </div>
  )
}

/* ---------------------------------------------------------------- live scoring */

const KINDS = ['bowled', 'caught', 'lbw', 'run_out', 'stumped', 'hit_wicket', 'caught_and_bowled', 'retired_hurt', 'retired_out']
const SHOTS = ['drive', 'cut', 'pull', 'flick', 'sweep', 'glance', 'loft', 'defence']
type Extra = 'none' | 'wide' | 'no_ball' | 'bye' | 'leg_bye'

function Live({ m, reload }: { m: any; reload: () => void }) {
  const { players, opposition, reloadPlayers } = useApp()
  const toast = useToast()
  const inn = m.cards.find((c: any) => !c.closed)
  const them = useMemo(() => opposition.filter((p) => p.side === m.opponent), [opposition, m.opponent])
  const [card, setCard] = useState<any | null>(inn ?? null)
  const [striker, setStriker] = useState<number | null>(null)
  const [nonStriker, setNonStriker] = useState<number | null>(null)
  const [bowler, setBowler] = useState<number | null>(null)
  const [runs, setRuns] = useState(0)
  const [extra, setExtra] = useState<Extra>('none')
  const [extraRuns, setExtraRuns] = useState(0)
  const [wicket, setWicket] = useState('')
  const [outWho, setOutWho] = useState<'striker' | 'non_striker'>('striker')
  const [fielder, setFielder] = useState<number | null>(null)
  const [detail, setDetail] = useState(false)
  const [spot, setSpot] = useState<{ x: number; y: number } | null>(null)
  const [angle, setAngle] = useState<number | null>(null)
  const [shot, setShot] = useState('')
  const [newName, setNewName] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => { setCard(inn ?? null) }, [inn?.innings_id, inn?.legal_balls, inn?.total]) // eslint-disable-line
  useEffect(() => {
    if (!card) return
    setStriker(card.next.striker); setNonStriker(card.next.non_striker)
    if (card.next.over_complete) setBowler(null)
    else if (card.over_by_over.length) setBowler((b) => b ?? card.over_by_over[card.over_by_over.length - 1].bowler)
  }, [card])

  const start = async (side: 'us' | 'them') => { try { await api.post(`/matches/${m.id}/innings`, { batting_side: side }); reload() } catch (e: any) { toast(e.message, 'error') } }

  if (!inn) {
    if (m.cards.length === 0) return (
      <Empty title="Start the first innings" action={<><Button variant="primary" onClick={() => start('us')}>We bat first</Button><Button onClick={() => start('them')}>{m.opponent} bat first</Button></>}>
        Choose who is batting first. You will then pick the two opening batters and the bowler, and record each ball.
      </Empty>
    )
    if (m.cards.length === 1) {
      const next = m.cards[0].batting_side === 'us' ? 'them' : 'us'
      return <Empty title="First innings closed" action={<Button variant="primary" onClick={() => start(next)}>Start the second innings ({next === 'us' ? 'we bat' : `${m.opponent} bat`})</Button>}>The target will be {m.cards[0].total + 1}.</Empty>
    }
    return <Empty title="Both innings are complete">See the scorecard and analytics. Set the result under Match status below.</Empty>
  }
  if (!card) return null

  const batSide = card.batting_side === 'us' ? players : them
  const bowlSide = card.batting_side === 'us' ? them : players
  const oppSideBatting = card.batting_side === 'them'
  const outIds = new Set(card.batting.filter((b: any) => b.out).map((b: any) => b.player))
  const canBat = batSide.filter((p) => !outIds.has(p.id))
  const current = card.over_by_over.find((o: any) => o.in_progress)
  const lastOverBowler = card.next.over_complete && card.over_by_over.length ? card.over_by_over[card.over_by_over.length - 1].bowler : null

  const addOpp = async () => {
    if (!newName.trim()) return
    try { await api.post('/players', { name: newName.trim(), side: m.opponent }); setNewName(''); await reloadPlayers(); toast(`${newName.trim()} added to ${m.opponent}`) } catch (e: any) { toast(e.message, 'error') }
  }
  const reset = () => { setRuns(0); setExtra('none'); setExtraRuns(0); setWicket(''); setOutWho('striker'); setFielder(null); setSpot(null); setAngle(null); setShot('') }

  const record = async () => {
    const body: any = { striker_id: striker, non_striker_id: nonStriker, bowler_id: bowler, runs_bat: 0, wides: 0, no_balls: 0, byes: 0, leg_byes: 0 }
    if (extra === 'wide') body.wides = 1 + extraRuns
    else if (extra === 'bye') body.byes = Math.max(1, extraRuns)
    else if (extra === 'leg_bye') body.leg_byes = Math.max(1, extraRuns)
    else { body.runs_bat = runs; if (extra === 'no_ball') body.no_balls = 1 }
    if (wicket) { body.wicket_kind = wicket; body.player_out_id = outWho === 'striker' ? striker : nonStriker; if (fielder) body.fielder_id = fielder }
    if (spot) { body.x = spot.x; body.y = spot.y }
    if (angle !== null && body.runs_bat > 0) body.shot_angle = angle
    if (shot) body.shot_type = shot
    setBusy(true)
    try { const c = await api.post(`/innings/${card.innings_id}/balls`, body); setCard(c); reset(); reload() } catch (e: any) { toast(e.message, 'error') }
    setBusy(false)
  }
  const undo = async () => { try { setCard(await api.del(`/innings/${card.innings_id}/balls/last`)); setBowler(null); reload() } catch (e: any) { toast(e.message, 'error') } }
  const close = async () => {
    if (!window.confirm('Close this innings? No more balls can be added to it unless you undo.')) return
    try { await api.post(`/innings/${card.innings_id}/close`); reload() } catch (e: any) { toast(e.message, 'error') }
  }
  const ready = striker && nonStriker && bowler && striker !== nonStriker
  const bat = (id: number | null) => card.batting.find((b: any) => b.player === id)
  const bowl = card.bowling.find((b: any) => b.player === bowler)
  const summary = extra === 'wide' ? `${1 + extraRuns} wide${extraRuns ? 's' : ''}` : extra === 'bye' ? `${Math.max(1, extraRuns)} bye${Math.max(1, extraRuns) > 1 ? 's' : ''}` : extra === 'leg_bye' ? `${Math.max(1, extraRuns)} leg-bye${Math.max(1, extraRuns) > 1 ? 's' : ''}` : extra === 'no_ball' ? `No-ball + ${runs} off the bat` : runs === 0 ? 'Dot ball' : `${runs} run${runs > 1 ? 's' : ''}`

  return (
    <div>
      <Board cols={5}>
        <Win wide label={`${card.batting_side === 'us' ? 'Us' : m.opponent} · innings ${card.number}`} value={`${card.total}/${card.wickets}`} tone="accent" />
        <Win label="Overs" value={card.overs} hint={`of ${m.overs}`} />
        <Win label="Run rate" value={fmt(card.run_rate, 2)} />
        <Win label={card.target ? 'Need' : 'Extras'} value={card.target ? card.runs_required : card.extras.total} hint={card.target ? `from ${card.balls_remaining} balls · target ${card.target}` : undefined} />
        <Win label={card.target ? 'Required rate' : 'Last wicket'} value={card.target ? fmt(card.required_run_rate, 2) : card.fall_of_wickets.length ? card.fall_of_wickets[card.fall_of_wickets.length - 1].score : null} />
      </Board>
      <div className="mt-4 flex flex-wrap items-center gap-x-6 gap-y-2">
        <OverStrip balls={current?.balls ?? []} label="This over" />
        <Button small variant="quiet" disabled={card.legal_balls === 0 && card.total === 0} onClick={undo}><Undo2 size={15} aria-hidden />Undo last ball</Button>
        <Button small variant="quiet" onClick={close}>Close innings</Button>
      </div>

      <div className="mt-6 grid gap-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <div>
          <Section title="At the crease">
            {batSide.length < 2 && <div className="mb-3"><Notice tone="warn">{oppSideBatting ? `Add at least two ${m.opponent} batters below to start scoring.` : 'Add your squad in the Team Hub before scoring.'}</Notice></div>}
            <div className="grid gap-3 sm:grid-cols-2">
              <PlayerSelect players={canBat.filter((p) => p.id !== nonStriker)} value={striker} onChange={setStriker} label="On strike" />
              <PlayerSelect players={canBat.filter((p) => p.id !== striker)} value={nonStriker} onChange={setNonStriker} label="Non-striker" />
              <PlayerSelect players={bowlSide.filter((p) => p.id !== lastOverBowler)} value={bowler} onChange={setBowler} label={card.next.over_complete ? 'Bowler for the new over' : 'Bowler'} />
              <div className="flex items-end"><Button disabled={!striker || !nonStriker} onClick={() => { setStriker(nonStriker); setNonStriker(striker) }}>Swap the batters</Button></div>
            </div>
            {(striker || bowler) && (
              <div className="mt-3 text-ink-2">
                {[striker, nonStriker].map((id) => id && <div key={id}>{batSide.find((p) => p.id === id)?.name}{id === striker ? ' *' : ''}: <b className="num text-ink">{bat(id)?.runs ?? 0}</b> ({bat(id)?.balls ?? 0} balls)</div>)}
                {bowler && <div>{bowlSide.find((p) => p.id === bowler)?.name}: <b className="num text-ink">{bowl ? `${bowl.overs}-${bowl.maidens}-${bowl.runs}-${bowl.wickets}` : '0.0-0-0-0'}</b></div>}
              </div>
            )}
            <div className="mt-4 flex items-end gap-2">
              <Field label={`Add a ${m.opponent} player`} className="flex-1"><input className="field" value={newName} placeholder="Name" onChange={(e) => setNewName(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter') addOpp() }} /></Field>
              <Button disabled={!newName.trim()} onClick={addOpp}>Add</Button>
            </div>
          </Section>
        </div>

        <div>
          <Section title="This ball">
            <div className="flex flex-col gap-3">
              <div>
                <div className="painted mb-1 text-label text-ink-2">Runs off the bat</div>
                <div className="flex flex-wrap gap-1.5">
                  {[0, 1, 2, 3, 4, 5, 6].map((r) => (
                    <button key={r} type="button" disabled={extra === 'wide' || extra === 'bye' || extra === 'leg_bye'} onClick={() => setRuns(r)} aria-pressed={runs === r}
                      className={`num h-11 w-11 rounded-plate font-board text-fig font-semibold transition-colors disabled:opacity-30 ${runs === r && extra !== 'wide' && extra !== 'bye' && extra !== 'leg_bye' ? 'bg-accent text-accent-ink' : 'bg-plate text-plate-ink hover:brightness-125'}`}>{r}</button>
                  ))}
                </div>
              </div>
              <div className="flex flex-wrap items-end gap-3">
                <div>
                  <div className="painted mb-1 text-label text-ink-2">Extra</div>
                  <Seg label="Extra" value={extra} onChange={(v) => { setExtra(v); setExtraRuns(0) }} options={[{ id: 'none', label: 'None' }, { id: 'wide', label: 'Wide' }, { id: 'no_ball', label: 'No-ball' }, { id: 'bye', label: 'Bye' }, { id: 'leg_bye', label: 'Leg bye' }]} />
                </div>
                {(extra === 'wide' || extra === 'bye' || extra === 'leg_bye') && (
                  <Field label={extra === 'wide' ? 'Runs run as well' : 'Runs run'} className="w-32"><select className="field" value={extraRuns} onChange={(e) => setExtraRuns(Number(e.target.value))}>{(extra === 'wide' ? [0, 1, 2, 3, 4] : [1, 2, 3, 4]).map((n) => <option key={n} value={n}>{n}</option>)}</select></Field>
                )}
              </div>
              <div className="grid gap-3 sm:grid-cols-3">
                <Field label="Wicket"><select className="field" value={wicket} onChange={(e) => setWicket(e.target.value)}><option value="">No wicket</option>{KINDS.map((k) => <option key={k} value={k}>{cap(k)}</option>)}</select></Field>
                {wicket && <Field label="Who is out"><select className="field" value={outWho} onChange={(e) => setOutWho(e.target.value as any)}><option value="striker">Striker</option><option value="non_striker">Non-striker</option></select></Field>}
                {['caught', 'run_out', 'stumped'].includes(wicket) && <PlayerSelect players={bowlSide} value={fielder} onChange={setFielder} label="Fielder" allowEmpty="Not recorded" />}
              </div>
              <button type="button" className="self-start underline" onClick={() => setDetail(!detail)}>{detail ? 'Hide' : 'Add'} where it pitched and where it was hit (optional)</button>
              {detail && (
                <div className="grid gap-4 sm:grid-cols-2">
                  <div>
                    <div className="painted mb-1 text-label text-ink-2">Where it pitched{spot ? `: ${spot.y.toFixed(1)} m, ${(spot.x * 100).toFixed(0)} cm across` : ''}</div>
                    <Pitch yMax={12} dots={spot ? [{ x: spot.x, y: spot.y, tone: 'wicket' }] : []} onAdd={(x, y) => setSpot({ x, y })} className="w-full max-w-[280px]" />
                  </div>
                  <div>
                    <div className="painted mb-1 text-label text-ink-2">Where it was hit{angle !== null ? `: ${angle}°` : ''}</div>
                    <Ground onPick={setAngle} picked={angle} className="w-full max-w-[280px]" />
                    <Field label="Shot" className="mt-2"><select className="field" value={shot} onChange={(e) => setShot(e.target.value)}><option value="">Not recorded</option>{SHOTS.map((s) => <option key={s} value={s}>{cap(s)}</option>)}</select></Field>
                  </div>
                </div>
              )}
              <div className="flex flex-wrap items-center gap-3 border-t border-rule-strong pt-3">
                <Button variant="primary" busy={busy} disabled={!ready} onClick={record}>Record ball</Button>
                <span className="text-ink-2">{ready ? <>{summary}{wicket ? `, ${words(wicket)}` : ''}</> : card.next.over_complete && !bowler ? 'Over complete. Choose the bowler for the new over.' : 'Choose both batters and the bowler.'}</span>
              </div>
            </div>
          </Section>
        </div>
      </div>
    </div>
  )
}

/* ---------------------------------------------------------------- scorecard entry and import */

function Entry({ m, reload }: { m: any; reload: () => void }) {
  const { players, opposition } = useApp()
  const toast = useToast()
  const them = opposition.filter((p) => p.side === m.opponent)
  const [iid, setIid] = useState<number | null>(m.cards[0]?.innings_id ?? null)
  const card = m.cards.find((c: any) => c.innings_id === iid)
  const [bat, setBat] = useState<any[]>([])
  const [bowl, setBowl] = useState<any[]>([])
  const [file, setFile] = useState<File | null>(null)

  useEffect(() => {
    if (!card) return
    setBat(card.source === 'scorecard' ? card.batting.map((b: any) => ({ player_id: b.player, runs: b.runs, balls: b.balls, fours: b.fours, sixes: b.sixes, out: b.out })) : [])
    setBowl(card.source === 'scorecard' ? card.bowling.map((b: any) => ({ player_id: b.player, overs: b.overs, maidens: b.maidens, runs: b.runs, wickets: b.wickets, wides: b.wides, no_balls: b.no_balls })) : [])
  }, [iid, m]) // eslint-disable-line

  const start = async (side: 'us' | 'them') => { try { const r = await api.post(`/matches/${m.id}/innings`, { batting_side: side }); setIid(r.innings_id); reload() } catch (e: any) { toast(e.message, 'error') } }
  const save = async () => {
    try {
      await api.put(`/innings/${iid}/lines`, { batting: bat.filter((b) => b.player_id), bowling: bowl.filter((b) => b.player_id) })
      toast('Scorecard saved'); reload()
    } catch (e: any) { toast(e.message, 'error') }
  }
  const importCsv = async () => {
    if (!file) return
    const form = new FormData(); form.append('file', file)
    try { const r = await api.upload(`/innings/${iid}/import-csv`, form); toast(`${r.imported} balls imported`); setFile(null); reload() } catch (e: any) { toast(e.message, 'error') }
  }
  const num = (v: string) => (v === '' ? 0 : parseInt(v, 10) || 0)

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-end gap-3">
        <Field label="Innings" className="w-64">
          <select className="field" value={iid ?? ''} onChange={(e) => setIid(Number(e.target.value))} disabled={m.cards.length === 0}>
            {m.cards.length === 0 && <option value="">No innings yet</option>}
            {m.cards.map((c: any) => <option key={c.innings_id} value={c.innings_id}>Innings {c.number}: {c.batting_side === 'us' ? 'we' : m.opponent} batted</option>)}
          </select>
        </Field>
        {m.cards.length === 0 && <><Button onClick={() => start('us')}>Add innings: we batted first</Button><Button onClick={() => start('them')}>Add innings: {m.opponent} batted first</Button></>}
        {m.cards.length === 1 && <Button onClick={() => start(m.cards[0].batting_side === 'us' ? 'them' : 'us')}>Add the second innings</Button>}
      </div>
      {!card ? <Empty title="Add an innings first">A scorecard is entered one innings at a time.</Empty> : card.source === 'ball_by_ball' ? (
        <Notice title="This innings was scored ball by ball">Its scorecard is calculated from the recorded balls, so it cannot be typed over. Use Undo on the Live scoring tab to correct a ball.</Notice>
      ) : (
        <>
          <Section title="Batting" aside={<Button small onClick={() => setBat([...bat, { player_id: null, runs: 0, balls: 0, fours: 0, sixes: 0, out: true }])}>Add batter</Button>}>
            {bat.length === 0 ? <p className="text-ink-2">Add each batter in batting order with their runs and balls faced.</p> : (
              <div className="flex flex-col gap-2">
                {bat.map((b, i) => {
                  const upd = (patch: any) => setBat(bat.map((x, j) => (j === i ? { ...x, ...patch } : x)))
                  return (
                    <div key={i} className="grid grid-cols-2 items-end gap-2 border-b border-rule pb-2 sm:grid-cols-[minmax(0,1.6fr)_repeat(4,72px)_110px_auto]">
                      <PlayerSelect players={card.batting_side === 'us' ? players : them} value={b.player_id} onChange={(v) => upd({ player_id: v })} label={`Batter ${i + 1}`} />
                      {(['runs', 'balls', 'fours', 'sixes'] as const).map((k) => <Field key={k} label={cap(k)}><input className="field num" type="number" min={0} value={b[k]} onChange={(e) => upd({ [k]: num(e.target.value) })} /></Field>)}
                      <Field label="Dismissed"><select className="field" value={b.out ? '1' : '0'} onChange={(e) => upd({ out: e.target.value === '1' })}><option value="1">Out</option><option value="0">Not out</option></select></Field>
                      <Button small variant="quiet" onClick={() => setBat(bat.filter((_, j) => j !== i))}>Remove</Button>
                    </div>
                  )
                })}
              </div>
            )}
          </Section>
          <Section title="Bowling" aside={<Button small onClick={() => setBowl([...bowl, { player_id: null, overs: '0.0', maidens: 0, runs: 0, wickets: 0, wides: 0, no_balls: 0 }])}>Add bowler</Button>}>
            {bowl.length === 0 ? <p className="text-ink-2">Add each bowler with their overs (for example 3.4 means 3 overs and 4 balls), runs and wickets.</p> : (
              <div className="flex flex-col gap-2">
                {bowl.map((b, i) => {
                  const upd = (patch: any) => setBowl(bowl.map((x, j) => (j === i ? { ...x, ...patch } : x)))
                  return (
                    <div key={i} className="grid grid-cols-2 items-end gap-2 border-b border-rule pb-2 sm:grid-cols-[minmax(0,1.6fr)_repeat(6,72px)_auto]">
                      <PlayerSelect players={card.batting_side === 'us' ? them : players} value={b.player_id} onChange={(v) => upd({ player_id: v })} label={`Bowler ${i + 1}`} />
                      <Field label="Overs"><input className="field num" value={b.overs} onChange={(e) => upd({ overs: e.target.value })} /></Field>
                      {(['maidens', 'runs', 'wickets', 'wides', 'no_balls'] as const).map((k) => <Field key={k} label={k === 'no_balls' ? 'NB' : cap(k)}><input className="field num" type="number" min={0} value={b[k]} onChange={(e) => upd({ [k]: num(e.target.value) })} /></Field>)}
                      <Button small variant="quiet" onClick={() => setBowl(bowl.filter((_, j) => j !== i))}>Remove</Button>
                    </div>
                  )
                })}
              </div>
            )}
          </Section>
          <div className="mt-4"><Button variant="primary" disabled={bat.length + bowl.length === 0} onClick={save}>Save scorecard</Button></div>

          <Section title="Import ball-by-ball data from CSV">
            <p className="mb-2 max-w-[80ch] text-ink-2">One row per ball, in order. Required columns: <code>striker</code>, <code>bowler</code> (player names). Optional: <code>non_striker</code>, <code>runs_bat</code>, <code>wides</code>, <code>no_balls</code>, <code>byes</code>, <code>leg_byes</code>, <code>wicket_kind</code>, <code>player_out</code>, <code>bowl_type</code>, <code>x</code>, <code>y</code>, <code>shot_type</code>, <code>shot_angle</code>. Names not already in the squad are added. The file is checked against the scoring rules before anything is saved.</p>
            <div className="flex flex-wrap items-end gap-2">
              <Field label="CSV file" className="w-full max-w-[360px]"><input className="field py-1.5" type="file" accept=".csv,text/csv" onChange={(e) => setFile(e.target.files?.[0] ?? null)} /></Field>
              <Button disabled={!file} onClick={importCsv}>Import balls</Button>
            </div>
          </Section>
        </>
      )}
    </div>
  )
}
