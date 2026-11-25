import { useState, useEffect, useCallback, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { Pause, Play, Trash2, ChevronRight, Building2, Copy, Download, ArrowUpDown, AlertTriangle } from 'lucide-react'
import api, { apiError } from '../services/api'
import { useI18n } from '../i18n'
import HelpLink from '../components/HelpLink'
import FacebookPagePanel from '../components/FacebookPagePanel'
import AdsSyncPanel, { type SyncedOverview } from '../components/AdsSyncPanel'
import {
  DeliveryBadge, Delta, MetricHelp, MetricLabel, PeriodPicker, WarningBanner, accountWarning, resultLabel, type MetricKey,
} from '../components/AdsUi'
import { makeFormat } from '../utils/format'
import { Diagnostics, Funnel } from '../components/AdsInsights'

interface Campaign {
  id: string
  name: string
  status: string
  effective_status: string | null
  issues: string[]
  objective: string
  daily_budget: string | null
  lifetime_budget: string | null
}

export interface Insights {
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

interface Compared { current: Insights; previous: Insights }

interface Overview {
  period: { days: number; since: string; until: string; previous_since: string; previous_until: string }
  account: { account_status: number | null; disable_reason: number | null; currency: string | null }
  totals: Compared
  campaigns: Record<string, Compared>
  problems: { id: string; name: string | null; campaign_id: string | null; effective_status: string; reasons: string[] }[]
}

interface AdAccount {
  id: string
  name: string
  account_status: number
  currency: string
  business_name: string | null
  relationship?: 'owned' | 'client' | null
}

interface Business {
  id: string
  name: string
  ad_accounts: AdAccount[]
}

interface AttributionSummary {
  total_leads: number
  leads_from_ads: number
  by_ad: { ad_id: string; ad_name: string | null; leads: number }[]
}

type SortKey = 'name' | 'spend' | 'results' | 'cpr' | 'ctr'

const EMPTY: Insights = {
  spend: 0, impressions: 0, reach: 0, frequency: 0, clicks: 0, ctr: 0, cpc: 0, cpm: 0,
  results: 0, result_label: '', cost_per_result: 0, purchase_value: 0, roas: 0,
}

export default function Marketing() {
  const { t, locale } = useI18n()
  const [specialCategory, setSpecialCategory] = useState('NONE')
  const specialCategories: Record<string, string> = {
    NONE: t('Nenhuma', 'None'),
    FINANCIAL_PRODUCTS_SERVICES: t('Produtos e serviços financeiros (crédito)', 'Financial products and services (credit)'),
    EMPLOYMENT: t('Emprego', 'Employment'),
    HOUSING: t('Imóveis / moradia', 'Housing'),
    ISSUES_ELECTIONS_POLITICS: t('Temas sociais, eleições ou política', 'Social issues, elections or politics'),
    ONLINE_GAMBLING_AND_GAMING: t('Jogos de azar online', 'Online gambling and gaming'),
  }
  const [campaigns, setCampaigns] = useState<Campaign[]>([])
  const [overview, setOverview] = useState<Overview | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const [accounts, setAccounts] = useState<AdAccount[]>([])
  const [businesses, setBusinesses] = useState<Business[]>([])
  const [activeAccountId, setActiveAccountId] = useState<string | null>(null)
  const [switchingAccount, setSwitchingAccount] = useState(false)
  const [attribution, setAttribution] = useState<AttributionSummary | null>(null)
  const [synced, setSynced] = useState<SyncedOverview | null>(null)

  const [days, setDays] = useState(30)
  const [sort, setSort] = useState<{ key: SortKey; desc: boolean }>({ key: 'spend', desc: true })
  const [busyCampaignId, setBusyCampaignId] = useState<string | null>(null)
  const [exporting, setExporting] = useState(false)

  const [showCreate, setShowCreate] = useState(false)
  const [accountsLoaded, setAccountsLoaded] = useState(false)
  const noAdAccount = accountsLoaded && accounts.length === 0 && businesses.length === 0
  const [campName, setCampName] = useState('')
  const [campObjective, setCampObjective] = useState('OUTCOME_LEADS')
  const [creating, setCreating] = useState(false)

  const objectiveLabels: Record<string, string> = {
    OUTCOME_LEADS: t('Geração de Leads', 'Leads'),
    OUTCOME_SALES: t('Vendas', 'Sales'),
    OUTCOME_AWARENESS: t('Reconhecimento', 'Awareness'),
    OUTCOME_ENGAGEMENT: t('Engajamento', 'Engagement'),
    OUTCOME_TRAFFIC: t('Tráfego', 'Traffic'),
  }

  const currency = overview?.account.currency || accounts.find((a) => a.id === activeAccountId)?.currency || 'BRL'
  const fmt = useMemo(() => makeFormat(locale, currency), [locale, currency])

  const loadAccounts = useCallback(async () => {
    try {
      const { data } = await api.get<AdAccount[]>('/marketing/ad-accounts')
      setAccounts(data)
      if (data.length > 0) setActiveAccountId((prev) => prev ?? data[0].id)
    } catch { /* sem conexão de anúncios ainda — o estado vazio cobre isso */ }
    try {
      const { data } = await api.get<Business[]>('/marketing/businesses')
      setBusinesses(data.filter((b) => b.ad_accounts.length > 0))
    } catch { /* portfólios são opcionais */ }
    setAccountsLoaded(true)
  }, [])

  const loadData = useCallback(async (d: number) => {
    setLoading(true)
    setError('')
    api.get<SyncedOverview>('/marketing/synced-overview').then(({ data }) => setSynced(data)).catch(() => setSynced(null))
    try {
      const [campRes, ovRes] = await Promise.all([
        api.get<Campaign[]>('/marketing/campaigns'),
        api.get<Overview>('/marketing/overview', { params: { days: d } }),
      ])
      setCampaigns(campRes.data)
      setOverview(ovRes.data)
    } catch {
      setError(t('Erro ao carregar dados. Conecte uma conta de anúncios primeiro.', 'Failed to load data. Connect an ad account first.'))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadAccounts() }, [loadAccounts])
  useEffect(() => { loadData(days) }, [loadData, days])
  useEffect(() => {
    api.get<AttributionSummary>('/marketing/attribution').then(({ data }) => setAttribution(data)).catch(() => {})
  }, [])

  async function handleSwitchAccount(id: string) {
    if (id === activeAccountId || switchingAccount) return
    setSwitchingAccount(true)
    try {
      await api.put('/marketing/ad-account', { ad_account_id: id })
      setActiveAccountId(id)
      await loadData(days)
    } catch {
      setError(t('Erro ao trocar de conta de anúncios.', 'Failed to switch ad account.'))
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
        name: campName.trim(), objective: campObjective, status: 'PAUSED', special_ad_categories: [specialCategory],
      })
      setShowCreate(false)
      setCampName('')
      await loadData(days)
    } catch (err: any) {
      setError(apiError(err, t('Erro ao criar campanha.', 'Failed to create campaign.')))
    } finally {
      setCreating(false)
    }
  }

  async function toggleStatus(c: Campaign) {
    setBusyCampaignId(c.id)
    try {
      await api.patch(`/marketing/campaigns/${c.id}`, { status: c.status === 'ACTIVE' ? 'PAUSED' : 'ACTIVE' })
      await loadData(days)
    } catch {
      setError(t('Erro ao atualizar status da campanha.', 'Failed to update campaign status.'))
    } finally {
      setBusyCampaignId(null)
    }
  }

  async function handleDelete(c: Campaign) {
    if (!confirm(t(`Excluir a campanha "${c.name}"? Essa ação não pode ser desfeita.`, `Delete the campaign "${c.name}"? This cannot be undone.`))) return
    setBusyCampaignId(c.id)
    try {
      await api.delete(`/marketing/campaigns/${c.id}`)
      setCampaigns((prev) => prev.filter((x) => x.id !== c.id))
    } catch {
      setError(t('Erro ao excluir campanha.', 'Failed to delete campaign.'))
    } finally {
      setBusyCampaignId(null)
    }
  }

  async function handleDuplicate(c: Campaign) {
    setBusyCampaignId(c.id)
    try {
      await api.post(`/marketing/campaigns/${c.id}/copy`)
      await loadData(days)
    } catch (err: any) {
      setError(apiError(err, t('Erro ao duplicar campanha.', 'Failed to duplicate campaign.')))
    } finally {
      setBusyCampaignId(null)
    }
  }

  async function exportCsv() {
    setExporting(true)
    setError('')
    try {
      const { data } = await api.get<{ name: string; phone: string; ad_name: string | null }[]>('/marketing/attribution/leads')
      if (data.length === 0) {
        setError(t('Nenhum lead com telefone veio dos anúncios ainda. Assim que chegarem leads por Click-to-WhatsApp/Lead Ads, eles aparecem aqui.', 'No leads with a phone number came from ads yet. Leads from Click-to-WhatsApp/Lead Ads will show up here.'))
        return
      }
      const header = ['nome', 'telefone', 'anuncio']
      const rows = data.map((l) => [l.name, l.phone, l.ad_name || ''])
      const csv = [header, ...rows].map((r) => r.map((v) => `"${String(v).replace(/"/g, '""')}"`).join(',')).join('\n')
      const blob = new Blob([`﻿${csv}`], { type: 'text/csv;charset=utf-8;' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `leads-anuncios-${new Date().toISOString().slice(0, 10)}.csv`
      a.click()
      URL.revokeObjectURL(url)
    } catch (err: any) {
      setError(apiError(err, t('Erro ao exportar leads.', 'Failed to export leads.')))
    } finally {
      setExporting(false)
    }
  }

  const perf = (id: string): Compared => overview?.campaigns[id] ?? { current: EMPTY, previous: EMPTY }
  const sorted = useMemo(() => {
    const value = (c: Campaign): number | string => {
      const cur = perf(c.id).current
      switch (sort.key) {
        case 'name': return c.name.toLowerCase()
        case 'spend': return cur.spend
        case 'results': return cur.results
        case 'cpr': return cur.cost_per_result || Number.POSITIVE_INFINITY
        case 'ctr': return cur.ctr
      }
    }
    return [...campaigns].sort((a, b) => {
      const va = value(a), vb = value(b)
      const cmp = va < vb ? -1 : va > vb ? 1 : 0
      return sort.desc ? -cmp : cmp
    })
  }, [campaigns, overview, sort])

  const campaignName = (id: string | null) => campaigns.find((c) => c.id === id)?.name
  const problemCount = (id: string) => overview?.problems.filter((p) => p.campaign_id === id).length ?? 0
  const ProblemNote = ({ id }: { id: string }) => {
    const n = problemCount(id)
    if (!n) return null
    return (
      <span className="inline-flex items-center gap-1 text-[11px] font-medium text-red-300">
        <AlertTriangle size={11} />{t(`${n} anúncio(s) com problema`, `${n} ad(s) with issues`)}
      </span>
    )
  }
  const warning = accountWarning(t, overview?.account.account_status, overview?.account.disable_reason)
  const cur = overview?.totals.current
  const prev = overview?.totals.previous

  const headerCell = (key: SortKey, label: string, metric?: MetricKey, right = true) => (
    <th className={`pb-2 px-2 font-medium ${right ? 'text-right' : 'text-left'}`}>
      <span className="inline-flex items-center gap-1">
        <button onClick={() => setSort((s) => ({ key, desc: s.key === key ? !s.desc : key !== 'name' && key !== 'cpr' }))}
          className={`inline-flex items-center gap-1 uppercase hover:text-ink-2 ${sort.key === key ? 'text-ink-2' : ''}`}>
          {label}<ArrowUpDown size={10} />
        </button>
        {metric && <MetricHelp label={label} metric={metric} />}
      </span>
    </th>
  )

  return (
    <div>
      <div className="flex items-start justify-between mb-5 flex-wrap gap-3">
        <div>
          <h2 className="text-2xl font-bold text-ink">{t('Anúncios', 'Ads')}</h2>
          <p className="text-ink-4 text-sm mt-1">{t('Veja o que está dando resultado e o que precisa de atenção.', 'See what is working and what needs attention.')}</p>
          <HelpLink section="campanhas" className="mt-1" />
        </div>
        <div className="flex flex-wrap items-center gap-2 max-w-full">
          {(accounts.length > 0 || businesses.length > 0) && (
            <div className="flex items-center gap-1.5 max-w-full bg-card border border-white/[0.08] rounded-lg px-2.5 py-1.5" title={t('Conta de anúncios', 'Ad account')}>
              <Building2 size={13} className="text-ink-4" />
              <select value={activeAccountId ?? ''} onChange={(e) => handleSwitchAccount(e.target.value)} disabled={switchingAccount}
                className="bg-transparent text-ink text-xs outline-none disabled:opacity-50 max-w-[260px]">
                {businesses.map((b) => (
                  <optgroup key={b.id} label={`${t('Portfólio', 'Business')}: ${b.name}`} className="bg-card">
                    {b.ad_accounts.map((a) => (
                      <option key={`${b.id}-${a.id}`} value={a.id} className="bg-card">
                        {a.name} ({a.currency}){a.relationship === 'client' ? ` · ${t('cliente', 'client')}` : ''}
                      </option>
                    ))}
                  </optgroup>
                ))}
                {(() => {
                  const inBusiness = new Set(businesses.flatMap((b) => b.ad_accounts.map((a) => a.id)))
                  const others = accounts.filter((a) => !inBusiness.has(a.id))
                  if (others.length === 0) return null
                  const options = others.map((a) => <option key={a.id} value={a.id} className="bg-card">{a.name} ({a.currency})</option>)
                  return businesses.length > 0 ? <optgroup label={t('Outras contas', 'Other ad accounts')} className="bg-card">{options}</optgroup> : options
                })()}
              </select>
            </div>
          )}
          <PeriodPicker value={days} onChange={setDays} />
          <button onClick={exportCsv} disabled={exporting} title={t('Exportar leads dos anúncios (nome, telefone)', 'Export leads from ads (name, phone)')}
            className="flex items-center gap-1.5 px-3 py-2 bg-card border border-white/[0.08] text-ink-3 hover:text-white text-sm font-medium rounded-lg transition-colors disabled:opacity-40">
            <Download size={14} /> {exporting ? t('Exportando…', 'Exporting…') : t('Leads CSV', 'Leads CSV')}
          </button>
          {noAdAccount ? (
            <Link to="/app/conexao" className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-semibold rounded-lg transition-colors">
              {t('Conectar conta de anúncios', 'Connect ad account')}
            </Link>
          ) : (
            <button onClick={() => setShowCreate(true)} className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-semibold rounded-lg transition-colors">
              + {t('Nova Campanha', 'New Campaign')}
            </button>
          )}
        </div>
      </div>

      {error && !noAdAccount && (
        <div className="mb-4 bg-red-900/20 border border-red-500/20 text-red-400 text-sm rounded-lg px-4 py-3">{error}</div>
      )}

      {warning && <WarningBanner tone={warning.tone}>{warning.text}</WarningBanner>}

      {overview && overview.problems.length > 0 && (
        <div className="bg-red-900/10 border border-red-500/20 rounded-xl p-4 mb-5">
          <p className="flex items-center gap-2 text-sm font-semibold text-red-200 mb-2">
            <AlertTriangle size={15} />
            {t(`${overview.problems.length} anúncio(s) precisam de atenção`, `${overview.problems.length} ad(s) need attention`)}
          </p>
          <div className="space-y-1.5">
            {overview.problems.map((p) => (
              <div key={p.id} className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
                <DeliveryBadge status={p.effective_status} effective={p.effective_status} reasons={p.reasons} small />
                <span className="text-ink-2 font-medium">{p.name || p.id}</span>
                {p.campaign_id && (
                  <Link to={`/app/marketing/${p.campaign_id}`} className="text-ink-4 hover:text-indigo-300">
                    {campaignName(p.campaign_id) || t('Abrir campanha', 'Open campaign')} →
                  </Link>
                )}
                {p.reasons[0] && <span className="text-ink-4 basis-full sm:basis-auto">{p.reasons[0]}</span>}
              </div>
            ))}
          </div>
        </div>
      )}

      {!noAdAccount && overview && <Diagnostics days={days} fmt={fmt} />}

      {cur && prev && (
        <div className="mb-6 space-y-3">
          {overview && (
            <p className="text-[11px] text-ink-5">
              {t(`Últimos ${overview.period.days} dias, comparados com os ${overview.period.days} dias anteriores.`, `Last ${overview.period.days} days, compared with the previous ${overview.period.days} days.`)}
            </p>
          )}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {([
              { metric: 'spend', label: t('Gasto', 'Spend'), value: fmt.money(cur.spend), c: cur.spend, p: prev.spend, good: 'none', tone: 'from-indigo-900/40 border-indigo-500/20 text-indigo-300' },
              { metric: 'results', label: resultLabel(t, cur.result_label), value: cur.results ? fmt.int(cur.results) : '—', c: cur.results, p: prev.results, good: 'up', tone: 'from-emerald-900/40 border-emerald-500/20 text-emerald-300' },
              { metric: 'cost_per_result', label: t('Custo por resultado', 'Cost per result'), value: cur.cost_per_result ? fmt.money(cur.cost_per_result) : '—', c: cur.cost_per_result, p: prev.cost_per_result, good: 'down', tone: 'from-amber-900/40 border-amber-500/20 text-amber-300' },
              { metric: 'roas', label: 'ROAS', value: cur.roas ? `${fmt.dec(cur.roas)}×` : '—', c: cur.roas, p: prev.roas, good: 'up', tone: 'from-violet-900/40 border-violet-500/20 text-violet-300' },
            ] as const).map((m) => (
              <div key={m.metric} className={`bg-gradient-to-br ${m.tone.split(' ').slice(0, 2).join(' ')} to-card rounded-2xl border p-4`}>
                <MetricLabel label={m.label} metric={m.metric} className={`text-xs font-medium ${m.tone.split(' ')[2]}`} />
                <p className="text-2xl font-bold text-white mt-1">{m.value}</p>
                <Delta current={m.c} previous={m.p} good={m.good} />
              </div>
            ))}
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-2">
            {([
              ['reach', t('Alcance', 'Reach'), fmt.int(cur.reach), cur.reach, prev.reach, 'up'],
              ['frequency', t('Frequência', 'Frequency'), cur.frequency ? fmt.dec(cur.frequency) : '—', cur.frequency, prev.frequency, 'none'],
              ['impressions', t('Impressões', 'Impressions'), fmt.int(cur.impressions), cur.impressions, prev.impressions, 'up'],
              ['clicks', t('Cliques', 'Clicks'), fmt.int(cur.clicks), cur.clicks, prev.clicks, 'up'],
              ['ctr', 'CTR', fmt.pct(cur.ctr), cur.ctr, prev.ctr, 'up'],
              ['cpc', 'CPC', cur.cpc ? fmt.money(cur.cpc) : '—', cur.cpc, prev.cpc, 'down'],
              ['cpm', 'CPM', fmt.money(cur.cpm), cur.cpm, prev.cpm, 'down'],
              ['leads_from_ads', t('Leads de anúncios', 'Leads from ads'), fmt.int(attribution?.leads_from_ads ?? 0), 0, 0, 'none'],
            ] as [MetricKey, string, string, number, number, 'up' | 'down' | 'none'][]).map(([metric, label, value, c, p, good]) => (
              <div key={metric} className="bg-card rounded-xl border border-white/[0.06] p-3">
                <MetricLabel label={label} metric={metric} className="text-ink-4 text-[11px]" />
                <p className="text-base font-bold text-ink mt-0.5">{value}</p>
                {metric !== 'leads_from_ads' && <Delta current={c} previous={p} good={good} />}
              </div>
            ))}
          </div>
          {cur.frequency >= 3 && days <= 14 && (
            <p className="text-[11px] text-amber-300">
              {t('Frequência alta: o mesmo público está vendo os anúncios muitas vezes. Troque o criativo ou amplie o público.', 'High frequency: the same people are seeing the ads many times. Change the creative or widen the audience.')}
            </p>
          )}
        </div>
      )}

      {/* Campanhas */}
      <h3 className="text-lg font-bold text-ink mb-3">{t('Suas Campanhas', 'Your Campaigns')}</h3>
      {loading ? (
        <div className="flex justify-center py-10">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-500"></div>
        </div>
      ) : campaigns.length === 0 ? (
        <div className="bg-card/80 rounded-2xl border border-white/[0.06] p-12 text-center mb-8">
          <div className="w-14 h-14 bg-indigo-500/10 rounded-full flex items-center justify-center mx-auto mb-4">
            <Building2 size={28} className="text-indigo-400" />
          </div>
          <h3 className="text-lg font-bold text-white mb-2">
            {noAdAccount ? t('Conecte sua conta de anúncios', 'Connect your ad account') : t('Nenhuma campanha encontrada', 'No campaigns found')}
          </h3>
          <p className="text-ink-3 text-sm">
            {noAdAccount
              ? t('Com a conta conectada você vê investimento, resultados e cria campanhas por aqui.', 'Once connected you can see spend and results and create campaigns here.')
              : t('Crie sua primeira campanha para começar.', 'Create your first campaign to get started.')}
          </p>
        </div>
      ) : (
        <>
          {/* Computador: tabela ordenável */}
          <div className="max-md:hidden bg-card rounded-2xl border border-white/[0.06] p-4 mb-8 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-ink-4 text-[11px] uppercase tracking-wide">
                  {headerCell('name', t('Campanha', 'Campaign'), undefined, false)}
                  {headerCell('spend', t('Gasto', 'Spend'), 'spend')}
                  {headerCell('results', t('Resultados', 'Results'), 'results')}
                  {headerCell('cpr', t('Custo/resultado', 'Cost/result'), 'cost_per_result')}
                  {headerCell('ctr', 'CTR', 'ctr')}
                  <th className="pb-2" />
                </tr>
              </thead>
              <tbody>
                {sorted.map((c) => {
                  const { current: pc, previous: pp } = perf(c.id)
                  const busy = busyCampaignId === c.id
                  return (
                    <tr key={c.id} className="border-t border-white/[0.06] align-middle hover:bg-white/[0.02]">
                      <td className="py-3 px-2 min-w-[240px]">
                        <Link to={`/app/marketing/${c.id}`} className="text-white font-semibold hover:text-indigo-300 no-underline">{c.name}</Link>
                        <div className="flex flex-wrap items-center gap-2 mt-1">
                          <DeliveryBadge status={c.status} effective={c.effective_status} reasons={c.issues} small />
                          <ProblemNote id={c.id} />
                          <span className="text-[11px] text-ink-4">
                            {objectiveLabels[c.objective] || c.objective}
                            {c.daily_budget && ` · ${fmt.money(parseInt(c.daily_budget) / 100)}${t('/dia', '/day')}`}
                            {synced?.campaign_counts[c.id] && ` · ${synced.campaign_counts[c.id].ad_sets} ${t('conjuntos', 'ad sets')} · ${synced.campaign_counts[c.id].ads} ${t('anúncios', 'ads')}`}
                          </span>
                        </div>
                      </td>
                      <td className="py-3 px-2 text-right whitespace-nowrap">
                        <p className="text-ink">{fmt.money(pc.spend)}</p><Delta current={pc.spend} previous={pp.spend} good="none" />
                      </td>
                      <td className="py-3 px-2 text-right whitespace-nowrap">
                        <p className="text-ink">{pc.results ? fmt.int(pc.results) : '—'}</p>
                        <p className="text-[10px] text-ink-5">{pc.results ? resultLabel(t, pc.result_label) : ''}</p>
                      </td>
                      <td className="py-3 px-2 text-right whitespace-nowrap">
                        <p className="text-ink">{pc.cost_per_result ? fmt.money(pc.cost_per_result) : '—'}</p>
                        {pc.cost_per_result > 0 && <Delta current={pc.cost_per_result} previous={pp.cost_per_result} good="down" />}
                      </td>
                      <td className="py-3 px-2 text-right whitespace-nowrap text-ink">{pc.impressions ? fmt.pct(pc.ctr) : '—'}</td>
                      <td className="py-3 pl-2">
                        <CampaignActions c={c} busy={busy} onToggle={toggleStatus} onDuplicate={handleDuplicate} onDelete={handleDelete} />
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          {/* Celular: cartões */}
          <div className="md:hidden space-y-3 mb-8">
            {sorted.map((c) => {
              const { current: pc, previous: pp } = perf(c.id)
              return (
                <div key={c.id} className="bg-card rounded-2xl border border-white/[0.06] p-4">
                  <Link to={`/app/marketing/${c.id}`} className="text-white font-semibold no-underline">{c.name}</Link>
                  <div className="flex flex-wrap items-center gap-2 mt-1 mb-3">
                    <DeliveryBadge status={c.status} effective={c.effective_status} reasons={c.issues} small />
                    <ProblemNote id={c.id} />
                    <span className="text-[11px] text-ink-4">{objectiveLabels[c.objective] || c.objective}</span>
                  </div>
                  <div className="grid grid-cols-3 gap-2 mb-3">
                    <div><p className="text-[10px] text-ink-4">{t('Gasto', 'Spend')}</p><p className="text-sm text-ink">{fmt.money(pc.spend)}</p></div>
                    <div><p className="text-[10px] text-ink-4">{resultLabel(t, pc.result_label)}</p><p className="text-sm text-ink">{pc.results ? fmt.int(pc.results) : '—'}</p></div>
                    <div>
                      <p className="text-[10px] text-ink-4">{t('Custo/resultado', 'Cost/result')}</p>
                      <p className="text-sm text-ink">{pc.cost_per_result ? fmt.money(pc.cost_per_result) : '—'}</p>
                      {pc.cost_per_result > 0 && <Delta current={pc.cost_per_result} previous={pp.cost_per_result} good="down" />}
                    </div>
                  </div>
                  <CampaignActions c={c} busy={busyCampaignId === c.id} onToggle={toggleStatus} onDuplicate={handleDuplicate} onDelete={handleDelete} />
                </div>
              )
            })}
          </div>
        </>
      )}

      {!noAdAccount && overview && <Funnel days={days} fmt={fmt} />}

      {synced && <AdsSyncPanel overview={synced} />}

      <FacebookPagePanel />

      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center max-lg:[align-items:safe_center] max-lg:overflow-y-auto max-lg:py-4 bg-black/70 backdrop-blur-sm px-4">
          <div className="bg-card border border-white/[0.08] rounded-2xl p-8 w-full max-w-md">
            <h3 className="text-lg font-bold text-white mb-6">{t('Nova Campanha', 'New Campaign')}</h3>
            <form onSubmit={handleCreate} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-ink-4 mb-1.5">{t('Nome da campanha', 'Campaign name')}</label>
                <input type="text" value={campName} onChange={(e) => setCampName(e.target.value)} placeholder={t('Ex: Captação Leads - Maio', 'E.g. Lead Generation - May')}
                  className="w-full px-4 py-2.5 bg-field border border-white/[0.08] text-ink text-sm rounded-lg focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500 focus:outline-none placeholder-ink-5" />
              </div>
              <div>
                <label className="block text-xs font-medium text-ink-4 mb-1.5">{t('Objetivo', 'Objective')}</label>
                <select value={campObjective} onChange={(e) => setCampObjective(e.target.value)}
                  className="w-full px-4 py-2.5 bg-field border border-white/[0.08] text-ink text-sm rounded-lg focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500 focus:outline-none">
                  {Object.entries(objectiveLabels).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-ink-4 mb-1.5">{t('Categoria especial de anúncio', 'Special ad category')}</label>
                <select value={specialCategory} onChange={(e) => setSpecialCategory(e.target.value)}
                  className="w-full px-4 py-2.5 bg-field border border-white/[0.08] text-ink text-sm rounded-lg focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500 focus:outline-none">
                  {Object.entries(specialCategories).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                </select>
                <p className="text-[10px] text-ink-4 mt-1">
                  {t('A Meta exige declarar anúncios de crédito, emprego, moradia, política ou jogos. A campanha é criada pausada.', 'Meta requires declaring ads about credit, employment, housing, politics or gambling. The campaign is created paused.')}
                </p>
              </div>
              <div className="flex gap-3 pt-2">
                <button type="button" onClick={() => setShowCreate(false)} className="flex-1 py-2.5 border border-white/[0.08] text-ink-4 hover:text-white text-sm font-medium rounded-lg transition-colors">
                  {t('Cancelar', 'Cancel')}
                </button>
                <button type="submit" disabled={creating || !campName.trim()} className="flex-1 py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm font-semibold rounded-lg transition-colors">
                  {creating ? t('Criando...', 'Creating...') : t('Criar Campanha', 'Create Campaign')}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}

function CampaignActions({ c, busy, onToggle, onDuplicate, onDelete }: {
  c: Campaign
  busy: boolean
  onToggle: (c: Campaign) => void
  onDuplicate: (c: Campaign) => void
  onDelete: (c: Campaign) => void
}) {
  const { t } = useI18n()
  const btn = 'w-9 h-9 shrink-0 rounded-xl bg-white/[0.04] text-ink-3 flex items-center justify-center transition-colors disabled:opacity-40'
  return (
    <div className="flex items-center justify-end gap-1.5">
      <button onClick={() => onToggle(c)} disabled={busy} title={c.status === 'ACTIVE' ? t('Pausar', 'Pause') : t('Ativar', 'Activate')}
        className={`${btn} hover:bg-indigo-500/20 hover:text-indigo-400`}>
        {c.status === 'ACTIVE' ? <Pause size={15} fill="currentColor" /> : <Play size={15} fill="currentColor" className="ml-0.5" />}
      </button>
      <button onClick={() => onDuplicate(c)} disabled={busy} title={t('Duplicar (cria uma cópia pausada)', 'Duplicate (creates a paused copy)')}
        className={`${btn} hover:bg-emerald-500/20 hover:text-emerald-400`}>
        <Copy size={14} />
      </button>
      <button onClick={() => onDelete(c)} disabled={busy} title={t('Excluir', 'Delete')} className={`${btn} hover:bg-red-500/20 hover:text-red-400`}>
        <Trash2 size={15} />
      </button>
      <Link to={`/app/marketing/${c.id}`} title={t('Abrir', 'Open')} className={`${btn} hover:bg-white/[0.1] hover:text-white`}>
        <ChevronRight size={18} />
      </Link>
    </div>
  )
}
