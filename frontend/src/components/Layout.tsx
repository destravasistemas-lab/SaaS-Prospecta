import { useEffect, useState } from 'react'
import { Navigate, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { Home, Menu, MessageSquare, Send, Users } from 'lucide-react'
import Sidebar from './Sidebar'
import { CallProvider } from './CallProvider'
import { MeContext, hasModule, type Me } from './MeContext'
import api from '../services/api'
import { BRANDING } from '../config/branding'
import { useI18n } from '../i18n'

export default function Layout() {
  const location = useLocation()
  const navigate = useNavigate()
  const { t } = useI18n()
  const token = localStorage.getItem('access_token')
  const [menuOpen, setMenuOpen] = useState(false)
  const [me, setMe] = useState<Me | null>(null)

  useEffect(() => {
    if (!token) return
    api.get<Me>('/auth/me').then(({ data }) => setMe(data)).catch((err) => {
      // Conta que ainda espera aprovação (ou foi recusada) volta para o login com o aviso.
      const code = err?.response?.data?.detail?.code
      if (code === 'pending_approval' || code === 'account_rejected') {
        localStorage.removeItem('access_token')
        localStorage.removeItem('refresh_token')
        navigate(`/login?status=${code}`, { replace: true })
      }
    })
  }, [token, navigate])

  useEffect(() => {
    setMenuOpen(false)
  }, [location.pathname, location.search])

  useEffect(() => {
    if (!menuOpen) return
    const onKeyDown = (e: KeyboardEvent) => { if (e.key === 'Escape') setMenuOpen(false) }
    document.addEventListener('keydown', onKeyDown)
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKeyDown)
      document.body.style.overflow = ''
    }
  }, [menuOpen])

  if (!token) {
    return <Navigate to={`/login?redirect=${encodeURIComponent(location.pathname)}`} replace />
  }

  const tabs = [
    { to: '/app', label: t('Início', 'Home'), icon: Home, end: true },
    ...(hasModule(me, 'whatsapp') ? [{ to: '/app/whatsapp', label: t('Conversas', 'Inbox'), icon: MessageSquare, end: false }] : []),
    { to: '/app/leads', label: 'Leads', icon: Users, end: false },
    ...(hasModule(me, 'whatsapp') ? [{ to: '/app/followups', label: t('Disparos', 'Broadcasts'), icon: Send, end: false }] : []),
  ]

  return (
    <MeContext.Provider value={me}>
      <CallProvider>
        <div className="flex min-h-screen bg-canvas text-ink">
          <Sidebar menuOpen={menuOpen} onClose={() => setMenuOpen(false)} />
          {menuOpen && <div className="lg:hidden fixed inset-0 z-40 bg-black/70 backdrop-blur-sm" onClick={() => setMenuOpen(false)} />}
          <div className="flex-1 min-w-0 flex flex-col">
            <header className="lg:hidden sticky top-0 z-30 h-14 shrink-0 flex items-center gap-2.5 px-4 bg-canvas/90 backdrop-blur border-b border-line">
              <span className="w-7 h-7 rounded-lg bg-gradient-to-br from-violet-600 to-fuchsia-500 flex items-center justify-center text-white font-bold text-xs">P</span>
              <span className="text-sm font-semibold text-white tracking-tight flex-1 truncate">
                {me?.brand_name || BRANDING.name}
              </span>
            </header>
            <main className="flex-1 overflow-auto px-4 pt-5 pb-24 sm:px-6 lg:px-10 lg:pt-8 lg:pb-10">
              <Outlet />
            </main>
          </div>

          {/* Celular: barra de abas fixa com as telas mais usadas; "Menu" abre o resto. */}
          <nav className="lg:hidden fixed bottom-0 inset-x-0 z-30 bg-panel/95 backdrop-blur border-t border-line pb-[env(safe-area-inset-bottom)]">
            <div className="grid" style={{ gridTemplateColumns: `repeat(${tabs.length + 1}, minmax(0, 1fr))` }}>
              {tabs.map(({ to, label, icon: Icon, end }) => (
                <NavLink
                  key={to}
                  to={to}
                  end={end}
                  className={({ isActive }) => `flex flex-col items-center gap-1 py-2.5 text-[11px] font-medium ${
                    isActive ? 'text-violet-300' : 'text-ink-4'
                  }`}
                >
                  <Icon size={20} strokeWidth={1.75} />
                  {label}
                </NavLink>
              ))}
              <button
                onClick={() => setMenuOpen(true)}
                aria-label={t('Abrir menu', 'Open menu')}
                aria-expanded={menuOpen}
                className="flex flex-col items-center gap-1 py-2.5 text-[11px] font-medium text-ink-4"
              >
                <Menu size={20} strokeWidth={1.75} />
                {t('Menu', 'Menu')}
              </button>
            </div>
          </nav>
        </div>
      </CallProvider>
    </MeContext.Provider>
  )
}
