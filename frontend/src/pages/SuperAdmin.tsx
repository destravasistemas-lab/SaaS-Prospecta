import { useEffect, useState } from 'react'
import { Shield, Building2, Save, Check, X, Clock } from 'lucide-react'
import api, { apiError } from '../services/api'
import HelpLink from '../components/HelpLink'
import { useI18n, tr } from '../i18n'
import { AIUsagePanel, PlansEditor, TenantBilling, type TenantBillingInfo } from '../components/AdminBilling'
import { useMe } from '../components/MeContext'

interface Tenant {
  id: string
  brand_name: string | null
  plan_type: string | null
  parent_account_id: string | null
  blocked_modules: string[]
  user_count: number
  approval_status: 'pending' | 'approved' | 'rejected'
  owner_email: string | null
  owner_name: string | null
  created_at: string | null
  billing: TenantBillingInfo
}

const MODULES: { key: string; label: string }[] = [
  { key: 'whatsapp', label: 'WhatsApp' },
  { key: 'instagram', label: 'Instagram' },
  { key: 'ads', label: 'Meta Ads' },
  { key: 'ia', label: 'IA' },
]

const PLAN_LABEL: Record<string, [string, string]> = {
  autonomo: ['Autônomo', 'Business'],
  agencia: ['Agência', 'Agency'],
  dependente: ['Empresa-filha', 'Client business'],
}

type Filter = 'pending' | 'approved' | 'rejected'

export default function SuperAdmin() {
  const { locale } = useI18n()
  const [tenants, setTenants] = useState<Tenant[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [busyId, setBusyId] = useState<string | null>(null)
  const [query, setQuery] = useState('')
  const [filter, setFilter] = useState<Filter>('pending')
  const [view, setView] = useState<'accounts' | 'plans' | 'ai'>('accounts')
  const [plans, setPlans] = useState<any[]>([])
  const me = useMe()

  const loadPlans = () => api.get('/admin/plans').then(({ data }) => setPlans(data)).catch(() => {})
  useEffect(() => { load(); loadPlans() }, [])

  async function load() {
    setLoading(true)
    try {
      const { data } = await api.get<Tenant[]>('/admin/tenants')
      setTenants(data)
      if (!data.some((t) => t.approval_status === 'pending')) setFilter('approved')
    } catch (err: any) {
      setError(err.response?.status === 403
        ? tr('Acesso restrito. Seu e-mail precisa estar em SUPER_ADMIN_EMAILS.', 'Restricted access. Your email must be in SUPER_ADMIN_EMAILS.')
        : tr('Erro ao carregar as contas.', 'Failed to load accounts.'))
    } finally {
      setLoading(false)
    }
  }

  function replace(updated: Tenant) {
    setTenants((prev) => prev.map((x) => (x.id === updated.id ? updated : x)))
  }

  async function decide(t: Tenant, approved: boolean) {
    if (!approved && !confirm(tr(`Recusar o cadastro de ${t.brand_name}? A pessoa não vai conseguir entrar.`, `Reject ${t.brand_name}? They will not be able to sign in.`))) return
    setBusyId(t.id)
    try {
      const { data } = await api.post<Tenant>(`/admin/tenants/${t.id}/approval`, { approved })
      replace(data)
    } catch (err: any) {
      alert(apiError(err, tr('Erro ao salvar.', 'Failed to save.')))
    } finally {
      setBusyId(null)
    }
  }

  function toggleModule(t: Tenant, key: string) {
    const blocked = new Set(t.blocked_modules)
    blocked.has(key) ? blocked.delete(key) : blocked.add(key)
    replace({ ...t, blocked_modules: [...blocked] })
  }

  async function saveModules(t: Tenant) {
    setBusyId(t.id)
    try {
      await api.put(`/admin/tenants/${t.id}/modules`, { blocked_modules: t.blocked_modules })
    } catch (err: any) {
      alert(apiError(err, tr('Erro ao salvar.', 'Failed to save.')))
    } finally {
      setBusyId(null)
    }
  }

  const count = (f: Filter) => tenants.filter((t) => t.approval_status === f).length
  const q = query.toLowerCase()
  const filtered = tenants.filter((t) => t.approval_status === filter && (
    (t.brand_name || '').toLowerCase().includes(q) || (t.owner_email || '').toLowerCase().includes(q)))

  const tabs: { key: Filter; label: string }[] = [
    { key: 'pending', label: tr('Aguardando', 'Waiting') },
    { key: 'approved', label: tr('Aprovadas', 'Approved') },
    { key: 'rejected', label: tr('Recusadas', 'Rejected') },
  ]

  return (
    <div className="max-w-4xl mx-auto">
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-white flex items-center gap-2">
          <Shield size={20} className="text-amber-400" />
          Super Admin
        </h1>
        <p className="text-ink-4 text-sm mt-1">
          {tr(
            'Cadastro novo só entra no painel depois que você aprova. Aqui você também escolhe os módulos de cada conta; as empresas-filhas herdam o bloqueio e a aprovação da conta-mãe.',
            'New sign-ups only get in after you approve them. You also choose each account’s modules here; client businesses inherit the parent’s block and approval.',
          )}
        </p>
        <HelpLink section="super-admin" className="mt-2" />
      </div>

      {error && <div className="mb-5 bg-red-900/20 border border-red-500/20 text-red-400 text-sm rounded-lg px-4 py-3">{error}</div>}

      <div className="flex gap-2 mb-4">
        {([['accounts', tr('Contas', 'Accounts')], ['plans', tr('Planos', 'Plans')], ['ai', 'IA']] as const).map(([key, label]) => (
          <button key={key} onClick={() => setView(key)}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium border ${view === key ? 'bg-violet-600/20 border-violet-500/40 text-violet-200' : 'border-line text-ink-4 hover:text-ink'}`}>
            {label}
          </button>
        ))}
      </div>

      {me?.billing && !me.billing.enforced && (
        <div className="mb-4 bg-amber-900/15 border border-amber-500/25 text-amber-200 text-xs rounded-lg px-4 py-3">
          {tr(
            'A cobrança está desligada (BILLING_ENFORCED=false): os prazos e avisos aparecem, mas ninguém é bloqueado nem limitado. Ligue no Render depois de configurar o Asaas.',
            'Billing enforcement is off (BILLING_ENFORCED=false): deadlines and notices show, but nobody is blocked or limited. Turn it on in Render once Asaas is set up.',
          )}
        </div>
      )}

      {view === 'ai' ? <AIUsagePanel /> : view === 'plans' ? <PlansEditor plans={plans} reload={loadPlans} /> : <>

      <div className="flex flex-col sm:flex-row gap-3 mb-4">
        <div className="flex rounded-lg border border-line bg-card p-1 text-sm">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setFilter(tab.key)}
              className={`flex-1 sm:flex-none px-3 py-1.5 rounded-md font-medium transition-colors ${
                filter === tab.key ? 'bg-white/[0.08] text-white' : 'text-ink-4 hover:text-ink'
              }`}
            >
              {tab.label}
              <span className={`ml-1.5 text-xs ${tab.key === 'pending' && count('pending') ? 'text-amber-300' : 'text-ink-5'}`}>{count(tab.key)}</span>
            </button>
          ))}
        </div>
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={tr('Buscar por nome ou e-mail…', 'Search by name or email…')}
          className="flex-1 px-4 py-2.5 bg-field border border-line text-ink text-sm rounded-lg focus:border-violet-500 focus:outline-none placeholder-ink-5"
        />
      </div>

      {loading ? (
        <p className="text-center text-ink-4 text-sm py-10">{tr('Carregando…', 'Loading…')}</p>
      ) : filtered.length === 0 ? (
        <p className="text-center text-ink-4 text-sm py-10">
          {filter === 'pending' ? tr('Nenhum cadastro esperando aprovação.', 'No sign-ups waiting for approval.') : tr('Nenhuma conta encontrada.', 'No accounts found.')}
        </p>
      ) : (
        <div className="space-y-2">
          {filtered.map((t) => (
            <div key={t.id} className="bg-card rounded-xl border border-line p-4">
              <div className="flex flex-wrap items-center gap-3">
                <div className="w-9 h-9 rounded-lg bg-white/[0.06] flex items-center justify-center text-ink-3 shrink-0">
                  {t.approval_status === 'pending' ? <Clock size={16} className="text-amber-300" /> : <Building2 size={16} />}
                </div>
                <div className="flex-1 min-w-[12rem]">
                  <p className="text-sm font-semibold text-ink truncate">{t.brand_name || tr('(sem nome)', '(no name)')}</p>
                  <p className="text-xs text-ink-4 truncate">
                    {t.owner_email || '—'}
                    {t.created_at && ` · ${new Date(t.created_at).toLocaleDateString(locale)}`}
                  </p>
                  <p className="text-[11px] text-ink-5">
                    {PLAN_LABEL[t.plan_type || ''] ? tr(...PLAN_LABEL[t.plan_type || '']) : t.plan_type || '—'}
                    {t.parent_account_id && tr(' · filha', ' · client')} · {t.user_count} {tr('usuário(s)', 'user(s)')}
                  </p>
                </div>
                {t.approval_status === 'approved' ? (
                  <button
                    onClick={() => saveModules(t)}
                    disabled={busyId === t.id}
                    className="flex items-center gap-1.5 px-3 py-1.5 bg-violet-600 hover:bg-violet-500 disabled:opacity-50 text-white rounded-lg text-xs font-semibold transition-colors"
                  >
                    <Save size={12} />
                    {busyId === t.id ? tr('Salvando…', 'Saving…') : tr('Salvar módulos', 'Save modules')}
                  </button>
                ) : (
                  <div className="flex gap-2 w-full sm:w-auto">
                    {t.approval_status === 'pending' && (
                      <button
                        onClick={() => decide(t, false)}
                        disabled={busyId === t.id}
                        className="flex-1 sm:flex-none flex items-center justify-center gap-1.5 px-3 py-2 border border-line text-ink-3 hover:text-red-300 hover:border-red-400/40 disabled:opacity-50 rounded-lg text-xs font-semibold transition-colors"
                      >
                        <X size={13} /> {tr('Recusar', 'Reject')}
                      </button>
                    )}
                    <button
                      onClick={() => decide(t, true)}
                      disabled={busyId === t.id}
                      className="flex-1 sm:flex-none flex items-center justify-center gap-1.5 px-3 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white rounded-lg text-xs font-semibold transition-colors"
                    >
                      <Check size={13} /> {tr('Aprovar acesso', 'Approve access')}
                    </button>
                  </div>
                )}
              </div>
              {t.approval_status === 'approved' && (
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-1.5 mt-3">
                  {MODULES.map((m) => {
                    const on = !t.blocked_modules.includes(m.key)
                    return (
                      <button
                        key={m.key}
                        onClick={() => toggleModule(t, m.key)}
                        className={`px-3 py-2 rounded-lg border text-xs font-medium transition-colors ${
                          on ? 'bg-green-600/10 border-green-500/40 text-green-300' : 'bg-field border-line text-ink-5 line-through'
                        }`}
                      >
                        {m.label}
                      </button>
                    )
                  })}
                </div>
              )}
              {t.approval_status === 'approved' && !t.parent_account_id && (
                <TenantBilling tenantId={t.id} info={t.billing} plans={plans} onChange={replace} />
              )}
            </div>
          ))}
        </div>
      )}
      </>}
    </div>
  )
}
