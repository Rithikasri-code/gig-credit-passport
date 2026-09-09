import { useMemo } from 'react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer, CartesianGrid } from 'recharts'

const PLATFORM_COLORS = ['#0F3D3E', '#A8842C', '#2F6B4F', '#9A6A1F', '#5C6560']

function buildMonthlyData(transactions) {
  const byMonth = {}
  const platforms = new Set()

  for (const t of transactions) {
    if (t.type !== 'CREDIT' || t.category !== 'GIG_INCOME' || !t.source_platform) continue
    const month = t.date.slice(0, 7)
    platforms.add(t.source_platform)
    byMonth[month] = byMonth[month] || {}
    byMonth[month][t.source_platform] = (byMonth[month][t.source_platform] || 0) + t.amount
  }

  const months = Object.keys(byMonth).sort()
  const data = months.map((month) => ({
    month: new Date(month + '-01').toLocaleDateString('en-IN', { month: 'short', year: '2-digit' }),
    ...byMonth[month],
  }))

  return { data, platforms: Array.from(platforms) }
}

export default function IncomeTimeline({ transactions }) {
  const { data, platforms } = useMemo(() => buildMonthlyData(transactions), [transactions])

  if (data.length === 0) {
    return (
      <div className="bg-white rounded-xl border border-paper-200 p-6">
        <h2 className="text-base font-semibold text-ink-950 mb-1">Income by platform</h2>
        <p className="text-sm text-ink-950/50 py-10 text-center">
          No income data yet. Link and sync an account to see this chart.
        </p>
      </div>
    )
  }

  return (
    <div className="bg-white rounded-xl border border-paper-200 p-6">
      <h2 className="text-base font-semibold text-ink-950">Income by platform</h2>
      <p className="text-sm text-ink-950/60 mt-0.5 mb-5">
        Each platform sees only its own payouts. This is the combined picture, unified across {platforms.length} source{platforms.length === 1 ? '' : 's'}.
      </p>

      <div className="h-72">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 0, right: 0, left: -12, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#E5E1D8" vertical={false} />
            <XAxis dataKey="month" tick={{ fontSize: 12, fill: '#5C6560' }} axisLine={{ stroke: '#E5E1D8' }} tickLine={false} />
            <YAxis
              tick={{ fontSize: 12, fill: '#5C6560' }}
              axisLine={false}
              tickLine={false}
              tickFormatter={(v) => `₹${v / 1000}k`}
            />
            <Tooltip
              formatter={(value) => `₹${Number(value).toLocaleString('en-IN')}`}
              contentStyle={{ borderRadius: 8, borderColor: '#E5E1D8', fontSize: 13 }}
            />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            {platforms.map((p, i) => (
              <Bar key={p} dataKey={p} stackId="income" fill={PLATFORM_COLORS[i % PLATFORM_COLORS.length]} radius={i === platforms.length - 1 ? [3, 3, 0, 0] : 0} />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
