import { useState } from 'react'
import { useApp } from '../context'
import { Async, Button, DataTable, Field, Notice, Page, Section, Seg, useAsync, useToast } from '../components/ui'
import { api } from '../lib/api'

export default function Settings() {
  const { team, user, players, isCoach, reloadTeam, reloadPlayers, theme, setTheme, signOut } = useApp()
  const toast = useToast()
  const [form, setForm] = useState({ name: team.name, season: team.season, default_overs: String(team.default_overs), speed_unit: team.speed_unit })
  const [busy, setBusy] = useState(false)
  const users = useAsync(() => (isCoach ? api.get<any[]>('/users') : Promise.resolve([])), [isCoach])
  const admin = user.role === 'admin'

  const save = async (e: React.FormEvent) => {
    e.preventDefault()
    try { await api.put('/team', { ...form, default_overs: parseInt(form.default_overs, 10) }); await reloadTeam(); toast('Team settings saved') } catch (err: any) { toast(err.message, 'error') }
  }
  const patchUser = async (id: number, body: Record<string, unknown>) => { try { await api.patch(`/users/${id}`, body); users.reload(); toast('Account updated') } catch (err: any) { toast(err.message, 'error') } }
  const sample = async (load: boolean) => {
    if (!load && !window.confirm('Remove all synthetic sample players, matches, sessions and readings? Your own data is not touched.')) return
    setBusy(true)
    try {
      if (load) { const r = await api.post('/sample-data'); toast(`Sample data loaded: ${r.players} players, ${r.matches} matches`) } else { await api.del('/sample-data'); toast('Sample data removed') }
      await Promise.all([reloadTeam(), reloadPlayers()])
    } catch (err: any) { toast(err.message, 'error') }
    setBusy(false)
  }

  return (
    <Page title="Settings">
      <Section title="Team">
        {isCoach ? (
          <form onSubmit={save} className="grid items-end gap-3 sm:grid-cols-2 lg:grid-cols-[minmax(0,1.5fr)_140px_140px_auto_auto]">
            <Field label="Team name"><input className="field" maxLength={120} value={form.name} placeholder="e.g. Greenfield School 1st XI" onChange={(e) => setForm({ ...form, name: e.target.value })} /></Field>
            <Field label="Current season"><input className="field" maxLength={20} value={form.season} onChange={(e) => setForm({ ...form, season: e.target.value })} /></Field>
            <Field label="Usual overs a side"><input className="field num" type="number" min={1} max={100} value={form.default_overs} onChange={(e) => setForm({ ...form, default_overs: e.target.value })} /></Field>
            <div><div className="painted mb-1 text-label text-ink-2">Speeds shown in</div><Seg label="Speed unit" value={form.speed_unit} onChange={(v) => setForm({ ...form, speed_unit: v })} options={[{ id: 'kmh', label: 'km/h' }, { id: 'mph', label: 'mph' }]} /></div>
            <Button variant="primary" type="submit">Save team settings</Button>
          </form>
        ) : <p className="text-ink-2">{team.name || 'Team name not set'} · {team.season} season. Only a coach or the team admin can change team settings.</p>}
      </Section>

      <Section title="Appearance">
        <Seg label="Theme" value={theme} onChange={setTheme} options={[{ id: 'dark', label: 'Dark board' }, { id: 'light', label: 'Whitewash' }]} />
      </Section>

      <Section title="Your account">
        <p>{user.name} · {user.email} · {user.role === 'admin' ? 'Team admin' : user.role === 'coach' ? 'Coach' : 'Player'}{user.player_id ? ` · linked to ${players.find((p) => p.id === user.player_id)?.name ?? 'a player profile'}` : ''}</p>
        {user.role === 'player' && !user.player_id && <p className="mt-1 text-ink-2">Your account is not linked to a player profile yet. Ask your coach to link it so you can log your own readings, sessions and goals.</p>}
        <div className="mt-3"><Button onClick={signOut}>Sign out</Button></div>
      </Section>

      {isCoach && (
        <Section title="Accounts" aside={admin ? 'Give coaches access and link players to their profiles' : 'Only the team admin can change roles'}>
          <Async state={users}>
            {(rows) => (
              <DataTable rows={rows} rowKey={(u) => u.id} cols={[
                { key: 'n', label: 'Name', render: (u) => <b>{u.name}</b> },
                { key: 'e', label: 'Email', render: (u) => u.email },
                { key: 'r', label: 'Role', render: (u) => admin && u.id !== user.id ? (
                  <select className="field h-8 w-32" aria-label={`Role for ${u.name}`} value={u.role} onChange={(e) => patchUser(u.id, { role: e.target.value })}><option value="player">Player</option><option value="coach">Coach</option><option value="admin">Team admin</option></select>
                ) : (u.role === 'admin' ? 'Team admin' : u.role[0].toUpperCase() + u.role.slice(1)) },
                { key: 'p', label: 'Player profile', render: (u) => admin ? (
                  <select className="field h-8 w-48" aria-label={`Player profile for ${u.name}`} value={u.player_id ?? ''} onChange={(e) => patchUser(u.id, e.target.value ? { player_id: Number(e.target.value) } : { unlink_player: true })}>
                    <option value="">Not linked</option>{players.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
                  </select>
                ) : (players.find((p) => p.id === u.player_id)?.name ?? 'Not linked') },
              ]} />
            )}
          </Async>
        </Section>
      )}

      {admin && (
        <Section title="Sample data">
          <div className="flex flex-col gap-3">
            <Notice tone={team.has_sample_data ? 'warn' : 'info'} title={team.has_sample_data ? 'Synthetic sample data is loaded' : 'PitchVision starts empty'}>
              {team.has_sample_data
                ? 'Sample players, matches, net sessions, speed readings and fielding records are in the database. They are computer-generated and labelled as sample data wherever they appear. Remove them before recording real results so they do not mix into your statistics.'
                : 'You can load a synthetic squad of 14 with 8 matches to see how every screen behaves with data in it. Everything loaded is labelled as sample data and can be removed again in one step.'}
            </Notice>
            <div>{team.has_sample_data
              ? <Button variant="danger" busy={busy} onClick={() => sample(false)}>Remove sample data</Button>
              : <Button busy={busy} onClick={() => sample(true)}>Load synthetic sample data</Button>}</div>
          </div>
        </Section>
      )}

      <Section title="About the numbers">
        <ul className="max-w-[80ch] list-disc space-y-1 pl-5 text-ink-2">
          <li>Every statistic is calculated from data your team entered. Nothing is estimated to fill a gap.</li>
          <li>A speed worked out from distance and time is an average over that distance, not the speed at release.</li>
          <li>Pose measurements are 2-D angles from one camera. They are coaching observations, not a medical or legal assessment of an action.</li>
          <li>Ball tracking and the DRS simulation are for training and learning. They are not an official decision system.</li>
          <li>The same Python code produces the figures here and in the project's Jupyter notebooks.</li>
        </ul>
      </Section>
    </Page>
  )
}
