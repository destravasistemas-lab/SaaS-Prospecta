import { useEffect, useState } from 'react'
import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { Menu } from 'lucide-react'
import Sidebar from './Sidebar'
import { CallProvider } from './CallProvider'
import { BRANDING } from '../config/branding'
import { useI18n } from '../i18n'

export default function Layout() {
  const location = useLocation()
  const { t } = useI18n()
  const token = localStorage.getItem('access_token')
  const [menuOpen, setMenuOpen] = useState(false)

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

  // Guard: sem JWT não entra no painel — volta pro login (com redirect de retorno)
  if (!token) {
    return <Navigate to={`/login?redirect=${encodeURIComponent(location.pathname)}`} replace />
  }

  return (
    <CallProvider>
      <div className="flex min-h-screen bg-[#0c0618] text-[#f8fafc]">
        <Sidebar menuOpen={menuOpen} onClose={() => setMenuOpen(false)} />
        {menuOpen && <div className="lg:hidden fixed inset-0 z-40 bg-black/60" onClick={() => setMenuOpen(false)} />}
        <div className="flex-1 min-w-0 flex flex-col">
          {/* Celular e tablet: o menu lateral vira gaveta */}
          <header className="lg:hidden sticky top-0 z-30 h-14 shrink-0 flex items-center gap-2 px-2 bg-[#0c0618] border-b border-[#a78bfa]/10">
            <button
              onClick={() => setMenuOpen(true)}
              aria-label={t('Abrir menu', 'Open menu')}
              aria-expanded={menuOpen}
              className="w-10 h-10 flex items-center justify-center rounded-lg text-[#c0c0d0] hover:bg-white/[0.06]"
            >
              <Menu size={20} />
            </button>
            <span className="w-7 h-7 rounded-lg bg-gradient-to-br from-violet-600 via-fuchsia-500 to-orange-400 flex items-center justify-center text-white font-bold text-xs">P</span>
            <span className="text-sm font-semibold text-white tracking-tight">{BRANDING.name}</span>
          </header>
          <main className="flex-1 overflow-auto p-4 sm:p-6 lg:p-8">
            <Outlet />
          </main>
        </div>
      </div>
    </CallProvider>
  )
}
