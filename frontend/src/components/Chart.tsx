// Recharts wrappers themed from the board's palette.
import { Bar, BarChart, CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

export const SERIES = ['var(--ink)', 'var(--green)', 'var(--red)', 'var(--ink-2)']

const tip = {
  contentStyle: { background: 'var(--plate)', border: 'none', borderRadius: 2, color: 'var(--plate-ink)', fontSize: 12, padding: '6px 10px' },
  itemStyle: { color: 'var(--plate-ink)', padding: 0 },
  labelStyle: { color: 'var(--plate-dim)', marginBottom: 2 },
  cursor: { stroke: 'var(--rule-strong)', fill: 'var(--rule)' },
}

export interface SeriesDef { key: string; label: string; colour?: string; dashed?: boolean }

export function LineTrend({ data, x, series, unit = '', height = 220, domain, reference }: {
  data: any[]; x: string; series: SeriesDef[]; unit?: string; height?: number; domain?: [number | 'auto' | 'dataMin' | 'dataMax', number | 'auto' | 'dataMin' | 'dataMax']
  reference?: { y: number; label: string }
}) {
  return (
    <div style={{ height }} role="img" aria-label={`Line chart of ${series.map((s) => s.label).join(', ')}`}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: -14 }}>
          <CartesianGrid vertical={false} />
          <XAxis dataKey={x} tickLine={false} minTickGap={24} />
          <YAxis tickLine={false} domain={domain ?? ['auto', 'auto']} width={52} tickFormatter={(v) => (Math.abs(v) >= 100 ? v.toFixed(0) : String(Math.round(v * 10) / 10))} />
          <Tooltip {...tip} formatter={(v: any, name: any) => [`${typeof v === 'number' ? Math.round(v * 10) / 10 : v}${unit ? ' ' + unit : ''}`, name]} />
          {reference && <ReferenceLine y={reference.y} stroke="var(--rule-strong)" strokeDasharray="4 4" label={{ value: reference.label, position: 'insideTopRight', fontSize: 12, fill: 'var(--ink-2)' }} />}
          {series.map((s, i) => (
            <Line key={s.key} type="monotone" dataKey={s.key} name={s.label} stroke={s.colour ?? SERIES[i % SERIES.length]} strokeWidth={2}
              strokeDasharray={s.dashed ? '5 4' : undefined} dot={{ r: 3, strokeWidth: 0, fill: s.colour ?? SERIES[i % SERIES.length] }} activeDot={{ r: 5 }} connectNulls isAnimationActive={false} />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

export function Bars({ data, x, series, unit = '', height = 220, stacked }: { data: any[]; x: string; series: SeriesDef[]; unit?: string; height?: number; stacked?: boolean }) {
  return (
    <div style={{ height }} role="img" aria-label={`Bar chart of ${series.map((s) => s.label).join(', ')}`}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: -14 }}>
          <CartesianGrid vertical={false} />
          <XAxis dataKey={x} tickLine={false} minTickGap={8} />
          <YAxis tickLine={false} width={52} allowDecimals={false} />
          <Tooltip {...tip} formatter={(v: any, name: any) => [`${typeof v === 'number' ? Math.round(v * 10) / 10 : v}${unit ? ' ' + unit : ''}`, name]} />
          {series.map((s, i) => <Bar key={s.key} dataKey={s.key} name={s.label} fill={s.colour ?? SERIES[i % SERIES.length]} stackId={stacked ? 'a' : undefined} isAnimationActive={false} maxBarSize={34} />)}
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

export function SeriesKey({ series }: { series: SeriesDef[] }) {
  return (
    <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-label text-ink-2">
      {series.map((s, i) => <span key={s.key} className="inline-flex items-center gap-1.5"><span className="inline-block h-[3px] w-4" style={{ background: s.colour ?? SERIES[i % SERIES.length] }} />{s.label}</span>)}
    </div>
  )
}
