import { useState, useEffect } from 'react'
import { NavLink, useNavigate, useLocation } from 'react-router-dom'
import {
  LayoutDashboard, Clapperboard, Megaphone, Link2, Send,
  Users, Settings, CreditCard, Building2, LogOut,
  ChevronRight, ChevronDown, MessageSquare, FileText, Clock,
  Headphones, Camera, Zap, Shield,
  type LucideIcon,
} from 'lucide-react'
import api from '../services/api'
import AccountSwitcher from './AccountSwitcher'

type NavItem = { to: string; label: string; icon: LucideIcon; end?: boolean; sub?: string }
type NavGroup = { id: string; label: string; icon: LucideIcon; items: NavItem[] }

const topLinks: NavItem[] = [
  { to: '/app', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/app/leads', label: 'Leads', icon: Users },
  { to: '/app/conexao', label: 'Conexão Meta', icon: Link2 },
]

const bottomLinks: NavItem[] = [
  { to: '/app/equipe', label: 'Equipe', icon: Users },
  { to: '/app/configuracoes', label: 'Configurações', icon: Settings },
  { to: '/pricing', label: 'Planos', icon: CreditCard },
]

function navItemClass(isActive: boolean): string {
  return `flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-all ${
    isActive
      ? 'bg-indigo-600/20 text-indigo-300 border border-indigo-500/20'
      : 'text-[#5a5a6e] hover:bg-white/[0.04] hover:text-[#c0c0d0]'
  }`
}

export default function Sidebar() {
  const navigate = useNavigate()
  const location = useLocation()
  const [planType, setPlanType] = useState<string | null>(null)
  const [isSuperAdmin, setIsSuperAdmin] = useState(false)
  const [waNumber, setWaNumber] = useState<string | null>(null)
  const [blockedModules, setBlockedModules] = useState<string[]>([])
  // Módulos efetivos deste usuário (conta - bloqueados ∩ permitidos do usuário).
  const [modules, setModules] = useState<string[] | null>(null)

  // Um módulo "some" do menu se não estiver nos módulos efetivos do usuário.
  // Fallback para blocked_modules quando o backend antigo não mandar `modules`.
  const blocked = (m: string) =>
    modules !== null ? !modules.includes(m) : blockedModules.includes(m)

  // Módulos bloqueados pela agência-mãe/super admin somem do menu
  // (o backend também bloqueia as rotas com 403).
  const groups: NavGroup[] = [
    {
      id: 'atendimento',
      label: 'Atendimento ao Cliente',
      icon: Headphones,
      items: [
        ...(!blocked('whatsapp') ? [
          { to: '/app/whatsapp', label: 'WhatsApp', icon: MessageSquare, sub: waNumber ?? undefined },
        ] : []),
        ...(!blocked('ia') ? [
          { to: '/app/ia', label: 'IA & Conhecimento', icon: Zap },
        ] : []),
        ...(!blocked('whatsapp') ? [
          { to: '/app/templates', label: 'Templates', icon: FileText },
          { to: '/app/followups', label: 'Follow-ups', icon: Clock },
        ] : []),
      ],
    },
    ...(!blocked('instagram') ? [{
      id: 'instagram',
      label: 'Instagram',
      icon: Camera,
      items: [
        { to: '/app/publicar', label: 'Publicar & Automação', icon: Send },
        { to: '/app/instagram-dm', label: 'Direct', icon: MessageSquare },
      ],
    }] : []),
    ...(!blocked('ads') ? [{
      id: 'ads',
      label: 'Meta Ads',
      icon: Megaphone,
      items: [
        { to: '/app/marketing', label: 'Campanhas', icon: Megaphone },
      ],
    }] : []),
  ].filter((g) => g.items.length > 0)

  // Abre por padrão o grupo que contém a rota atual
  const [open, setOpen] = useState<Record<string, boolean>>(() => {
    const initial: Record<string, boolean> = {}
    for (const g of groups) {
      initial[g.id] = g.items.some((i) => location.pathname.startsWith(i.to))
    }
    return initial
  })

  useEffect(() => {
    api.get('/auth/me').then(({ data }) => {
      if (data?.plan_type) setPlanType(data.plan_type)
      if (Array.isArray(data?.blocked_modules)) setBlockedModules(data.blocked_modules)
      if (Array.isArray(data?.modules)) setModules(data.modules)
      setIsSuperAdmin(!!data?.is_super_admin)
    }).catch(() => {})

    // Número do WhatsApp conectado (via Meta) — mostrado sob o item WhatsApp
    api.get('/whatsapp/credentials').then(({ data }) => {
      if (data?.phone_number) setWaNumber(data.phone_number)
    }).catch(() => {})
  }, [])

  const isAgency = planType === 'agencia'

  function toggleGroup(id: string) {
    setOpen((prev) => ({ ...prev, [id]: !prev[id] }))
  }

  function handleLogout() {
    localStorage.clear()
    navigate('/login')
  }

  return (
    <aside className="w-64 bg-[#07070c] min-h-screen flex flex-col border-r border-white/[0.05]">
      {/* Logo */}
      <div className="px-5 pt-6 pb-4">
        <button
          onClick={() => navigate('/')}
          className="flex items-center gap-2 group"
        >
          <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-neon-pink via-neon-purple to-neon-cyan flex items-center justify-center shadow-lg shadow-neon-purple/40">
            <Clapperboard size={14} className="text-white" />
          </div>
          <span className="text-sm font-semibold text-white">
            ad<span className="bg-gradient-to-r from-neon-pink via-neon-purple to-neon-cyan bg-clip-text text-transparent">Studio</span>AI
          </span>
        </button>
      </div>

      {/* Account switcher (agência ↔ clientes) */}
      <AccountSwitcher />

      {/* Main nav */}
      <nav className="flex-1 px-3 py-2 flex flex-col gap-0.5 overflow-y-auto">
        <p className="text-[10px] font-semibold uppercase tracking-wider text-[#3a3a4a] px-2 mb-2 mt-1">
          Principal
        </p>
        {topLinks.map((link) => {
          const Icon = link.icon
          return (
            <NavLink
              key={link.to}
              to={link.to}
              end={'end' in link ? link.end : false}
              className={({ isActive }) => navItemClass(isActive)}
            >
              <Icon size={15} strokeWidth={1.75} />
              <span className="flex-1">{link.label}</span>
            </NavLink>
          )
        })}

        {/* Grupos (dropdown) */}
        {groups.map((group) => {
          const GroupIcon = group.icon
          const isOpen = !!open[group.id]
          const hasActive = group.items.some((i) => location.pathname.startsWith(i.to))
          return (
            <div key={group.id} className="mt-1">
              <button
                onClick={() => toggleGroup(group.id)}
                className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-all ${
                  hasActive && !isOpen
                    ? 'text-indigo-300'
                    : 'text-[#7a7a8e] hover:bg-white/[0.04] hover:text-[#c0c0d0]'
                }`}
              >
                <GroupIcon size={15} strokeWidth={1.75} />
                <span className="flex-1 text-left">{group.label}</span>
                {isOpen
                  ? <ChevronDown size={13} className="opacity-50" />
                  : <ChevronRight size={13} className="opacity-50" />}
              </button>

              {isOpen && (
                <div className="ml-3 pl-3 border-l border-white/[0.06] flex flex-col gap-0.5 mt-0.5">
                  {group.items.map((item) => {
                    const Icon = item.icon
                    return (
                      <NavLink
                        key={item.to}
                        to={item.to}
                        className={({ isActive }) => navItemClass(isActive)}
                      >
                        <Icon size={14} strokeWidth={1.75} />
                        <span className="flex-1 min-w-0">
                          <span className="block truncate">{item.label}</span>
                          {item.sub && (
                            <span className="block text-[10px] text-emerald-500/80 truncate leading-tight">
                              {item.sub}
                            </span>
                          )}
                        </span>
                      </NavLink>
                    )
                  })}
                </div>
              )}
            </div>
          )
        })}

        {isAgency && (
          <>
            <div className="h-px bg-white/[0.05] my-3 mx-2" />
            <p className="text-[10px] font-semibold uppercase tracking-wider text-[#3a3a4a] px-2 mb-2">
              Agência
            </p>
            <NavLink
              to="/app/clientes"
              className={({ isActive }) => navItemClass(isActive)}
            >
              <Building2 size={15} strokeWidth={1.75} />
              <span className="flex-1">Clientes</span>
              <ChevronRight size={12} className="opacity-40" />
            </NavLink>
          </>
        )}

        {isSuperAdmin && (
          <>
            <div className="h-px bg-white/[0.05] my-3 mx-2" />
            <p className="text-[10px] font-semibold uppercase tracking-wider text-[#3a3a4a] px-2 mb-2">
              Sistema
            </p>
            <NavLink
              to="/app/super-admin"
              className={({ isActive }) => navItemClass(isActive)}
            >
              <Shield size={15} strokeWidth={1.75} />
              <span className="flex-1">Super Admin</span>
              <ChevronRight size={12} className="opacity-40" />
            </NavLink>
          </>
        )}
      </nav>

      {/* Bottom nav */}
      <div className="px-3 pb-4 border-t border-white/[0.05] pt-3 flex flex-col gap-0.5">
        {bottomLinks.map((link) => {
          const Icon = link.icon
          return (
            <NavLink
              key={link.to}
              to={link.to}
              className={({ isActive }) => navItemClass(isActive)}
            >
              <Icon size={15} strokeWidth={1.75} />
              {link.label}
            </NavLink>
          )
        })}
        <button
          onClick={handleLogout}
          className="flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium text-[#5a5a6e] hover:bg-white/[0.04] hover:text-red-400 transition-all w-full mt-1"
        >
          <LogOut size={15} strokeWidth={1.75} />
          Sair
        </button>
      </div>
    </aside>
  )
}
