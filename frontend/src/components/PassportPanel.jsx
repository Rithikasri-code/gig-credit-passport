import { useState } from 'react'
import { BadgeCheck, Copy, Check, Ban } from 'lucide-react'

export default function PassportPanel({ passports, latestScoreId, onIssue, onRevoke, issuing, revokingId }) {
  const [copiedId, setCopiedId] = useState(null)

  function verifyUrl(id) {
    return `${window.location.origin}/verify/${id}`
  }

  function handleCopy(id) {
    navigator.clipboard?.writeText(verifyUrl(id))
    setCopiedId(id)
    setTimeout(() => setCopiedId(null), 1500)
  }

  return (
    <div className="bg-white rounded-xl border border-paper-200 p-6">
      <div className="flex items-start justify-between mb-4 gap-3">
        <div>
          <h2 className="text-base font-semibold text-ink-950">Shareable passport</h2>
          <p className="text-sm text-ink-950/60 mt-0.5">
            A verifiable link any lender or landlord can check. No login required on their end.
          </p>
        </div>
        <button
          onClick={onIssue}
          disabled={issuing || !latestScoreId}
          className="flex items-center gap-1.5 text-sm font-medium bg-gold-600 text-white rounded-lg px-3 py-1.5 hover:opacity-90 disabled:opacity-50 transition-opacity whitespace-nowrap"
        >
          <BadgeCheck size={14} />
          {issuing ? 'Issuing' : 'New passport'}
        </button>
      </div>

      {!latestScoreId && (
        <p className="text-sm text-ink-950/50 py-6 text-center">Compute a score first to issue a passport.</p>
      )}

      {latestScoreId && passports.length === 0 && (
        <p className="text-sm text-ink-950/50 py-6 text-center">No passports issued yet.</p>
      )}

      <div className="space-y-2">
        {passports.map((p) => (
          <div key={p.id} className="border border-paper-200 rounded-lg p-3">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-ink-950 font-mono tabular-nums">{p.score_value} of 900</p>
                <p className="text-xs text-ink-950/50 mt-0.5">
                  Issued {new Date(p.issued_at).toLocaleDateString()} · Expires{' '}
                  {new Date(p.expires_at).toLocaleDateString()}
                </p>
              </div>
              <span
                className={`text-xs font-medium px-2 py-1 rounded-md ${
                  p.revoked ? 'bg-paper-200 text-ink-950/50' : 'bg-positive-100 text-positive-700'
                }`}
              >
                {p.revoked ? 'Revoked' : 'Active'}
              </span>
            </div>
            {!p.revoked && (
              <div className="flex items-center gap-3 mt-2.5">
                <button
                  onClick={() => handleCopy(p.id)}
                  className="flex items-center gap-1 text-xs font-medium text-ink-900 hover:text-ink-700"
                >
                  {copiedId === p.id ? <Check size={12} /> : <Copy size={12} />}
                  {copiedId === p.id ? 'Copied' : 'Copy verify link'}
                </button>
                <button
                  onClick={() => onRevoke(p.id)}
                  disabled={revokingId === p.id}
                  className="flex items-center gap-1 text-xs font-medium text-negative-700 hover:opacity-80 disabled:opacity-50"
                >
                  <Ban size={12} />
                  {revokingId === p.id ? 'Revoking' : 'Revoke'}
                </button>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
