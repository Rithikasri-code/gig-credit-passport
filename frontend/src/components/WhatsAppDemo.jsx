import { useState, useRef, useEffect } from 'react'
import { Send } from 'lucide-react'
import client from '../api/client'

export default function WhatsAppDemo({ phoneNumber }) {
  const [messages, setMessages] = useState([
    { from: 'bot', text: 'Try typing "score", "simulate itr", or "passport". This connects to the same backend a messaging integration would use.' },
  ])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const scrollRef = useRef(null)

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages])

  async function handleSend() {
    const text = input.trim()
    if (!text || sending) return

    setMessages((m) => [...m, { from: 'user', text }])
    setInput('')
    setSending(true)

    try {
      const { data } = await client.post('/whatsapp/webhook', {
        from_number: phoneNumber,
        body: text,
      })
      setMessages((m) => [...m, { from: 'bot', text: data.reply }])
    } catch (err) {
      setMessages((m) => [...m, { from: 'bot', text: 'Something went wrong processing that message.' }])
    } finally {
      setSending(false)
    }
  }

  return (
    <div className="bg-white rounded-xl border border-paper-200 p-6">
      <h2 className="text-base font-semibold text-ink-950">Messaging assistant</h2>
      <p className="text-sm text-ink-950/60 mt-0.5 mb-4">
        Simulated here for testing. In production, this logic runs behind a real messaging number.
      </p>

      <div ref={scrollRef} className="h-64 overflow-y-auto bg-paper-50 rounded-lg p-3 space-y-2 mb-3">
        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.from === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div
              className={`max-w-[80%] rounded-lg px-3 py-2 text-sm whitespace-pre-line ${
                m.from === 'user' ? 'bg-ink-900 text-paper-50' : 'bg-white border border-paper-200 text-ink-950'
              }`}
            >
              {m.text}
            </div>
          </div>
        ))}
      </div>

      <div className="flex gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSend()}
          placeholder="Type a message"
          className="flex-1 rounded-lg border border-paper-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ink-900/30"
        />
        <button
          onClick={handleSend}
          disabled={sending}
          className="flex items-center justify-center rounded-lg bg-ink-900 text-paper-50 px-4 py-2 text-sm font-medium hover:bg-ink-800 disabled:opacity-50 transition-colors"
        >
          <Send size={15} />
        </button>
      </div>
    </div>
  )
}
