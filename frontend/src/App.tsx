import { Activity, BarChart3, CircleDot, Crosshair, LayoutGrid, LogOut, MessagesSquare, Moon, Settings as Cog, Shield, Sun, Users } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { NavLink, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { Loading, ToastProvider, cx } from './components/ui'
import { Ctx, ErrorBoundary, useApp } from './context'
import type { AppState, Player, Team, User } from './context'
import { api, getToken, setToken } from './lib/api'
import AICoach from './pages/AICoach'
import BattingLab from './pages/BattingLab'
import BowlingLab from './pages/BowlingLab'
import DrsStudio from './pages/DrsStudio'
import FieldingLab from './pages/FieldingLab'
import Login from './pages/Login'
import MatchCenter from './pages/MatchCenter'
import Overview from './pages/Overview'
import Settings from './pages/Settings'
import TeamHub from './pages/TeamHub'

const NAV = [
  { to: '/', label: 'Overview', icon: LayoutGrid },
  { to: '/bowling', label: 'Bowling Lab', icon: CircleDot },
  { to: '/drs', label: 'DRS Studio', icon: Crosshair },
  { to: '/batting', label: 'Batting Lab', icon: Activity },
  { to: '/fielding', label: 'Fielding Lab', icon: Shield },
  { to: '/team', label: 'Team Hub', icon: Users },
  { to: '/matches', label: 'Match Center', icon: BarChart3 },
  { to: '/coach', label: 'AI Coach', icon: MessagesSquare },
  { to: '/settings', label: 'Settings', icon: Cog },
]

export default function App() {
  const [user, setUser] = useState<User | null>(null)
  const [team, setTeam] = useState<Team | null>(null)
  const [all, setAll] = useState<Player[]>([])
  const [booting, setBooting] = useState(true)
  const [theme, setThemeState] = useState<'dark' | 'light'>((document.documentElement.dataset.theme as 'dark' | 'light') || 'dark')

  const setTheme = (t: 'dark' | 'light') => {
    document.documentElement.dataset.theme = t
    try { localStorage.setItem('pv-theme', t) } catch { /* private mode */ }
    setThemeState(t)
  }
  const reloadPlayers = useCallback(async () => setAll(await api.get<Player[]>('/players')), [])
  const reloadTeam = useCallback(async () => setTeam(await api.get<Team>('/team')), [])
  const signOut = useCallback(() => { setToken(null); setUser(null) }, [])

  const boot = useCallback(async () => {
    if (!getToken()) { setBooting(false); return }
    try {
      const u = await api.get<User>('/auth/me')
      await Promise.all([reloadPlayers(), reloadTeam()])
      setUser(u)
    } catch { setToken(null) }
    setBooting(false)
  }, [reloadPlayers, reloadTeam])

  useEffect(() => { boot() }, [boot])
  useEffect(() => {
    const off = () => setUser(null)
    window.addEventListener('pv-signed-out', off)
    return () => window.removeEventListener('pv-signed-out', off)
  }, [])

  if (booting) return <div className="p-6"><Loading label="Opening PitchVision" /></div>
  if (!user || !team) return <ToastProvider><Login onSignedIn={() => { setBooting(true); boot() }} /></ToastProvider>

  const isCoach = user.role !== 'player'
  const state: AppState = {
    user, team, isCoach, reloadPlayers, reloadTeam, signOut, theme, setTheme,
    players: all.filter((p) => p.side === 'us'), opposition: all.filter((p) => p.side !== 'us'),
    canEdit: (pid) => isCoach || (pid !== null && pid === user.player_id),
  }
  return (
    <Ctx.Provider value={state}>
      <ToastProvider>
        <Shell />
      </ToastProvider>
    </Ctx.Provider>
  )
}

function Shell() {
  const { user, team, signOut, theme, setTheme } = useApp()
  const loc = useLocation()
  useEffect(() => { window.scrollTo(0, 0) }, [loc.pathname])
  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[212px_minmax(0,1fr)]">
      {/* the board's label column */}
      <aside className="border-rule-strong lg:sticky lg:top-0 lg:flex lg:h-screen lg:flex-col lg:border-r">
        <div className="flex items-center justify-between gap-3 border-b border-rule-strong px-4 py-3 lg:block lg:py-4">
          <div className="min-w-0">
            <div className="font-board text-fig font-bold uppercase leading-none tracking-[0.01em]">Pitch<span className="text-accent [html[data-theme=light]_&]:bg-plate [html[data-theme=light]_&]:px-1">Vision</span></div>
            <div className="painted mt-1 truncate text-label text-ink-2">{team.name || 'Team name not set'}{team.season ? ` · ${team.season}` : ''}</div>
          </div>
          <div className="flex items-center gap-1 lg:hidden">
            <ThemeButton theme={theme} setTheme={setTheme} />
            <button onClick={signOut} aria-label="Sign out" className="ctl rounded-ctl p-2 text-ink-2 hover:bg-surface hover:text-ink"><LogOut size={18} /></button>
          </div>
        </div>
        <nav aria-label="Sections" className="flex gap-1 overflow-x-auto border-b border-rule-strong px-2 py-2 lg:flex-1 lg:flex-col lg:gap-0.5 lg:overflow-visible lg:border-b-0 lg:px-2 lg:py-3">
          {NAV.map((n) => (
            <NavLink key={n.to} to={n.to} end={n.to === '/'}
              className={({ isActive }) => cx('painted flex shrink-0 items-center gap-2.5 whitespace-nowrap rounded-ctl px-2.5 py-2 text-text transition-colors',
                isActive ? 'bg-accent text-accent-ink' : 'text-ink-2 hover:bg-surface hover:text-ink')}>
              <n.icon size={17} strokeWidth={1.9} aria-hidden />{n.label}
            </NavLink>
          ))}
        </nav>
        <div className="hidden border-t border-rule-strong px-3 py-3 lg:block">
          <div className="truncate font-semibold">{user.name}</div>
          <div className="painted text-label text-ink-2">{user.role === 'admin' ? 'Team admin' : user.role}</div>
          <div className="mt-2 flex items-center gap-1">
            <ThemeButton theme={theme} setTheme={setTheme} />
            <button onClick={signOut} className="ctl painted flex items-center gap-1.5 rounded-ctl px-2 py-1.5 text-label text-ink-2 hover:bg-surface hover:text-ink"><LogOut size={15} aria-hidden />Sign out</button>
          </div>
        </div>
      </aside>
      <main className="min-w-0">
        <ErrorBoundary resetKey={loc.pathname}>
        <Routes>
          <Route path="/" element={<Overview />} />
          <Route path="/bowling" element={<BowlingLab />} />
          <Route path="/drs" element={<DrsStudio />} />
          <Route path="/batting" element={<BattingLab />} />
          <Route path="/fielding" element={<FieldingLab />} />
          <Route path="/team/*" element={<TeamHub />} />
          <Route path="/matches/*" element={<MatchCenter />} />
          <Route path="/coach" element={<AICoach />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
        </ErrorBoundary>
      </main>
    </div>
  )
}

function ThemeButton({ theme, setTheme }: { theme: 'dark' | 'light'; setTheme: (t: 'dark' | 'light') => void }) {
  const next = theme === 'dark' ? 'light' : 'dark'
  return (
    <button onClick={() => setTheme(next)} aria-label={`Switch to ${next} theme`} title={`Switch to ${next} theme`}
      className="ctl rounded-ctl p-2 text-ink-2 hover:bg-surface hover:text-ink">
      {theme === 'dark' ? <Sun size={17} /> : <Moon size={17} />}
    </button>
  )
}
