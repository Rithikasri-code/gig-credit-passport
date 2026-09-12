import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { Phone, User, AlertCircle } from 'lucide-react'
import { useAuth } from '../context/AuthContext'

export default function Login() {
  const [step, setStep] = useState('phone')
  const [phoneNumber, setPhoneNumber] = useState('')
  const [fullName, setFullName] = useState('')
  const [otp, setOtp] = useState('')
  const [debugOtp, setDebugOtp] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const { requestOtp, verifyOtp } = useAuth()
  const navigate = useNavigate()

  async function handleRequestOtp(e) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const data = await requestOtp(phoneNumber)
      setDebugOtp(data.debug_otp || null)
      setStep('otp')
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not send a verification code. Try again.')
    } finally {
      setLoading(false)
    }
  }

  async function handleVerifyOtp(e) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await verifyOtp(phoneNumber, otp, fullName)
      navigate('/app/home')
    } catch (err) {
      setError(err.response?.data?.detail || 'Incorrect code. Try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex flex-col bg-paper-50">
      <div className="flex-1 flex items-center justify-center px-4">
        <div className="w-full max-w-sm">
          <div className="mb-8 flex flex-col items-center text-center">
            <svg width="40" height="40" viewBox="0 0 32 32" className="mb-3">
              <rect width="32" height="32" rx="6" fill="#0F3D3E" />
              <path d="M9 16.5L14 21L23 10.5" stroke="#E8DCC8" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" fill="none" />
            </svg>
            <h1 className="text-xl font-semibold text-ink-950">Gig Credit Passport</h1>
            <p className="mt-1 text-sm text-ink-950/60">A portable, explainable credit score built from your own income data.</p>
          </div>

          <div className="bg-white rounded-xl border border-paper-200 p-6">
            {step === 'phone' && (
              <form onSubmit={handleRequestOtp} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-ink-950 mb-1.5">Phone number</label>
                  <div className="relative">
                    <Phone size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-950/40" />
                    <input
                      type="tel"
                      required
                      value={phoneNumber}
                      onChange={(e) => setPhoneNumber(e.target.value)}
                      placeholder="10-digit mobile number"
                      className="w-full rounded-lg border border-paper-300 pl-9 pr-3 py-2.5 text-sm text-ink-950 focus:outline-none focus:ring-2 focus:ring-ink-900/30"
                    />
                  </div>
                </div>
                <div>
                  <label className="block text-sm font-medium text-ink-950 mb-1.5">
                    Name <span className="text-ink-950/40 font-normal">(first time only)</span>
                  </label>
                  <div className="relative">
                    <User size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-950/40" />
                    <input
                      type="text"
                      value={fullName}
                      onChange={(e) => setFullName(e.target.value)}
                      placeholder="Your name"
                      className="w-full rounded-lg border border-paper-300 pl-9 pr-3 py-2.5 text-sm text-ink-950 focus:outline-none focus:ring-2 focus:ring-ink-900/30"
                    />
                  </div>
                </div>
                {error && (
                  <p className="flex items-start gap-1.5 text-sm text-negative-700">
                    <AlertCircle size={15} className="shrink-0 mt-0.5" />
                    {error}
                  </p>
                )}
                <button
                  type="submit"
                  disabled={loading}
                  className="w-full rounded-lg bg-ink-900 text-paper-50 font-medium py-2.5 text-sm hover:bg-ink-800 disabled:opacity-50 transition-colors"
                >
                  {loading ? 'Sending code' : 'Send code'}
                </button>
              </form>
            )}

            {step === 'otp' && (
              <form onSubmit={handleVerifyOtp} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-ink-950 mb-1.5">
                    Enter the 6-digit code sent to {phoneNumber}
                  </label>
                  <input
                    type="text"
                    required
                    maxLength={6}
                    value={otp}
                    onChange={(e) => setOtp(e.target.value)}
                    placeholder="000000"
                    className="w-full rounded-lg border border-paper-300 px-3 py-2.5 text-center text-lg font-mono tracking-widest focus:outline-none focus:ring-2 focus:ring-ink-900/30"
                  />
                  {debugOtp && (
                    <p className="mt-2 text-xs text-caution-700 bg-caution-100 rounded-lg px-2.5 py-1.5">
                      Test mode: your code is <strong className="font-mono">{debugOtp}</strong>. No text message is sent yet.
                    </p>
                  )}
                </div>
                {error && (
                  <p className="flex items-start gap-1.5 text-sm text-negative-700">
                    <AlertCircle size={15} className="shrink-0 mt-0.5" />
                    {error}
                  </p>
                )}
                <button
                  type="submit"
                  disabled={loading}
                  className="w-full rounded-lg bg-ink-900 text-paper-50 font-medium py-2.5 text-sm hover:bg-ink-800 disabled:opacity-50 transition-colors"
                >
                  {loading ? 'Verifying' : 'Verify and continue'}
                </button>
                <button
                  type="button"
                  onClick={() => setStep('phone')}
                  className="w-full text-sm text-ink-950/50 hover:text-ink-950"
                >
                  Use a different number
                </button>
              </form>
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
