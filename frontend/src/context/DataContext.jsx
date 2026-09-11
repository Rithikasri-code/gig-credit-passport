import { createContext, useContext, useState, useEffect, useCallback } from 'react'
import client from '../api/client'

const DataContext = createContext(null)

export function DataProvider({ children }) {
  const [score, setScore] = useState(null)
  const [latestScoreId, setLatestScoreId] = useState(null)
  const [reasonCodes, setReasonCodes] = useState([])
  const [consents, setConsents] = useState([])
  const [transactions, setTransactions] = useState([])
  const [passports, setPassports] = useState([])
  const [events, setEvents] = useState([])
  const [itrFiled, setItrFiled] = useState(false)
  const [loaded, setLoaded] = useState(false)
  const [loadError, setLoadError] = useState('')

  const refresh = useCallback(async () => {
    try {
      const [consentsRes, txnsRes, historyRes, passportsRes, eventsRes, meRes] = await Promise.all([
        client.get('/consent/mine'),
        client.get('/accounts/mine/transactions'),
        client.get('/score/history'),
        client.get('/passport/mine'),
        client.get('/score/events'),
        client.get('/users/me'),
      ])
      setConsents(consentsRes.data)
      setTransactions(txnsRes.data)
      setPassports(passportsRes.data)
      setEvents(eventsRes.data)
      setItrFiled(meRes.data.itr_filed)
      if (historyRes.data.length > 0) {
        setScore(historyRes.data[0].score)
        setLatestScoreId(historyRes.data[0].id)
        setReasonCodes(historyRes.data[0].reason_codes)
      }
      setLoadError('')
    } catch (err) {
      setLoadError('Could not load your data. Try refreshing the page.')
    } finally {
      setLoaded(true)
    }
  }, [])

  useEffect(() => {
    refresh()
  }, [refresh])

  const value = {
    score, latestScoreId, reasonCodes, consents, transactions, passports, events, itrFiled,
    loaded, loadError, refresh,
    setScore, setLatestScoreId, setReasonCodes,
  }

  return <DataContext.Provider value={value}>{children}</DataContext.Provider>
}

export function useAppData() {
  const ctx = useContext(DataContext)
  if (!ctx) throw new Error('useAppData must be used within DataProvider')
  return ctx
}
