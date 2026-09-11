import { useState } from 'react'
import { Sparkles } from 'lucide-react'

export default function SimulatorPanel({ onSimulate, simulating, result, itrAlreadyFiled }) {
  const [itrFiled, setItrFiled] = useState(!itrAlreadyFiled)
  const [months, setMonths] = useState(0)
  const [platforms, setPlatforms] = useState(0)

  function handleRun() {
    onSimulate({
      itr_filed: itrAlreadyFiled ? undefined : itrFiled,
      additional_months_of_history: months,
      additional_platforms: platforms,
    })
  }

  return (
    <div className="bg-white rounded-xl border border-paper-200 p-6">
      <h2 className="text-base font-semibold text-ink-950">What if</h2>
      <p className="text-sm text-ink-950/60 mt-0.5 mb-5">
        Test a change before making it. Nothing here is saved until you actually do it.
      </p>

      <div className="space-y-5">
        {!itrAlreadyFiled && (
          <label className="flex items-center gap-2.5 text-sm text-ink-950">
            <input
              type="checkbox"
              checked={itrFiled}
              onChange={(e) => setItrFiled(e.target.checked)}
              className="w-4 h-4 rounded border-paper-300 text-ink-900 focus:ring-ink-900"
            />
            File an income tax return
          </label>
        )}
        {itrAlreadyFiled && (
          <p className="text-sm text-positive-700 bg-positive-100 rounded-lg px-3 py-2">
            You have already filed your ITR. It is already counted in your score.
          </p>
        )}

        <div>
          <div className="flex items-center justify-between mb-1.5">
            <label className="text-sm text-ink-950">Additional months of steady history</label>
            <span className="text-sm font-mono font-medium text-ink-900">{months}</span>
          </div>
          <input
            type="range" min="0" max="12" value={months}
            onChange={(e) => setMonths(Number(e.target.value))}
            className="w-full accent-ink-900"
          />
        </div>

        <div>
          <div className="flex items-center justify-between mb-1.5">
            <label className="text-sm text-ink-950">Additional gig platforms</label>
            <span className="text-sm font-mono font-medium text-ink-900">{platforms}</span>
          </div>
          <input
            type="range" min="0" max="3" value={platforms}
            onChange={(e) => setPlatforms(Number(e.target.value))}
            className="w-full accent-ink-900"
          />
        </div>

        <button
          onClick={handleRun}
          disabled={simulating}
          className="w-full flex items-center justify-center gap-1.5 rounded-lg bg-ink-900 text-paper-50 font-medium py-2.5 text-sm hover:bg-ink-800 disabled:opacity-50 transition-colors"
        >
          <Sparkles size={15} />
          {simulating ? 'Simulating' : 'See projected score'}
        </button>
      </div>

      {result && result.simulated_score !== null && (
        <div className="mt-5 rounded-lg bg-paper-100 border border-paper-200 p-4">
          <div className="flex items-baseline gap-2">
            <span className="font-mono text-2xl font-semibold text-ink-950 tabular-nums">{result.simulated_score}</span>
            {result.delta !== null && (
              <span className={`text-sm font-medium ${result.delta >= 0 ? 'text-positive-700' : 'text-negative-700'}`}>
                {result.delta >= 0 ? '+' : ''}
                {result.delta} from today
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
