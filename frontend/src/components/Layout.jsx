import { NavLink, useNavigate } from 'react-router-dom'
import { LayoutDashboard, LineChart, BadgeCheck, Clock, MessageSquare, LogOut } from 'lucide-react'
import { useAuth } from '../context/AuthContext'

const navItems = [
  { to: '/app/home', label: 'Score', icon: LayoutDashboard },
  { to: '/app/insights', label: 'Insights', icon: LineChart },
  { to: '/app/passport', label: 'Passport', icon: BadgeCheck },
  { to: '/app/activity', label: 'Activity', icon: Clock },
  { to: '/app/assistant', label: 'Assistant', icon: MessageSquare },
]

export default function Layout({ children }) {
  const { logout } = useAuth()
  const navigate = useNavigate()

  function handleLogout() {
    logout()
    navigate('/login')
  }

  return (
    <div className="min-h-screen bg-paper-50 flex">
      {/* Desktop sidebar */}
      <aside className="hidden md:flex md:flex-col md:w-60 md:shrink-0 border-r border-paper-200 bg-white">
        <div className="px-5 py-5 border-b border-paper-200">
          <div className="flex items-center gap-2.5">
            <svg width="28" height="28" viewBox="0 0 32 32" className="shrink-0">
              <rect width="32" height="32" rx="6" fill="#0F3D3E" />
              <path d="M9 16.5L14 21L23 10.5" stroke="#E8DCC8" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" fill="none" />
            </svg>
            <span className="font-semibold text-ink-950 text-[15px] leading-tight">Gig Credit<br />Passport</span>
          </div>
        </div>

        <nav className="flex-1 px-3 py-4 space-y-0.5">
          {navItems.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-ink-900 text-paper-50'
                    : 'text-ink-950/70 hover:bg-paper-100'
                }`
              }
            >
              <Icon size={18} strokeWidth={2} />
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="px-3 py-4 border-t border-paper-200">
          <button
            onClick={handleLogout}
            className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium text-ink-950/70 hover:bg-paper-100 w-full transition-colors"
          >
            <LogOut size={18} strokeWidth={2} />
            Log out
          </button>
        </div>
      </aside>

      <div className="flex-1 flex flex-col min-w-0">
        {/* Mobile header */}
        <header className="md:hidden flex items-center justify-between px-4 py-3 bg-white border-b border-paper-200">
          <div className="flex items-center gap-2">
            <svg width="24" height="24" viewBox="0 0 32 32">
              <rect width="32" height="32" rx="6" fill="#0F3D3E" />
              <path d="M9 16.5L14 21L23 10.5" stroke="#E8DCC8" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" fill="none" />
            </svg>
            <span className="font-semibold text-ink-950 text-sm">Gig Credit Passport</span>
          </div>
          <button onClick={handleLogout} aria-label="Log out">
            <LogOut size={20} strokeWidth={2} className="text-ink-950/60" />
          </button>
        </header>

        <main className="flex-1 pb-20 md:pb-0">{children}</main>

        {/* Mobile bottom nav */}
        <nav className="md:hidden fixed bottom-0 inset-x-0 bg-white border-t border-paper-200 flex items-stretch z-20">
          {navItems.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex-1 flex flex-col items-center gap-0.5 py-2.5 text-[11px] font-medium ${
                  isActive ? 'text-ink-900' : 'text-ink-950/50'
                }`
              }
            >
              <Icon size={20} strokeWidth={2} />
              {label}
            </NavLink>
          ))}
        </nav>
      </div>
    </div>
  )
}
