import { useState, useRef } from 'react'
import { UploadCloud, AlertCircle } from 'lucide-react'

export default function UploadEarnings({ onUpload, uploading, lastResult }) {
  const fileRef = useRef(null)
  const [dragOver, setDragOver] = useState(false)

  function handleFile(file) {
    if (file) onUpload(file)
  }

  return (
    <div className="bg-white rounded-xl border border-paper-200 p-6">
      <h2 className="text-base font-semibold text-ink-950">Add earnings screenshot</h2>
      <p className="text-sm text-ink-950/60 mt-0.5 mb-4">
        Upload a Swiggy, Uber, or Zomato earnings screenshot for extra context. This is self-reported.
        It is checked against your linked bank data and never used on its own.
      </p>

      <div
        onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault()
          setDragOver(false)
          handleFile(e.dataTransfer.files?.[0])
        }}
        onClick={() => fileRef.current?.click()}
        className={`border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition-colors ${
          dragOver ? 'border-ink-900 bg-paper-100' : 'border-paper-300 hover:border-ink-900/40'
        }`}
      >
        <input
          ref={fileRef}
          type="file"
          accept="image/*"
          className="hidden"
          onChange={(e) => handleFile(e.target.files?.[0])}
        />
        <UploadCloud size={20} className="mx-auto mb-2 text-ink-950/40" />
        <p className="text-sm text-ink-950/60">
          {uploading ? 'Reading screenshot' : 'Click or drag a screenshot here'}
        </p>
      </div>

      {lastResult && (
        <div className="mt-4 text-sm bg-paper-50 border border-paper-200 rounded-lg p-3 space-y-1.5">
          <div className="flex items-center justify-between">
            <span className="font-medium text-ink-950">{lastResult.source_platform}</span>
            <span className="flex items-center gap-1 text-xs bg-caution-100 text-caution-700 px-2 py-0.5 rounded-md">
              <AlertCircle size={11} />
              Self-reported, not verified
            </span>
          </div>
          {lastResult.total_earnings && <p className="text-ink-950/70">Earnings: ₹{lastResult.total_earnings}</p>}
          {lastResult.trip_or_order_count && <p className="text-ink-950/70">{lastResult.trip_or_order_count} orders or trips</p>}
          {lastResult.rating && <p className="text-ink-950/70">Rating: {lastResult.rating}</p>}
        </div>
      )}
    </div>
  )
}
