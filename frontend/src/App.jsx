import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './context/AuthContext'
import { DataProvider } from './context/DataContext'
import Layout from './components/Layout'
import Login from './pages/Login'
import Home from './pages/Home'
import Insights from './pages/Insights'
import PassportPage from './pages/PassportPage'
import ActivityPage from './pages/ActivityPage'
import AssistantPage from './pages/AssistantPage'
import PassportVerify from './pages/PassportVerify'
import PrivacyPolicy from './pages/PrivacyPolicy'
import TermsAndConditions from './pages/TermsAndConditions'

function ProtectedApp({ children }) {
  const { isAuthenticated } = useAuth()
  if (!isAuthenticated) return <Navigate to="/login" replace />
  return (
    <DataProvider>
      <Layout>{children}</Layout>
    </DataProvider>
  )
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/privacy" element={<PrivacyPolicy />} />
      <Route path="/terms" element={<TermsAndConditions />} />
      {/* Public — no auth, this is what a lender or landlord opens from a shared link */}
      <Route path="/verify/:passportId" element={<PassportVerify />} />

      <Route path="/app/home" element={<ProtectedApp><Home /></ProtectedApp>} />
      <Route path="/app/insights" element={<ProtectedApp><Insights /></ProtectedApp>} />
      <Route path="/app/passport" element={<ProtectedApp><PassportPage /></ProtectedApp>} />
      <Route path="/app/activity" element={<ProtectedApp><ActivityPage /></ProtectedApp>} />
      <Route path="/app/assistant" element={<ProtectedApp><AssistantPage /></ProtectedApp>} />

      <Route path="*" element={<Navigate to="/app/home" replace />} />
    </Routes>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  )
}
