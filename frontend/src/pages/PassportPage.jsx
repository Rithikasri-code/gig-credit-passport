import { useState } from 'react'
import client from '../api/client'
import { useAppData } from '../context/DataContext'
import PassportPanel from '../components/PassportPanel'

export default function PassportPage() {
  const { passports, latestScoreId, refresh } = useAppData()

  const [issuing, setIssuing] = useState(false)
  const [revokingId, setRevokingId] = useState(null)
  const [error, setError] = useState('')

  async function handleIssue() {
    if (!latestScoreId) return
    setIssuing(true)
    setError('')
    try {
      await client.post('/passport/issue', { score_id: latestScoreId })
      await refresh()
    } catch (err) {
      setError('Could not issue a passport right now.')
    } finally {
      setIssuing(false)
    }
  }

  async function handleRevoke(passportId) {
    setRevokingId(passportId)
    try {
      await client.post(`/passport/${passportId}/revoke`)
      await refresh()
    } catch (err) {
      setError('Could not revoke that passport.')
    } finally {
      setRevokingId(null)
    }
  }

  return (
    <div className="max-w-3xl mx-auto px-4 md:px-8 py-6 md:py-10">
      <h1 className="text-xl font-semibold text-ink-950 mb-1">Passport</h1>
      <p className="text-sm text-ink-950/60 mb-6">
        A credential you own. Share it with a lender or landlord without giving them access to your account.
      </p>

      {error && (
        <div className="mb-4 text-sm bg-negative-100 text-negative-700 rounded-lg px-3 py-2">{error}</div>
      )}

      <PassportPanel
        passports={passports}
        latestScoreId={latestScoreId}
        onIssue={handleIssue}
        onRevoke={handleRevoke}
        issuing={issuing}
        revokingId={revokingId}
      />
    </div>
  )
}
