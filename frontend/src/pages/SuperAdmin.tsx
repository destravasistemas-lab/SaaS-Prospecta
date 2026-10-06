import { useEffect, useState } from 'react'
import { Shield, Building2, Save } from 'lucide-react'
import api from '../services/api'
import { useI18n, tr } from '../i18n'

interface Tenant {
  id: string
  brand_name: string | null
  plan_type: string | null
  parent_account_id: string | null
  blocked_modules: string[]
  user_count: number
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

export default function SuperAdmin() {
  useI18n()
  const [tenants, setTenants] = useState<Tenant[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [savingId, setSavingId] = useState<string | null>(null)
  const [query, setQuery] = useState('')

  useEffect(() => { load() }, [])

  async function load() {
    setLoading(true)
    try {
      const { data } = await api.get('/admin/tenants')
      setTenants(data)
    } catch (err: any) {
      setError(err.response?.status === 403
        ? tr('Acesso restrito. Seu e-mail precisa estar em SUPER_ADMIN_EMAILS.', 'Restricted access. Your email must be in SUPER_ADMIN_EMAILS.')
        : tr('Erro ao carregar as contas.', 'Failed to load accounts.'))
    } finally {
      setLoading(false)
    }
  }

  // Um módulo está LIBERADO quando NÃO está em blocked_modules.
  function isEnabled(t: Tenant, key: string) {
    return !t.blocked_modules.includes(key)
  }

  function toggle(t: Tenant, key: string) {
    setTenants((prev) => prev.map((x) => {
      if (x.id !== t.id) return x
      const blocked = new Set(x.blocked_modules)
      blocked.has(key) ? blocked.delete(key) : blocked.add(key)
      return { ...x, blocked_modules: [...blocked] }
    }))
  }

  async function save(t: Tenant) {
    setSavingId(t.id)
    try {
      await api.put(`/admin/tenants/${t.id}/modules`, { blocked_modules: t.blocked_modules })
    } catch (err: any) {
      alert(err.response?.data?.detail || tr('Erro ao salvar.', 'Failed to save.'))
    } finally {
      setSavingId(null)
    }
  }

  const filtered = tenants.filter((t) =>
    (t.brand_name || '').toLowerCase().includes(query.toLowerCase()) ||
    (t.plan_type || '').toLowerCase().includes(query.toLowerCase()))

  return (
    <div className="max-w-4xl mx-auto">
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-[#e2e2e8] flex items-center gap-2">
          <Shield size={20} className="text-amber-400" />
          Super Admin
        </h1>
        <p className="text-[#555] text-sm mt-0.5">
          {tr(
            'Controle quais módulos cada conta do sistema pode usar. As empresas-filhas herdam o bloqueio: se você desligar aqui, nem o admin delas consegue ativar.',
            'Control which modules each account can use. Client businesses inherit the block: if you turn it off here, not even their admin can turn it on.',
          )}
        </p>
      </div>

      {error && <div className="mb-5 bg-red-900/20 border border-red-500/20 text-red-400 text-sm rounded-lg px-4 py-3">{error}</div>}

      <input
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder={tr('Buscar por nome ou tipo…', 'Search by name or type…')}
        className="w-full mb-4 px-4 py-2.5 bg-[#0a0a0f] border border-white/[0.08] text-[#e2e2e8] text-sm rounded-lg focus:border-indigo-500 focus:outline-none placeholder-[#333]"
      />

      {loading ? (
        <p className="text-center text-[#555] text-sm py-10">{tr('Carregando…', 'Loading…')}</p>
      ) : filtered.length === 0 ? (
        <p className="text-center text-[#555] text-sm py-10">{tr('Nenhuma conta encontrada.', 'No accounts found.')}</p>
      ) : (
        <div className="space-y-2">
          {filtered.map((t) => (
            <div key={t.id} className="bg-[#111118] rounded-xl border border-white/[0.06] p-4">
              <div className="flex items-center gap-3 mb-3">
                <div className="w-9 h-9 rounded-lg bg-white/[0.06] flex items-center justify-center text-[#8a8a9e] shrink-0">
                  <Building2 size={16} />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-[#e2e2e8] truncate">{t.brand_name || tr('(sem nome)', '(no name)')}</p>
                  <p className="text-[11px] text-[#555]">
                    {PLAN_LABEL[t.plan_type || ''] ? tr(...PLAN_LABEL[t.plan_type || '']) : t.plan_type || '—'}
                    {t.parent_account_id && tr(' · filha', ' · client')} · {t.user_count} {tr('usuário(s)', 'user(s)')}
                  </p>
                </div>
                <button
                  onClick={() => save(t)}
                  disabled={savingId === t.id}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-lg text-xs font-semibold transition-colors"
                >
                  <Save size={12} />
                  {savingId === t.id ? tr('Salvando…', 'Saving…') : tr('Salvar', 'Save')}
                </button>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-1.5">
                {MODULES.map((m) => {
                  const on = isEnabled(t, m.key)
                  return (
                    <button
                      key={m.key}
                      onClick={() => toggle(t, m.key)}
                      className={`px-3 py-2 rounded-lg border text-xs font-medium transition-colors ${
                        on
                          ? 'bg-green-600/10 border-green-500/40 text-green-300'
                          : 'bg-[#0a0a0f] border-white/[0.08] text-[#555] line-through'
                      }`}
                    >
                      {m.label}
                    </button>
                  )
                })}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
