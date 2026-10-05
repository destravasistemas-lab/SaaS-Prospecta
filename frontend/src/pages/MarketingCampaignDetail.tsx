import { useState, useEffect, useCallback, useRef } from 'react'
import { useParams, Link } from 'react-router-dom'
import {
  ArrowLeft, Plus, Pause, Play, Trash2, ChevronDown, ChevronRight,
  X, Image as ImageIcon, Video, GalleryHorizontal, Search, Copy, Camera,
} from 'lucide-react'
import api from '../services/api'

interface Campaign {
  id: string
  name: string
  status: string
  objective: string
  daily_budget: string | null
}

interface AdSet {
  id: string
  name: string
  status: string
  daily_budget: string | null
  bid_amount: string | null
  billing_event: string | null
  optimization_goal: string | null
}

interface Ad {
  id: string
  name: string
  status: string
  creative_id: string | null
  creative_name: string | null
  thumbnail_url: string | null
}

interface InsightsPoint {
  date: string
  spend: number
  impressions: number
  clicks: number
}

interface EntityInsights {
  id: string
  name: string | null
  spend: number
  impressions: number
  reach: number
  clicks: number
  ctr: number
  results: number
  result_label: string
  cost_per_result: number
}

interface BreakdownRow {
  key: string
  spend: number
  impressions: number
  reach: number
  clicks: number
  ctr: number
  results: number
}

const BREAKDOWN_DIMS: { value: string; label: string }[] = [
  { value: 'age', label: 'Idade' },
  { value: 'gender', label: 'Gênero' },
  { value: 'publisher_platform', label: 'Plataforma' },
  { value: 'impression_device', label: 'Dispositivo' },
  { value: 'region', label: 'Região' },
]

interface TargetingOption {
  id: string
  name: string
  audience_size?: number | null
  type?: string | null
}

type CreativeKind = 'image' | 'video' | 'carousel' | 'post'

interface IgPost {
  id: string
  caption: string | null
  media_type: string | null
  thumbnail_url: string | null
  permalink: string | null
}

interface CarouselItemForm {
  image_url: string
  link_url: string
  message: string
}

function centsToBRL(cents: string | null): string {
  if (!cents) return '—'
  return `R$ ${(parseInt(cents) / 100).toFixed(2)}`
}

/** Métrica de desempenho compacta (rótulo em cima, valor embaixo). */
function PerfMetric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-[10px] uppercase tracking-wider text-[#555]">{label}</p>
      <p className="text-[13px] font-semibold text-[#e2e2e8]">{value}</p>
    </div>
  )
}

/** Autocomplete simples de segmentação (interesses ou localizações). */
function TargetingSearch({
  label, endpoint, selected, onAdd, onRemove,
}: {
  label: string
  endpoint: string
  selected: TargetingOption[]
  onAdd: (opt: TargetingOption) => void
  onRemove: (id: string) => void
}) {
  const [q, setQ] = useState('')
  const [results, setResults] = useState<TargetingOption[]>([])
  const [searching, setSearching] = useState(false)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    if (q.trim().length < 2) {
      setResults([])
      return
    }
    debounceRef.current = setTimeout(async () => {
      setSearching(true)
      try {
        const { data } = await api.get<TargetingOption[]>(endpoint, { params: { q: q.trim() } })
        setResults(data)
      } catch {
        setResults([])
      } finally {
        setSearching(false)
      }
    }, 350)
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current) }
  }, [q, endpoint])

  return (
    <div>
      <label className="block text-[11px] text-[#666] mb-1">{label}</label>
      <div className="relative">
        <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#444]" />
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Digite para buscar…"
          className="w-full pl-8 pr-3 py-2 bg-[#0a0a0f] border border-white/[0.08] text-[#e2e2e8] text-sm rounded-lg focus:border-indigo-500 focus:outline-none"
        />
      </div>
      {q.trim().length >= 2 && (
        <div className="mt-1 bg-[#0a0a0f] border border-white/[0.08] rounded-lg max-h-40 overflow-y-auto">
          {searching ? (
            <p className="text-[11px] text-[#555] px-3 py-2">Buscando…</p>
          ) : results.length === 0 ? (
            <p className="text-[11px] text-[#555] px-3 py-2">Nenhum resultado.</p>
          ) : (
            results.map((r) => (
              <button
                key={r.id}
                type="button"
                onClick={() => { onAdd(r); setQ('') }}
                className="w-full text-left px-3 py-1.5 text-xs text-[#c0c0d0] hover:bg-white/[0.05] flex items-center justify-between"
              >
                <span className="truncate">{r.name}</span>
                {r.audience_size != null && (
                  <span className="text-[#555] shrink-0 ml-2">{r.audience_size.toLocaleString()}</span>
                )}
              </button>
            ))
          )}
        </div>
      )}
      {selected.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mt-2">
          {selected.map((s) => (
            <span key={s.id} className="flex items-center gap-1 bg-indigo-600/15 border border-indigo-500/30 text-indigo-300 text-[11px] px-2 py-1 rounded-full">
              {s.name}
              <button type="button" onClick={() => onRemove(s.id)} className="hover:text-white">
                <X size={11} />
              </button>
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

export default function MarketingCampaignDetail() {
  const { campaignId } = useParams<{ campaignId: string }>()

  const [campaign, setCampaign] = useState<Campaign | null>(null)
  const [adSets, setAdSets] = useState<AdSet[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [insights, setInsights] = useState<InsightsPoint[]>([])
  const [adSetInsights, setAdSetInsights] = useState<Record<string, EntityInsights>>({})
  const [adInsights, setAdInsights] = useState<Record<string, EntityInsights>>({})
  const [breakdownDim, setBreakdownDim] = useState('age')
  const [breakdownRows, setBreakdownRows] = useState<BreakdownRow[]>([])
  const [loadingBreakdown, setLoadingBreakdown] = useState(false)

  const [expandedSet, setExpandedSet] = useState<string | null>(null)
  const [adsBySet, setAdsBySet] = useState<Record<string, Ad[]>>({})
  const [busyId, setBusyId] = useState<string | null>(null)

  // Modal: novo conjunto de anúncios
  const [showAdSetModal, setShowAdSetModal] = useState(false)
  const [asName, setAsName] = useState('')
  const [asBudget, setAsBudget] = useState('20.00')
  const [asBid, setAsBid] = useState('')
  const [asOptGoal, setAsOptGoal] = useState('REACH')
  const [asAgeMin, setAsAgeMin] = useState(18)
  const [asAgeMax, setAsAgeMax] = useState(65)
  const [asGender, setAsGender] = useState<'all' | 'male' | 'female'>('all')
  const [asCountries, setAsCountries] = useState('BR')
  const [asInterests, setAsInterests] = useState<TargetingOption[]>([])
  const [creatingAdSet, setCreatingAdSet] = useState(false)

  // Modal: novo anúncio (criativo + ad)
  const [showAdModal, setShowAdModal] = useState<string | null>(null) // ad_set_id
  const [adName, setAdName] = useState('')
  const [creativeKind, setCreativeKind] = useState<CreativeKind>('image')
  const [creativeMessage, setCreativeMessage] = useState('')
  const [creativeImageUrl, setCreativeImageUrl] = useState('')
  const [creativeLinkUrl, setCreativeLinkUrl] = useState('')
  const [creativeVideoFile, setCreativeVideoFile] = useState<File | null>(null)
  const [carouselItems, setCarouselItems] = useState<CarouselItemForm[]>([
    { image_url: '', link_url: '', message: '' },
    { image_url: '', link_url: '', message: '' },
  ])
  const [creatingAd, setCreatingAd] = useState(false)
  const [adModalStep, setAdModalStep] = useState<'idle' | 'uploading' | 'creating_creative' | 'creating_ad'>('idle')
  // Impulsionar post existente
  const [igPosts, setIgPosts] = useState<IgPost[]>([])
  const [loadingPosts, setLoadingPosts] = useState(false)
  const [selectedPostId, setSelectedPostId] = useState('')

  const loadCampaign = useCallback(async () => {
    try {
      const { data } = await api.get<Campaign[]>('/marketing/campaigns')
      setCampaign(data.find((c) => c.id === campaignId) ?? null)
    } catch { /* ignore */ }
  }, [campaignId])

  const loadAdSets = useCallback(async () => {
    if (!campaignId) return
    setLoading(true)
    try {
      const { data } = await api.get<AdSet[]>(`/marketing/campaigns/${campaignId}/ad-sets`)
      setAdSets(data)
    } catch {
      setError('Erro ao carregar conjuntos de anúncios.')
    } finally {
      setLoading(false)
    }
  }, [campaignId])

  const loadInsights = useCallback(async () => {
    if (!campaignId) return
    try {
      const { data } = await api.get<InsightsPoint[]>(`/marketing/campaigns/${campaignId}/insights`, {
        params: { date_preset: 'last_30d' },
      })
      setInsights(data)
    } catch { /* ignore */ }
  }, [campaignId])

  const loadEntityInsights = useCallback(async () => {
    if (!campaignId) return
    try {
      const [asRes, adRes] = await Promise.all([
        api.get<EntityInsights[]>(`/marketing/campaigns/${campaignId}/insights/by-level`, { params: { level: 'adset', date_preset: 'last_30d' } }),
        api.get<EntityInsights[]>(`/marketing/campaigns/${campaignId}/insights/by-level`, { params: { level: 'ad', date_preset: 'last_30d' } }),
      ])
      setAdSetInsights(Object.fromEntries(asRes.data.map((r) => [r.id, r])))
      setAdInsights(Object.fromEntries(adRes.data.map((r) => [r.id, r])))
    } catch { /* insights por entidade é enriquecimento — não bloqueia a tela */ }
  }, [campaignId])

  const loadBreakdown = useCallback(async (dim: string) => {
    if (!campaignId) return
    setLoadingBreakdown(true)
    try {
      const { data } = await api.get<BreakdownRow[]>(`/marketing/campaigns/${campaignId}/insights/breakdown`, {
        params: { dimension: dim, date_preset: 'last_30d' },
      })
      setBreakdownRows(data)
    } catch { setBreakdownRows([]) } finally { setLoadingBreakdown(false) }
  }, [campaignId])

  useEffect(() => { loadCampaign(); loadAdSets(); loadInsights(); loadEntityInsights() }, [loadCampaign, loadAdSets, loadInsights, loadEntityInsights])
  useEffect(() => { loadBreakdown(breakdownDim) }, [breakdownDim, loadBreakdown])

  async function loadAds(adSetId: string) {
    try {
      const { data } = await api.get<Ad[]>(`/marketing/ad-sets/${adSetId}/ads`)
      setAdsBySet((prev) => ({ ...prev, [adSetId]: data }))
    } catch { /* ignore */ }
  }

  function toggleExpand(adSetId: string) {
    const next = expandedSet === adSetId ? null : adSetId
    setExpandedSet(next)
    if (next && !adsBySet[next]) loadAds(next)
  }

  async function toggleAdSetStatus(as: AdSet) {
    setBusyId(as.id)
    try {
      await api.patch(`/marketing/ad-sets/${as.id}`, { status: as.status === 'ACTIVE' ? 'PAUSED' : 'ACTIVE' })
      await loadAdSets()
    } catch {
      setError('Erro ao atualizar conjunto.')
    } finally {
      setBusyId(null)
    }
  }

  async function deleteAdSet(as: AdSet) {
    if (!confirm(`Excluir o conjunto "${as.name}"?`)) return
    setBusyId(as.id)
    try {
      await api.delete(`/marketing/ad-sets/${as.id}`)
      setAdSets((prev) => prev.filter((x) => x.id !== as.id))
    } catch {
      setError('Erro ao excluir conjunto.')
    } finally {
      setBusyId(null)
    }
  }

  async function toggleAdStatus(adSetId: string, ad: Ad) {
    setBusyId(ad.id)
    try {
      await api.patch(`/marketing/ads/${ad.id}`, { status: ad.status === 'ACTIVE' ? 'PAUSED' : 'ACTIVE' })
      await loadAds(adSetId)
    } catch {
      setError('Erro ao atualizar anúncio.')
    } finally {
      setBusyId(null)
    }
  }

  async function deleteAd(adSetId: string, ad: Ad) {
    if (!confirm(`Excluir o anúncio "${ad.name}"?`)) return
    setBusyId(ad.id)
    try {
      await api.delete(`/marketing/ads/${ad.id}`)
      setAdsBySet((prev) => ({ ...prev, [adSetId]: (prev[adSetId] || []).filter((a) => a.id !== ad.id) }))
    } catch {
      setError('Erro ao excluir anúncio.')
    } finally {
      setBusyId(null)
    }
  }

  async function duplicateAdSet(as: AdSet) {
    setBusyId(as.id)
    try {
      await api.post(`/marketing/ad-sets/${as.id}/copy`)
      await loadAdSets()
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Erro ao duplicar conjunto.')
    } finally {
      setBusyId(null)
    }
  }

  async function duplicateAd(adSetId: string, ad: Ad) {
    setBusyId(ad.id)
    try {
      await api.post(`/marketing/ads/${ad.id}/copy`)
      await loadAds(adSetId)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Erro ao duplicar anúncio.')
    } finally {
      setBusyId(null)
    }
  }

  function openAdSetModal() {
    setAsName(''); setAsBudget('20.00'); setAsBid(''); setAsOptGoal('REACH')
    setAsAgeMin(18); setAsAgeMax(65); setAsGender('all'); setAsCountries('BR'); setAsInterests([])
    setShowAdSetModal(true)
  }

  async function createAdSet(e: React.FormEvent) {
    e.preventDefault()
    if (!asName.trim() || !campaignId) return
    setCreatingAdSet(true)
    setError('')
    try {
      await api.post('/marketing/ad-sets', {
        campaign_id: campaignId,
        name: asName.trim(),
        daily_budget_cents: Math.round(parseFloat(asBudget || '0') * 100),
        bid_amount_cents: asBid ? Math.round(parseFloat(asBid) * 100) : null,
        optimization_goal: asOptGoal,
        targeting: {
          age_min: asAgeMin,
          age_max: asAgeMax,
          genders: asGender === 'all' ? null : asGender === 'male' ? [1] : [2],
          country_codes: asCountries.split(',').map((c) => c.trim().toUpperCase()).filter(Boolean),
          interest_ids: asInterests.map((i) => i.id),
        },
      })
      setShowAdSetModal(false)
      await loadAdSets()
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Erro ao criar conjunto de anúncios.')
    } finally {
      setCreatingAdSet(false)
    }
  }

  function openAdModal(adSetId: string) {
    setAdName(''); setCreativeKind('image'); setCreativeMessage('')
    setCreativeImageUrl(''); setCreativeLinkUrl(''); setCreativeVideoFile(null)
    setCarouselItems([{ image_url: '', link_url: '', message: '' }, { image_url: '', link_url: '', message: '' }])
    setSelectedPostId('')
    setAdModalStep('idle')
    setShowAdModal(adSetId)
  }

  async function loadIgPosts() {
    if (igPosts.length > 0 || loadingPosts) return
    setLoadingPosts(true)
    try {
      const { data } = await api.get<IgPost[]>('/marketing/instagram-posts')
      setIgPosts(data)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Não foi possível carregar seus posts do Instagram.')
    } finally {
      setLoadingPosts(false)
    }
  }

  const adFormValid = adName.trim() && (
    creativeKind === 'post' ? !!selectedPostId && !!creativeLinkUrl.trim() :
    !creativeMessage.trim() ? false :
    creativeKind === 'image' ? !!creativeImageUrl.trim() :
    creativeKind === 'video' ? !!creativeVideoFile :
    carouselItems.filter((c) => c.image_url.trim()).length >= 2
  )

  async function createAd() {
    if (!showAdModal || !adFormValid || creatingAd) return
    const adSetId = showAdModal
    setCreatingAd(true)
    setError('')
    try {
      let video_id: string | undefined
      if (creativeKind === 'video' && creativeVideoFile) {
        setAdModalStep('uploading')
        const form = new FormData()
        form.append('file', creativeVideoFile)
        const { data: up } = await api.post('/marketing/videos/upload', form, {
          headers: { 'Content-Type': 'multipart/form-data' },
        })
        video_id = up.video_id
      }

      setAdModalStep('creating_creative')
      const creativePayload: Record<string, unknown> = {
        name: `${adName.trim()} — criativo`,
        message: creativeMessage.trim(),
      }
      if (creativeKind === 'post') {
        creativePayload.source_instagram_media_id = selectedPostId
        creativePayload.link_url = creativeLinkUrl.trim()
      } else if (creativeKind === 'image') {
        creativePayload.image_url = creativeImageUrl.trim()
        if (creativeLinkUrl.trim()) creativePayload.link_url = creativeLinkUrl.trim()
      } else if (creativeKind === 'video') {
        creativePayload.video_id = video_id
        if (creativeLinkUrl.trim()) creativePayload.link_url = creativeLinkUrl.trim()
      } else {
        creativePayload.link_url = creativeLinkUrl.trim() || undefined
        creativePayload.carousel_items = carouselItems
          .filter((c) => c.image_url.trim())
          .map((c) => ({ image_url: c.image_url.trim(), link_url: c.link_url.trim() || undefined, message: c.message.trim() }))
      }
      const { data: creative } = await api.post('/marketing/creatives', creativePayload)

      setAdModalStep('creating_ad')
      await api.post('/marketing/ads', {
        ad_set_id: adSetId,
        creative_id: creative.creative_id,
        name: adName.trim(),
        status: 'PAUSED',
      })

      setShowAdModal(null)
      await loadAds(adSetId)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Erro ao criar anúncio.')
    } finally {
      setCreatingAd(false)
      setAdModalStep('idle')
    }
  }

  const maxSpend = Math.max(1, ...insights.map((p) => p.spend))

  return (
    <div>
      <Link to="/app/marketing" className="inline-flex items-center gap-1.5 text-[#5a5a6e] hover:text-[#c0c0d0] text-sm mb-4 no-underline transition-colors">
        <ArrowLeft size={15} />
        Campanhas
      </Link>

      <div className="flex items-center justify-between mb-6 flex-wrap gap-3">
        <div>
          <h2 className="text-2xl font-bold text-[#e2e2e8]">{campaign?.name || 'Campanha'}</h2>
          {campaign && (
            <p className="text-[#555] text-sm mt-1">
              {campaign.status === 'ACTIVE' ? 'Ativa' : 'Pausada'}
              {campaign.daily_budget && ` · ${centsToBRL(campaign.daily_budget)}/dia`}
            </p>
          )}
        </div>
        <button
          onClick={openAdSetModal}
          className="flex items-center gap-1.5 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-semibold rounded-lg transition-colors"
        >
          <Plus size={15} />
          Novo conjunto de anúncios
        </button>
      </div>

      {error && (
        <div className="mb-4 bg-red-900/20 border border-red-500/20 text-red-400 text-sm rounded-lg px-4 py-3">{error}</div>
      )}

      {/* Gráfico de gastos (últimos 30 dias) */}
      {insights.length > 0 && (
        <div className="bg-[#111118] rounded-xl border border-white/[0.06] p-5 mb-6">
          <p className="text-[#555] text-xs mb-3">Gastos por dia — últimos 30 dias</p>
          <div className="flex items-end gap-0.5 h-24">
            {insights.map((p) => (
              <div
                key={p.date}
                title={`${p.date}: R$ ${p.spend.toFixed(2)}`}
                className="flex-1 bg-indigo-500/60 hover:bg-indigo-400 rounded-t transition-colors min-w-[2px]"
                style={{ height: `${Math.max(2, (p.spend / maxSpend) * 100)}%` }}
              />
            ))}
          </div>
        </div>
      )}

      {/* Desempenho por segmento (breakdowns) */}
      <div className="bg-[#111118] rounded-xl border border-white/[0.06] p-5 mb-6 max-w-4xl">
        <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
          <p className="text-sm font-semibold text-[#e2e2e8]">Desempenho por segmento</p>
          <div className="flex gap-1 bg-[#0a0a0f] border border-white/[0.08] rounded-lg p-1">
            {BREAKDOWN_DIMS.map((d) => (
              <button
                key={d.value}
                onClick={() => setBreakdownDim(d.value)}
                className={`px-2.5 py-1 rounded text-xs font-medium transition-colors ${breakdownDim === d.value ? 'bg-indigo-600 text-white' : 'text-[#5a5a6e] hover:text-[#c0c0d0]'}`}
              >
                {d.label}
              </button>
            ))}
          </div>
        </div>
        {loadingBreakdown ? (
          <p className="text-[#555] text-sm">Carregando…</p>
        ) : breakdownRows.length === 0 ? (
          <p className="text-[#555] text-sm">Sem dados neste período (a campanha precisa ter tido entrega/gasto).</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-[#555] text-xs text-left">
                  <th className="pb-2 pr-4">Segmento</th>
                  <th className="pb-2 pr-4 text-right">Gasto</th>
                  <th className="pb-2 pr-4 text-right">Resultados</th>
                  <th className="pb-2 pr-4 text-right">Alcance</th>
                  <th className="pb-2 pr-4 text-right">Cliques</th>
                  <th className="pb-2 text-right">CTR</th>
                </tr>
              </thead>
              <tbody>
                {breakdownRows.map((r) => (
                  <tr key={r.key} className="border-t border-white/[0.06] text-[#c0c0d0]">
                    <td className="py-2 pr-4 capitalize">{r.key}</td>
                    <td className="py-2 pr-4 text-right">R$ {r.spend.toFixed(2)}</td>
                    <td className="py-2 pr-4 text-right">{r.results ? r.results.toLocaleString() : '—'}</td>
                    <td className="py-2 pr-4 text-right">{r.reach ? r.reach.toLocaleString() : '—'}</td>
                    <td className="py-2 pr-4 text-right">{r.clicks.toLocaleString()}</td>
                    <td className="py-2 text-right">{r.ctr.toFixed(2)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Conjuntos de anúncios */}
      {loading ? (
        <div className="text-[#555] text-sm">Carregando...</div>
      ) : adSets.length === 0 ? (
        <div className="bg-[#111118] rounded-xl border border-white/[0.06] p-12 text-center">
          <p className="text-[#555]">Nenhum conjunto de anúncios ainda. Crie um para começar a segmentar.</p>
        </div>
      ) : (
        <div className="space-y-3 max-w-4xl">
          {adSets.map((as) => {
            const isOpen = expandedSet === as.id
            const busy = busyId === as.id
            const ads = adsBySet[as.id] || []
            return (
              <div key={as.id} className="bg-[#111118]/80 backdrop-blur-sm rounded-2xl border border-white/[0.06] overflow-hidden hover:border-indigo-500/30 transition-all shadow-xl">
                <div className="p-5 flex items-center gap-4">
                  <button onClick={() => toggleExpand(as.id)} className="text-[#5a5a6e] hover:text-white shrink-0">
                    {isOpen ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                  </button>
                  <div className="flex-1 min-w-0 cursor-pointer" onClick={() => toggleExpand(as.id)}>
                    <h4 className="text-white font-bold text-base truncate hover:text-indigo-400 transition-colors">{as.name}</h4>
                    <p className="text-[#888] text-xs mt-1 flex items-center gap-2">
                      <span className="flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>{centsToBRL(as.daily_budget)}/dia</span>
                      {as.bid_amount && <span>· lance {centsToBRL(as.bid_amount)}</span>}
                      {as.optimization_goal && <span>· {as.optimization_goal}</span>}
                    </p>
                  </div>
                  <span className={`text-[11px] font-bold px-2.5 py-1 rounded-full shrink-0 ${
                    as.status === 'ACTIVE' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-white/[0.05] text-[#888] border border-white/[0.05]'
                  }`}>
                    {as.status === 'ACTIVE' ? 'Ativo' : 'Pausado'}
                  </span>
                  <button
                    onClick={() => toggleAdSetStatus(as)}
                    disabled={busy}
                    className="w-9 h-9 shrink-0 rounded-xl bg-white/[0.04] hover:bg-indigo-500/20 text-[#8a8a9e] hover:text-indigo-400 flex items-center justify-center transition-colors disabled:opacity-40"
                  >
                    {as.status === 'ACTIVE' ? <Pause size={15} fill="currentColor" /> : <Play size={15} fill="currentColor" className="ml-1" />}
                  </button>
                  <button
                    onClick={() => duplicateAdSet(as)}
                    disabled={busy}
                    title="Duplicar conjunto (cópia pausada)"
                    className="w-9 h-9 shrink-0 rounded-xl bg-white/[0.04] hover:bg-emerald-500/20 text-[#8a8a9e] hover:text-emerald-400 flex items-center justify-center transition-colors disabled:opacity-40"
                  >
                    <Copy size={14} />
                  </button>
                  <button
                    onClick={() => deleteAdSet(as)}
                    disabled={busy}
                    className="w-9 h-9 shrink-0 rounded-xl bg-white/[0.04] hover:bg-red-500/20 text-[#8a8a9e] hover:text-red-400 flex items-center justify-center transition-colors disabled:opacity-40"
                  >
                    <Trash2 size={15} />
                  </button>
                </div>

                {adSetInsights[as.id] && (
                  <div className="px-5 pb-4 -mt-2 flex flex-wrap gap-x-6 gap-y-1">
                    <PerfMetric label="Gasto" value={`R$ ${adSetInsights[as.id].spend.toFixed(2)}`} />
                    <PerfMetric label={adSetInsights[as.id].result_label || 'Resultados'} value={adSetInsights[as.id].results ? adSetInsights[as.id].results.toLocaleString() : '—'} />
                    <PerfMetric label="Custo/result." value={adSetInsights[as.id].cost_per_result ? `R$ ${adSetInsights[as.id].cost_per_result.toFixed(2)}` : '—'} />
                    <PerfMetric label="CTR" value={`${adSetInsights[as.id].ctr.toFixed(2)}%`} />
                    <PerfMetric label="Alcance" value={adSetInsights[as.id].reach ? adSetInsights[as.id].reach.toLocaleString() : '—'} />
                  </div>
                )}

                {isOpen && (
                  <div className="border-t border-white/[0.06] p-5 bg-black/20">
                    <div className="flex items-center justify-between mb-4">
                      <p className="text-[12px] font-bold uppercase tracking-wider text-indigo-400 flex items-center gap-2"><ImageIcon size={14} /> Anúncios</p>
                      <button
                        onClick={() => openAdModal(as.id)}
                        className="flex items-center gap-1.5 text-xs text-white bg-indigo-600 hover:bg-indigo-500 px-3 py-1.5 rounded-lg font-medium shadow-lg shadow-indigo-500/20 transition-all"
                      >
                        <Plus size={14} /> Novo anúncio
                      </button>
                    </div>
                    {ads.length === 0 ? (
                      <p className="text-[#444] text-xs py-2">Nenhum anúncio neste conjunto ainda.</p>
                    ) : (
                      <div className="space-y-2">
                        {ads.map((ad) => (
                          <div key={ad.id} className="flex items-center gap-4 bg-[#0a0a0f] border border-white/[0.04] rounded-xl p-3 hover:border-white/[0.1] transition-colors shadow-sm">
                            {ad.thumbnail_url ? (
                              <img src={ad.thumbnail_url} className="w-12 h-12 rounded-lg object-cover shrink-0 shadow-md" alt="" />
                            ) : (
                              <div className="w-12 h-12 rounded-lg bg-white/[0.02] border border-white/[0.05] flex items-center justify-center shrink-0">
                                <ImageIcon size={18} className="text-[#444]" />
                              </div>
                            )}
                            <div className="flex-1 min-w-0">
                              <p className="text-white text-sm font-semibold truncate">{ad.name}</p>
                              <p className="text-[#888] text-xs truncate mt-0.5">{ad.creative_name}</p>
                              {adInsights[ad.id] && (
                                <div className="flex flex-wrap gap-x-4 gap-y-0.5 mt-1.5 text-[11px] text-[#888]">
                                  <span>Gasto <b className="text-[#c0c0d0]">R$ {adInsights[ad.id].spend.toFixed(2)}</b></span>
                                  <span>{adInsights[ad.id].result_label || 'Result.'} <b className="text-[#c0c0d0]">{adInsights[ad.id].results ? adInsights[ad.id].results.toLocaleString() : '—'}</b></span>
                                  <span>Custo/res. <b className="text-[#c0c0d0]">{adInsights[ad.id].cost_per_result ? `R$ ${adInsights[ad.id].cost_per_result.toFixed(2)}` : '—'}</b></span>
                                  <span>CTR <b className="text-[#c0c0d0]">{adInsights[ad.id].ctr.toFixed(2)}%</b></span>
                                </div>
                              )}
                            </div>
                            <span className={`text-[10px] font-bold px-2 py-1 rounded-md shrink-0 ${
                              ad.status === 'ACTIVE' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-white/[0.05] text-[#888] border border-white/[0.05]'
                            }`}>
                              {ad.status === 'ACTIVE' ? 'Ativo' : 'Pausado'}
                            </span>
                            <button
                              onClick={() => toggleAdStatus(as.id, ad)}
                              disabled={busyId === ad.id}
                              className="w-8 h-8 shrink-0 rounded-lg bg-white/[0.04] hover:bg-indigo-500/20 text-[#8a8a9e] hover:text-indigo-400 flex items-center justify-center transition-colors disabled:opacity-40"
                            >
                              {ad.status === 'ACTIVE' ? <Pause size={14} fill="currentColor" /> : <Play size={14} fill="currentColor" className="ml-0.5" />}
                            </button>
                            <button
                              onClick={() => duplicateAd(as.id, ad)}
                              disabled={busyId === ad.id}
                              title="Duplicar anúncio (cópia pausada)"
                              className="w-8 h-8 shrink-0 rounded-lg bg-white/[0.04] hover:bg-emerald-500/20 text-[#8a8a9e] hover:text-emerald-400 flex items-center justify-center transition-colors disabled:opacity-40"
                            >
                              <Copy size={13} />
                            </button>
                            <button
                              onClick={() => deleteAd(as.id, ad)}
                              disabled={busyId === ad.id}
                              className="w-8 h-8 shrink-0 rounded-lg bg-white/[0.04] hover:bg-red-500/20 text-[#8a8a9e] hover:text-red-400 flex items-center justify-center transition-colors disabled:opacity-40"
                            >
                              <Trash2 size={14} />
                            </button>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}

      {/* Modal: novo conjunto de anúncios */}
      {showAdSetModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm px-4 py-8 overflow-y-auto">
          <div className="bg-[#111118] border border-white/[0.08] rounded-2xl p-6 w-full max-w-lg my-auto">
            <div className="flex items-center justify-between mb-5">
              <h3 className="text-base font-semibold text-white">Novo conjunto de anúncios</h3>
              <button onClick={() => setShowAdSetModal(false)} className="text-[#444] hover:text-[#888]"><X size={18} /></button>
            </div>
            <form onSubmit={createAdSet} className="space-y-4">
              <div>
                <label className="block text-[11px] text-[#666] mb-1">Nome</label>
                <input
                  value={asName}
                  onChange={(e) => setAsName(e.target.value)}
                  placeholder="Ex: Mulheres 25-45 — Grande SP"
                  className="w-full px-3 py-2 bg-[#0a0a0f] border border-white/[0.08] text-[#e2e2e8] text-sm rounded-lg focus:border-indigo-500 focus:outline-none"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[11px] text-[#666] mb-1">Orçamento diário (R$)</label>
                  <input
                    type="number" step="0.01" min="1" value={asBudget}
                    onChange={(e) => setAsBudget(e.target.value)}
                    className="w-full px-3 py-2 bg-[#0a0a0f] border border-white/[0.08] text-[#e2e2e8] text-sm rounded-lg focus:border-indigo-500 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-[11px] text-[#666] mb-1">Lance máx. (R$, opcional)</label>
                  <input
                    type="number" step="0.01" min="0" value={asBid}
                    onChange={(e) => setAsBid(e.target.value)}
                    placeholder="Automático"
                    className="w-full px-3 py-2 bg-[#0a0a0f] border border-white/[0.08] text-[#e2e2e8] text-sm rounded-lg focus:border-indigo-500 focus:outline-none"
                  />
                </div>
              </div>
              <div>
                <label className="block text-[11px] text-[#666] mb-1">Otimização</label>
                <select
                  value={asOptGoal}
                  onChange={(e) => setAsOptGoal(e.target.value)}
                  className="w-full px-3 py-2 bg-[#0a0a0f] border border-white/[0.08] text-[#e2e2e8] text-sm rounded-lg focus:border-indigo-500 focus:outline-none"
                >
                  <option value="REACH">Alcance</option>
                  <option value="LINK_CLICKS">Cliques no link</option>
                  <option value="LEAD_GENERATION">Geração de leads</option>
                  <option value="IMPRESSIONS">Impressões</option>
                  <option value="CONVERSATIONS">Conversas</option>
                </select>
              </div>

              <div className="h-px bg-white/[0.06]" />
              <p className="text-[11px] font-semibold uppercase tracking-wider text-[#444]">Segmentação</p>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[11px] text-[#666] mb-1">Idade mínima</label>
                  <input
                    type="number" min="13" max="65" value={asAgeMin}
                    onChange={(e) => setAsAgeMin(parseInt(e.target.value) || 18)}
                    className="w-full px-3 py-2 bg-[#0a0a0f] border border-white/[0.08] text-[#e2e2e8] text-sm rounded-lg focus:border-indigo-500 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-[11px] text-[#666] mb-1">Idade máxima</label>
                  <input
                    type="number" min="13" max="65" value={asAgeMax}
                    onChange={(e) => setAsAgeMax(parseInt(e.target.value) || 65)}
                    className="w-full px-3 py-2 bg-[#0a0a0f] border border-white/[0.08] text-[#e2e2e8] text-sm rounded-lg focus:border-indigo-500 focus:outline-none"
                  />
                </div>
              </div>

              <div>
                <label className="block text-[11px] text-[#666] mb-1">Gênero</label>
                <div className="flex gap-2">
                  {([['all', 'Todos'], ['male', 'Masculino'], ['female', 'Feminino']] as const).map(([val, label]) => (
                    <button
                      key={val}
                      type="button"
                      onClick={() => setAsGender(val)}
                      className={`flex-1 py-1.5 rounded-lg text-xs font-medium border transition-colors ${
                        asGender === val
                          ? 'bg-indigo-600/20 border-indigo-500/50 text-indigo-300'
                          : 'bg-white/[0.03] border-white/[0.08] text-[#5a5a6e] hover:text-white'
                      }`}
                    >
                      {label}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="block text-[11px] text-[#666] mb-1">Países (códigos separados por vírgula)</label>
                <input
                  value={asCountries}
                  onChange={(e) => setAsCountries(e.target.value)}
                  placeholder="BR, PT"
                  className="w-full px-3 py-2 bg-[#0a0a0f] border border-white/[0.08] text-[#e2e2e8] text-sm rounded-lg focus:border-indigo-500 focus:outline-none"
                />
              </div>

              <TargetingSearch
                label="Interesses (opcional)"
                endpoint="/marketing/targeting/interests"
                selected={asInterests}
                onAdd={(opt) => setAsInterests((prev) => (prev.some((p) => p.id === opt.id) ? prev : [...prev, opt]))}
                onRemove={(id) => setAsInterests((prev) => prev.filter((p) => p.id !== id))}
              />

              <div className="flex gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowAdSetModal(false)}
                  className="flex-1 py-2.5 border border-white/[0.08] text-[#666] hover:text-white text-sm font-medium rounded-lg transition-colors"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  disabled={creatingAdSet || !asName.trim()}
                  className="flex-1 py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm font-semibold rounded-lg transition-colors"
                >
                  {creatingAdSet ? 'Criando…' : 'Criar conjunto'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: novo anúncio */}
      {showAdModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm px-4 py-8 overflow-y-auto">
          <div className="bg-[#111118] border border-white/[0.08] rounded-2xl p-6 w-full max-w-lg my-auto">
            <div className="flex items-center justify-between mb-5">
              <h3 className="text-base font-semibold text-white">Novo anúncio</h3>
              <button onClick={() => setShowAdModal(null)} className="text-[#444] hover:text-[#888]"><X size={18} /></button>
            </div>

            <div className="space-y-4">
              <div>
                <label className="block text-[11px] text-[#666] mb-1">Nome do anúncio</label>
                <input
                  value={adName}
                  onChange={(e) => setAdName(e.target.value)}
                  placeholder="Ex: Anúncio — Carrossel Coleção Verão"
                  className="w-full px-3 py-2 bg-[#0a0a0f] border border-white/[0.08] text-[#e2e2e8] text-sm rounded-lg focus:border-indigo-500 focus:outline-none"
                />
              </div>

              <div className="grid grid-cols-4 gap-2">
                {([['image', 'Imagem', ImageIcon], ['video', 'Vídeo', Video], ['carousel', 'Carrossel', GalleryHorizontal], ['post', 'Post IG', Camera]] as const).map(([val, label, Icon]) => (
                  <button
                    key={val}
                    type="button"
                    onClick={() => { setCreativeKind(val); if (val === 'post') loadIgPosts() }}
                    className={`flex flex-col items-center gap-1 py-2.5 rounded-lg text-xs font-medium border transition-colors ${
                      creativeKind === val
                        ? 'bg-indigo-600/20 border-indigo-500/50 text-indigo-300'
                        : 'bg-white/[0.03] border-white/[0.08] text-[#5a5a6e] hover:text-white'
                    }`}
                  >
                    <Icon size={15} />
                    {label}
                  </button>
                ))}
              </div>

              {creativeKind !== 'post' && (
                <div>
                  <label className="block text-[11px] text-[#666] mb-1">Texto do anúncio</label>
                  <textarea
                    value={creativeMessage}
                    onChange={(e) => setCreativeMessage(e.target.value)}
                    rows={3}
                    placeholder="Ex.: Frete grátis em compras acima de R$150!"
                    className="w-full px-3 py-2 bg-[#0a0a0f] border border-white/[0.08] text-[#e2e2e8] text-sm rounded-lg focus:border-indigo-500 focus:outline-none resize-none"
                  />
                </div>
              )}

              <div>
                <label className="block text-[11px] text-[#666] mb-1">
                  Link de destino {creativeKind === 'post' ? '(obrigatório)' : '(opcional)'}
                </label>
                <input
                  value={creativeLinkUrl}
                  onChange={(e) => setCreativeLinkUrl(e.target.value)}
                  placeholder="https://seusite.com/promo"
                  className="w-full px-3 py-2 bg-[#0a0a0f] border border-white/[0.08] text-[#e2e2e8] text-sm rounded-lg focus:border-indigo-500 focus:outline-none"
                />
              </div>

              {creativeKind === 'post' && (
                <div>
                  <label className="block text-[11px] text-[#666] mb-2">Escolha o post para impulsionar</label>
                  {loadingPosts ? (
                    <p className="text-[#555] text-sm">Carregando seus posts…</p>
                  ) : igPosts.length === 0 ? (
                    <p className="text-[#555] text-sm">Nenhum post encontrado (a conta do Instagram precisa estar vinculada a uma Página do Facebook).</p>
                  ) : (
                    <div className="grid grid-cols-4 gap-2 max-h-56 overflow-y-auto">
                      {igPosts.map((p) => (
                        <button
                          key={p.id}
                          type="button"
                          onClick={() => setSelectedPostId(p.id)}
                          title={p.caption || p.media_type || ''}
                          className={`relative rounded-lg overflow-hidden border-2 transition-colors ${selectedPostId === p.id ? 'border-indigo-500' : 'border-transparent hover:border-white/[0.15]'}`}
                        >
                          {p.thumbnail_url ? (
                            <img src={p.thumbnail_url} alt="" className="w-full h-16 object-cover" />
                          ) : (
                            <div className="w-full h-16 flex items-center justify-center bg-white/[0.03] text-[#444] text-[10px]">{p.media_type}</div>
                          )}
                          {selectedPostId === p.id && <span className="absolute top-1 right-1 w-4 h-4 rounded-full bg-indigo-500 text-white text-[10px] flex items-center justify-center">✓</span>}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {creativeKind === 'image' && (
                <div>
                  <label className="block text-[11px] text-[#666] mb-1">URL da imagem</label>
                  <input
                    value={creativeImageUrl}
                    onChange={(e) => setCreativeImageUrl(e.target.value)}
                    placeholder="https://cdn.seusite.com/produto.jpg"
                    className="w-full px-3 py-2 bg-[#0a0a0f] border border-white/[0.08] text-[#e2e2e8] text-sm rounded-lg focus:border-indigo-500 focus:outline-none"
                  />
                </div>
              )}

              {creativeKind === 'video' && (
                <div>
                  <label className="block text-[11px] text-[#666] mb-1">Arquivo de vídeo</label>
                  <input
                    type="file"
                    accept="video/*"
                    onChange={(e) => setCreativeVideoFile(e.target.files?.[0] ?? null)}
                    className="w-full text-xs text-[#8a8a9e] file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:bg-indigo-600 file:text-white file:text-xs file:font-medium"
                  />
                </div>
              )}

              {creativeKind === 'carousel' && (
                <div className="space-y-2">
                  <label className="block text-[11px] text-[#666]">Itens do carrossel (mín. 2)</label>
                  {carouselItems.map((item, i) => (
                    <div key={i} className="bg-[#0a0a0f] border border-white/[0.06] rounded-lg p-3 space-y-1.5">
                      <input
                        value={item.image_url}
                        onChange={(e) => setCarouselItems((prev) => prev.map((x, j) => (j === i ? { ...x, image_url: e.target.value } : x)))}
                        placeholder={`Imagem ${i + 1} — URL`}
                        className="w-full px-2.5 py-1.5 bg-[#111118] border border-white/[0.06] text-[#e2e2e8] text-xs rounded-md focus:border-indigo-500 focus:outline-none"
                      />
                      <input
                        value={item.message}
                        onChange={(e) => setCarouselItems((prev) => prev.map((x, j) => (j === i ? { ...x, message: e.target.value } : x)))}
                        placeholder="Título do card"
                        className="w-full px-2.5 py-1.5 bg-[#111118] border border-white/[0.06] text-[#e2e2e8] text-xs rounded-md focus:border-indigo-500 focus:outline-none"
                      />
                    </div>
                  ))}
                  <div className="flex gap-2">
                    {carouselItems.length < 10 && (
                      <button
                        type="button"
                        onClick={() => setCarouselItems((prev) => [...prev, { image_url: '', link_url: '', message: '' }])}
                        className="flex items-center gap-1 text-[11px] text-indigo-400 hover:text-indigo-300"
                      >
                        <Plus size={12} /> Adicionar item
                      </button>
                    )}
                    {carouselItems.length > 2 && (
                      <button
                        type="button"
                        onClick={() => setCarouselItems((prev) => prev.slice(0, -1))}
                        className="flex items-center gap-1 text-[11px] text-[#5a5a6e] hover:text-red-400"
                      >
                        <Trash2 size={12} /> Remover último
                      </button>
                    )}
                  </div>
                </div>
              )}

              <div className="flex gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowAdModal(null)}
                  className="flex-1 py-2.5 border border-white/[0.08] text-[#666] hover:text-white text-sm font-medium rounded-lg transition-colors"
                >
                  Cancelar
                </button>
                <button
                  type="button"
                  onClick={createAd}
                  disabled={!adFormValid || creatingAd}
                  className="flex-1 py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm font-semibold rounded-lg transition-colors"
                >
                  {adModalStep === 'uploading' ? 'Enviando vídeo…'
                    : adModalStep === 'creating_creative' ? 'Criando criativo…'
                    : adModalStep === 'creating_ad' ? 'Criando anúncio…'
                    : 'Criar anúncio'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
