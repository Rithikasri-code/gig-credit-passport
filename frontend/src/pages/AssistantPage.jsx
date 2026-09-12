import { useAuth } from '../context/AuthContext'
import WhatsAppDemo from '../components/WhatsAppDemo'

export default function AssistantPage() {
  const { phoneNumber } = useAuth()

  return (
    <div className="max-w-3xl mx-auto px-4 md:px-8 py-6 md:py-10">
      <h1 className="text-xl font-semibold text-ink-950 mb-1">Assistant</h1>
      <p className="text-sm text-ink-950/60 mb-6">
        Check your score or issue a passport through a simple text interface.
      </p>

      <WhatsAppDemo phoneNumber={phoneNumber} />
    </div>
  )
}
