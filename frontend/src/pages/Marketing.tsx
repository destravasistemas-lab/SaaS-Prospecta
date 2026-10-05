import { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { Pause, Play, Trash2, ChevronRight, Building2, Copy, Download } from 'lucide-react'
import api from '../services/api'

interface Campaign {
  id: string
  name: string
  status: string
  objective: string
  daily_budget: string | null
  lifetime_budget: string | null
}

interface Insights {
  spend: number
  impressions: number
  reach: number
  frequency: number
  clicks: number
  ctr: number
  cpc: number
  cpm: number
  results: number
  result_label: string
  cost_per_result: number
  purchase_value: number
  roas: number
}

interface AdAccount {
  id: string
  name: string
  account_status: number
  currency: string
  business_name: string | null
}

interface AdAttribution {
  ad_id: string
  ad_name: string | null
  leads: number
}

interface AttributionSummary {
  total_leads: number
  leads_from_ads: number
  by_ad: AdAttribution[]
}

const DATE_PRESETS: { value: string; label: string }[] = [
  { value: 'last_7d', label: '7 dias' },
  { value: 'last_30d', label: '30 dias' },
  { value: 'last_90d', label: '90 dias' },
]

export default function Marketing() {
  const [campaigns, setCampaigns] = useState<Campaign[]>([])
  const [insights, setInsights] = useState<Insights | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const [accounts, setAccounts] = useState<AdAccount[]>([])
  const [activeAccountId, setActiveAccountId] = useState<string | null>(null)
  const [switchingAccount, setSwitchingAccount] = useState(false)
  const [attribution, setAttribution] = useState<AttributionSummary | null>(null)

  const [datePreset, setDatePreset] = useState('last_30d')
  const [busyCampaignId, setBusyCampaignId] = useState<string | null>(null)
  const [exporting, setExporting] = useState(false)

  const [showCreate, setShowCreate] = useState(false)
  const [campName, setCampName] = useState('')
  const [campObjective, setCampObjective] = useState('OUTCOME_LEADS')
  const [creating, setCreating] = useState(false)

  const objectiveLabels: Record<string, string> = {
    OUTCOME_LEADS: 'Geração de Leads',
    OUTCOME_SALES: 'Vendas',
    OUTCOME_AWARENESS: 'Reconhecimento',
    OUTCOME_ENGAGEMENT: 'Engajamento',
    OUTCOME_TRAFFIC: 'Tráfego',
  }

  const loadAccounts = useCallback(async () => {
    try {
      const { data } = await api.get<AdAccount[]>('/marketing/ad-accounts')
      setAccounts(data)
      if (data.length > 0) setActiveAccountId((prev) => prev ?? data[0].id)
    } catch { /* sem conexão de anúncios ainda — silencioso, o erro de campanhas cobre isso */ }
  }, [])

  const loadData = useCallback(async (preset: string) => {
    setLoading(true)
    setError('')
    try {
      const [campRes, insRes] = await Promise.all([
        api.get('/marketing/campaigns'),
        api.get('/marketing/insights', { params: { date_preset: preset } }),
      ])
      setCampaigns(campRes.data)
      setInsights(insRes.data)
    } catch {
      setError('Erro ao carregar dados. Conecte uma conta de anúncios primeiro.')
    } finally {
      setLoading(false)
    }
  }, [])

  const loadAttribution = useCallback(async () => {
    try {
      const { data } = await api.get<AttributionSummary>('/marketing/attribution')
      setAttribution(data)
    } catch { /* atribuição é enriquecimento — não bloqueia a tela */ }
  }, [])

  useEffect(() => { loadAccounts() }, [loadAccounts])
  useEffect(() => { loadData(datePreset) }, [loadData, datePreset])
  useEffect(() => { loadAttribution() }, [loadAttribution])

  async function handleSwitchAccount(id: string) {
    if (id === activeAccountId || switchingAccount) return
    setSwitchingAccount(true)
    try {
      await api.put('/marketing/ad-account', { ad_account_id: id })
      setActiveAccountId(id)
      await loadData(datePreset)
    } catch {
      setError('Erro ao trocar de conta de anúncios.')
    } finally {
      setSwitchingAccount(false)
    }
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault()
    if (!campName.trim()) return
    setCreating(true)
    try {
      await api.post('/marketing/campaigns', {
        name: campName.trim(),
        objective: campObjective,
        status: 'PAUSED',
      })
      setShowCreate(false)
      setCampName('')
      await loadData(datePreset)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Erro ao criar campanha.')
    } finally {
      setCreating(false)
    }
  }

  async function toggleStatus(c: Campaign) {
    setBusyCampaignId(c.id)
    try {
      await api.patch(`/marketing/campaigns/${c.id}`, {
        status: c.status === 'ACTIVE' ? 'PAUSED' : 'ACTIVE',
      })
      await loadData(datePreset)
    } catch {
      setError('Erro ao atualizar status da campanha.')
    } finally {
      setBusyCampaignId(null)
    }
  }

  async function handleDelete(c: Campaign) {
    if (!confirm(`Excluir a campanha "${c.name}"? Essa ação não pode ser desfeita.`)) return
    setBusyCampaignId(c.id)
    try {
      await api.delete(`/marketing/campaigns/${c.id}`)
      setCampaigns((prev) => prev.filter((x) => x.id !== c.id))
    } catch {
      setError('Erro ao excluir campanha.')
    } finally {
      setBusyCampaignId(null)
    }
  }

  async function handleDuplicate(c: Campaign) {
    setBusyCampaignId(c.id)
    try {
      await api.post(`/marketing/campaigns/${c.id}/copy`)
      await loadData(datePreset)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Erro ao duplicar campanha.')
    } finally {
      setBusyCampaignId(null)
    }
  }

  async function exportCsv() {
    setExporting(true)
    setError('')
    try {
      // Leads dos anúncios (nome, telefone) — encaixe direto no import do disparo (Follow-ups)
      const { data } = await api.get<{ name: string; phone: string; ad_name: string | null }[]>('/marketing/attribution/leads')
      if (data.length === 0) {
        setError('Nenhum lead com telefone veio dos anúncios ainda. Assim que chegarem leads por Click-to-WhatsApp/Lead Ads, eles aparecem aqui.')
        return
      }
      // Cabeçalho nome,telefone (o import casa por nome de coluna); "anuncio" é contexto extra e é ignorado no import
      const header = ['nome', 'telefone', 'anuncio']
      const rows = data.map((l) => [l.name, l.phone, l.ad_name || ''])
      const csv = [header, ...rows]
        .map((r) => r.map((v) => `"${String(v).replace(/"/g, '""')}"`).join(','))
        .join('\n')
      const blob = new Blob([`﻿${csv}`], { type: 'text/csv;charset=utf-8;' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `leads-anuncios-${new Date().toISOString().slice(0, 10)}.csv`
      a.click()
      URL.revokeObjectURL(url)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Erro ao exportar leads.')
    } finally {
      setExporting(false)
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6 flex-wrap gap-3">
        <div>
          <h2 className="text-2xl font-bold text-[#e2e2e8]">Marketing</h2>
          <p className="text-[#555] text-sm mt-1">Gerencie suas campanhas de anúncios.</p>
        </div>
        <div className="flex items-center gap-2">
          {accounts.length > 1 && (
            <div className="flex items-center gap-1.5 bg-[#111118] border border-white/[0.08] rounded-lg px-2.5 py-1.5">
              <Building2 size={13} className="text-[#5a5a6e]" />
              <select
                value={activeAccountId ?? ''}
                onChange={(e) => handleSwitchAccount(e.target.value)}
                disabled={switchingAccount}
                className="bg-transparent text-[#e2e2e8] text-xs outline-none disabled:opacity-50"
              >
                {accounts.map((a) => (
                  <option key={a.id} value={a.id} className="bg-[#111118]">
                    {a.name} ({a.currency})
                  </option>
                ))}
              </select>
            </div>
          )}
          <div className="flex gap-1 bg-[#111118] border border-white/[0.08] rounded-lg p-1">
            {DATE_PRESETS.map((p) => (
              <button
                key={p.value}
                onClick={() => setDatePreset(p.value)}
                className={`px-2.5 py-1 rounded text-xs font-medium transition-colors ${
                  datePreset === p.value ? 'bg-indigo-600 text-white' : 'text-[#5a5a6e] hover:text-[#c0c0d0]'
                }`}
              >
                {p.label}
              </button>
            ))}
          </div>
          <button
            onClick={exportCsv}
            disabled={exporting}
            title="Exportar leads dos anúncios (nome, telefone) para o disparo em Follow-ups"
            className="flex items-center gap-1.5 px-3 py-2 bg-[#111118] border border-white/[0.08] text-[#8a8a9e] hover:text-white text-sm font-medium rounded-lg transition-colors disabled:opacity-40"
          >
            <Download size={14} /> {exporting ? 'Exportando…' : 'Leads CSV'}
          </button>
          <button
            onClick={() => setShowCreate(true)}
            className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-semibold rounded-lg transition-colors"
          >
            + Nova Campanha
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-4 bg-red-900/20 border border-red-500/20 text-red-400 text-sm rounded-lg px-4 py-3">{error}</div>
      )}

      {/* Insights */}
      {insights && (
        <div className="mb-8 space-y-4">
          {/* Métricas de resultado — o que importa pra otimizar */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-gradient-to-br from-indigo-900/40 to-[#111118] rounded-2xl border border-indigo-500/20 p-5 shadow-lg shadow-indigo-900/10 transition-transform hover:-translate-y-1">
              <p className="text-indigo-300 text-xs mb-1 font-medium">Gastos</p>
              <p className="text-2xl font-bold text-white">R$ {insights.spend.toFixed(2)}</p>
            </div>
            <div className="bg-gradient-to-br from-emerald-900/40 to-[#111118] rounded-2xl border border-emerald-500/20 p-5 shadow-lg shadow-emerald-900/10 transition-transform hover:-translate-y-1">
              <p className="text-emerald-300 text-xs mb-1 font-medium">{insights.result_label || 'Resultados'}</p>
              <p className="text-2xl font-bold text-white">{insights.results ? insights.results.toLocaleString() : '—'}</p>
            </div>
            <div className="bg-gradient-to-br from-amber-900/40 to-[#111118] rounded-2xl border border-amber-500/20 p-5 shadow-lg shadow-amber-900/10 transition-transform hover:-translate-y-1">
              <p className="text-amber-300 text-xs mb-1 font-medium">Custo / resultado</p>
              <p className="text-2xl font-bold text-white">{insights.cost_per_result ? `R$ ${insights.cost_per_result.toFixed(2)}` : '—'}</p>
            </div>
            <div className="bg-gradient-to-br from-violet-900/40 to-[#111118] rounded-2xl border border-violet-500/20 p-5 shadow-lg shadow-violet-900/10 transition-transform hover:-translate-y-1">
              <p className="text-violet-300 text-xs mb-1 font-medium">ROAS</p>
              <p className="text-2xl font-bold text-white">{insights.roas ? `${insights.roas.toFixed(2)}×` : '—'}</p>
            </div>
          </div>
          {/* Alcance / engajamento */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {[
              { label: 'Alcance', value: insights.reach ? insights.reach.toLocaleString() : '—' },
              { label: 'Frequência', value: insights.frequency ? insights.frequency.toFixed(2) : '—' },
              { label: 'Impressões', value: insights.impressions.toLocaleString() },
              { label: 'Cliques', value: insights.clicks.toLocaleString() },
              { label: 'CTR', value: `${insights.ctr.toFixed(2)}%` },
              { label: 'CPC', value: insights.cpc ? `R$ ${insights.cpc.toFixed(2)}` : '—' },
              { label: 'CPM', value: `R$ ${insights.cpm.toFixed(2)}` },
              { label: 'Leads de anúncios', value: (attribution?.leads_from_ads ?? 0).toLocaleString() },
            ].map((m) => (
              <div key={m.label} className="bg-[#111118] rounded-xl border border-white/[0.06] p-4">
                <p className="text-[#666] text-xs mb-1">{m.label}</p>
                <p className="text-lg font-bold text-[#e2e2e8]">{m.value}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Leads por anúncio — atribuição real (conversas/formulários, não cliques) */}
      {attribution && attribution.by_ad.length > 0 && (
        <div className="bg-[#111118] rounded-xl border border-white/[0.06] p-5 mb-8 max-w-3xl">
          <h3 className="text-sm font-semibold text-[#e2e2e8] mb-1">📣 Leads por anúncio</h3>
          <p className="text-[#555] text-xs mb-4">
            Leads que chegaram por Click-to-WhatsApp, Direct ou formulário — atribuídos ao anúncio de origem.
          </p>
          <div className="space-y-2">
            {attribution.by_ad.map((a) => (
              <div key={a.ad_id} className="flex items-center gap-3">
                <div className="flex-1 min-w-0">
                  <p className="text-[13px] text-[#c0c0d0] truncate">{a.ad_name || `Anúncio ${a.ad_id}`}</p>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <div className="w-32 h-1.5 rounded-full bg-white/[0.05] overflow-hidden">
                    <div
                      className="h-full bg-violet-500 rounded-full"
                      style={{ width: `${Math.max(8, (a.leads / attribution.by_ad[0].leads) * 100)}%` }}
                    />
                  </div>
                  <span className="text-[13px] font-semibold text-violet-300 w-8 text-right">{a.leads}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Campanhas */}
      <h3 className="text-xl font-bold text-[#e2e2e8] mb-5">Suas Campanhas</h3>
      {loading ? (
        <div className="flex justify-center py-10">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-500"></div>
        </div>
      ) : campaigns.length === 0 ? (
        <div className="bg-[#111118]/80 backdrop-blur-md rounded-2xl border border-white/[0.06] p-16 text-center shadow-xl">
          <div className="w-16 h-16 bg-indigo-500/10 rounded-full flex items-center justify-center mx-auto mb-4">
            <Building2 size={32} className="text-indigo-400" />
          </div>
          <h3 className="text-lg font-bold text-white mb-2">Nenhuma campanha encontrada</h3>
          <p className="text-[#888] text-sm">Crie sua primeira campanha para começar a escalar seus resultados.</p>
        </div>
      ) : (
        <div className="grid gap-4 max-w-4xl">
          {campaigns.map((c) => {
            const busy = busyCampaignId === c.id
            return (
              <div key={c.id} className="bg-[#111118]/80 backdrop-blur-sm rounded-2xl border border-white/[0.06] p-5 flex items-center gap-4 hover:bg-white/[0.02] hover:border-white/[0.1] transition-all group">
                <Link to={`/app/marketing/${c.id}`} className="flex-1 min-w-0 no-underline">
                  <div className="flex items-center gap-3">
                    <h4 className="text-white font-semibold text-base group-hover:text-indigo-400 transition-colors">
                      {c.name}
                    </h4>
                    <span className={`text-[11px] font-bold px-2.5 py-1 rounded-full shrink-0 ${
                      c.status === 'ACTIVE' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-white/[0.05] text-[#888] border border-white/[0.05]'
                    }`}>
                      {c.status === 'ACTIVE' ? 'Ativa' : c.status === 'PAUSED' ? 'Pausada' : c.status}
                    </span>
                  </div>
                  <div className="flex items-center gap-4 mt-2">
                    <p className="text-[#888] text-sm flex items-center gap-1.5">
                      <span className="w-1.5 h-1.5 rounded-full bg-indigo-500"></span>
                      {objectiveLabels[c.objective] || c.objective}
                    </p>
                    {c.daily_budget && (
                      <p className="text-[#888] text-sm flex items-center gap-1.5">
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
                        R$ {(parseInt(c.daily_budget) / 100).toFixed(2)}/dia
                      </p>
                    )}
                  </div>
                </Link>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => toggleStatus(c)}
                    disabled={busy}
                    title={c.status === 'ACTIVE' ? 'Pausar' : 'Ativar'}
                    className="w-10 h-10 shrink-0 rounded-xl bg-white/[0.04] hover:bg-indigo-500/20 text-[#8a8a9e] hover:text-indigo-400 flex items-center justify-center transition-colors disabled:opacity-40"
                  >
                    {c.status === 'ACTIVE' ? <Pause size={18} fill="currentColor" /> : <Play size={18} fill="currentColor" className="ml-1" />}
                  </button>
                  <button
                    onClick={() => handleDuplicate(c)}
                    disabled={busy}
                    title="Duplicar (cria uma cópia pausada)"
                    className="w-10 h-10 shrink-0 rounded-xl bg-white/[0.04] hover:bg-emerald-500/20 text-[#8a8a9e] hover:text-emerald-400 flex items-center justify-center transition-colors disabled:opacity-40"
                  >
                    <Copy size={17} />
                  </button>
                  <button
                    onClick={() => handleDelete(c)}
                    disabled={busy}
                    title="Excluir"
                    className="w-10 h-10 shrink-0 rounded-xl bg-white/[0.04] hover:bg-red-500/20 text-[#8a8a9e] hover:text-red-400 flex items-center justify-center transition-colors disabled:opacity-40"
                  >
                    <Trash2 size={18} />
                  </button>
                  <Link to={`/app/marketing/${c.id}`} className="w-10 h-10 shrink-0 rounded-xl bg-white/[0.04] hover:bg-white/[0.1] text-[#8a8a9e] hover:text-white flex items-center justify-center transition-colors">
                     <ChevronRight size={20} />
                  </Link>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* Modal criar campanha */}
      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm px-4">
          <div className="bg-[#111118] border border-white/[0.08] rounded-2xl p-8 w-full max-w-md">
            <h3 className="text-lg font-bold text-white mb-6">Nova Campanha</h3>
            <form onSubmit={handleCreate} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-[#666] mb-1.5">Nome da campanha</label>
                <input
                  type="text"
                  value={campName}
                  onChange={(e) => setCampName(e.target.value)}
                  placeholder="Ex: Captação Leads - Maio"
                  className="w-full px-4 py-2.5 bg-[#0a0a0f] border border-white/[0.08] text-[#e2e2e8] text-sm rounded-lg focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500 focus:outline-none placeholder-[#333]"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-[#666] mb-1.5">Objetivo</label>
                <select
                  value={campObjective}
                  onChange={(e) => setCampObjective(e.target.value)}
                  className="w-full px-4 py-2.5 bg-[#0a0a0f] border border-white/[0.08] text-[#e2e2e8] text-sm rounded-lg focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500 focus:outline-none"
                >
                  {Object.entries(objectiveLabels).map(([k, v]) => (
                    <option key={k} value={k}>{v}</option>
                  ))}
                </select>
              </div>
              <div className="flex gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setShowCreate(false)}
                  className="flex-1 py-2.5 border border-white/[0.08] text-[#666] hover:text-white text-sm font-medium rounded-lg transition-colors"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  disabled={creating || !campName.trim()}
                  className="flex-1 py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm font-semibold rounded-lg transition-colors"
                >
                  {creating ? 'Criando...' : 'Criar Campanha'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
