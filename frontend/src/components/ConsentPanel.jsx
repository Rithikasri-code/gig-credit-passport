import { Link2, ShieldOff, RefreshCw } from 'lucide-react'

const statusStyles = {
  ACTIVE: 'bg-positive-100 text-positive-700',
  PENDING: 'bg-caution-100 text-caution-700',
  REVOKED: 'bg-paper-200 text-ink-950/50',
  EXPIRED: 'bg-paper-200 text-ink-950/50',
}

export default function ConsentPanel({ consents, onLinkAccount, onRevoke, onSync, linking, revokingId, syncingId }) {
  return (
    <div className="bg-white rounded-xl border border-paper-200 p-6">
      <div className="flex items-start justify-between mb-4 gap-3">
        <div>
          <h2 className="text-base font-semibold text-ink-950">Data access</h2>
          <p className="text-sm text-ink-950/60 mt-0.5">
            Every consent you have granted, with full control to revoke it.
          </p>
        </div>
        <button
          onClick={onLinkAccount}
          disabled={linking}
          className="flex items-center gap-1.5 text-sm font-medium bg-ink-900 text-paper-50 rounded-lg px-3 py-1.5 hover:bg-ink-800 disabled:opacity-50 transition-colors whitespace-nowrap"
        >
          <Link2 size={14} />
          {linking ? 'Linking' : 'Link account'}
        </button>
      </div>

      {consents.length === 0 && (
        <p className="text-sm text-ink-950/50 py-6 text-center">
          No accounts linked yet.
        </p>
      )}

      <div className="space-y-2">
        {consents.map((c) => (
          <div key={c.id} className="border border-paper-200 rounded-lg p-3">
            <div className="flex items-center justify-between gap-2">
              <div className="min-w-0">
                <p className="text-sm font-medium text-ink-950 truncate">{c.purpose}</p>
                <p className="text-xs text-ink-950/50 mt-0.5">
                  Requested {new Date(c.requested_at).toLocaleDateString()}
                  {c.expires_at && ` · Expires ${new Date(c.expires_at).toLocaleDateString()}`}
                </p>
              </div>
              <span className={`text-xs font-medium px-2 py-1 rounded-md shrink-0 ${statusStyles[c.status] || ''}`}>
                {c.status}
              </span>
            </div>
            {c.status === 'ACTIVE' && (
              <div className="flex items-center gap-3 mt-2.5">
                <button
                  onClick={() => onSync(c.id)}
                  disabled={syncingId === c.id}
                  className="flex items-center gap-1 text-xs font-medium text-ink-900 hover:text-ink-700 disabled:opacity-50"
                >
                  <RefreshCw size={12} className={syncingId === c.id ? 'animate-spin' : ''} />
                  Sync data
                </button>
                <button
                  onClick={() => onRevoke(c.id)}
                  disabled={revokingId === c.id}
                  className="flex items-center gap-1 text-xs font-medium text-negative-700 hover:opacity-80 disabled:opacity-50"
                >
                  <ShieldOff size={12} />
                  {revokingId === c.id ? 'Revoking' : 'Revoke access'}
                </button>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
