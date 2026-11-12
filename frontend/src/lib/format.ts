export const fmt = (v: number | null | undefined, digits = 1, none = '–') =>
  v === null || v === undefined || Number.isNaN(v) ? none : v.toFixed(digits)

export const pct = (v: number | null | undefined, digits = 0) => (v === null || v === undefined ? '–' : `${v.toFixed(digits)}%`)

export const words = (s: string | null | undefined) => (s ?? '').replace(/_/g, ' ')
export const cap = (s: string | null | undefined) => { const w = words(s); return w ? w[0].toUpperCase() + w.slice(1) : '' }

export const today = () => new Date().toISOString().slice(0, 10)

export const day = (iso: string | null | undefined) => {
  if (!iso) return '–'
  const d = new Date(iso.length === 10 ? iso + 'T00:00:00' : iso)
  return d.toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })
}

export const ROLE_LABEL: Record<string, string> = {
  batter: 'Batter', bowler: 'Bowler', all_rounder: 'All-rounder', wicket_keeper: 'Wicket-keeper',
}
export const STYLE_LABEL: Record<string, string> = {
  pace_fast: 'Pace (fast)', pace_medium: 'Pace (medium)', spin_off: 'Off spin', spin_leg: 'Leg spin',
}
