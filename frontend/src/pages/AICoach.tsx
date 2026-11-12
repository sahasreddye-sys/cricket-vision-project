import { Send } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useApp } from '../context'
import { Bars, LineTrend, SeriesKey } from '../components/Chart'
import { Async, Button, DataTable, Empty, Field, Notice, Page, PlayerSelect, Section, Tabs, useAsync, useToast } from '../components/ui'
import { api, qs } from '../lib/api'
import { cap, day, fmt, today } from '../lib/format'

type Tab = 'ask' | 'recommendations' | 'progress'

export default function AICoach() {
  const { players, user } = useApp()
  const [tab, setTab] = useState<Tab>('ask')
  const [playerId, setPlayerId] = useState<number | null>(user.player_id ?? players[0]?.id ?? null)
  return (
    <Page title="AI Coach" lead="Answers and training recommendations worked out from your team's recorded data. When the data for an answer is missing, the coach tells you what to record.">
      <Tabs value={tab} onChange={setTab} tabs={[{ id: 'ask', label: 'Ask the coach' }, { id: 'recommendations', label: 'Recommendations' }, { id: 'progress', label: 'Progress tracker' }]} />
      {tab !== 'recommendations' && players.length > 0 && (
        <div className="mb-5 max-w-[320px]"><PlayerSelect players={players} value={playerId} onChange={setPlayerId} label={tab === 'ask' ? '"I" and "my" refer to' : 'Player'} allowEmpty={tab === 'ask' ? 'Nobody in particular' : undefined} /></div>
      )}
      {tab === 'ask' && <Ask playerId={playerId} />}
      {tab === 'recommendations' && <Recommendations />}
      {tab === 'progress' && (playerId ? <Progress playerId={playerId} /> : <Empty title="Add a player first">Training logs and goals belong to a player. Add the squad in the Team Hub.</Empty>)}
    </Page>
  )
}

interface Turn { q: string; a?: any; error?: string }

function Ask({ playerId }: { playerId: number | null }) {
  const { team } = useApp()
  const [turns, setTurns] = useState<Turn[]>([])
  const [text, setText] = useState('')
  const [useLlm, setUseLlm] = useState(false)
  const [busy, setBusy] = useState(false)
  const suggestions = useAsync(() => api.get<string[]>('/coach/suggestions'), [])
  const end = useRef<HTMLDivElement>(null)
  useEffect(() => { end.current?.scrollIntoView({ block: 'nearest' }) }, [turns])

  const ask = async (q: string) => {
    q = q.trim()
    if (!q || busy) return
    setText(''); setBusy(true)
    setTurns((t) => [...t, { q }])
    try {
      const a = await api.post('/coach/ask', { question: q, player_id: playerId, use_llm: useLlm })
      setTurns((t) => t.map((x, i) => (i === t.length - 1 ? { ...x, a } : x)))
    } catch (e: any) { setTurns((t) => t.map((x, i) => (i === t.length - 1 ? { ...x, error: e.message } : x))) }
    setBusy(false)
  }
  return (
    <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_300px]">
      <div className="min-w-0">
        <div className="flex min-h-[220px] flex-col gap-4">
          {turns.length === 0 && <Empty title="Ask about your team's records">Try one of the suggested questions, or ask about batting, bowling and fielding records, bowling speeds, who does best against pace or spin, team weaknesses, or what a player should practise.</Empty>}
          {turns.map((t, i) => (
            <div key={i} className="rise">
              <div className="painted text-label text-ink-2">Question</div>
              <div className="mb-2 font-semibold">{t.q}</div>
              {t.error && <Notice tone="error">{t.error}</Notice>}
              {!t.a && !t.error && <div className="text-ink-2">Looking through the records…</div>}
              {t.a && (
                <div className="border-l border-rule-strong pl-3">
                  <div>{t.a.answer}</div>
                  {t.a.evidence?.length > 0 && (
                    <div className="mt-2">
                      <div className="painted text-label text-ink-2">Evidence from stored data</div>
                      <ul className="mt-0.5 text-ink-2">{t.a.evidence.map((e: string, j: number) => <li key={j} className="num">{e}</li>)}</ul>
                    </div>
                  )}
                  <div className="mt-1.5 text-label text-ink-2">
                    {t.a.engine === 'llm' ? 'Phrased by the language model from the facts above.' : 'Rule-based answer.'}
                    {t.a.about_player ? ` "I" was read as ${t.a.about_player}.` : ''}
                    {t.a.llm_note ? ` ${t.a.llm_note}` : ''}
                  </div>
                </div>
              )}
            </div>
          ))}
          <div ref={end} />
        </div>
        <form className="mt-4 flex items-end gap-2 border-t border-rule-strong pt-3" onSubmit={(e) => { e.preventDefault(); ask(text) }}>
          <Field label="Your question" className="flex-1"><input className="field" value={text} maxLength={500} placeholder="e.g. Which of our bowlers has the best economy?" onChange={(e) => setText(e.target.value)} /></Field>
          <Button variant="primary" type="submit" busy={busy} disabled={!text.trim()}><Send size={15} aria-hidden />Ask</Button>
        </form>
        <label className={`mt-2 flex items-center gap-2 ${team.llm_available ? '' : 'text-ink-2'}`}>
          <input type="checkbox" checked={useLlm && team.llm_available} disabled={!team.llm_available} onChange={(e) => setUseLlm(e.target.checked)} />
          Phrase answers with a language model
          <span className="text-label text-ink-2">{team.llm_available ? '(it is given only the retrieved facts)' : '(not configured on this server; the built-in coach is used)'}</span>
        </label>
      </div>
      <div>
        <h3 className="painted mb-2 border-b border-rule-strong pb-2 text-text">Suggested questions</h3>
        <ul className="flex flex-col">
          {suggestions.data?.map((s) => <li key={s}><button className="w-full border-b border-rule py-1.5 text-left text-ink-2 hover:text-ink" onClick={() => ask(s)}>{s}</button></li>)}
        </ul>
      </div>
    </div>
  )
}

function Recommendations() {
  const state = useAsync(() => api.get('/coach/recommendations'), [])
  return (
    <Async state={state}>
      {(d: any) => d.team.length === 0 && d.players.length === 0 ? (
        <Empty title="No recommendations yet">Recommendations are triggered when a recorded figure crosses a coaching threshold: for example fewer than 40% of practice deliveries in the target zone, a much lower strike rate against spin than pace, or a catch success rate below 60%. Record matches, net sessions and fielding to give the coach something to work from.</Empty>
      ) : (
        <>
          {d.team.length > 0 && (
            <Section title="Team">
              <ul className="flex flex-col">{d.team.map((i: any) => <li key={i.title} className="border-b border-rule py-2"><div><b>{i.title}.</b> {i.detail}</div><div className="text-label text-ink-2">{i.kind === 'weakness' ? 'Needs work' : i.kind === 'strength' ? 'Strength' : 'Team figure'} · {i.evidence}</div></li>)}</ul>
            </Section>
          )}
          {d.players.map((p: any) => (
            <Section key={p.player_id} title={p.name}>
              <DataTable rows={p.recommendations} rowKey={(r: any) => r.area} cols={[
                { key: 'a', label: 'Area', render: (r: any) => <b>{r.area}</b> },
                { key: 'r', label: 'Recommendation and drill', render: (r: any) => <div><div>{r.recommendation}</div><div className="text-ink-2">{r.drill}</div></div> },
                { key: 'e', label: 'Evidence', render: (r: any) => <span className="text-ink-2">{r.evidence}</span> },
              ]} />
            </Section>
          ))}
        </>
      )}
    </Async>
  )
}

const METRICS: [string, string][] = [['', 'No measurement (tick off by hand)'], ['max_speed', 'Fastest recorded speed (km/h)'], ['accuracy_pct', 'Practice deliveries in target zone (%)'], ['batting_average', 'Batting average'], ['strike_rate', 'Batting strike rate'], ['runs', 'Runs'], ['wickets', 'Wickets'], ['economy', 'Bowling economy (lower is better)'], ['catch_pct', 'Catch success (%)']]

function Progress({ playerId }: { playerId: number }) {
  const { canEdit } = useApp()
  const toast = useToast()
  const state = useAsync(() => api.get(`/progress${qs({ player_id: playerId })}`), [playerId])
  const [log, setLog] = useState({ date: today(), kind: 'bowling', duration_min: '60', intensity: '3', notes: '' })
  const [goal, setGoal] = useState({ title: '', metric: '', target_value: '', due_date: '' })
  const [period, setPeriod] = useState<'weekly' | 'monthly'>('weekly')
  const editable = canEdit(playerId)

  const addLog = async (e: React.FormEvent) => {
    e.preventDefault()
    try { await api.post('/training', { player_id: playerId, ...log, duration_min: parseInt(log.duration_min, 10), intensity: parseInt(log.intensity, 10) }); toast('Training logged'); setLog({ ...log, notes: '' }); state.reload() } catch (err: any) { toast(err.message, 'error') }
  }
  const addGoal = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      await api.post('/goals', { player_id: playerId, title: goal.title, metric: goal.metric || null, target_value: goal.target_value === '' ? null : parseFloat(goal.target_value), due_date: goal.due_date || null })
      toast('Goal added'); setGoal({ title: '', metric: '', target_value: '', due_date: '' }); state.reload()
    } catch (err: any) { toast(err.message, 'error') }
  }
  const setStatus = async (id: number, status: string) => { try { await api.patch(`/goals/${id}`, { status }); state.reload() } catch (err: any) { toast(err.message, 'error') } }
  const kinds = ['batting', 'bowling', 'fielding', 'fitness', 'match']
  const kindSeries = kinds.map((k, i) => ({ key: k, label: cap(k), colour: ['var(--ink)', 'var(--green)', 'var(--red)', 'var(--ink-2)', 'var(--accent)'][i] }))

  return (
    <Async state={state}>
      {(p: any) => (
        <>
          {!editable && <div className="mb-4"><Notice>You can view this player's progress. Only a coach or the player can add to it.</Notice></div>}
          <div className="mt-8 grid gap-x-10 gap-y-8 lg:grid-cols-2">
            <div>
              <Section title="Training log">
                {editable && (
                  <form onSubmit={addLog} className="mb-4 grid grid-cols-2 items-end gap-3 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_90px_110px]">
                    <Field label="Date"><input className="field" type="date" required max={today()} value={log.date} onChange={(e) => setLog({ ...log, date: e.target.value })} /></Field>
                    <Field label="Type"><select className="field" value={log.kind} onChange={(e) => setLog({ ...log, kind: e.target.value })}>{kinds.map((k) => <option key={k} value={k}>{cap(k)}</option>)}</select></Field>
                    <Field label="Minutes"><input className="field num" type="number" min={1} max={600} required value={log.duration_min} onChange={(e) => setLog({ ...log, duration_min: e.target.value })} /></Field>
                    <Field label="Effort (1–5)"><select className="field" value={log.intensity} onChange={(e) => setLog({ ...log, intensity: e.target.value })}>{[1, 2, 3, 4, 5].map((n) => <option key={n}>{n}</option>)}</select></Field>
                    <Field label="Notes" className="col-span-2 sm:col-span-3"><input className="field" maxLength={2000} value={log.notes} onChange={(e) => setLog({ ...log, notes: e.target.value })} /></Field>
                    <Button variant="primary" type="submit">Log session</Button>
                  </form>
                )}
                {p.training.length === 0 ? <p className="text-ink-2">No training logged yet.</p> : (
                  <div className="max-h-[300px] overflow-y-auto">
                    <DataTable dense rows={p.training} rowKey={(r: any) => r.id} cols={[
                      { key: 'd', label: 'Date', render: (r: any) => day(r.date) },
                      { key: 'k', label: 'Type', render: (r: any) => cap(r.kind) },
                      { key: 'm', label: 'Min', num: true, render: (r: any) => r.duration_min },
                      { key: 'i', label: 'Effort', num: true, render: (r: any) => r.intensity },
                      { key: 'n', label: 'Notes', render: (r: any) => <span className="text-ink-2">{r.notes}</span> },
                      { key: 'x', label: '', render: (r: any) => editable && <Button small variant="quiet" onClick={async () => { await api.del(`/training/${r.id}`); state.reload() }}>Remove</Button> },
                    ]} />
                  </div>
                )}
              </Section>
              {p[period].length > 0 && (
                <Section title="Training minutes" aside={<><button className={period === 'weekly' ? 'font-semibold text-ink underline' : 'underline'} onClick={() => setPeriod('weekly')}>By week</button><button className={period === 'monthly' ? 'font-semibold text-ink underline' : 'underline'} onClick={() => setPeriod('monthly')}>By month</button></>}>
                  <Bars data={p[period].map((w: any) => ({ ...w, period: period === 'weekly' ? day(w.period).replace(/ \d{4}$/, '') : w.period }))} x="period" series={kindSeries} stacked unit="min" height={200} />
                  <SeriesKey series={kindSeries} />
                </Section>
              )}
            </div>
            <div>
              <Section title="Development goals">
                {editable && (
                  <form onSubmit={addGoal} className="mb-4 grid grid-cols-2 items-end gap-3">
                    <Field label="Goal" className="col-span-2"><input className="field" required maxLength={200} value={goal.title} placeholder="e.g. Hit the target zone with half my deliveries" onChange={(e) => setGoal({ ...goal, title: e.target.value })} /></Field>
                    <Field label="Measured by" className="col-span-2"><select className="field" value={goal.metric} onChange={(e) => setGoal({ ...goal, metric: e.target.value })}>{METRICS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></Field>
                    <Field label="Target value"><input className="field num" type="number" step="any" required={!!goal.metric} disabled={!goal.metric} value={goal.target_value} onChange={(e) => setGoal({ ...goal, target_value: e.target.value })} /></Field>
                    <Field label="By (optional)"><input className="field" type="date" value={goal.due_date} onChange={(e) => setGoal({ ...goal, due_date: e.target.value })} /></Field>
                    <Button variant="primary" type="submit">Add goal</Button>
                  </form>
                )}
                {p.goals.length === 0 ? <p className="text-ink-2">No goals set yet.</p> : (
                  <ul className="flex flex-col">
                    {p.goals.map((g: any) => (
                      <li key={g.id} className="border-b border-rule py-2">
                        <div className="flex flex-wrap items-start justify-between gap-2">
                          <div className="min-w-0">
                            <div className={g.status === 'dropped' ? 'text-ink-2 line-through' : 'font-semibold'}>{g.title}</div>
                            <div className="text-label text-ink-2">
                              {cap(g.status)}{g.due_date ? ` · by ${day(g.due_date)}` : ''}
                              {g.metric && <> · now <b className="num text-ink">{fmt(g.current_value)}</b> against a target of <b className="num text-ink">{fmt(g.target_value)}</b>{g.met === true && g.status === 'open' ? ' · target reached' : g.current_value == null ? ' · nothing recorded yet' : ''}</>}
                            </div>
                          </div>
                          {editable && (
                            <div className="flex gap-1">
                              {g.status !== 'achieved' && <Button small variant={g.met ? 'primary' : 'quiet'} onClick={() => setStatus(g.id, 'achieved')}>Mark achieved</Button>}
                              {g.status === 'open' && <Button small variant="quiet" onClick={() => setStatus(g.id, 'dropped')}>Drop</Button>}
                              {g.status !== 'open' && <Button small variant="quiet" onClick={() => setStatus(g.id, 'open')}>Reopen</Button>}
                            </div>
                          )}
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </Section>
              <Section title="Milestones">
                {p.milestones.length === 0 ? <p className="text-ink-2">Milestones appear as runs, wickets, speeds and achieved goals are recorded.</p> : (
                  <ul className="flex flex-col">{p.milestones.map((m: any, i: number) => <li key={i} className="flex justify-between gap-3 border-b border-rule py-1.5"><span>{m.title}</span><span className="shrink-0 text-label text-ink-2">{day(m.date)}</span></li>)}</ul>
                )}
              </Section>
            </div>
          </div>
          <div className="mt-8 grid gap-x-10 gap-y-8 lg:grid-cols-2">
            {p.batting_scores.length > 1 && (
              <Section title="Runs by innings" aside={trendText(p.batting_trend, 'runs per innings')}>
                <LineTrend data={p.batting_scores.map((s: any, i: number) => ({ n: `${i + 1}`, Runs: s.runs, Trend: p.batting_trend?.fitted?.[i] }))} x="n" series={[{ key: 'Runs', label: 'Runs' }, { key: 'Trend', label: 'Trend', colour: 'var(--ink-2)', dashed: true }]} height={190} />
              </Section>
            )}
            {p.speeds.length > 1 && (
              <Section title="Recorded speeds" aside={trendText(p.speed_trend, 'km/h per reading')}>
                <LineTrend data={p.speeds.map((s: any, i: number) => ({ n: `${i + 1}`, Speed: s.kmh, Trend: p.speed_trend?.fitted?.[i] }))} x="n" series={[{ key: 'Speed', label: 'Speed' }, { key: 'Trend', label: 'Trend', colour: 'var(--ink-2)', dashed: true }]} unit="km/h" height={190} />
              </Section>
            )}
          </div>
        </>
      )}
    </Async>
  )
}

function trendText(t: any, unit: string) {
  if (!t || t.status !== 'ok') return 'Needs 5 readings for a trend'
  return t.direction === 'no clear trend' ? 'No clear trend (the 95% range includes zero)' : `Trending ${t.direction}: ${t.slope > 0 ? '+' : ''}${fmt(t.slope, 2)} ${unit}`
}
