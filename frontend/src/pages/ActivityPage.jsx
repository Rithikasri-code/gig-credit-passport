import { useAppData } from '../context/DataContext'
import EventsFeed from '../components/EventsFeed'
import TransactionsList from '../components/TransactionsList'

export default function ActivityPage() {
  const { transactions, events } = useAppData()

  return (
    <div className="max-w-3xl mx-auto px-4 md:px-8 py-6 md:py-10">
      <h1 className="text-xl font-semibold text-ink-950 mb-1">Activity</h1>
      <p className="text-sm text-ink-950/60 mb-6">
        Your transaction history and every change to your score.
      </p>

      <div className="space-y-6">
        <EventsFeed events={events} />
        <TransactionsList transactions={transactions} />
      </div>
    </div>
  )
}
