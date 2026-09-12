import { useState } from 'react'
import client from '../api/client'
import { useAppData } from '../context/DataContext'
import ScoreCard from '../components/ScoreCard'
import ConsentPanel from '../components/ConsentPanel'

export default function Home() {
  const { score, reasonCodes, latestScoreId, consents, refresh, setScore, setLatestScoreId, setReasonCodes } = useAppData()

  const [computingScore, setComputingScore] = useState(false)
  const [linking, setLinking] = useState(false)
  const [revokingId, setRevokingId] = useState(null)
  const [syncingId, setSyncingId] = useState(null)
  const [error, setError] = useState('')

  async function handleComputeScore() {
    setComputingScore(true)
    setError('')
    try {
      const { data } = await client.post('/score/compute')
      setScore(data.score)
      setLatestScoreId(data.score_id)
      setReasonCodes(data.reason_codes)
      await refresh()
    } catch (err) {
      setError('Could not compute score. Link and sync an account first.')
    } finally {
      setComputingScore(false)
    }
  }

  async function handleLinkAccount() {
    setLinking(true)
    setError('')
    try {
      const { data: consent } = await client.post('/consent/initiate', {
        purpose: 'Gig Credit Passport: income and repayment scoring',
      })
      if (consent.status === 'ACTIVE') {
        await client.post(`/accounts/sync/${consent.id}`)
      }
      await refresh()
    } catch (err) {
      setError('Could not link account. Try again.')
    } finally {
      setLinking(false)
    }
  }

  async function handleRevoke(consentId) {
    setRevokingId(consentId)
    try {
      await client.post(`/consent/${consentId}/revoke`)
      await refresh()
    } catch (err) {
      setError('Could not revoke access.')
    } finally {
      setRevokingId(null)
    }
  }

  async function handleSync(consentId) {
    setSyncingId(consentId)
    try {
      await client.post(`/accounts/sync/${consentId}`)
      await refresh()
    } catch (err) {
      setError('Sync failed. The consent may have expired or been revoked.')
    } finally {
      setSyncingId(null)
    }
  }

  return (
    <div className="max-w-3xl mx-auto px-4 md:px-8 py-6 md:py-10">
      <h1 className="text-xl font-semibold text-ink-950 mb-1">Your score</h1>
      <p className="text-sm text-ink-950/60 mb-6">
        Built from your linked income data, updated automatically as new data arrives.
      </p>

      {error && (
        <div className="mb-4 text-sm bg-negative-100 text-negative-700 rounded-lg px-3 py-2">{error}</div>
      )}

      <div className="space-y-6">
        <ScoreCard score={score} reasonCodes={reasonCodes} onCompute={handleComputeScore} loading={computingScore} />
        <ConsentPanel
          consents={consents}
          onLinkAccount={handleLinkAccount}
          onRevoke={handleRevoke}
          onSync={handleSync}
          linking={linking}
          revokingId={revokingId}
          syncingId={syncingId}
        />
      </div>
    </div>
  )
}
