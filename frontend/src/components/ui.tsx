// The scoreboard's parts: number plates in labelled windows, painted labels, ruled sections.
import { AlertTriangle, Info, Loader2 } from 'lucide-react'
import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'
import type { ButtonHTMLAttributes, DependencyList, ReactNode } from 'react'

const cx = (...c: (string | false | null | undefined)[]) => c.filter(Boolean).join(' ')
export { cx }

/* ---------------------------------------------------------------- data hook */

export function useAsync<T>(fn: () => Promise<T>, deps: DependencyList) {
  const [state, setState] = useState<{ data: T | null; error: string | null; loading: boolean }>({ data: null, error: null, loading: true })
  const run = useRef(0)
  const load = useCallback(() => {
    const id = ++run.current
    setState((s) => ({ ...s, loading: true, error: null }))
    fn().then(
      (data) => id === run.current && setState({ data, error: null, loading: false }),
      (e) => id === run.current && setState({ data: null, error: e?.message ?? 'Something went wrong.', loading: false }),
    )
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)
  useEffect(load, [load])
  return { ...state, reload: load, setData: (data: T) => setState({ data, error: null, loading: false }) }
}

/* ---------------------------------------------------------------- plates */

type Tone = 'plain' | 'accent' | 'green' | 'red'
const toneClass: Record<Tone, string> = { plain: 'text-plate-ink', accent: 'text-accent', green: 'text-[#6fd39a]', red: 'text-[#ff8a80]' }

/** A number plate. The numeral slots in from above whenever the value changes. */
export function Plate({ value, unit, tone = 'plain', wide }: { value: ReactNode; unit?: string; tone?: Tone; wide?: boolean }) {
  const empty = value === null || value === undefined || value === '' || value === '–'
  return (
    <div className={cx('flex h-[52px] items-center justify-center overflow-hidden rounded-plate bg-plate px-3', wide ? 'min-w-[132px]' : 'min-w-[88px]')}>
      <span key={String(value)} className={cx('slot num font-board text-fig font-semibold', empty ? 'text-plate-dim' : toneClass[tone])}>
        {empty ? '–' : value}
      </span>
      {unit && !empty && <span className="painted ml-1.5 self-end pb-[9px] text-label text-plate-dim">{unit}</span>}
    </div>
  )
}

/** A labelled window on the board: painted label above, plate below. */
export function Win({ label, value, unit, tone, hint, wide }: { label: string; value: ReactNode; unit?: string; tone?: Tone; hint?: ReactNode; wide?: boolean }) {
  return (
    <div className="flex min-w-0 flex-col gap-1.5">
      <div className="painted truncate text-label text-ink-2">{label}</div>
      <Plate value={value} unit={unit} tone={tone} wide={wide} />
      {hint && <div className="text-label text-ink-2">{hint}</div>}
    </div>
  )
}

/** A row of windows sitting on one ruled strip of board. */
export function Board({ children, cols = 6 }: { children: ReactNode; cols?: number }) {
  const grid = { 2: 'sm:grid-cols-2', 3: 'sm:grid-cols-3', 4: 'sm:grid-cols-2 lg:grid-cols-4', 5: 'sm:grid-cols-3 lg:grid-cols-5', 6: 'sm:grid-cols-3 xl:grid-cols-6' }[cols] ?? 'sm:grid-cols-3'
  return <div className={cx('grid grid-cols-2 gap-x-4 gap-y-4 border-y border-rule-strong py-4', grid)}>{children}</div>
}

/* ---------------------------------------------------------------- structure */

export function Page({ title, lead, actions, children }: { title: string; lead?: ReactNode; actions?: ReactNode; children: ReactNode }) {
  return (
    <div className="rise mx-auto w-full max-w-[1320px] px-4 pb-16 pt-5 sm:px-6">
      <header className="mb-5 flex flex-wrap items-end justify-between gap-x-6 gap-y-3">
        <div className="min-w-0">
          <h1 className="font-board text-fig font-bold uppercase tracking-[0.01em]">{title}</h1>
          {lead && <p className="mt-1 max-w-[72ch] text-ink-2">{lead}</p>}
        </div>
        {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
      </header>
      {children}
    </div>
  )
}

export function Section({ title, aside, children, className }: { title: string; aside?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={cx('mt-8 first:mt-0', className)}>
      <div className="mb-3 flex flex-wrap items-end justify-between gap-x-4 gap-y-2 border-b border-rule-strong pb-2">
        <h2 className="painted text-text">{title}</h2>
        {aside && <div className="flex flex-wrap items-center gap-2 text-label text-ink-2">{aside}</div>}
      </div>
      {children}
    </section>
  )
}

export function Tabs<T extends string>({ tabs, value, onChange }: { tabs: { id: T; label: string }[]; value: T; onChange: (t: T) => void }) {
  return (
    <div role="tablist" className="mb-6 flex gap-1 overflow-x-auto border-b border-rule-strong">
      {tabs.map((t) => (
        <button key={t.id} role="tab" aria-selected={value === t.id} onClick={() => onChange(t.id)}
          className={cx('painted -mb-px shrink-0 whitespace-nowrap rounded-t-ctl px-3 py-2 text-text transition-colors',
            value === t.id ? 'bg-accent text-accent-ink' : 'text-ink-2 hover:bg-surface hover:text-ink')}>
          {t.label}
        </button>
      ))}
    </div>
  )
}

/* ---------------------------------------------------------------- controls */

type BtnProps = ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'default' | 'danger' | 'quiet'; busy?: boolean; small?: boolean }
export function Button({ variant = 'default', busy, small, className, children, disabled, ...rest }: BtnProps) {
  const v = {
    primary: 'bg-accent text-accent-ink hover:brightness-95 active:brightness-90',
    default: 'border border-rule-strong text-ink hover:border-ink hover:bg-surface',
    danger: 'border border-red text-red hover:bg-red hover:text-bg',
    quiet: 'text-ink-2 hover:bg-surface hover:text-ink',
  }[variant]
  return (
    <button {...rest} disabled={disabled || busy}
      className={cx('ctl painted inline-flex shrink-0 items-center justify-center gap-1.5 whitespace-nowrap rounded-ctl text-text disabled:cursor-not-allowed disabled:opacity-45',
        small ? 'h-8 px-2.5' : 'h-9 px-3.5', v, className)}>
      {busy && <Loader2 size={15} className="animate-spin" aria-hidden />}
      {children}
    </button>
  )
}

export function Field({ label, hint, error, children, className }: { label: string; hint?: ReactNode; error?: string | null; children: ReactNode; className?: string }) {
  return (
    <label className={cx('flex min-w-0 flex-col gap-1', className)}>
      <span className="painted text-label text-ink-2">{label}</span>
      {children}
      {error ? <span className="text-label text-red">{error}</span> : hint ? <span className="text-label text-ink-2">{hint}</span> : null}
    </label>
  )
}

export function Seg<T extends string>({ value, onChange, options, label }: { value: T; onChange: (v: T) => void; options: { id: T; label: string }[]; label: string }) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex h-9 overflow-hidden rounded-ctl border border-rule-strong">
      {options.map((o) => (
        <button key={o.id} type="button" role="radio" aria-checked={value === o.id} onClick={() => onChange(o.id)}
          className={cx('painted px-3 text-text transition-colors', value === o.id ? 'bg-ink text-bg' : 'text-ink-2 hover:bg-surface hover:text-ink')}>
          {o.label}
        </button>
      ))}
    </div>
  )
}

/* ---------------------------------------------------------------- messages */

export function Notice({ tone = 'info', title, children }: { tone?: 'info' | 'warn' | 'error'; title?: string; children: ReactNode }) {
  const Icon = tone === 'info' ? Info : AlertTriangle
  return (
    <div role={tone === 'error' ? 'alert' : 'note'} className="flex gap-2.5 rounded-ctl border border-rule-strong bg-surface px-3 py-2.5">
      <Icon size={17} className={cx('mt-0.5 shrink-0', tone === 'error' ? 'text-red' : tone === 'warn' ? 'text-accent' : 'text-ink-2')} aria-hidden />
      <div className="min-w-0 text-ink-2">
        {title && <div className="font-semibold text-ink">{title}</div>}
        {children}
      </div>
    </div>
  )
}

export function Empty({ title, children, action }: { title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-start gap-2 rounded-ctl border border-dashed border-rule-strong px-4 py-5">
      <div className="font-semibold">{title}</div>
      {children && <div className="max-w-[68ch] text-ink-2">{children}</div>}
      {action && <div className="mt-1 flex flex-wrap gap-2">{action}</div>}
    </div>
  )
}

export function Loading({ label = 'Loading' }: { label?: string }) {
  return <div className="flex items-center gap-2 py-6 text-ink-2" role="status"><Loader2 size={16} className="animate-spin" aria-hidden />{label}…</div>
}

export function Async<T>({ state, children, empty }: { state: { data: T | null; error: string | null; loading: boolean; reload: () => void }; children: (d: T) => ReactNode; empty?: ReactNode }) {
  if (state.error) return <Notice tone="error" title="Could not load this">{state.error} <button className="underline" onClick={state.reload}>Try again</button></Notice>
  if (state.data === null) return <Loading />
  if (empty && Array.isArray(state.data) && state.data.length === 0) return <>{empty}</>
  return <>{children(state.data)}</>
}

/* ---------------------------------------------------------------- table */

export interface Col<R> { key: string; label: string; num?: boolean; render: (r: R, i: number) => ReactNode; title?: string }

export function DataTable<R>({ cols, rows, rowKey, onHover, active, onRow, dense }: {
  cols: Col<R>[]; rows: R[]; rowKey: (r: R, i: number) => string | number; onHover?: (r: R | null) => void
  active?: (r: R) => boolean; onRow?: (r: R) => void; dense?: boolean
}) {
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full">
        <thead>
          <tr className="border-b border-rule-strong">
            {cols.map((c) => (
              <th key={c.key} title={c.title} scope="col" className={cx('painted whitespace-nowrap px-2 py-1.5 text-label text-ink-2 first:pl-0 last:pr-0', c.num ? 'text-right' : 'text-left')}>{c.label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={rowKey(r, i)} onMouseEnter={onHover ? () => onHover(r) : undefined} onMouseLeave={onHover ? () => onHover(null) : undefined}
              onClick={onRow ? () => onRow(r) : undefined} tabIndex={onRow ? 0 : undefined}
              onKeyDown={onRow ? (e) => { if (e.key === 'Enter') onRow(r) } : undefined}
              className={cx('border-b border-rule transition-colors', onRow && 'cursor-pointer', active?.(r) ? 'bg-accent/15' : (onHover || onRow) && 'hover:bg-surface')}>
              {cols.map((c) => (
                <td key={c.key} className={cx('px-2 first:pl-0 last:pr-0', dense ? 'py-1' : 'py-2', c.num && 'num whitespace-nowrap text-right')}>{c.render(r, i)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/* ---------------------------------------------------------------- over strip */

/** One over as six fixed cells. Wides and no-balls sit in narrow cells between them and never use up a cell. */
export function OverStrip({ balls, label }: { balls: string[]; label?: string }) {
  const legal = (s: string) => !/wd|nb/.test(s)
  const cells: { sym: string | null; legal: boolean }[] = []
  let used = 0
  for (const s of balls) { cells.push({ sym: s, legal: legal(s) }); if (legal(s)) used++ }
  for (let i = used; i < 6; i++) cells.push({ sym: null, legal: true })
  return (
    <div className="flex items-center gap-2">
      {label && <span className="painted w-14 shrink-0 text-label text-ink-2">{label}</span>}
      <div className="flex gap-1">
        {cells.map((c, i) => (
          <span key={i} className={cx('num flex h-8 items-center justify-center rounded-plate font-board text-text font-semibold',
            c.legal ? 'w-8' : 'w-7 text-label',
            c.sym === null ? 'border border-dashed border-rule-strong' : /W/.test(c.sym) ? 'bg-red text-bg' : /^[46]/.test(c.sym) && c.legal ? 'bg-accent text-accent-ink' : 'bg-plate text-plate-ink')}>
            {c.sym ?? ''}
          </span>
        ))}
      </div>
    </div>
  )
}

/* ---------------------------------------------------------------- toast */

const ToastCtx = createContext<(msg: string, tone?: 'ok' | 'error') => void>(() => {})
export const useToast = () => useContext(ToastCtx)

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<{ id: number; msg: string; tone: 'ok' | 'error' }[]>([])
  const push = useCallback((msg: string, tone: 'ok' | 'error' = 'ok') => {
    const id = Date.now() + Math.random()
    setItems((x) => [...x, { id, msg, tone }])
    setTimeout(() => setItems((x) => x.filter((i) => i.id !== id)), tone === 'error' ? 7000 : 3200)
  }, [])
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div className="pointer-events-none fixed inset-x-0 bottom-4 z-50 flex flex-col items-center gap-2 px-4" aria-live="polite">
        {items.map((i) => (
          <div key={i.id} className={cx('rise pointer-events-auto max-w-[560px] rounded-ctl px-3.5 py-2 text-text shadow-[0_6px_24px_rgba(0,0,0,0.35)]',
            i.tone === 'error' ? 'bg-red text-bg' : 'bg-plate text-plate-ink')}>{i.msg}</div>
        ))}
      </div>
    </ToastCtx.Provider>
  )
}

/* ---------------------------------------------------------------- misc */

export function Legend({ items }: { items: { label: string; swatch: ReactNode }[] }) {
  return <div className="flex flex-wrap gap-x-4 gap-y-1 text-label text-ink-2">{items.map((i) => <span key={i.label} className="inline-flex items-center gap-1.5">{i.swatch}{i.label}</span>)}</div>
}

export function Meter({ value, max = 100, label }: { value: number; max?: number; label?: string }) {
  return (
    <div className="flex items-center gap-2" title={label}>
      <div className="h-2 w-full min-w-[60px] bg-rule"><div className="h-full bg-accent" style={{ width: `${Math.max(0, Math.min(100, (value / max) * 100))}%` }} /></div>
    </div>
  )
}

export function PlayerSelect({ players, value, onChange, allowEmpty, label = 'Player', className }: {
  players: { id: number; name: string }[]; value: number | null; onChange: (id: number | null) => void; allowEmpty?: string; label?: string; className?: string
}) {
  return (
    <Field label={label} className={className}>
      <select className="field" value={value ?? ''} onChange={(e) => onChange(e.target.value ? Number(e.target.value) : null)}>
        {(allowEmpty !== undefined || value === null) && <option value="">{allowEmpty ?? 'Choose a player'}</option>}
        {players.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
      </select>
    </Field>
  )
}
