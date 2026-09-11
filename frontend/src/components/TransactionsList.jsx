import { ArrowUpRight, ArrowDownRight } from 'lucide-react'

const categoryStyles = {
  GIG_INCOME: 'text-positive-700 bg-positive-100',
  OTHER_INCOME: 'text-positive-700 bg-positive-100',
  RENT: 'text-ink-950/60 bg-paper-100',
  EMI: 'text-ink-950/60 bg-paper-100',
  ESSENTIAL_EXPENSE: 'text-ink-950/60 bg-paper-100',
  OTHER_DEBIT: 'text-ink-950/60 bg-paper-100',
}

export default function TransactionsList({ transactions }) {
  return (
    <div className="bg-white rounded-xl border border-paper-200 p-6">
      <h2 className="text-base font-semibold text-ink-950 mb-4">Recent transactions</h2>

      {transactions.length === 0 && (
        <p className="text-sm text-ink-950/50 py-6 text-center">
          No transactions yet. Link and sync an account to see your data here.
        </p>
      )}

      <div className="divide-y divide-paper-200 max-h-96 overflow-y-auto">
        {transactions.slice(0, 30).map((t) => (
          <div key={t.id} className="flex items-center justify-between py-3">
            <div className="min-w-0 flex-1 flex items-center gap-2.5">
              {t.type === 'CREDIT' ? (
                <ArrowUpRight size={16} className="text-positive-700 shrink-0" />
              ) : (
                <ArrowDownRight size={16} className="text-ink-950/40 shrink-0" />
              )}
              <div className="min-w-0">
                <p className="text-sm text-ink-950 truncate">{t.source_platform || t.narration}</p>
                <div className="flex items-center gap-2 mt-0.5">
                  <span className={`text-[11px] px-1.5 py-0.5 rounded ${categoryStyles[t.category] || 'text-ink-950/50 bg-paper-100'}`}>
                    {t.category.replace(/_/g, ' ').toLowerCase()}
                  </span>
                  <span className="text-[11px] text-ink-950/40">{new Date(t.date).toLocaleDateString()}</span>
                </div>
              </div>
            </div>
            <span className={`text-sm font-mono font-medium tabular-nums ml-3 ${t.type === 'CREDIT' ? 'text-positive-700' : 'text-ink-950/60'}`}>
              {t.type === 'CREDIT' ? '+' : '-'}₹{t.amount.toLocaleString('en-IN')}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
