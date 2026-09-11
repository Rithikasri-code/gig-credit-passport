import { createContext, useContext, useState, useCallback } from 'react'
import client from '../api/client'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [userId, setUserId] = useState(localStorage.getItem('user_id'))
  const [phoneNumber, setPhoneNumber] = useState(localStorage.getItem('phone_number'))
  const [isAuthenticated, setIsAuthenticated] = useState(!!localStorage.getItem('access_token'))

  const requestOtp = useCallback(async (phoneNumber) => {
    const { data } = await client.post('/auth/otp/request', { phone_number: phoneNumber })
    return data
  }, [])

  const verifyOtp = useCallback(async (phoneNumber, otp, fullName) => {
    const { data } = await client.post('/auth/otp/verify', {
      phone_number: phoneNumber,
      otp,
      full_name: fullName,
    })
    localStorage.setItem('access_token', data.access_token)
    localStorage.setItem('user_id', data.user_id)
    localStorage.setItem('phone_number', phoneNumber)
    setUserId(data.user_id)
    setPhoneNumber(phoneNumber)
    setIsAuthenticated(true)
    return data
  }, [])

  const logout = useCallback(() => {
    localStorage.removeItem('access_token')
    localStorage.removeItem('user_id')
    localStorage.removeItem('phone_number')
    setUserId(null)
    setPhoneNumber(null)
    setIsAuthenticated(false)
  }, [])

  return (
    <AuthContext.Provider value={{ userId, phoneNumber, isAuthenticated, requestOtp, verifyOtp, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
