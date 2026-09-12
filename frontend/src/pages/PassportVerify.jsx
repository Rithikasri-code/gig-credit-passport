import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import { CheckCircle2, XCircle } from 'lucide-react'
import client from '../api/client'

function scoreTierColor(score) {
  if (score >= 750) return '#2F6B4F'
  if (score >= 600) return '#9A6A1F'
  return '#A1402A'
}

export default function PassportVerify() {
  const { passportId } = useParams()
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    client
      .get(`/passport/verify/${passportId}`)
      .then(({ data }) => setResult(data))
      .catch(() => setResult({ valid: false, reason: 'Could not check this passport right now.' }))
      .finally(() => setLoading(false))
  }, [passportId])

  return (
    <div className="min-h-screen flex flex-col bg-paper-50">
      <div className="flex-1 flex items-center justify-center px-4">
        <div className="w-full max-w-sm">
          <div className="mb-6 text-center">
            <svg width="32" height="32" viewBox="0 0 32 32" className="mx-auto mb-3">
              <rect width="32" height="32" rx="6" fill="#0F3D3E" />
              <path d="M9 16.5L14 21L23 10.5" stroke="#E8DCC8" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" fill="none" />
            </svg>
            <h1 className="text-lg font-semibold text-ink-950">Passport verification</h1>
            <p className="text-xs text-ink-950/50 mt-1">No account or login required to check this.</p>
          </div>

          <div className="bg-white rounded-xl border border-paper-200 p-6">
            {loading && <p className="text-sm text-ink-950/50 text-center py-8">Checking</p>}

            {!loading && result?.valid && (
              <div className="text-center">
                <div className="inline-flex items-center gap-1.5 bg-positive-100 text-positive-700 text-xs font-medium px-3 py-1 rounded-md mb-4">
                  <CheckCircle2 size={13} />
                  Valid passport
                </div>
                <p className="font-mono text-4xl font-semibold tabular-nums" style={{ color: scoreTierColor(result.score_value) }}>
                  {result.score_value}
                </p>
                <p className="text-sm text-ink-950/60 mb-4">of 900 · {result.score_band}</p>
                <div className="text-xs text-ink-950/40 border-t border-paper-200 pt-3 mt-3">
                  Issued {new Date(result.issued_at).toLocaleDateString()} · Valid until{' '}
                  {new Date(result.expires_at).toLocaleDateString()}
                </div>
              </div>
            )}

            {!loading && result && !result.valid && (
              <div className="text-center">
                <div className="inline-flex items-center gap-1.5 bg-negative-100 text-negative-700 text-xs font-medium px-3 py-1 rounded-md mb-4">
                  <XCircle size={13} />
                  Not valid
                </div>
                <p className="text-sm text-ink-950/70">{result.reason}</p>
              </div>
            )}
          </div>
        </div>
      </div>

      <footer className="py-6 text-center">
        <div className="flex items-center justify-center gap-4 text-xs text-ink-950/40">
          <Link to="/privacy" className="hover:text-ink-950/70">Privacy policy</Link>
          <span>·</span>
          <Link to="/terms" className="hover:text-ink-950/70">Terms and conditions</Link>
        </div>
      </footer>
    </div>
  )
}
