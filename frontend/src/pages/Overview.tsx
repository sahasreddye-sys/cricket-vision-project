import { Link } from 'react-router-dom'
import { useApp } from '../context'
import { Async, Board, Button, DataTable, Empty, Notice, Page, Section, Win, useAsync } from '../components/ui'
import { api } from '../lib/api'
import { day, fmt } from '../lib/format'

export default function Overview() {
  const { team, isCoach, user } = useApp()
  const state = useAsync(() => api.get('/overview'), [])
  return (
    <Page title={team.name || 'Overview'} lead={team.name ? undefined : 'Give the team a name in Settings and it appears here.'}
      actions={isCoach ? <>
        <Link to="/team"><Button>Add player</Button></Link>
        <Link to="/matches"><Button variant="primary">Add match</Button></Link>
      </> : undefined}>
      <Async state={state}>
        {(o) => {
          const c = o.counts
          const blank = c.players === 0 && c.matches_played === 0 && c.speed_readings === 0 && c.deliveries === 0
          return (
            <>
              {team.has_sample_data && <div className="mb-4"><Notice tone="warn" title="Synthetic sample data is loaded">Players and matches marked as sample data are computer-generated, not real results. Remove them in Settings before recording real matches.</Notice></div>}
              <Board cols={6}>
                <Win label="Played" value={c.matches_played || null} hint={c.matches_played ? undefined : 'Score a match'} />
                <Win label="Won" value={c.matches_played ? c.won : null} tone="green" />
                <Win label="Lost" value={c.matches_played ? c.lost : null} tone="red" />
                <Win label="Squad" value={c.players || null} hint={c.players ? 'active players' : 'Add players'} />
                <Win label="Speed readings" value={c.speed_readings || null} hint={c.speed_readings ? undefined : 'Time a delivery'} />
                <Win label="Deliveries mapped" value={c.deliveries || null} hint={c.deliveries ? 'line and length' : 'Log a net session'} />
              </Board>

              {blank && (
                <div className="mt-6">
                  <Empty title="The board is blank until you put something on it" action={isCoach ? <>
                    <Link to="/team"><Button variant="primary">Add your players</Button></Link>
                    <Link to="/matches"><Button>Add a fixture or score a match</Button></Link>
                    <Link to="/bowling"><Button>Time a delivery</Button></Link>
                  </> : <Link to="/bowling"><Button variant="primary">Open the Bowling Lab</Button></Link>}>
                    {isCoach
                      ? 'Start with the squad, then score a match ball by ball or enter a finished scorecard. Statistics, leaderboards and coaching notes fill in from what you record.'
                      : user.player_id ? 'Log a speed reading, a net session or a training session to start your record.' : 'Ask your coach to link this account to your player profile so you can log your own sessions.'}
                  </Empty>
                </div>
              )}

              <div className="mt-8 grid gap-x-10 gap-y-8 lg:grid-cols-2">
                <div>
                  <Section title="Leading batters" aside={o.stats_scope}>
                    {o.top_batters.length ? (
                      <DataTable rows={o.top_batters} rowKey={(r: any) => r.player} dense cols={[
                        { key: 'n', label: 'Batter', render: (r: any) => <Link className="draw" to={`/team/player/${r.player}`}>{r.name}</Link> },
                        { key: 'i', label: 'Inns', num: true, render: (r: any) => r.innings },
                        { key: 'r', label: 'Runs', num: true, render: (r: any) => <b>{r.runs}</b> },
                        { key: 'a', label: 'Avg', num: true, render: (r: any) => fmt(r.average) },
                        { key: 's', label: 'SR', num: true, render: (r: any) => fmt(r.strike_rate, 0) },
                      ]} />
                    ) : <p className="text-ink-2">No innings recorded yet.</p>}
                  </Section>
                  <Section title="Leading bowlers" aside={o.fastest ? `Fastest recorded: ${o.fastest.name}, ${fmt(o.fastest.kmh)} km/h` : undefined}>
                    {o.top_bowlers.length ? (
                      <DataTable rows={o.top_bowlers} rowKey={(r: any) => r.player} dense cols={[
                        { key: 'n', label: 'Bowler', render: (r: any) => <Link className="draw" to={`/team/player/${r.player}`}>{r.name}</Link> },
                        { key: 'o', label: 'Overs', num: true, render: (r: any) => r.overs },
                        { key: 'w', label: 'Wkts', num: true, render: (r: any) => <b>{r.wickets}</b> },
                        { key: 'e', label: 'Econ', num: true, render: (r: any) => fmt(r.economy, 2) },
                      ]} />
                    ) : <p className="text-ink-2">No overs recorded yet.</p>}
                  </Section>
                  <Section title="What the data says">
                    {o.insights.length ? (
                      <ul className="flex flex-col">
                        {o.insights.map((i: any) => (
                          <li key={i.title} className="border-b border-rule py-2">
                            <div><b>{i.title}.</b> {i.detail}</div>
                            <div className="text-label text-ink-2">{i.kind === 'weakness' ? 'Needs work' : i.kind === 'strength' ? 'Strength' : 'Team figure'} · {i.evidence}</div>
                          </li>
                        ))}
                      </ul>
                    ) : <p className="text-ink-2">Team insights appear once there are enough recorded overs, innings and catches to compare against the coaching thresholds.</p>}
                    {o.my_recommendations.length > 0 && (
                      <div className="mt-4">
                        <h3 className="painted mb-1 text-label text-ink-2">For you</h3>
                        {o.my_recommendations.map((r: any) => <p key={r.area} className="border-b border-rule py-2"><b>{r.area}.</b> {r.recommendation} <span className="text-label text-ink-2">{r.evidence}</span></p>)}
                        <Link to="/coach" className="mt-2 inline-block underline">Open the AI Coach</Link>
                      </div>
                    )}
                  </Section>
                </div>
                <div>
                  <Section title="Upcoming matches">
                    {o.upcoming.length ? (
                      <DataTable rows={o.upcoming} rowKey={(r: any) => r.id} dense cols={[
                        { key: 'd', label: 'Date', render: (r: any) => day(r.date) },
                        { key: 'o', label: 'Opponent', render: (r: any) => <Link className="draw" to={`/matches/${r.id}`}>{r.opponent}</Link> },
                        { key: 'v', label: 'Venue', render: (r: any) => r.venue || '–' },
                        { key: 'f', label: 'Format', render: (r: any) => r.format },
                      ]} />
                    ) : <p className="text-ink-2">No fixtures scheduled. Add one in the Match Center.</p>}
                  </Section>
                  <Section title="Recent results">
                    {o.recent_matches.length ? (
                      <DataTable rows={o.recent_matches} rowKey={(r: any) => r.id} dense cols={[
                        { key: 'd', label: 'Date', render: (r: any) => day(r.date) },
                        { key: 'o', label: 'Opponent', render: (r: any) => <Link className="draw" to={`/matches/${r.id}`}>{r.opponent}</Link> },
                        { key: 's', label: 'Score', render: (r: any) => r.scores.map((s: any) => `${s.side === 'us' ? 'Us' : 'Them'} ${s.total}/${s.wickets}`).join(' · ') },
                        { key: 'r', label: 'Result', render: (r: any) => <span className={r.outcome === 'won' ? 'text-green' : r.outcome === 'lost' ? 'text-red' : ''}>{r.outcome ? r.outcome[0].toUpperCase() + r.outcome.slice(1).replace('_', ' ') : '–'}</span> },
                      ]} />
                    ) : <p className="text-ink-2">No completed matches yet.</p>}
                  </Section>
                  <Section title="Recent sessions and analysis">
                    {o.recent_sessions.length ? (
                      <DataTable rows={o.recent_sessions} rowKey={(_: any, i) => i} dense cols={[
                        { key: 'd', label: 'Date', render: (r: any) => day(r.date) },
                        { key: 'k', label: 'Session', render: (r: any) => r.kind },
                        { key: 'p', label: 'Player', render: (r: any) => r.player || '–' },
                        { key: 'x', label: 'Detail', render: (r: any) => r.detail },
                      ]} />
                    ) : <p className="text-ink-2">Net sessions, training logs and video analyses show here as they are recorded.</p>}
                  </Section>
                </div>
              </div>
            </>
          )
        }}
      </Async>
    </Page>
  )
}
