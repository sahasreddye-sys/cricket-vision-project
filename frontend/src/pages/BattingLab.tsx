import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useApp } from '../context'
import { Ground } from '../components/Ground'
import { VideoPose } from '../components/VideoPose'
import { Async, Board, DataTable, Empty, Field, Page, PlayerSelect, Section, Tabs, Win, useAsync } from '../components/ui'
import { api, qs } from '../lib/api'
import { cap, day, fmt, pct } from '../lib/format'

type Tab = 'shots' | 'wagon' | 'action'

export default function BattingLab() {
  const { players, opposition, user } = useApp()
  const [tab, setTab] = useState<Tab>('shots')
  const everyone = [...players, ...opposition.map((p) => ({ ...p, name: `${p.name} (${p.side})` }))]
  const [playerId, setPlayerId] = useState<number | null>(user.player_id ?? players[0]?.id ?? null)
  return (
    <Page title="Batting Lab" lead="Where a batter scores, how they fare against pace and spin and each line and length, and what their stance and shot look like on video.">
      <Tabs value={tab} onChange={setTab} tabs={[{ id: 'shots', label: 'Shot selection' }, { id: 'wagon', label: 'Wagon wheel' }, { id: 'action', label: 'Action analyzer' }]} />
      {tab !== 'action' && (
        everyone.length === 0
          ? <Empty title="Add a player first">Batting records come from matches scored in the Match Center. Add the squad in the Team Hub, then score a match.</Empty>
          : <div className="mb-5 max-w-[360px]"><PlayerSelect players={everyone} value={playerId} onChange={setPlayerId} label="Batter" /></div>
      )}
      {tab === 'shots' && playerId && <Shots playerId={playerId} />}
      {tab === 'wagon' && playerId && <Wagon playerId={playerId} />}
      {tab === 'action' && <VideoPose mode="batting" />}
    </Page>
  )
}

function NoBalls() {
  return (
    <Empty title="No balls recorded for this batter" action={<Link to="/matches" className="underline">Open the Match Center</Link>}>
      Shot types, directions and the bowling faced are recorded ball by ball while scoring a match, or imported from a CSV file. Once this batter has faced recorded balls, their scoring patterns appear here.
    </Empty>
  )
}

function SplitTable({ title, rows, order }: { title: string; rows: Record<string, any>; order?: string[] }) {
  const keys = (order ?? Object.keys(rows)).filter((k) => rows[k])
  if (!keys.length) return null
  return (
    <Section title={title}>
      <DataTable dense rows={keys.map((k) => ({ k, ...rows[k] }))} rowKey={(r: any) => r.k} cols={[
        { key: 'k', label: '', render: (r: any) => cap(r.k) },
        { key: 'b', label: 'Balls', num: true, render: (r: any) => r.balls },
        { key: 'r', label: 'Runs', num: true, render: (r: any) => r.runs },
        { key: 'o', label: 'Outs', num: true, render: (r: any) => r.dismissals },
        { key: 'a', label: 'Avg', num: true, title: 'Runs per dismissal', render: (r: any) => fmt(r.average) },
        { key: 's', label: 'SR', num: true, title: 'Runs per 100 balls', render: (r: any) => fmt(r.strike_rate, 0) },
        { key: 'd', label: 'Dots', num: true, render: (r: any) => pct(r.dot_pct) },
      ]} />
    </Section>
  )
}

function Shots({ playerId }: { playerId: number }) {
  const splits = useAsync(() => api.get(`/stats/splits${qs({ player_id: playerId })}`), [playerId])
  const report = useAsync(() => api.get(`/opposition/report${qs({ player_id: playerId })}`), [playerId])
  return (
    <Async state={splits}>
      {(s: any) => {
        const b = s.batting
        if (!b.overall.balls) return <NoBalls />
        return (
          <>
            <Board cols={5}>
              <Win label="Balls faced" value={b.overall.balls} />
              <Win label="Runs" value={b.overall.runs} tone="accent" />
              <Win label="Dismissals" value={b.overall.dismissals} />
              <Win label="Strike rate" value={fmt(b.overall.strike_rate, 0)} />
              <Win label="Dot balls" value={pct(b.overall.dot_pct)} />
            </Board>
            {report.data?.findings?.length > 0 && (
              <Section title="Scoring patterns" aside={report.data.note}>
                <ul className="flex flex-col">
                  {report.data.findings.map((f: any) => (
                    <li key={f.finding} className="border-b border-rule py-2"><div>{f.finding}</div><div className="text-label text-ink-2">{f.evidence}</div></li>
                  ))}
                </ul>
              </Section>
            )}
            <div className="mt-8 grid gap-x-10 gap-y-8 lg:grid-cols-2">
              <SplitTable title="Against pace and spin" rows={b.bowl_type} order={['pace', 'spin']} />
              <SplitTable title="By shot type" rows={b.shot_type} />
              <SplitTable title="By length" rows={b.length} order={['yorker', 'full', 'good', 'short', 'bouncer', 'full_toss']} />
              <SplitTable title="By line" rows={b.line} order={['wide_leg', 'leg', 'stumps', 'off', 'wide_off']} />
            </div>
            <p className="mt-4 text-label text-ink-2">Splits include only balls where that detail was recorded. A split with fewer than about 20 balls can change completely after one more innings.</p>
          </>
        )
      }}
    </Async>
  )
}

function Wagon({ playerId }: { playerId: number }) {
  const [matchA, setMatchA] = useState<number | null>(null)
  const [matchB, setMatchB] = useState<number | null>(null)
  const [zone, setZone] = useState<string | null>(null)
  const a = useAsync(() => api.get(`/stats/wagon${qs({ player_id: playerId, match_id: matchA })}`), [playerId, matchA])
  const b = useAsync(() => (matchB ? api.get(`/stats/wagon${qs({ player_id: playerId, match_id: matchB })}`) : Promise.resolve(null)), [playerId, matchB])
  return (
    <Async state={a}>
      {(w: any) => {
        if (!w.matches.length) return <NoBalls />
        const options = w.matches.map((m: any) => <option key={m.match_id} value={m.match_id}>Match on {day(m.date)}</option>)
        return (
          <>
            <div className="mb-4 grid max-w-[640px] grid-cols-2 gap-3">
              <Field label="Showing"><select className="field" value={matchA ?? ''} onChange={(e) => setMatchA(e.target.value ? Number(e.target.value) : null)}><option value="">All matches</option>{options}</select></Field>
              <Field label="Compare with"><select className="field" value={matchB ?? ''} onChange={(e) => setMatchB(e.target.value ? Number(e.target.value) : null)}><option value="">Nothing</option>{options}</select></Field>
            </div>
            <div className="grid gap-8 lg:grid-cols-[minmax(0,440px)_minmax(0,1fr)]">
              <div>
                <Ground shots={w.shots} zones={w.zones} highlightZone={zone} onHoverZone={setZone} />
                <p className="mt-1 text-label text-ink-2">Yellow lines are sixes, white lines are fours, shorter lines are runs run. Shown for a right-hander; left-handers are mirrored so off side is always on the right.</p>
              </div>
              <div className="min-w-0">
                <Board cols={4}>
                  <Win label="Runs plotted" value={w.total_runs || null} tone="accent" />
                  <Win label="Off side" value={pct(w.off_side_pct)} />
                  <Win label="Leg side" value={pct(w.leg_side_pct)} />
                  <Win label="Shots not plotted" value={w.unplotted} hint="no direction recorded" />
                </Board>
                {w.strong_zones.length > 0 && <p className="mt-2 text-ink-2">Strongest scoring areas: <b className="text-ink">{w.strong_zones.map((z: string) => cap(z)).join(', ')}</b>.</p>}
                <Section title="Scoring by zone">
                  <DataTable dense rows={w.zones} rowKey={(r: any) => r.zone} onHover={(r: any) => setZone(r ? r.zone : null)} active={(r: any) => r.zone === zone} cols={[
                    { key: 'z', label: 'Zone', render: (r: any) => cap(r.zone) },
                    { key: 's', label: 'Shots', num: true, render: (r: any) => r.shots },
                    { key: 'r', label: 'Runs', num: true, render: (r: any) => <b>{r.runs}</b> },
                    { key: 'p', label: 'Share', num: true, render: (r: any) => pct(r.pct_of_runs) },
                    { key: '4', label: '4s', num: true, render: (r: any) => r.fours },
                    { key: '6', label: '6s', num: true, render: (r: any) => r.sixes },
                    ...(b.data ? [{ key: 'c', label: 'Compared', num: true, render: (r: any) => { const o = b.data.zones.find((z: any) => z.zone === r.zone); return o ? `${o.runs} (${pct(o.pct_of_runs)})` : '–' } }] : []),
                  ]} />
                </Section>
              </div>
            </div>
            {b.data && (
              <Section title="Comparison innings">
                <div className="grid gap-8 lg:grid-cols-[minmax(0,440px)_minmax(0,1fr)]">
                  <Ground shots={b.data.shots} zones={b.data.zones} highlightZone={zone} onHoverZone={setZone} />
                  <div>
                    <Board cols={3}>
                      <Win label="Runs plotted" value={b.data.total_runs || null} tone="accent" />
                      <Win label="Off side" value={pct(b.data.off_side_pct)} />
                      <Win label="Leg side" value={pct(b.data.leg_side_pct)} />
                    </Board>
                    {b.data.strong_zones.length > 0 && <p className="mt-2 text-ink-2">Strongest areas in this match: <b className="text-ink">{b.data.strong_zones.map((z: string) => cap(z)).join(', ')}</b>.</p>}
                  </div>
                </div>
              </Section>
            )}
            <p className="mt-6 text-label text-ink-2">Shot directions are recorded on the ground picker while scoring a match, or imported with a shot_angle column in a ball-by-ball CSV (Match Center).</p>
          </>
        )
      }}
    </Async>
  )
}
