import { useState, useEffect } from 'react'
import {
  Building2, Plus, ExternalLink, Trash2, Users, TrendingUp,
  CheckCircle, Wifi, WifiOff, X, Eye, EyeOff,
  BarChart3, Blocks, MailCheck, MailWarning,
} from 'lucide-react'
import api from '../services/api'

interface Client {
  id: string
  brand_name: string
  username: string
  full_name: string | null
  is_active: boolean
  plan: string
  plan_type: string
  email: string | null
  email_verified: boolean
  blocked_modules: string[]
  created_at: string
}

// Módulos que a agência pode bloquear por cliente (espelha o backend)
const MODULES: { key: string; label: string; desc: string }[] = [
  { key: 'whatsapp', label: 'WhatsApp', desc: 'Atendimento, templates, follow-ups e disparos' },
  { key: 'instagram', label: 'Instagram', desc: 'Publicar, automação e Direct' },
  { key: 'ads', label: 'Meta Ads', desc: 'Campanhas, anúncios e métricas' },
  { key: 'ia', label: 'IA de atendimento', desc: 'Gemini + base de conhecimento (RAG)' },
]

interface AgencyStat {
  id: string
  brand_name: string
  is_active: boolean
  leads: number
  converted: number
  conversion_rate: number
  new_leads_7d: number
  instagram_connected: boolean
}

interface AgencyDashboard {
  total_clients: number
  active_clients: number
  total_leads: number
  total_converted: number
  overall_conversion_rate: number
  new_leads_7d: number
  clients: AgencyStat[]
}

const planLabel: Record<string, string> = {
  free: 'Grátis',
  starter: 'Iniciante',
  pro: 'Profissional',
  premium: 'Premium',
}

const planColor: Record<string, string> = {
  free:    'text-[#555] bg-white/[0.03] border-white/[0.04]',
  starter: 'text-blue-400 bg-blue-900/20 border-blue-500/20',
  pro:     'text-purple-400 bg-purple-900/20 border-purple-500/20',
  premium: 'text-amber-400 bg-amber-900/20 border-amber-500/20',
}

function MetricCard({ icon: Icon, iconColor, value, label, sub }: {
  icon: React.ElementType; iconColor: string; value: string | number; label: string; sub?: string
}) {
  return (
    <div className="bg-[#111118] border border-white/[0.06] rounded-xl p-4 hover:border-white/[0.1] transition-colors">
      <div className={`w-8 h-8 rounded-lg flex items-center justify-center mb-3 ${iconColor}`}>
        <Icon size={15} strokeWidth={1.75} />
      </div>
      <p className="text-xl font-semibold text-[#e2e2e8] leading-none mb-1">{value}</p>
      <p className="text-xs text-[#555]">{label}</p>
      {sub && <p className="text-[10px] text-[#444] mt-0.5">{sub}</p>}
    </div>
  )
}

export default function Clients() {
  const [clients, setClients] = useState<Client[]>([])
  const [agencyStats, setAgencyStats] = useState<AgencyDashboard | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  // modal criar
  const [showCreate, setShowCreate] = useState(false)
  const [createName, setCreateName] = useState('')
  const [createUsername, setCreateUsername] = useState('')
  const [createPassword, setCreatePassword] = useState('')
  const [createFullName, setCreateFullName] = useState('')
  const [createEmail, setCreateEmail] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [creating, setCreating] = useState(false)
  const [createError, setCreateError] = useState('')

  // modal módulos (bloquear/liberar por cliente)
  const [modulesOf, setModulesOf] = useState<Client | null>(null)
  const [blockedDraft, setBlockedDraft] = useState<string[]>([])
  const [savingModules, setSavingModules] = useState(false)

  useEffect(() => { loadData() }, [])

  async function loadData() {
    setLoading(true)
    try {
      const [clientsRes, statsRes] = await Promise.allSettled([
        api.get('/auth/clients'),
        api.get('/dashboard/agency'),
      ])
      if (clientsRes.status === 'fulfilled') setClients(clientsRes.value.data)
      if (statsRes.status === 'fulfilled') setAgencyStats(statsRes.value.data)
    } catch {
      setError('Erro ao carregar dados.')
    } finally {
      setLoading(false)
    }
  }

  async function handleCreate(e: React.SyntheticEvent) {
    e.preventDefault()
    setCreateError('')
    if (!createName.trim() || !createUsername.trim() || !createPassword.trim() || !createEmail.trim()) {
      setCreateError('Preencha todos os campos obrigatórios.')
      return
    }
    if (!createEmail.includes('@')) {
      setCreateError('Informe um email válido — o dono recebe o link de verificação nele.')
      return
    }
    setCreating(true)
    try {
      await api.post('/auth/clients', {
        brand_name: createName.trim(),
        username: createUsername.trim(),
        password: createPassword,
        full_name: createFullName.trim() || null,
        email: createEmail.trim(),
      })
      setShowCreate(false)
      setCreateName('')
      setCreateUsername('')
      setCreatePassword('')
      setCreateFullName('')
      setCreateEmail('')
      await loadData()
    } catch (err: any) {
      setCreateError(err.response?.data?.detail || 'Erro ao criar cliente.')
    } finally {
      setCreating(false)
    }
  }

  function openModules(client: Client) {
    setModulesOf(client)
    setBlockedDraft([...(client.blocked_modules || [])])
  }

  async function saveModules() {
    if (!modulesOf) return
    setSavingModules(true)
    try {
      await api.put(`/auth/clients/${modulesOf.id}/modules`, { blocked_modules: blockedDraft })
      setModulesOf(null)
      await loadData()
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Erro ao salvar os módulos.')
    } finally {
      setSavingModules(false)
    }
  }

  async function handleImpersonate(clientId: string) {
    try {
      // Preserve the agency session so the account switcher can return to it.
      localStorage.setItem('agency_access_token', localStorage.getItem('access_token') || '')
      localStorage.setItem('agency_refresh_token', localStorage.getItem('refresh_token') || '')
      localStorage.setItem('agency_tenant_id', localStorage.getItem('tenant_id') || '')
      localStorage.setItem('agency_user_id', localStorage.getItem('user_id') || '')

      const { data } = await api.post(`/auth/clients/${clientId}/impersonate`)
      localStorage.setItem('access_token', data.access_token)
      localStorage.setItem('refresh_token', data.refresh_token)
      localStorage.setItem('user_id', data.user_id)
      localStorage.setItem('tenant_id', data.tenant_id)
      localStorage.setItem('impersonating', 'true')
      localStorage.setItem('impersonating_name', data.client_brand_name)
      // Full reload so every screen refetches with the client's tenant.
      window.location.href = '/app'
    } catch {
      alert('Erro ao acessar conta do cliente.')
    }
  }

  async function handleDelete(clientId: string) {
    if (!confirm('Desativar este cliente?')) return
    try {
      await api.delete(`/auth/clients/${clientId}`)
      await loadData()
    } catch {
      alert('Erro ao remover cliente.')
    }
  }

  const getClientStat = (clientId: string): AgencyStat | undefined =>
    agencyStats?.clients.find((c) => c.id === clientId)

  return (
    <div className="max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold text-[#e2e2e8] flex items-center gap-2">
            <Building2 size={20} className="text-indigo-400" />
            Meus Clientes
          </h1>
          <p className="text-[#555] text-sm mt-0.5">
            Gerencie as contas dos seus clientes como agência.
          </p>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-semibold rounded-lg transition-colors"
        >
          <Plus size={15} />
          Novo Cliente
        </button>
      </div>

      {error && (
        <div className="mb-5 bg-red-900/20 border border-red-500/20 text-red-400 text-sm rounded-lg px-4 py-3">{error}</div>
      )}

      {/* Agency metrics */}
      {agencyStats && (
        <div className="mb-6">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-[#444] mb-3 flex items-center gap-2">
            <BarChart3 size={11} />
            Visão geral da agência
            <span className="flex-1 h-px bg-white/[0.05]" />
          </p>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <MetricCard
              icon={Building2}
              iconColor="bg-indigo-500/10 text-indigo-400"
              value={agencyStats.total_clients}
              label="Total de clientes"
              sub={`${agencyStats.active_clients} ativos`}
            />
            <MetricCard
              icon={Users}
              iconColor="bg-blue-500/10 text-blue-400"
              value={agencyStats.total_leads}
              label="Total de leads"
              sub={`+${agencyStats.new_leads_7d} esta semana`}
            />
            <MetricCard
              icon={CheckCircle}
              iconColor="bg-green-500/10 text-green-400"
              value={agencyStats.total_converted}
              label="Leads convertidos"
              sub="em todos os clientes"
            />
            <MetricCard
              icon={TrendingUp}
              iconColor="bg-purple-500/10 text-purple-400"
              value={`${agencyStats.overall_conversion_rate}%`}
              label="Taxa de conversão"
              sub="conversão global"
            />
          </div>
        </div>
      )}

      {/* Client list */}
      {loading ? (
        <div className="space-y-3">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="bg-[#111118] rounded-xl border border-white/[0.06] p-5 animate-pulse">
              <div className="flex items-center gap-4">
                <div className="w-10 h-10 rounded-xl bg-white/[0.04]" />
                <div className="flex-1 space-y-2">
                  <div className="h-3.5 bg-white/[0.04] rounded w-40" />
                  <div className="h-2.5 bg-white/[0.03] rounded w-24" />
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : clients.length === 0 ? (
        <div className="bg-[#111118] rounded-xl border border-white/[0.06] p-16 text-center">
          <div className="w-14 h-14 rounded-2xl bg-indigo-500/10 flex items-center justify-center mx-auto mb-4">
            <Building2 size={24} className="text-indigo-400" />
          </div>
          <h3 className="text-base font-semibold text-[#e2e2e8] mb-2">Nenhum cliente ainda</h3>
          <p className="text-[#444] text-sm max-w-sm mx-auto mb-5">
            Crie contas para seus clientes e gerencie tudo em um só lugar.
          </p>
          <button
            onClick={() => setShowCreate(true)}
            className="px-5 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-semibold rounded-lg transition-colors"
          >
            Criar primeiro cliente
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          {clients.map((client) => {
            const stat = getClientStat(client.id)
            return (
              <div
                key={client.id}
                className="bg-[#111118] rounded-xl border border-white/[0.06] p-5 hover:border-white/[0.1] transition-colors"
              >
                <div className="flex items-center gap-4">
                  {/* Avatar */}
                  <div className="w-10 h-10 rounded-xl bg-indigo-500/10 flex items-center justify-center text-sm font-bold text-indigo-400 shrink-0">
                    {client.brand_name.charAt(0).toUpperCase()}
                  </div>

                  {/* Info */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <h3 className="text-[#e2e2e8] font-semibold text-sm">{client.brand_name}</h3>
                      <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded border ${
                        client.is_active
                          ? 'bg-green-900/20 text-green-400 border-green-500/20'
                          : 'bg-red-900/20 text-red-400 border-red-500/20'
                      }`}>
                        {client.is_active ? 'Ativo' : 'Inativo'}
                      </span>
                      <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded border ${planColor[client.plan] ?? planColor.free}`}>
                        {planLabel[client.plan] ?? client.plan}
                      </span>
                      {client.plan_type === 'dependente' && (
                        <span className="text-[10px] font-medium px-1.5 py-0.5 rounded border bg-indigo-900/20 text-indigo-300 border-indigo-500/20">
                          Dependente
                        </span>
                      )}
                      {client.email && (
                        client.email_verified ? (
                          <span title={`${client.email} — verificado`} className="text-[10px] font-medium px-1.5 py-0.5 rounded border bg-green-900/20 text-green-400 border-green-500/20 flex items-center gap-1">
                            <MailCheck size={10} /> verificado
                          </span>
                        ) : (
                          <span title={`Aguardando o dono confirmar ${client.email}`} className="text-[10px] font-medium px-1.5 py-0.5 rounded border bg-amber-900/20 text-amber-400 border-amber-500/20 flex items-center gap-1">
                            <MailWarning size={10} /> email pendente
                          </span>
                        )
                      )}
                      {(client.blocked_modules?.length ?? 0) > 0 && (
                        <span className="text-[10px] font-medium px-1.5 py-0.5 rounded border bg-red-900/20 text-red-400 border-red-500/20">
                          {client.blocked_modules.length} módulo(s) off
                        </span>
                      )}
                    </div>
                    <p className="text-[#555] text-xs mt-0.5">@{client.username}</p>
                  </div>

                  {/* Stats from agency dashboard */}
                  {stat && (
                    <div className="hidden md:flex items-center gap-5 mr-4">
                      <div className="text-center">
                        <p className="text-sm font-semibold text-[#e2e2e8] leading-none">{stat.leads}</p>
                        <p className="text-[10px] text-[#444] mt-0.5">leads</p>
                      </div>
                      <div className="text-center">
                        <p className="text-sm font-semibold text-green-400 leading-none">{stat.conversion_rate}%</p>
                        <p className="text-[10px] text-[#444] mt-0.5">conversão</p>
                      </div>
                      <div className="text-center">
                        <p className="text-[10px] text-[#444]">Instagram</p>
                        {stat.instagram_connected
                          ? <Wifi size={12} className="text-green-400 mx-auto mt-0.5" />
                          : <WifiOff size={12} className="text-[#444] mx-auto mt-0.5" />
                        }
                      </div>
                      {stat.new_leads_7d > 0 && (
                        <div className="text-center">
                          <p className="text-sm font-semibold text-blue-400 leading-none">+{stat.new_leads_7d}</p>
                          <p className="text-[10px] text-[#444] mt-0.5">7 dias</p>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Actions */}
                  <div className="flex gap-2 shrink-0">
                    <button
                      onClick={() => openModules(client)}
                      title="Bloquear/liberar módulos deste cliente"
                      className="flex items-center gap-1.5 px-3 py-1.5 bg-white/[0.04] hover:bg-white/[0.08] text-[#8a8a9e] hover:text-white rounded-lg text-xs font-semibold transition-colors"
                    >
                      <Blocks size={12} />
                      Módulos
                    </button>
                    <button
                      onClick={() => handleImpersonate(client.id)}
                      className="flex items-center gap-1.5 px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-semibold transition-colors"
                    >
                      <ExternalLink size={12} />
                      Acessar
                    </button>
                    <button
                      onClick={() => handleDelete(client.id)}
                      className="p-1.5 bg-red-900/20 text-red-400 rounded-lg hover:bg-red-900/40 transition-colors"
                    >
                      <Trash2 size={13} />
                    </button>
                  </div>
                </div>

                {/* Mobile stats */}
                {stat && (
                  <div className="flex md:hidden items-center gap-4 mt-3 pt-3 border-t border-white/[0.04]">
                    <span className="text-xs text-[#555]">{stat.leads} leads</span>
                    <span className="text-xs text-green-400">{stat.conversion_rate}% conversão</span>
                    {stat.instagram_connected
                      ? <span className="text-xs text-green-400 flex items-center gap-1"><Wifi size={10} /> Instagram</span>
                      : <span className="text-xs text-[#444] flex items-center gap-1"><WifiOff size={10} /> Sem Instagram</span>
                    }
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}

      {/* Create modal */}
      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm px-4">
          <div className="bg-[#111118] border border-white/[0.08] rounded-2xl p-7 w-full max-w-md">
            <div className="flex items-center justify-between mb-5">
              <div>
                <h3 className="text-base font-semibold text-white">Novo Cliente</h3>
                <p className="text-xs text-[#555] mt-0.5">Crie uma subconta para seu cliente.</p>
              </div>
              <button onClick={() => setShowCreate(false)} className="text-[#444] hover:text-[#888] transition-colors">
                <X size={18} />
              </button>
            </div>

            <form onSubmit={handleCreate} className="space-y-4">
              {createError && (
                <div className="bg-red-900/20 border border-red-500/20 text-red-400 text-xs rounded-lg px-4 py-3">
                  {createError}
                </div>
              )}

              <div>
                <label className="block text-xs font-medium text-[#666] mb-1.5">Nome da empresa / cliente *</label>
                <input
                  type="text"
                  value={createName}
                  onChange={(e) => setCreateName(e.target.value)}
                  placeholder="Ex: Padaria do João"
                  className="w-full px-4 py-2.5 bg-[#0a0a0f] border border-white/[0.08] text-[#e2e2e8] text-sm rounded-lg focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500 focus:outline-none placeholder-[#333]"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-[#666] mb-1.5">Email do dono *</label>
                <input
                  type="email"
                  value={createEmail}
                  onChange={(e) => setCreateEmail(e.target.value)}
                  placeholder="dono@empresa.com"
                  className="w-full px-4 py-2.5 bg-[#0a0a0f] border border-white/[0.08] text-[#e2e2e8] text-sm rounded-lg focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500 focus:outline-none placeholder-[#333]"
                />
                <p className="text-[10px] text-[#555] mt-1">
                  O dono recebe um link de verificação neste email — o login dele só ativa depois de confirmar.
                </p>
              </div>

              <div>
                <label className="block text-xs font-medium text-[#666] mb-1.5">Nome de usuário *</label>
                <input
                  type="text"
                  value={createUsername}
                  onChange={(e) => setCreateUsername(e.target.value)}
                  placeholder="Ex: padariajoao"
                  className="w-full px-4 py-2.5 bg-[#0a0a0f] border border-white/[0.08] text-[#e2e2e8] text-sm rounded-lg focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500 focus:outline-none placeholder-[#333]"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-[#666] mb-1.5">Senha *</label>
                <div className="relative">
                  <input
                    type={showPassword ? 'text' : 'password'}
                    value={createPassword}
                    onChange={(e) => setCreatePassword(e.target.value)}
                    placeholder="Mínimo 6 caracteres"
                    className="w-full px-4 py-2.5 pr-10 bg-[#0a0a0f] border border-white/[0.08] text-[#e2e2e8] text-sm rounded-lg focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500 focus:outline-none placeholder-[#333]"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-[#444] hover:text-[#888]"
                  >
                    {showPassword ? <EyeOff size={14} /> : <Eye size={14} />}
                  </button>
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-[#666] mb-1.5">Nome completo (opcional)</label>
                <input
                  type="text"
                  value={createFullName}
                  onChange={(e) => setCreateFullName(e.target.value)}
                  placeholder="Ex: João Silva"
                  className="w-full px-4 py-2.5 bg-[#0a0a0f] border border-white/[0.08] text-[#e2e2e8] text-sm rounded-lg focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500 focus:outline-none placeholder-[#333]"
                />
              </div>

              <div className="flex gap-3 pt-1">
                <button
                  type="button"
                  onClick={() => setShowCreate(false)}
                  className="flex-1 py-2.5 border border-white/[0.08] text-[#666] hover:text-white text-sm font-medium rounded-lg transition-colors"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  disabled={creating}
                  className="flex-1 py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm font-semibold rounded-lg transition-colors"
                >
                  {creating ? 'Criando...' : 'Criar Cliente'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: módulos do cliente (bloquear/liberar) */}
      {modulesOf && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm px-4">
          <div className="bg-[#111118] border border-white/[0.08] rounded-2xl p-7 w-full max-w-md">
            <div className="flex items-center justify-between mb-1">
              <h3 className="text-base font-semibold text-white flex items-center gap-2">
                <Blocks size={16} className="text-indigo-400" /> Módulos — {modulesOf.brand_name}
              </h3>
              <button onClick={() => setModulesOf(null)} className="text-[#444] hover:text-[#888] transition-colors">
                <X size={18} />
              </button>
            </div>
            <p className="text-xs text-[#555] mb-5">
              Desligue um módulo para escondê-lo e bloqueá-lo por completo para este cliente.
            </p>

            <div className="space-y-3">
              {MODULES.map((m) => {
                const blocked = blockedDraft.includes(m.key)
                return (
                  <div key={m.key} className="flex items-center justify-between gap-3 bg-[#0a0a0f] border border-white/[0.05] rounded-lg p-3">
                    <div className="min-w-0">
                      <p className={`text-sm font-medium ${blocked ? 'text-[#555] line-through' : 'text-[#e2e2e8]'}`}>{m.label}</p>
                      <p className="text-[11px] text-[#555]">{m.desc}</p>
                    </div>
                    <button
                      onClick={() =>
                        setBlockedDraft((prev) =>
                          blocked ? prev.filter((k) => k !== m.key) : [...prev, m.key]
                        )
                      }
                      title={blocked ? 'Bloqueado — clique para liberar' : 'Liberado — clique para bloquear'}
                      className={`w-11 h-6 rounded-full relative transition-colors shrink-0 ${blocked ? 'bg-white/[0.08]' : 'bg-green-500'}`}
                    >
                      <span className={`absolute top-0.5 w-5 h-5 rounded-full bg-white transition-all ${blocked ? 'left-0.5' : 'left-[22px]'}`} />
                    </button>
                  </div>
                )
              })}
            </div>

            <div className="flex gap-3 pt-5">
              <button
                onClick={() => setModulesOf(null)}
                className="flex-1 py-2.5 border border-white/[0.08] text-[#666] hover:text-white text-sm font-medium rounded-lg transition-colors"
              >
                Cancelar
              </button>
              <button
                onClick={saveModules}
                disabled={savingModules}
                className="flex-1 py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm font-semibold rounded-lg transition-colors"
              >
                {savingModules ? 'Salvando…' : 'Salvar módulos'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
