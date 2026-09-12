import { useState } from 'react'
import client from '../api/client'
import { useAppData } from '../context/DataContext'
import IncomeTimeline from '../components/IncomeTimeline'
import SimulatorPanel from '../components/SimulatorPanel'
import UploadEarnings from '../components/UploadEarnings'

export default function Insights() {
  const { transactions, itrFiled } = useAppData()

  const [simulating, setSimulating] = useState(false)
  const [simResult, setSimResult] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [lastUploadResult, setLastUploadResult] = useState(null)
  const [error, setError] = useState('')

  async function handleSimulate(payload) {
    setSimulating(true)
    setSimResult(null)
    setError('')
    try {
      const { data } = await client.post('/score/simulate', payload)
      setSimResult(data)
    } catch (err) {
      setError('Could not run that simulation. Link and sync an account first.')
    } finally {
      setSimulating(false)
    }
  }

  async function handleUpload(file) {
    setUploading(true)
    setLastUploadResult(null)
    setError('')
    try {
      const formData = new FormData()
      formData.append('file', file)
      const { data } = await client.post('/self-reported/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      setLastUploadResult(data)
    } catch (err) {
      setError('Could not read that screenshot. Try a clearer image.')
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="max-w-3xl mx-auto px-4 md:px-8 py-6 md:py-10">
      <h1 className="text-xl font-semibold text-ink-950 mb-1">Insights</h1>
      <p className="text-sm text-ink-950/60 mb-6">
        What your income data shows, and what could change it.
      </p>

      {error && (
        <div className="mb-4 text-sm bg-negative-100 text-negative-700 rounded-lg px-3 py-2">{error}</div>
      )}

      <div className="space-y-6">
        <IncomeTimeline transactions={transactions} />
        <SimulatorPanel onSimulate={handleSimulate} simulating={simulating} result={simResult} itrAlreadyFiled={itrFiled} />
        <UploadEarnings onUpload={handleUpload} uploading={uploading} lastResult={lastUploadResult} />
      </div>
    </div>
  )
}
