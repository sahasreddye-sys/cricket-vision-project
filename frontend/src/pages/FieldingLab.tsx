import { useEffect, useState } from 'react'
import { useApp } from '../context'
import { Ground, nearestPosition } from '../components/Ground'
import type { Fielder } from '../components/Ground'
import { VideoPose } from '../components/VideoPose'
import { Async, Button, DataTable, Empty, Field, Notice, Page, PlayerSelect, Section, Seg, Tabs, useAsync, useToast } from '../components/ui'
import { api, qs } from '../lib/api'
import { cap, day, pct, today } from '../lib/format'

type Tab = 'positions' | 'performance' | 'catching'
type Style = 'attacking' | 'balanced' | 'defensive'

const PRESETS: Record<Style, string[]> = {
  attacking: ['slip', 'gully', 'point', 'cover', 'mid_off', 'mid_on', 'midwicket', 'square_leg', 'fine_leg'],
  balanced: ['slip', 'point', 'cover', 'mid_off', 'mid_on', 'midwicket', 'square_leg', 'third_man', 'fine_leg'],
  defensive: ['deep_point', 'deep_cover', 'long_off', 'long_on', 'deep_midwicket', 'deep_square_leg', 'fine_leg', 'third_man', 'cover'],
}
const KINDS = [
  ['catch', 'Catch taken'], ['drop', 'Catch dropped'], ['run_out', 'Run-out'], ['direct_hit', 'Direct-hit run-out'], ['missed_run_out', 'Run-out chance missed'],
  ['stumping', 'Stumping'], ['missed_stumping', 'Stumping missed'], ['clean_stop', 'Clean stop'], ['misfield', 'Misfield'],
]

export default function FieldingLab() {
  const [tab, setTab] = useState<Tab>('positions')
  return (
    <Page title="Fielding Lab" lead="Set a field, record catches, run-outs and ground fielding, and look at catching technique on video.">
      <Tabs value={tab} onChange={setTab} tabs={[{ id: 'positions', label: 'Field positions' }, { id: 'performance', label: 'Performance tracker' }, { id: 'catching', label: 'Catching technique' }]} />
      {tab === 'positions' && <Positions />}
      {tab === 'performance' && <Performance />}
      {tab === 'catching' && <VideoPose mode="catching" />}
    </Page>
  )
}

function Positions() {
  const { players, opposition, isCoach } = useApp()
  const toast = useToast()
  const named = useAsync(() => api.get<Fielder[]>('/fielding/positions'), [])
  const setups = useAsync(() => api.get<any[]>('/fielding/setups'), [])
  const [style, setStyle] = useState<Style>('balanced')
  const [field, setField] = useState<Fielder[]>([])
  const [batterId, setBatterId] = useState<number | null>(null)
  const [name, setName] = useState('')
  const [rec, setRec] = useState<any | null>(null)
  const batters = [...opposition.map((p) => ({ ...p, name: `${p.name} (${p.side})` })), ...players]

  const preset = (s: Style) => { if (named.data) setField(PRESETS[s].map((n) => named.data!.find((p) => p.name === n)!).filter(Boolean)) }
  useEffect(() => { if (named.data && field.length === 0) preset('balanced') /* eslint-disable-next-line */ }, [named.data])

  const move = (i: number, angle: number, distance: number) => setField((f) => f.map((p, j) => (j === i ? { name: nearestPosition(angle, distance, named.data ?? []), angle, distance } : p)))
  const recommend = async () => {
    if (!batterId) return
    try {
      const r = await api.get(`/fielding/recommend${qs({ batter_id: batterId, style })}`)
      setRec(r)
      if (r.enough_data) { setField(r.positions); toast('Field set from this batter\'s recorded scoring areas') }
    } catch (e: any) { toast(e.message, 'error') }
  }
  const save = async () => {
    try { await api.post('/fielding/setups', { name, style, positions: field }); toast('Field saved'); setName(''); setups.reload() } catch (e: any) { toast(e.message, 'error') }
  }

  return (
    <div className="grid gap-8 lg:grid-cols-[minmax(0,460px)_minmax(0,1fr)]">
      <div>
        <div className="mb-2 flex flex-wrap items-center gap-2">
          <Seg label="Field style" value={style} onChange={(s) => { setStyle(s); preset(s); setRec(null) }} options={[{ id: 'attacking', label: 'Attacking' }, { id: 'balanced', label: 'Balanced' }, { id: 'defensive', label: 'Defensive' }]} />
        </div>
        <Ground fielders={field} onMoveFielder={move} shots={rec?.wagon_wheel?.shots} zones={rec?.wagon_wheel?.zones} />
        <p className="mt-1 text-label text-ink-2">Drag a numbered fielder to move them. The bowler and wicket-keeper are fixed. Shown for a right-handed batter.</p>
      </div>
      <div className="min-w-0">
        <Section title="Fielders">
          <DataTable dense rows={field} rowKey={(_, i) => i} cols={[
            { key: 'n', label: 'No.', num: true, render: (_, i) => i + 1 },
            { key: 'p', label: 'Position', render: (r) => cap(r.name) },
            { key: 'w', label: 'Where', render: (r) => (r.distance > 0.7 ? 'On the boundary' : r.distance > 0.3 ? 'In the ring' : 'Close catcher') },
            ...(rec?.enough_data ? [{ key: 'r', label: 'Why', render: (_: Fielder, i: number) => <span className="text-ink-2">{rec.reasons[i]?.reason ?? ''}</span> }] : []),
          ]} />
        </Section>

        <Section title="Recommend a field for a batter">
          {batters.length === 0 ? <p className="text-ink-2">Recommendations use a batter's recorded shot directions. Score a match with shot directions to build that record.</p> : (
            <div className="flex flex-wrap items-end gap-2">
              <PlayerSelect players={batters} value={batterId} onChange={(v) => { setBatterId(v); setRec(null) }} label="Batter" className="w-full max-w-[320px]" />
              <Button variant="primary" disabled={!batterId} onClick={recommend}>Recommend {style} field</Button>
            </div>
          )}
          {rec && !rec.enough_data && <div className="mt-3"><Notice tone="warn" title="Not enough data for a recommendation">{rec.note}</Notice></div>}
          {rec?.enough_data && <p className="mt-3 text-ink-2">Based on {rec.based_on_shots} plotted scoring shots worth {rec.total_runs} runs. Fielders are shared between zones in proportion to the runs scored there. {rec.note}</p>}
        </Section>

        <Section title="Saved fields">
          {isCoach && (
            <div className="mb-3 flex flex-wrap items-end gap-2">
              <Field label="Name this field" className="w-full max-w-[320px]"><input className="field" value={name} maxLength={120} placeholder="e.g. New ball to a left-hander" onChange={(e) => setName(e.target.value)} /></Field>
              <Button disabled={!name.trim() || field.length === 0} onClick={save}>Save field</Button>
            </div>
          )}
          <Async state={setups} empty={<p className="text-ink-2">No fields saved yet.</p>}>
            {(rows) => (
              <DataTable dense rows={rows} rowKey={(r) => r.id} cols={[
                { key: 'n', label: 'Name', render: (r) => r.name },
                { key: 's', label: 'Style', render: (r) => cap(r.style) },
                { key: 'd', label: 'Saved', render: (r) => day(r.created_at) },
                { key: 'a', label: '', render: (r) => (
                  <div className="flex justify-end gap-1">
                    <Button small variant="quiet" onClick={() => { setField(r.positions); setStyle(r.style); setRec(null) }}>Load</Button>
                    {isCoach && <Button small variant="quiet" onClick={async () => { if (window.confirm(`Delete the saved field "${r.name}"?`)) { await api.del(`/fielding/setups/${r.id}`); setups.reload() } }}>Delete</Button>}
                  </div>
                ) },
              ]} />
            )}
          </Async>
        </Section>
      </div>
    </div>
  )
}

function Performance() {
  const { players, user, canEdit } = useApp()
  const toast = useToast()
  const [playerId, setPlayerId] = useState<number | null>(user.player_id ?? players[0]?.id ?? null)
  const [kind, setKind] = useState('catch')
  const [count, setCount] = useState('1')
  const [date, setDate] = useState(today())
  const tables = useAsync(() => api.get('/stats/tables'), [])
  const events = useAsync(() => api.get<any[]>('/fielding/events'), [])

  const add = async () => {
    try {
      await api.post('/fielding/events', { player_id: playerId, date, kind, count: parseInt(count, 10) || 1 })
      toast('Fielding record added'); tables.reload(); events.reload()
    } catch (e: any) { toast(e.message, 'error') }
  }
  if (players.length === 0) return <Empty title="Add a player first">Fielding records are saved against a player. Add the squad in the Team Hub.</Empty>
  return (
    <div>
      <Section title="Record fielding">
        <div className="grid items-end gap-3 sm:grid-cols-2 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,1.2fr)_100px_minmax(0,1fr)_auto]">
          <PlayerSelect players={players} value={playerId} onChange={setPlayerId} label="Fielder" />
          <Field label="What happened"><select className="field" value={kind} onChange={(e) => setKind(e.target.value)}>{KINDS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></Field>
          <Field label="How many"><input className="field num" type="number" min={1} max={50} value={count} onChange={(e) => setCount(e.target.value)} /></Field>
          <Field label="Date"><input className="field" type="date" value={date} max={today()} onChange={(e) => setDate(e.target.value)} /></Field>
          <Button variant="primary" disabled={!playerId || !canEdit(playerId)} onClick={add}>Add record</Button>
        </div>
      </Section>
      <Section title="Fielding by player" aside="Percentages need recorded chances, taken and missed">
        <Async state={tables}>
          {(t: any) => t.fielding.length === 0 ? <Empty title="No fielding recorded yet">Add catches, drops, run-outs and ground fielding above. Recording the misses as well as the successes is what makes the percentages meaningful.</Empty> : (
            <DataTable rows={t.fielding} rowKey={(r: any) => r.player} cols={[
              { key: 'n', label: 'Fielder', render: (r: any) => r.name },
              { key: 'o', label: 'Chances', num: true, title: 'All recorded fielding opportunities', render: (r: any) => r.opportunities },
              { key: 'c', label: 'Catches', num: true, render: (r: any) => <b>{r.catch}</b> },
              { key: 'd', label: 'Dropped', num: true, render: (r: any) => r.drop },
              { key: 'cp', label: 'Catch %', num: true, render: (r: any) => pct(r.catch_pct) },
              { key: 'ro', label: 'Run-outs', num: true, render: (r: any) => r.run_outs_total },
              { key: 'dh', label: 'Direct hits', num: true, render: (r: any) => r.direct_hit },
              { key: 'st', label: 'Stumpings', num: true, render: (r: any) => r.stumping },
              { key: 'g', label: 'Ground %', num: true, title: 'Clean stops as a share of ground-fielding chances', render: (r: any) => pct(r.ground_pct) },
            ]} />
          )}
        </Async>
      </Section>
      <Section title="Recent records">
        <Async state={events} empty={<p className="text-ink-2">Nothing recorded yet.</p>}>
          {(rows) => (
            <DataTable dense rows={rows.slice(0, 40)} rowKey={(r) => r.id} cols={[
              { key: 'd', label: 'Date', render: (r) => day(r.date) },
              { key: 'p', label: 'Fielder', render: (r) => r.player },
              { key: 'k', label: 'Record', render: (r) => KINDS.find(([k]) => k === r.kind)?.[1] ?? cap(r.kind) },
              { key: 'c', label: 'Count', num: true, render: (r) => r.count },
              { key: 'x', label: '', render: (r) => canEdit(r.player_id) && <Button small variant="quiet" onClick={async () => { await api.del(`/fielding/events/${r.id}`); events.reload(); tables.reload() }}>Remove</Button> },
            ]} />
          )}
        </Async>
      </Section>
    </div>
  )
}
