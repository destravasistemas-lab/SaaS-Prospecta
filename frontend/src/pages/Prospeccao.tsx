import { useEffect, useRef, useState } from 'react'
import {
  Radar, Building2, MapPin, Search, Download, UserPlus, Copy, Check, X, Star, Phone, Globe, ExternalLink,
  QrCode, Loader2, Info,
} from 'lucide-react'
import api, { apiError } from '../services/api'
import { useI18n } from '../i18n'

interface Status {
  cnpj_available: boolean
  reference_month: string | null
  ufs: string[]
  total: number
  price_per_contact: number
  min_order: number
  max_per_order: number
  maps_enabled: boolean
  maps_searches_per_day: number
  free: boolean
}
interface Option { code: string; label: string }
interface Quote {
  available: number
  quantity: number
  amount: number
  already_delivered_total: number
  preview: { name: string; bairro: string | null; phone: string; email: string; porte: string }[]
}
interface Order {
  id: string
  status: 'pending' | 'paid' | 'canceled'
  quantity: number
  amount: number
  created_at: string
  paid_at: string | null
  invoice_url: string | null
  pix_payload?: string | null
  pix_image?: string | null
  cnae_description?: string
  city?: string
}
interface Place {
  id: string
  name: string
  address: string | null
  phone: string | null
  phone_intl: string | null
  website: string | null
  maps_url: string | null
  rating: number | null
  reviews: number | null
  status: string | null
}

const brl = (v: number) => v.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })
const input = 'w-full px-3 py-2 bg-field border border-white/[0.08] text-ink text-sm rounded-lg focus:border-indigo-500 focus:outline-none placeholder-ink-5'

function Autocomplete({ label, placeholder, value, onPick, fetcher }: {
  label: string
  placeholder: string
  value: Option | null
  onPick: (o: Option | null) => void
  fetcher: (q: string) => Promise<Option[]>
}) {
  const [text, setText] = useState(value?.label ?? '')
  const [options, setOptions] = useState<Option[]>([])
  const [open, setOpen] = useState(false)
  const timer = useRef<number | undefined>(undefined)

  useEffect(() => { setText(value?.label ?? '') }, [value?.code])

  function change(v: string) {
    setText(v)
    onPick(null)
    window.clearTimeout(timer.current)
    if (v.trim().length < 2) { setOptions([]); return }
    timer.current = window.setTimeout(async () => {
      try { setOptions(await fetcher(v.trim())); setOpen(true) } catch { setOptions([]) }
    }, 250)
  }

  return (
    <div className="relative">
      <label className="block text-[11px] text-ink-4 mb-1">{label}</label>
      <input value={text} onChange={(e) => change(e.target.value)} onFocus={() => options.length && setOpen(true)}
        onBlur={() => window.setTimeout(() => setOpen(false), 150)} placeholder={placeholder} className={input} />
      {open && options.length > 0 && (
        <ul className="absolute z-20 mt-1 w-full max-h-64 overflow-y-auto bg-raised border border-white/[0.1] rounded-lg shadow-xl">
          {options.map((o) => (
            <li key={o.code}>
              <button type="button" onMouseDown={() => { onPick(o); setText(o.label); setOpen(false) }}
                className="w-full text-left px-3 py-2 text-sm text-ink-2 hover:bg-white/[0.06]">{o.label}</button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

async function downloadCsv(order: Order) {
  const { data } = await api.get(`/prospect/orders/${order.id}/csv`, { responseType: 'blob' })
  const url = URL.createObjectURL(data)
  const a = document.createElement('a')
  a.href = url
  a.download = `prospeccao-${order.id.slice(0, 8)}.csv`
  a.click()
  URL.revokeObjectURL(url)
}

export default function Prospeccao() {
  const { t } = useI18n()
  const [tab, setTab] = useState<'cnpj' | 'maps'>('cnpj')
  const [status, setStatus] = useState<Status | null>(null)

  useEffect(() => { api.get('/prospect/status').then((r) => setStatus(r.data)).catch(() => setStatus(null)) }, [])

  return (
    <div className="max-w-5xl mx-auto">
      <div className="mb-5">
        <h1 className="text-xl font-semibold text-ink flex items-center gap-2">
          <Radar size={20} className="text-indigo-400" /> {t('Prospecção', 'Prospecting')}
        </h1>
        <p className="text-ink-4 text-sm mt-0.5">
          {t('Encontre empresas do seu nicho na sua cidade para oferecer o seu serviço.', 'Find businesses in your niche and city to offer your service to.')}
        </p>
      </div>

      <div className="flex gap-2 mb-5">
        {([['cnpj', t('Lista por CNPJ', 'CNPJ list'), Building2], ['maps', 'Google Maps', MapPin]] as const).map(([id, label, Icon]) => (
          <button key={id} onClick={() => setTab(id)}
            className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium border transition-colors ${tab === id ? 'bg-indigo-600/20 border-indigo-500/40 text-indigo-200' : 'border-white/[0.08] text-ink-3 hover:text-white'}`}>
            <Icon size={15} /> {label}
          </button>
        ))}
      </div>

      {!status ? (
        <p className="text-ink-5 text-sm">{t('Carregando…', 'Loading…')}</p>
      ) : tab === 'cnpj' ? <CnpjTab status={status} /> : <MapsTab status={status} />}
    </div>
  )
}

function CnpjTab({ status }: { status: Status }) {
  const { t } = useI18n()
  const [cnae, setCnae] = useState<Option | null>(null)
  const [city, setCity] = useState<Option | null>(null)
  const [bairro, setBairro] = useState('')
  const [onlyPhone, setOnlyPhone] = useState(true)
  const [onlyEmail, setOnlyEmail] = useState(false)
  const [excludeMei, setExcludeMei] = useState(false)
  const [secondary, setSecondary] = useState(false)
  const [quantity, setQuantity] = useState('')
  const [quote, setQuote] = useState<Quote | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [orders, setOrders] = useState<Order[]>([])
  const [buying, setBuying] = useState(false)
  const [pixOrder, setPixOrder] = useState<Order | null>(null)

  const loadOrders = () => api.get('/prospect/orders').then((r) => setOrders(r.data)).catch(() => {})
  useEffect(() => { loadOrders() }, [])

  const search = () => ({
    cnae: cnae?.code, municipio_code: city?.code, bairro: bairro.trim() || null,
    only_phone: onlyPhone, only_email: onlyEmail, exclude_mei: excludeMei, include_secondary: secondary,
    quantity: parseInt(quantity) > 0 ? parseInt(quantity) : null,
  })

  useEffect(() => { setQuote(null) }, [cnae?.code, city?.code, bairro, onlyPhone, onlyEmail, excludeMei, secondary, quantity])

  async function runQuote() {
    if (!cnae || !city) return
    setLoading(true)
    setError('')
    try { setQuote((await api.post('/prospect/quote', search())).data) } catch (e) {
      setError(apiError(e, t('Não foi possível consultar.', 'Could not search.')))
    } finally { setLoading(false) }
  }

  if (!status.cnpj_available) {
    return (
      <div className="bg-card border border-white/[0.06] rounded-xl p-10 text-center">
        <Building2 size={28} className="mx-auto text-ink-5 mb-3" />
        <p className="text-ink font-medium">{t('A base de empresas ainda não foi carregada.', 'The company database has not been loaded yet.')}</p>
        <p className="text-ink-4 text-sm mt-1">{t('Assim que estiver disponível, a busca aparece aqui.', 'Once it is available, the search shows up here.')}</p>
      </div>
    )
  }

  return (
    <>
      <div className="bg-card border border-white/[0.06] rounded-xl p-5 mb-5">
        <div className="grid sm:grid-cols-2 gap-3 mb-3">
          <Autocomplete
            label={t('Nicho (atividade da empresa)', 'Niche (business activity)')}
            placeholder={t('Ex.: odontológica, academia, restaurante', 'E.g. dental, gym, restaurant')}
            value={cnae} onPick={setCnae}
            fetcher={async (q) => (await api.get('/prospect/cnaes', { params: { q } })).data.map((c: any) => ({ code: c.code, label: `${c.description} (${c.code})` }))}
          />
          <Autocomplete
            label={t('Cidade', 'City')}
            placeholder={t('Ex.: João Pessoa', 'E.g. São Paulo')}
            value={city} onPick={setCity}
            fetcher={async (q) => (await api.get('/prospect/cities', { params: { q } })).data.map((c: any) => ({ code: c.code, label: `${c.name} - ${c.uf}` }))}
          />
        </div>
        <div className="grid sm:grid-cols-2 gap-3 mb-3">
          <div>
            <label className="block text-[11px] text-ink-4 mb-1">{t('Bairro (opcional)', 'Neighborhood (optional)')}</label>
            <input value={bairro} onChange={(e) => setBairro(e.target.value)} className={input} />
          </div>
          <div>
            <label className="block text-[11px] text-ink-4 mb-1">{t(`Quantidade (máx. ${status.max_per_order})`, `Quantity (max ${status.max_per_order})`)}</label>
            <input value={quantity} onChange={(e) => setQuantity(e.target.value.replace(/\D/g, ''))} inputMode="numeric"
              placeholder={t('Todas as disponíveis', 'All available')} className={input} />
          </div>
        </div>
        <div className="flex flex-wrap gap-x-5 gap-y-2 mb-4 text-sm text-ink-2">
          {([
            [onlyPhone, setOnlyPhone, t('Só com telefone', 'Phone only')],
            [onlyEmail, setOnlyEmail, t('Só com e-mail', 'Email only')],
            [excludeMei, setExcludeMei, t('Sem MEI', 'Exclude MEI')],
            [secondary, setSecondary, t('Incluir atividade secundária', 'Include secondary activity')],
          ] as const).map(([v, set, label]) => (
            <label key={label} className="flex items-center gap-2 cursor-pointer">
              <input type="checkbox" checked={v} onChange={(e) => set(e.target.checked)} className="accent-indigo-500" /> {label}
            </label>
          ))}
        </div>
        <button onClick={runQuote} disabled={!cnae || !city || loading}
          className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm font-semibold rounded-lg">
          {loading ? <Loader2 size={15} className="animate-spin" /> : <Search size={15} />}
          {t('Ver quantas empresas', 'See how many companies')}
        </button>
        {error && <p className="text-xs text-red-400 mt-3">{error}</p>}
        <p className="text-[11px] text-ink-5 mt-3 flex items-start gap-1.5">
          <Info size={12} className="mt-0.5 shrink-0" />
          {t(
            `Dados abertos da Receita Federal (${status.reference_month}, ${status.ufs.join(', ')}). Só empresas ativas. As que você já comprou não aparecem de novo.`,
            `Brazilian Federal Revenue open data (${status.reference_month}, ${status.ufs.join(', ')}). Active companies only. Companies you already bought don't show up again.`,
          )}
        </p>
      </div>

      {quote && (
        <div className="bg-card border border-white/[0.06] rounded-xl p-5 mb-5">
          {quote.available === 0 ? (
            <p className="text-sm text-ink-3">{t('Nenhuma empresa nova para essa busca.', 'No new companies for this search.')}</p>
          ) : (
            <>
              <div className="flex flex-wrap items-end justify-between gap-3 mb-4">
                <div>
                  <p className="text-2xl font-semibold text-ink">{quote.quantity} <span className="text-sm font-normal text-ink-4">{t(`de ${quote.available} empresas disponíveis`, `of ${quote.available} available companies`)}</span></p>
                  <p className="text-xs text-ink-4 mt-0.5">
                    {status.free ? t('Grátis para a sua conta.', 'Free for your account.')
                      : t(`${brl(status.price_per_contact)} por empresa · mínimo ${brl(status.min_order)}`, `${brl(status.price_per_contact)} per company · minimum ${brl(status.min_order)}`)}
                  </p>
                </div>
                <button onClick={() => setBuying(true)}
                  className="flex items-center gap-2 px-4 py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-semibold rounded-lg">
                  <QrCode size={15} /> {status.free ? t('Gerar lista', 'Generate list') : t(`Comprar por ${brl(quote.amount)} no Pix`, `Buy for ${brl(quote.amount)} via Pix`)}
                </button>
              </div>
              <p className="text-[11px] uppercase tracking-wide text-ink-5 mb-2">{t('Prévia', 'Preview')}</p>
              <div className="space-y-1.5">
                {quote.preview.map((p, i) => (
                  <div key={i} className="flex flex-wrap items-center gap-x-3 gap-y-0.5 text-xs bg-white/[0.03] border border-white/[0.06] rounded-lg px-3 py-2">
                    <span className="font-medium text-ink">{p.name}</span>
                    {p.bairro && <span className="text-ink-4">{p.bairro}</span>}
                    {p.phone && <span className="text-ink-3">{p.phone}</span>}
                    {p.email && <span className="text-ink-4">{p.email}</span>}
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      )}

      <Orders orders={orders} onOpenPix={setPixOrder} reload={loadOrders} />

      {buying && quote && (
        <BuyDialog
          amount={quote.amount} quantity={quote.quantity} free={status.free}
          payload={search()}
          onClose={() => setBuying(false)}
          onCreated={(o) => { setBuying(false); setQuote(null); loadOrders(); if (o.status === 'pending') setPixOrder(o) }}
        />
      )}
      {pixOrder && <PixDialog order={pixOrder} onClose={() => { setPixOrder(null); loadOrders() }} />}
    </>
  )
}

function BuyDialog({ amount, quantity, free, payload, onClose, onCreated }: {
  amount: number; quantity: number; free: boolean; payload: any; onClose: () => void; onCreated: (o: Order) => void
}) {
  const { t } = useI18n()
  const [name, setName] = useState('')
  const [doc, setDoc] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  async function create() {
    setSaving(true)
    setError('')
    try {
      onCreated((await api.post('/prospect/orders', { ...payload, buyer_name: name, buyer_document: doc })).data)
    } catch (e) {
      setError(apiError(e, t('Não foi possível gerar o pedido.', 'Could not create the order.')))
    } finally { setSaving(false) }
  }

  return (
    <Modal title={free ? t('Gerar lista', 'Generate list') : t('Pagar com Pix', 'Pay with Pix')} onClose={onClose}>
      <p className="text-sm text-ink-3 mb-4">
        {free ? t(`${quantity} empresas, sem custo para a sua conta.`, `${quantity} companies, free for your account.`)
          : t(`${quantity} empresas por ${brl(amount)}. A lista é liberada assim que o Pix for pago.`, `${quantity} companies for ${brl(amount)}. The list is released once the Pix is paid.`)}
      </p>
      <label className="block text-[11px] text-ink-4 mb-1">{t('Nome de quem paga', 'Payer name')}</label>
      <input value={name} onChange={(e) => setName(e.target.value)} className={`${input} mb-3`} />
      <label className="block text-[11px] text-ink-4 mb-1">CPF ou CNPJ</label>
      <input value={doc} onChange={(e) => setDoc(e.target.value)} inputMode="numeric" className={`${input} mb-4`} />
      {error && <p className="text-xs text-red-400 mb-3">{error}</p>}
      <button onClick={create} disabled={saving || name.trim().length < 2 || doc.replace(/\D/g, '').length < 11}
        className="w-full py-2.5 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-sm font-semibold rounded-lg">
        {saving ? t('Gerando…', 'Creating…') : free ? t('Gerar lista', 'Generate list') : t('Gerar Pix', 'Create Pix')}
      </button>
    </Modal>
  )
}

function PixDialog({ order, onClose }: { order: Order; onClose: () => void }) {
  const { t } = useI18n()
  const [current, setCurrent] = useState(order)
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    if (current.status !== 'pending') return
    const id = window.setInterval(async () => {
      try { setCurrent((await api.get(`/prospect/orders/${order.id}`)).data) } catch { /* tenta de novo */ }
    }, 4000)
    return () => window.clearInterval(id)
  }, [current.status, order.id])

  async function copy() {
    if (!current.pix_payload) return
    await navigator.clipboard.writeText(current.pix_payload)
    setCopied(true)
    window.setTimeout(() => setCopied(false), 2000)
  }

  return (
    <Modal title={current.status === 'paid' ? t('Pagamento confirmado', 'Payment confirmed') : t('Pague com Pix', 'Pay with Pix')} onClose={onClose}>
      {current.status === 'paid' ? (
        <div className="text-center">
          <div className="w-12 h-12 rounded-full bg-emerald-500/15 flex items-center justify-center mx-auto mb-3"><Check className="text-emerald-400" /></div>
          <p className="text-sm text-ink-2 mb-4">{t(`Sua lista com ${current.quantity} empresas está liberada.`, `Your list with ${current.quantity} companies is ready.`)}</p>
          <button onClick={() => downloadCsv(current)} className="w-full py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-semibold rounded-lg flex items-center justify-center gap-2">
            <Download size={15} /> {t('Baixar CSV', 'Download CSV')}
          </button>
        </div>
      ) : (
        <>
          <p className="text-sm text-ink-3 mb-3">{t(`${brl(current.amount)} · ${current.quantity} empresas`, `${brl(current.amount)} · ${current.quantity} companies`)}</p>
          {current.pix_image ? (
            <img src={`data:image/png;base64,${current.pix_image}`} alt="QR Code Pix" className="w-56 h-56 mx-auto rounded-lg bg-white p-2 mb-3" />
          ) : current.invoice_url ? (
            <a href={current.invoice_url} target="_blank" rel="noreferrer" className="block text-center text-sm text-indigo-300 underline mb-3">{t('Abrir a cobrança', 'Open the charge')}</a>
          ) : null}
          {current.pix_payload && (
            <button onClick={copy} className="w-full py-2.5 border border-white/[0.1] text-ink-2 hover:text-white text-sm rounded-lg flex items-center justify-center gap-2 mb-3">
              {copied ? <Check size={15} className="text-emerald-400" /> : <Copy size={15} />} {copied ? t('Copiado', 'Copied') : t('Copiar Pix copia e cola', 'Copy Pix code')}
            </button>
          )}
          <p className="text-[11px] text-ink-5 text-center flex items-center justify-center gap-1.5">
            <Loader2 size={12} className="animate-spin" /> {t('Esperando o pagamento. A tela atualiza sozinha.', 'Waiting for payment. This screen updates by itself.')}
          </p>
        </>
      )}
    </Modal>
  )
}

function Orders({ orders, onOpenPix, reload }: { orders: Order[]; onOpenPix: (o: Order) => void; reload: () => void }) {
  const { t } = useI18n()
  const [msg, setMsg] = useState('')
  if (!orders.length) return null

  async function toLeads(o: Order) {
    try {
      const { data } = await api.post(`/prospect/orders/${o.id}/import-leads`)
      setMsg(t(`${data.created} empresas viraram leads (${data.skipped} já existiam ou sem telefone).`, `${data.created} companies added to Leads (${data.skipped} already existed or had no phone).`))
      reload()
    } catch (e) { setMsg(apiError(e, t('Não foi possível puxar para os Leads.', 'Could not add to Leads.'))) }
  }

  const label: Record<Order['status'], string> = {
    pending: t('Aguardando Pix', 'Awaiting Pix'), paid: t('Pago', 'Paid'), canceled: t('Cancelado', 'Canceled'),
  }
  return (
    <div className="bg-card border border-white/[0.06] rounded-xl p-5">
      <h2 className="text-sm font-semibold text-ink mb-3">{t('Suas listas', 'Your lists')}</h2>
      {msg && <p className="text-xs text-emerald-300 mb-3">{msg}</p>}
      <div className="space-y-2">
        {orders.map((o) => (
          <div key={o.id} className="flex flex-wrap items-center gap-3 bg-white/[0.03] border border-white/[0.06] rounded-lg px-3 py-2.5">
            <div className="flex-1 min-w-[200px]">
              <p className="text-sm text-ink">{o.cnae_description} · {o.city}</p>
              <p className="text-[11px] text-ink-4">
                {new Date(o.created_at).toLocaleDateString('pt-BR')} · {o.quantity} {t('empresas', 'companies')} · {brl(o.amount)} ·{' '}
                <span className={o.status === 'paid' ? 'text-emerald-400' : o.status === 'pending' ? 'text-amber-400' : 'text-ink-5'}>{label[o.status]}</span>
              </p>
            </div>
            {o.status === 'paid' ? (
              <div className="flex gap-2">
                <button onClick={() => downloadCsv(o)} className="flex items-center gap-1.5 px-3 py-1.5 bg-indigo-600/20 text-indigo-200 hover:bg-indigo-600/35 text-xs font-medium rounded-lg">
                  <Download size={13} /> CSV
                </button>
                <button onClick={() => toLeads(o)} className="flex items-center gap-1.5 px-3 py-1.5 bg-white/[0.05] text-ink-2 hover:text-white text-xs font-medium rounded-lg">
                  <UserPlus size={13} /> {t('Puxar para Leads', 'Add to Leads')}
                </button>
              </div>
            ) : o.status === 'pending' ? (
              <button onClick={async () => onOpenPix((await api.get(`/prospect/orders/${o.id}`)).data)}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-emerald-600/20 text-emerald-200 hover:bg-emerald-600/35 text-xs font-medium rounded-lg">
                <QrCode size={13} /> {t('Ver Pix', 'View Pix')}
              </button>
            ) : null}
          </div>
        ))}
      </div>
    </div>
  )
}

function MapsTab({ status }: { status: Status }) {
  const { t } = useI18n()
  const [q, setQ] = useState('')
  const [places, setPlaces] = useState<Place[]>([])
  const [next, setNext] = useState<string | null>(null)
  const [used, setUsed] = useState<number | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function run(pageToken?: string) {
    if (q.trim().length < 3) return
    setLoading(true)
    setError('')
    try {
      const { data } = await api.get('/prospect/places', { params: { q: q.trim(), page_token: pageToken } })
      setPlaces((prev) => (pageToken ? [...prev, ...data.places] : data.places))
      setNext(data.next_page_token || null)
      setUsed(data.used_today)
    } catch (e) {
      setError(apiError(e, t('Não foi possível buscar.', 'Could not search.')))
    } finally { setLoading(false) }
  }

  if (!status.maps_enabled) {
    return (
      <div className="bg-card border border-white/[0.06] rounded-xl p-10 text-center">
        <MapPin size={28} className="mx-auto text-ink-5 mb-3" />
        <p className="text-ink font-medium">{t('A busca no Google Maps ainda não está ativa.', 'Google Maps search is not active yet.')}</p>
        <p className="text-ink-4 text-sm mt-1">{t('Use a lista por CNPJ enquanto isso.', 'Use the CNPJ list in the meantime.')}</p>
      </div>
    )
  }

  const wa = (p: Place) => {
    const d = (p.phone_intl || '').replace(/\D/g, '')
    return d.startsWith('55') && d.length === 13 ? `https://wa.me/${d}` : null
  }

  return (
    <>
      <div className="bg-card border border-white/[0.06] rounded-xl p-5 mb-5">
        <div className="flex gap-2">
          <input value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && run()}
            placeholder={t('Ex.: dentista em João Pessoa', 'E.g. dentist in São Paulo')} className={input} />
          <button onClick={() => run()} disabled={loading || q.trim().length < 3}
            className="shrink-0 flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm font-semibold rounded-lg">
            {loading ? <Loader2 size={15} className="animate-spin" /> : <Search size={15} />} {t('Buscar', 'Search')}
          </button>
        </div>
        {error && <p className="text-xs text-red-400 mt-3">{error}</p>}
        <p className="text-[11px] text-ink-5 mt-3 flex items-start gap-1.5">
          <Info size={12} className="mt-0.5 shrink-0" />
          {t(
            `Consulta dentro do app: as regras do Google não permitem salvar nem exportar estes resultados. ${used ?? 0} de ${status.maps_searches_per_day} buscas hoje.`,
            `In-app lookup only: Google's terms don't allow saving or exporting these results. ${used ?? 0} of ${status.maps_searches_per_day} searches today.`,
          )}
        </p>
      </div>

      <div className="grid sm:grid-cols-2 gap-3">
        {places.map((p) => (
          <div key={p.id} className="bg-card border border-white/[0.06] rounded-xl p-4">
            <p className="text-sm font-semibold text-ink">{p.name}</p>
            {p.address && <p className="text-xs text-ink-4 mt-0.5">{p.address}</p>}
            {p.rating != null && (
              <p className="text-xs text-amber-300 mt-1 flex items-center gap-1"><Star size={12} fill="currentColor" /> {p.rating} <span className="text-ink-5">({p.reviews ?? 0})</span></p>
            )}
            <div className="flex flex-wrap gap-2 mt-3">
              {p.phone && <a href={`tel:${p.phone_intl || p.phone}`} className="flex items-center gap-1 px-2.5 py-1 bg-white/[0.05] text-ink-2 hover:text-white text-xs rounded-lg"><Phone size={12} /> {p.phone}</a>}
              {wa(p) && <a href={wa(p)!} target="_blank" rel="noreferrer" className="px-2.5 py-1 bg-emerald-600/15 text-emerald-300 hover:bg-emerald-600/30 text-xs rounded-lg">WhatsApp</a>}
              {p.website && <a href={p.website} target="_blank" rel="noreferrer" className="flex items-center gap-1 px-2.5 py-1 bg-white/[0.05] text-ink-2 hover:text-white text-xs rounded-lg"><Globe size={12} /> Site</a>}
              {p.maps_url && <a href={p.maps_url} target="_blank" rel="noreferrer" className="flex items-center gap-1 px-2.5 py-1 bg-white/[0.05] text-ink-2 hover:text-white text-xs rounded-lg"><ExternalLink size={12} /> {t('Abrir no Maps', 'Open in Maps')}</a>}
            </div>
          </div>
        ))}
      </div>
      {places.length > 0 && <p className="text-[10px] text-ink-5 mt-3">{t('Dados do Google Maps', 'Data from Google Maps')}</p>}
      {next && (
        <button onClick={() => run(next)} disabled={loading} className="mt-4 px-4 py-2 border border-white/[0.08] text-ink-3 hover:text-white text-sm rounded-lg">
          {t('Mais resultados', 'More results')}
        </button>
      )}
    </>
  )
}

function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center max-lg:[align-items:safe_center] max-lg:overflow-y-auto max-lg:py-4 bg-black/70 backdrop-blur-sm px-4">
      <div className="bg-card border border-white/[0.08] rounded-2xl p-6 w-full max-w-sm max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-base font-semibold text-white">{title}</h3>
          <button onClick={onClose} aria-label="Fechar" className="text-ink-5 hover:text-ink-3"><X size={18} /></button>
        </div>
        {children}
      </div>
    </div>
  )
}
