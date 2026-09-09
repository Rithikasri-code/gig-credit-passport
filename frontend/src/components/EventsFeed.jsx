import { Activity } from 'lucide-react'

const triggerLabels = {
  manual: 'You checked your score',
  auto_sync: 'New data synced',
  itr_status_change: 'Tax filing status updated',
}

export default function EventsFeed({ events }) {
  if (events.length === 0) return null

  return (
    <div className="bg-white rounded-xl border border-paper-200 p-6">
      <div className="flex items-center gap-1.5 mb-4">
        <Activity size={16} className="text-ink-950/50" />
        <h2 className="text-base font-semibold text-ink-950">Score activity</h2>
      </div>
      <div className="space-y-3">
        {events.slice(0, 5).map((e) => (
          <div key={e.id} className="flex items-center justify-between text-sm">
            <div>
              <span className="text-ink-950">{triggerLabels[e.trigger] || e.trigger}</span>
              <span className="text-ink-950/40 ml-2 text-xs">{new Date(e.created_at).toLocaleDateString()}</span>
            </div>
            <div className="font-mono font-medium tabular-nums">
              {e.previous_score === null ? (
                <span className="text-ink-950">{e.new_score}</span>
              ) : (
                <span className={e.delta >= 0 ? 'text-positive-700' : 'text-negative-700'}>
                  {e.previous_score} to {e.new_score} ({e.delta >= 0 ? '+' : ''}
                  {e.delta})
                </span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
