import { Link } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'

export default function PrivacyPolicy() {
  return (
    <div className="min-h-screen bg-paper-50">
      <div className="max-w-2xl mx-auto px-4 md:px-8 py-8 md:py-12">
        <Link to="/login" className="inline-flex items-center gap-1.5 text-sm text-ink-950/60 hover:text-ink-950 mb-8">
          <ArrowLeft size={15} />
          Back
        </Link>

        <h1 className="text-2xl font-semibold text-ink-950 mb-1">Privacy policy</h1>
        <p className="text-sm text-ink-950/50 mb-8">Last updated September 2026</p>

        <div className="prose-sm text-ink-950/80 space-y-6 text-sm leading-relaxed">
          <section>
            <h2 className="text-base font-semibold text-ink-950 mb-2">What we collect</h2>
            <p>
              With your explicit, revocable consent, we access bank and UPI transaction
              data through the Account Aggregator framework to compute a credit score.
              We also collect your phone number for login, and, if you choose to upload
              one, gig platform earnings screenshots. Each of these is used only for
              the purpose you consented to.
            </p>
          </section>

          <section>
            <h2 className="text-base font-semibold text-ink-950 mb-2">Consent and revocation</h2>
            <p>
              Every time we access your financial data, it is tied to a specific
              consent record showing what was requested, when, and for how long. You
              can revoke any consent at any time from the app. Revoking a consent
              immediately blocks any further data access under it. This is enforced
              in our system, not just displayed in the interface.
            </p>
          </section>

          <section>
            <h2 className="text-base font-semibold text-ink-950 mb-2">Self-reported data</h2>
            <p>
              Earnings screenshots you upload are stored separately from your
              bank-verified transactions and are always labeled as self-reported. We
              cross-check them against your linked bank data but never treat them as
              verified on their own.
            </p>
          </section>

          <section>
            <h2 className="text-base font-semibold text-ink-950 mb-2">Your passport</h2>
            <p>
              When you issue a shareable passport, the link contains your score and
              its validity period. It does not expose your underlying transaction
              data, account details, or the full breakdown of your score. Anyone
              checking a passport link sees only a valid or not valid result, the
              score, and its expiry. You can revoke any issued passport at any time.
              We keep a log of verification attempts, including the requester's IP
              address, to detect misuse of this feature, since it does not require a
              login to check.
            </p>
          </section>

          <section>
            <h2 className="text-base font-semibold text-ink-950 mb-2">Data retention</h2>
            <p>
              Financial data fetched under a consent is retained only for the period
              specified in that consent record, after which it is not used for
              further scoring. You can request deletion of your account and
              associated data by contacting us.
            </p>
          </section>

          <section>
            <h2 className="text-base font-semibold text-ink-950 mb-2">Who can see your data</h2>
            <p>
              Your raw transaction data, account details, and full score breakdown
              are never shared with any third party, including lenders, without your
              explicit action. A lender or landlord can only see what you choose to
              share through an issued passport link.
            </p>
          </section>

          <section>
            <h2 className="text-base font-semibold text-ink-950 mb-2">Contact</h2>
            <p>
              For questions about this policy or to request data deletion, contact us
              through the support channel listed in the app.
            </p>
          </section>
        </div>
      </div>
    </div>
  )
}
