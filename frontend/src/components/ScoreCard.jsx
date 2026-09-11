import { RefreshCw, ShieldCheck } from 'lucide-react'

function scoreTier(score) {
  if (score >= 750) return { label: 'Good', color: '#2F6B4F' }
  if (score >= 600) return { label: 'Fair', color: '#9A6A1F' }
  return { label: 'Needs work', color: '#A1402A' }
}

export default function ScoreCard({ score, reasonCodes, onCompute, loading }) {
  const hasScore = score !== null && score !== undefined
  const pct = hasScore ? Math.max(0, Math.min(1, (score - 300) / 600)) : 0
  const circumference = 2 * Math.PI * 70
  const offset = circumference * (1 - pct)
  const tier = hasScore ? scoreTier(score) : null

  return (
    <div className="bg-white rounded-xl border border-paper-200 p-6">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-base font-semibold text-ink-950">Passport score</h2>
        <button
          onClick={onCompute}
          disabled={loading}
          className="flex items-center gap-1.5 text-sm font-medium text-ink-900 border border-ink-900/20 rounded-lg px-3 py-1.5 hover:bg-paper-100 disabled:opacity-50 transition-colors"
        >
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
          {loading ? 'Computing' : hasScore ? 'Recompute' : 'Compute score'}
        </button>
      </div>

      {!hasScore && (
        <p className="text-sm text-ink-950/60 py-10 text-center">
          No score yet. Link an account, then compute your score.
        </p>
      )}

      {hasScore && (
        <div className="flex flex-col items-center">
          <div className="relative w-44 h-44">
            <svg className="w-44 h-44 -rotate-90" viewBox="0 0 160 160">
              <circle cx="80" cy="80" r="70" fill="none" stroke="#E5E1D8" strokeWidth="10" />
              <circle
                cx="80" cy="80" r="70" fill="none"
                strokeWidth="10" strokeLinecap="round"
                stroke={tier.color}
                strokeDasharray={circumference}
                strokeDashoffset={offset}
                className="transition-all duration-700"
              />
            </svg>
            <div className="absolute inset-0 flex flex-col items-center justify-center">
              <span className="font-mono text-4xl font-semibold text-ink-950 tabular-nums">{score}</span>
              <span className="text-xs text-ink-950/50 mt-0.5">of 900</span>
            </div>
          </div>
          <span className="mt-3 text-sm font-medium" style={{ color: tier.color }}>{tier.label}</span>

          {reasonCodes?.length > 0 && (
            <div className="mt-6 w-full space-y-2.5">
              <div className="flex items-center gap-1.5 text-xs font-medium text-ink-950/50 uppercase tracking-wide">
                <ShieldCheck size={13} />
                Why this score
              </div>
              {reasonCodes.map((reason, i) => (
                <p key={i} className="text-sm text-ink-950/80 leading-relaxed border-l-2 border-paper-300 pl-3">
                  {reason}
                </p>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
