import { useEffect, useState } from 'react'
import { Button, Field, Notice } from '../components/ui'
import { api, setToken } from '../lib/api'

export default function Login({ onSignedIn }: { onSignedIn: () => void }) {
  const [hasUsers, setHasUsers] = useState<boolean | null>(null)
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [form, setForm] = useState({ email: '', name: '', password: '' })
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    api.get('/auth/status').then((s) => { setHasUsers(s.has_users); if (!s.has_users) setMode('register') }, (e) => setError(e.message))
  }, [])

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setBusy(true); setError(null)
    try {
      const body = mode === 'register' ? form : { email: form.email, password: form.password }
      const res = await api.post(`/auth/${mode}`, body)
      setToken(res.token)
      onSignedIn()
    } catch (err: any) { setError(err.message) }
    setBusy(false)
  }
  const first = hasUsers === false

  return (
    <div className="grid min-h-screen lg:grid-cols-[minmax(0,1fr)_480px]">
      {/* the board */}
      <div className="hidden flex-col justify-between bg-plate p-10 text-plate-ink lg:flex">
        <div className="font-board text-fig font-bold uppercase">Pitch<span className="text-accent">Vision</span></div>
        <div className="grid max-w-[620px] grid-cols-3 gap-x-6 gap-y-7">
          {[['Total', '–'], ['Wickets', '–'], ['Overs', '–'], ['Last wicket', '–'], ['Run rate', '–'], ['Target', '–']].map(([l, v]) => (
            <div key={l}>
              <div className="painted text-label text-plate-dim">{l}</div>
              <div className="mt-1.5 flex h-[64px] items-center justify-center rounded-plate border border-white/15 font-board text-fig font-semibold text-plate-dim">{v}</div>
            </div>
          ))}
          <div className="col-span-3 max-w-[56ch]">
            <p className="font-board text-fig font-bold uppercase leading-[1.05] text-plate-ink">Cricket analytics for one school team</p>
            <p className="mt-2 text-plate-dim">Score matches ball by ball, time deliveries, map line and length, and measure actions from phone video. The board stays blank until your team records something, and each figure says how it was worked out.</p>
          </div>
        </div>
        <div className="painted text-label text-plate-dim">Runs on your own computer. Works without an internet connection.</div>
      </div>
      <div className="flex items-center justify-center px-5 py-10">
        <form onSubmit={submit} className="w-full max-w-[380px]">
          <div className="mb-6 font-board text-fig font-bold uppercase lg:hidden">Pitch<span className="text-accent">Vision</span></div>
          <h1 className="font-board text-fig font-bold uppercase">{first ? 'Set up your team' : mode === 'login' ? 'Sign in' : 'Create an account'}</h1>
          <p className="mb-5 mt-1 text-ink-2">
            {first ? 'The first account becomes the team admin, who can add players, score matches and give coaches access.'
              : mode === 'login' ? 'Use the email and password for your PitchVision account.'
                : 'New accounts start as players. Your coach links your account to your player profile.'}
          </p>
          <div className="flex flex-col gap-3.5">
            {mode === 'register' && (
              <Field label="Your name"><input className="field" required value={form.name} autoComplete="name" onChange={(e) => setForm({ ...form, name: e.target.value })} /></Field>
            )}
            <Field label="Email"><input className="field" type="email" required value={form.email} autoComplete="email" onChange={(e) => setForm({ ...form, email: e.target.value })} /></Field>
            <Field label="Password" hint={mode === 'register' ? 'At least 8 characters.' : undefined}>
              <input className="field" type="password" required minLength={mode === 'register' ? 8 : undefined} value={form.password}
                autoComplete={mode === 'register' ? 'new-password' : 'current-password'} onChange={(e) => setForm({ ...form, password: e.target.value })} />
            </Field>
            {error && <Notice tone="error">{error}</Notice>}
            <Button variant="primary" busy={busy} type="submit">{first ? 'Create team admin account' : mode === 'login' ? 'Sign in' : 'Create account'}</Button>
            {!first && (
              <button type="button" className="self-start text-ink-2 underline" onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setError(null) }}>
                {mode === 'login' ? 'Create an account' : 'I already have an account'}
              </button>
            )}
          </div>
        </form>
      </div>
    </div>
  )
}
