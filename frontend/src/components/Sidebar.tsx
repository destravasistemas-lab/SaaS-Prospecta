import { useEffect, useState } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import {
  Home, Users, Link2, Send, Megaphone, MessageSquare, FileText, Zap, Shield,
  BookOpen, CreditCard, Building2, LogOut, Settings, UserCog, Camera, Sparkles,
  X, Radar, type LucideIcon,
} from 'lucide-react'
import api from '../services/api'
import AccountSwitcher from './AccountSwitcher'
import { hasModule, useMe } from './MeContext'
import { BRANDING } from '../config/branding'
import { useI18n, LanguageToggle } from '../i18n'

type NavItem = { to: string; label: string; icon: LucideIcon; end?: boolean; hint?: string; badge?: number }
type NavSection = { label?: string; items: NavItem[] }

function NavRow({ item }: { item: NavItem }) {
  const Icon = item.icon
  return (
    <NavLink
      to={item.to}
      end={item.end}
      className={({ isActive }) => `group relative flex items-center gap-3 px-3 py-[7px] rounded-lg text-[13px] font-medium transition-colors ${
        isActive ? 'bg-white/[0.06] text-white' : 'text-ink-3 hover:bg-white/[0.03] hover:text-ink'
      }`}
    >
      {({ isActive }) => (
        <>
          {isActive && <span className="absolute left-0 top-1.5 bottom-1.5 w-0.5 rounded-full bg-violet-400" />}
          <Icon size={16} strokeWidth={1.75} className={isActive ? 'text-violet-300' : 'text-ink-4 group-hover:text-ink-2'} />
          <span className="flex-1 min-w-0">
            <span className="block truncate">{item.label}</span>
            {item.hint && <span className="block text-[10px] text-emerald-400/80 truncate leading-tight">{item.hint}</span>}
          </span>
          {!!item.badge && (
            <span className="min-w-5 h-5 px-1.5 rounded-full bg-amber-500/20 text-amber-300 text-[10px] font-semibold flex items-center justify-center">
              {item.badge}
            </span>
          )}
        </>
      )}
    </NavLink>
  )
}

export default function Sidebar({ menuOpen, onClose }: { menuOpen: boolean; onClose: () => void }) {
  const navigate = useNavigate()
  const { t } = useI18n()
  const me = useMe()
  const [waNumber, setWaNumber] = useState<string | null>(null)
  const [pendingApprovals, setPendingApprovals] = useState(0)

  useEffect(() => {
    if (!me) return
    if (hasModule(me, 'whatsapp')) {
      api.get('/whatsapp/credentials').then(({ data }) => {
        if (data?.credentials?.phone_number) setWaNumber(data.credentials.phone_number)
      }).catch(() => {})
    }
    if (me.is_super_admin) {
      api.get('/admin/tenants').then(({ data }) => {
        setPendingApprovals((data as { approval_status: string }[]).filter((a) => a.approval_status === 'pending').length)
      }).catch(() => {})
    }
  }, [me])

  const wa = hasModule(me, 'whatsapp')
  const ig = hasModule(me, 'instagram')
  const ads = hasModule(me, 'ads')
  const ia = hasModule(me, 'ia')

  const sections: NavSection[] = [
    { items: [{ to: '/app', label: t('Início', 'Home'), icon: Home, end: true }] },
    {
      label: t('Conversas', 'Inbox'),
      items: [
        ...(wa ? [{ to: '/app/whatsapp', label: 'WhatsApp', icon: MessageSquare, hint: waNumber ?? undefined }] : []),
        ...(ig ? [{ to: '/app/instagram-dm', label: t('Direct do Instagram', 'Instagram Direct'), icon: Camera }] : []),
      ],
    },
    {
      label: t('Crescimento', 'Growth'),
      items: [
        ...(ig ? [{ to: '/app/publicar', label: t('Posts e automações', 'Posts & automations'), icon: Sparkles }] : []),
        ...(wa ? [
          { to: '/app/followups', label: t('Disparos', 'Broadcasts'), icon: Send },
          { to: '/app/templates', label: 'Templates', icon: FileText },
        ] : []),
        ...(ads ? [{ to: '/app/marketing', label: t('Anúncios', 'Ads'), icon: Megaphone }] : []),
      ],
    },
    {
      label: t('Clientes', 'Customers'),
      items: [
        { to: '/app/leads', label: 'Leads', icon: Users },
        { to: '/app/prospeccao', label: t('Prospecção', 'Prospecting'), icon: Radar },
        ...(ia ? [{ to: '/app/ia', label: t('IA e conhecimento', 'AI & knowledge'), icon: Zap }] : []),
      ],
    },
    ...(me?.plan_type === 'agencia' ? [{
      label: t('Agência', 'Agency'),
      items: [{ to: '/app/clientes', label: t('Empresas clientes', 'Client businesses'), icon: Building2 }],
    }] : []),
    ...(me?.is_super_admin ? [{
      label: t('Sistema', 'System'),
      items: [{ to: '/app/super-admin', label: 'Super Admin', icon: Shield, badge: pendingApprovals }],
    }] : []),
    {
      label: t('Conta', 'Account'),
      items: [
        { to: '/app/conexao', label: t('Conexões', 'Connections'), icon: Link2 },
        { to: '/app/equipe', label: t('Equipe', 'Team'), icon: UserCog },
        { to: '/app/configuracoes', label: t('Configurações', 'Settings'), icon: Settings },
        { to: '/app/planos', label: t('Planos', 'Plans'), icon: CreditCard },
        { to: '/app/guia', label: t('Guia', 'Guide'), icon: BookOpen },
      ],
    },
  ].filter((s) => s.items.length > 0)

  function handleLogout() {
    localStorage.clear()
    navigate('/login')
  }

  const initials = (me?.full_name || me?.username || '?').trim().slice(0, 1).toUpperCase()

  return (
    <aside
      onClick={(e) => { if ((e.target as HTMLElement).closest('a')) onClose() }}
      className={`w-64 shrink-0 bg-panel border-r border-line flex flex-col lg:sticky lg:top-0 lg:h-screen max-lg:fixed max-lg:inset-y-0 max-lg:left-0 max-lg:z-50 max-lg:w-80 max-lg:max-w-[88vw] max-lg:transition-transform max-lg:duration-200 ${
        menuOpen ? '' : 'max-lg:-translate-x-full max-lg:invisible'
      }`}
    >
      <div className="h-16 shrink-0 px-5 flex items-center gap-2.5">
        <button onClick={() => navigate('/app')} className="flex items-center gap-2.5 flex-1 min-w-0">
          <span className="w-8 h-8 rounded-lg bg-gradient-to-br from-violet-600 to-fuchsia-500 flex items-center justify-center shadow-lg shadow-violet-600/25 text-white font-bold text-sm">P</span>
          <span className="text-left">
            <span className="block text-sm font-semibold text-white tracking-tight">{BRANDING.name}</span>
            <span className="block text-[10px] text-ink-4">by {BRANDING.company}</span>
          </span>
        </button>
        <button onClick={onClose} aria-label={t('Fechar menu', 'Close menu')} className="lg:hidden w-9 h-9 -mr-2 flex items-center justify-center rounded-lg text-ink-3 hover:bg-white/[0.06]">
          <X size={18} />
        </button>
      </div>

      <AccountSwitcher />

      <nav className="flex-1 overflow-y-auto px-3 pb-3">
        {sections.map((section, i) => (
          <div key={section.label ?? i} className={i ? 'mt-4' : 'mt-1'}>
            {section.label && (
              <p className="px-3 mb-1.5 text-[10px] font-semibold uppercase tracking-[0.08em] text-ink-5">{section.label}</p>
            )}
            <div className="flex flex-col gap-0.5">
              {section.items.map((item) => <NavRow key={item.to} item={item} />)}
            </div>
          </div>
        ))}
      </nav>

      <div className="shrink-0 border-t border-line px-3 py-3">
        <div className="flex items-center gap-2.5 rounded-lg bg-white/[0.03] px-2.5 py-2">
          <span className="w-8 h-8 rounded-full bg-violet-500/20 text-violet-200 text-xs font-semibold flex items-center justify-center shrink-0">{initials}</span>
          <span className="flex-1 min-w-0">
            <span className="block text-xs font-medium text-ink truncate">{me?.full_name || me?.username || '…'}</span>
            <span className="block text-[10px] text-ink-4 truncate">{me?.brand_name}</span>
          </span>
          <button onClick={handleLogout} title={t('Sair', 'Log out')} aria-label={t('Sair', 'Log out')} className="w-8 h-8 flex items-center justify-center rounded-lg text-ink-4 hover:text-red-400 hover:bg-white/[0.04]">
            <LogOut size={15} />
          </button>
        </div>
        <LanguageToggle compact className="mt-3 w-full justify-center" />
      </div>
    </aside>
  )
}
