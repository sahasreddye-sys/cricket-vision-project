// App-wide state shared by every page. Kept in its own module so pages never import App.tsx.
import { Component, createContext, useContext } from 'react'
import type { ReactNode } from 'react'

export interface User { id: number; email: string; name: string; role: 'admin' | 'coach' | 'player'; player_id: number | null }
export interface Player { id: number; name: string; side: string; role: string; batting_hand: string; bowl_style: string | null; active: boolean; notes: string; is_sample: boolean }
export interface Team { name: string; season: string; default_overs: number; speed_unit: 'kmh' | 'mph'; seasons: string[]; formats: string[]; has_sample_data: boolean; llm_available: boolean }

export interface AppState {
  user: User; team: Team; players: Player[]; opposition: Player[]; isCoach: boolean
  reloadPlayers: () => Promise<void>; reloadTeam: () => Promise<void>; signOut: () => void
  theme: 'dark' | 'light'; setTheme: (t: 'dark' | 'light') => void
  /** Whether this account may add records for the given player. */
  canEdit: (playerId: number | null) => boolean
}
export const Ctx = createContext<AppState>(null as unknown as AppState)
export const useApp = () => useContext(Ctx)

/** Shows a readable message instead of a blank screen if a page fails to render. */
export class ErrorBoundary extends Component<{ children: ReactNode; resetKey: string }, { error: Error | null }> {
  state = { error: null as Error | null }
  static getDerivedStateFromError(error: Error) { return { error } }
  componentDidUpdate(prev: { resetKey: string }) { if (prev.resetKey !== this.props.resetKey && this.state.error) this.setState({ error: null }) }
  render() {
    if (!this.state.error) return this.props.children
    return (
      <div className="mx-auto max-w-[720px] px-6 py-10" role="alert">
        <h1 className="font-board text-fig font-bold uppercase">This page could not be shown</h1>
        <p className="mt-2 text-ink-2">Something went wrong while drawing this page. Your data is not affected. Reload the page; if it happens again, note what you were doing and tell whoever maintains PitchVision.</p>
        <p className="mt-2 text-label text-ink-2">{this.state.error.message}</p>
        <button className="ctl painted mt-4 h-9 rounded-ctl bg-accent px-3.5 text-text text-accent-ink" onClick={() => window.location.reload()}>Reload page</button>
      </div>
    )
  }
}
