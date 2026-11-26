import { useEffect, useRef, useState } from 'react'
import { X, MessageCircle, MousePointerClick, Megaphone, Search, Check, ChevronLeft, Loader2, Image as ImageIcon, Video, Camera, Newspaper } from 'lucide-react'
import api, { apiError } from '../services/api'
import { useI18n } from '../i18n'
import { makeFormat } from '../utils/format'
import { parseAmount } from './SaleDialog'

type Goal = 'whatsapp' | 'traffic' | 'reach'
type Kind = 'image' | 'video' | 'post' | 'page_post'

interface Option { id: string; name: string; type?: string | null; audience_size?: number | null }
interface IgPost { id: string; caption: string | null; thumbnail_url: string | null }
interface PagePost { id: string; message: string | null; picture_url: string | null }

const input = 'w-full px-3 py-2 bg-field border border-white/[0.08] text-ink text-sm rounded-lg focus:border-indigo-500 focus:outline-none placeholder-ink-5'
const STEP_OF: Record<string, number> = { campaign: 0, audience: 1, budget: 1, creative: 2 }

function SearchPicker({ label, endpoint, selected, onAdd, onRemove, describe }: {
  label: string
  endpoint: string
  selected: Option[]
  onAdd: (o: Option) => void
  onRemove: (id: string) => void
  describe?: (o: Option) => string
}) {
  const { t } = useI18n()
  const [q, setQ] = useState('')
  const [results, setResults] = useState<Option[]>([])
  const timer = useRef<number | undefined>(undefined)
  useEffect(() => {
    window.clearTimeout(timer.current)
    if (q.trim().length < 2) { setResults([]); return }
    timer.current = window.setTimeout(async () => {
      try { setResults((await api.get<Option[]>(endpoint, { params: { q: q.trim() } })).data) } catch { setResults([]) }
    }, 300)
  }, [q, endpoint])
  return (
    <div>
      <label className="block text-[11px] text-ink-4 mb-1">{label}</label>
      <div className="relative">
        <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-5" />
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder={t('Digite para buscar…', 'Type to search…')} className={`${input} pl-8`} />
      </div>
      {results.length > 0 && (
        <div className="mt-1 bg-field border border-white/[0.08] rounded-lg max-h-40 overflow-y-auto">
          {results.map((r) => (
            <button key={r.id} type="button" onClick={() => { onAdd(r); setQ(''); setResults([]) }}
              className="w-full text-left px-3 py-1.5 text-xs text-ink-2 hover:bg-white/[0.05] flex justify-between gap-2">
              <span className="truncate">{r.name}</span>
              <span className="text-ink-5 shrink-0">{describe?.(r)}</span>
            </button>
          ))}
        </div>
      )}
      {selected.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mt-2">
          {selected.map((s) => (
            <span key={s.id} className="flex items-center gap-1 bg-indigo-600/15 border border-indigo-500/30 text-indigo-200 text-[11px] px-2 py-1 rounded-full">
              {s.name}
              <button type="button" onClick={() => onRemove(s.id)} className="hover:text-white"><X size={11} /></button>
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

export default function CampaignWizard({ currency, onClose, onCreated }: {
  currency: string
  onClose: () => void
  onCreated: (campaignId: string) => void
}) {
  const { t, locale } = useI18n()
  const fmt = makeFormat(locale, currency)
  const [step, setStep] = useState(0)
  const [goal, setGoal] = useState<Goal>('whatsapp')
  const [name, setName] = useState('')
  const [specialCategory, setSpecialCategory] = useState('NONE')
  const [locations, setLocations] = useState<Option[]>([{ id: 'BR', name: 'Brasil', type: 'country' }])
  const [ageMin, setAgeMin] = useState(18)
  const [ageMax, setAgeMax] = useState(65)
  const [gender, setGender] = useState<'all' | 'female' | 'male'>('all')
  const [interests, setInterests] = useState<Option[]>([])
  const [budget, setBudget] = useState('30,00')
  const [endDate, setEndDate] = useState('')
  const [kind, setKind] = useState<Kind>('image')
  const [message, setMessage] = useState('')
  const [headline, setHeadline] = useState('')
  const [imageUrl, setImageUrl] = useState('')
  const [videoFile, setVideoFile] = useState<File | null>(null)
  const [link, setLink] = useState('')
  const [welcome, setWelcome] = useState(t('Olá! Vi o anúncio e quero saber mais.', 'Hi! I saw the ad and want to know more.'))
  const [igPosts, setIgPosts] = useState<IgPost[] | null>(null)
  const [pagePosts, setPagePosts] = useState<PagePost[] | null>(null)
  const [postId, setPostId] = useState('')
  const [submitting, setSubmitting] = useState<string | null>(null)
  const [error, setError] = useState('')

  const goals: { id: Goal; icon: typeof MessageCircle; title: string; desc: string }[] = [
    { id: 'whatsapp', icon: MessageCircle, title: t('Conversas no WhatsApp', 'WhatsApp conversations'), desc: t('Quem clica abre uma conversa com você. A conversa cai no painel, marcada com o anúncio.', 'People who click open a chat with you. It lands in the inbox, tagged with the ad.') },
    { id: 'traffic', icon: MousePointerClick, title: t('Visitas ao site', 'Website visits'), desc: t('Leva as pessoas para um link: site, loja ou página de vendas.', 'Sends people to a link: website, store or sales page.') },
    { id: 'reach', icon: Megaphone, title: t('Alcance', 'Reach'), desc: t('Mostra o anúncio para o maior número de pessoas da região.', 'Shows the ad to as many people in the area as possible.') },
  ]
  const kinds: { id: Kind; icon: typeof ImageIcon; label: string }[] = [
    { id: 'image', icon: ImageIcon, label: t('Imagem', 'Image') },
    { id: 'video', icon: Video, label: t('Vídeo', 'Video') },
    ...(goal !== 'whatsapp' ? [
      { id: 'post' as Kind, icon: Camera, label: t('Post do Instagram', 'Instagram post') },
      { id: 'page_post' as Kind, icon: Newspaper, label: t('Post da Página', 'Page post') },
    ] : []),
  ]

  useEffect(() => { if (goal === 'whatsapp' && (kind === 'post' || kind === 'page_post')) setKind('image') }, [goal])
  useEffect(() => {
    setPostId('')
    if (kind === 'post' && igPosts === null) api.get<IgPost[]>('/marketing/instagram-posts').then(({ data }) => setIgPosts(data)).catch(() => setIgPosts([]))
    if (kind === 'page_post' && pagePosts === null) api.get<PagePost[]>('/marketing/page-posts').then(({ data }) => setPagePosts(data)).catch(() => setPagePosts([]))
  }, [kind])

  const budgetValue = parseAmount(budget)
  const needsLink = goal === 'traffic' && kind !== 'page_post' || kind === 'post'
  const validStep = [
    name.trim().length > 0,
    locations.length > 0 && ageMin <= ageMax && budgetValue >= 5,
    (kind === 'image' ? !!imageUrl.trim() && !!message.trim()
      : kind === 'video' ? !!videoFile && !!message.trim()
      : !!postId) && (!needsLink || /^https?:\/\//.test(link.trim())),
    true,
  ]

  const genderLabel = { all: t('Todos', 'All'), female: t('Mulheres', 'Women'), male: t('Homens', 'Men') }[gender]
  const goalTitle = goals.find((g) => g.id === goal)!.title

  async function submit(publish: boolean) {
    setError('')
    try {
      let video_id: string | undefined
      if (kind === 'video' && videoFile) {
        setSubmitting(t('Enviando o vídeo…', 'Uploading the video…'))
        const form = new FormData()
        form.append('file', videoFile)
        video_id = (await api.post('/marketing/videos/upload', form, { headers: { 'Content-Type': 'multipart/form-data' } })).data.video_id
      }
      setSubmitting(t('Criando a campanha na Meta…', 'Creating the campaign at Meta…'))
      const creative: Record<string, unknown> = { name: name.trim(), message: message.trim() }
      if (kind === 'image') creative.image_url = imageUrl.trim()
      if (kind === 'video') creative.video_id = video_id
      if (kind === 'post') creative.source_instagram_media_id = postId
      if (kind === 'page_post') creative.source_page_post_id = postId
      if (link.trim() && goal !== 'whatsapp') creative.link_url = link.trim()
      const { data } = await api.post('/marketing/quick-campaign', {
        name: name.trim(),
        goal,
        special_ad_category: specialCategory,
        daily_budget_cents: Math.round(budgetValue * 100),
        end_date: endDate || null,
        targeting: {
          age_min: ageMin, age_max: ageMax,
          genders: gender === 'all' ? null : gender === 'male' ? [1] : [2],
          locations: locations.map((l) => ({ key: l.id, type: l.type || 'country' })),
          interest_ids: interests.map((i) => i.id),
        },
        creative,
        headline: headline.trim() || null,
        welcome_message: goal === 'whatsapp' ? welcome.trim() || null : null,
        publish,
      })
      onCreated(data.campaign_id)
    } catch (e: any) {
      const detail = e?.response?.data?.detail
      if (detail?.step in STEP_OF) setStep(STEP_OF[detail.step])
      setError(apiError(e, t('Não foi possível criar a campanha.', 'Could not create the campaign.')))
    } finally {
      setSubmitting(null)
    }
  }

  const steps = [t('Objetivo', 'Goal'), t('Público e orçamento', 'Audience & budget'), t('Anúncio', 'Ad'), t('Revisão', 'Review')]

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center max-lg:[align-items:safe_center] max-lg:overflow-y-auto max-lg:py-4 bg-black/70 backdrop-blur-sm px-4">
      <div className="bg-card border border-white/[0.08] rounded-2xl w-full max-w-xl max-h-[92vh] overflow-y-auto">
        <div className="flex items-center justify-between px-6 pt-5">
          <h3 className="text-lg font-bold text-white">{t('Nova campanha', 'New campaign')}</h3>
          <button onClick={onClose} aria-label={t('Fechar', 'Close')} className="text-ink-5 hover:text-ink-3"><X size={18} /></button>
        </div>
        <ol className="flex gap-1 px-6 mt-3">
          {steps.map((s, i) => (
            <li key={s} className="flex-1">
              <div className={`h-1 rounded-full ${i <= step ? 'bg-indigo-500' : 'bg-white/[0.08]'}`} />
              <p className={`text-[10px] mt-1 ${i === step ? 'text-ink-2' : 'text-ink-5'} max-sm:hidden`}>{i + 1}. {s}</p>
            </li>
          ))}
        </ol>

        <div className="px-6 py-5 space-y-4">
          {step === 0 && (
            <>
              <div className="space-y-2">
                {goals.map((g) => {
                  const Icon = g.icon
                  return (
                    <button key={g.id} type="button" onClick={() => setGoal(g.id)}
                      className={`w-full text-left flex gap-3 p-3 rounded-xl border transition-colors ${goal === g.id ? 'border-indigo-500/60 bg-indigo-600/10' : 'border-white/[0.08] hover:border-white/[0.16]'}`}>
                      <Icon size={18} className={goal === g.id ? 'text-indigo-300 mt-0.5' : 'text-ink-4 mt-0.5'} />
                      <span>
                        <span className="block text-sm font-semibold text-ink">{g.title}{g.id === 'whatsapp' && <span className="ml-2 text-[10px] font-medium text-emerald-300">{t('recomendado', 'recommended')}</span>}</span>
                        <span className="block text-xs text-ink-4 mt-0.5">{g.desc}</span>
                      </span>
                    </button>
                  )
                })}
              </div>
              {goal === 'whatsapp' && (
                <p className="text-[11px] text-amber-200/90 bg-amber-900/15 border border-amber-500/20 rounded-lg px-3 py-2">
                  {t('A Página do Facebook escolhida em Anúncios precisa estar ligada ao número do WhatsApp (nas configurações da Página → WhatsApp).', 'The Facebook Page chosen in Ads must be linked to the WhatsApp number (Page settings → WhatsApp).')}
                </p>
              )}
              <div>
                <label className="block text-[11px] text-ink-4 mb-1">{t('Nome da campanha', 'Campaign name')}</label>
                <input value={name} onChange={(e) => setName(e.target.value)} placeholder={t('Ex.: Clareamento — Dezembro', 'E.g. Whitening — December')} className={input} />
              </div>
              <details className="text-xs text-ink-4">
                <summary className="cursor-pointer">{t('O anúncio fala de crédito, emprego, imóveis, política ou apostas?', 'Is the ad about credit, jobs, housing, politics or gambling?')}</summary>
                <select value={specialCategory} onChange={(e) => setSpecialCategory(e.target.value)} className={`${input} mt-2`}>
                  <option value="NONE">{t('Não', 'No')}</option>
                  <option value="FINANCIAL_PRODUCTS_SERVICES">{t('Produtos e serviços financeiros (crédito)', 'Financial products and services (credit)')}</option>
                  <option value="EMPLOYMENT">{t('Emprego', 'Employment')}</option>
                  <option value="HOUSING">{t('Imóveis / moradia', 'Housing')}</option>
                  <option value="ISSUES_ELECTIONS_POLITICS">{t('Temas sociais, eleições ou política', 'Social issues, elections or politics')}</option>
                  <option value="ONLINE_GAMBLING_AND_GAMING">{t('Jogos de azar online', 'Online gambling and gaming')}</option>
                </select>
                <p className="mt-1">{t('A Meta exige declarar esses temas e limita a segmentação deles.', 'Meta requires declaring these topics and limits their targeting.')}</p>
              </details>
            </>
          )}

          {step === 1 && (
            <>
              <SearchPicker label={t('Onde mostrar (cidades, estados ou países)', 'Where to show (cities, states or countries)')} endpoint="/marketing/targeting/locations"
                selected={locations} onAdd={(o) => setLocations((p) => p.some((x) => x.id === o.id) ? p : [...p.filter((x) => !(x.id === 'BR' && o.type !== 'country')), o])}
                onRemove={(id) => setLocations((p) => p.filter((x) => x.id !== id))}
                describe={(o) => o.type === 'city' ? t('cidade', 'city') : o.type === 'region' ? t('estado', 'state') : t('país', 'country')} />
              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="block text-[11px] text-ink-4 mb-1">{t('Idade mínima', 'Min age')}</label>
                  <input type="number" min={18} max={65} value={ageMin} onChange={(e) => setAgeMin(Number(e.target.value))} className={input} />
                </div>
                <div>
                  <label className="block text-[11px] text-ink-4 mb-1">{t('Idade máxima', 'Max age')}</label>
                  <input type="number" min={18} max={65} value={ageMax} onChange={(e) => setAgeMax(Number(e.target.value))} className={input} />
                </div>
                <div>
                  <label className="block text-[11px] text-ink-4 mb-1">{t('Gênero', 'Gender')}</label>
                  <select value={gender} onChange={(e) => setGender(e.target.value as typeof gender)} className={input}>
                    <option value="all">{t('Todos', 'All')}</option>
                    <option value="female">{t('Mulheres', 'Women')}</option>
                    <option value="male">{t('Homens', 'Men')}</option>
                  </select>
                </div>
              </div>
              <SearchPicker label={t('Interesses (opcional)', 'Interests (optional)')} endpoint="/marketing/targeting/interests"
                selected={interests} onAdd={(o) => setInterests((p) => p.some((x) => x.id === o.id) ? p : [...p, o])}
                onRemove={(id) => setInterests((p) => p.filter((x) => x.id !== id))}
                describe={(o) => (o.audience_size ? fmt.int(o.audience_size) : '')} />
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[11px] text-ink-4 mb-1">{t('Orçamento por dia', 'Daily budget')}</label>
                  <input value={budget} onChange={(e) => setBudget(e.target.value)} inputMode="decimal" className={input} />
                  <p className="text-[10px] text-ink-5 mt-1">
                    {budgetValue >= 5 ? t(`Cerca de ${fmt.money(budgetValue * 30)} por mês`, `About ${fmt.money(budgetValue * 30)} per month`) : t('Mínimo de 5 por dia', 'Minimum of 5 per day')}
                  </p>
                </div>
                <div>
                  <label className="block text-[11px] text-ink-4 mb-1">{t('Termina em (opcional)', 'Ends on (optional)')}</label>
                  <input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} className={input} />
                  <p className="text-[10px] text-ink-5 mt-1">{t('Vazio: roda até você pausar.', 'Empty: runs until you pause it.')}</p>
                </div>
              </div>
            </>
          )}

          {step === 2 && (
            <>
              <div className="flex flex-wrap gap-2">
                {kinds.map((k) => {
                  const Icon = k.icon
                  return (
                    <button key={k.id} type="button" onClick={() => setKind(k.id)}
                      className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border ${kind === k.id ? 'border-indigo-500/60 bg-indigo-600/15 text-indigo-200' : 'border-white/[0.08] text-ink-3'}`}>
                      <Icon size={13} />{k.label}
                    </button>
                  )
                })}
              </div>
              {kind === 'image' && (
                <div>
                  <label className="block text-[11px] text-ink-4 mb-1">{t('Link público da imagem', 'Public image link')}</label>
                  <input value={imageUrl} onChange={(e) => setImageUrl(e.target.value)} placeholder="https://…/imagem.jpg" className={input} />
                </div>
              )}
              {kind === 'video' && (
                <div>
                  <label className="block text-[11px] text-ink-4 mb-1">{t('Arquivo de vídeo', 'Video file')}</label>
                  <input type="file" accept="video/*" onChange={(e) => setVideoFile(e.target.files?.[0] ?? null)} className="text-xs text-ink-3" />
                </div>
              )}
              {(kind === 'post' || kind === 'page_post') && (
                <div className="grid grid-cols-3 gap-2 max-h-56 overflow-y-auto">
                  {(kind === 'post' ? igPosts : pagePosts) === null ? (
                    <p className="col-span-3 text-xs text-ink-4">{t('Carregando…', 'Loading…')}</p>
                  ) : ((kind === 'post' ? igPosts : pagePosts) ?? []).length === 0 ? (
                    <p className="col-span-3 text-xs text-ink-4">{t('Nenhum post encontrado.', 'No posts found.')}</p>
                  ) : (kind === 'post' ? (igPosts ?? []).map((p) => ({ id: p.id, img: p.thumbnail_url, text: p.caption }))
                    : (pagePosts ?? []).map((p) => ({ id: p.id, img: p.picture_url, text: p.message }))).map((p) => (
                    <button key={p.id} type="button" onClick={() => setPostId(p.id)}
                      className={`relative rounded-lg overflow-hidden border-2 text-left ${postId === p.id ? 'border-indigo-500' : 'border-transparent'}`}>
                      {p.img ? <img src={p.img} alt="" className="w-full aspect-square object-cover" /> : <div className="w-full aspect-square bg-white/[0.04]" />}
                      <p className="text-[10px] text-ink-3 p-1 line-clamp-2">{p.text || '—'}</p>
                      {postId === p.id && <Check size={14} className="absolute top-1 right-1 text-white bg-indigo-600 rounded-full p-0.5" />}
                    </button>
                  ))}
                </div>
              )}
              {kind !== 'page_post' && kind !== 'post' && (
                <>
                  <div>
                    <label className="block text-[11px] text-ink-4 mb-1">{t('Texto do anúncio', 'Ad text')}</label>
                    <textarea value={message} onChange={(e) => setMessage(e.target.value)} rows={3}
                      placeholder={t('Ex.: Clareamento em 1 sessão. Agende sua avaliação gratuita!', 'E.g. Whitening in 1 session. Book your free assessment!')} className={input} />
                  </div>
                  <div>
                    <label className="block text-[11px] text-ink-4 mb-1">{t('Título (opcional)', 'Headline (optional)')}</label>
                    <input value={headline} onChange={(e) => setHeadline(e.target.value)} maxLength={100} className={input} />
                  </div>
                </>
              )}
              {(needsLink || (goal === 'reach' && kind !== 'page_post')) && (
                <div>
                  <label className="block text-[11px] text-ink-4 mb-1">{t('Link de destino', 'Destination link')}{!needsLink && ` ${t('(opcional)', '(optional)')}`}</label>
                  <input value={link} onChange={(e) => setLink(e.target.value)} placeholder="https://" className={input} />
                </div>
              )}
              {goal === 'whatsapp' && (
                <div>
                  <label className="block text-[11px] text-ink-4 mb-1">{t('Mensagem que o cliente envia ao clicar', 'Message the customer sends when they click')}</label>
                  <input value={welcome} onChange={(e) => setWelcome(e.target.value)} maxLength={300} className={input} />
                  <p className="text-[10px] text-ink-5 mt-1">{t('Ela já aparece escrita no WhatsApp; a pessoa só toca em enviar.', 'It shows up pre-typed in WhatsApp; the person just taps send.')}</p>
                </div>
              )}
            </>
          )}

          {step === 3 && (
            <dl className="text-sm space-y-2">
              {[
                [t('Campanha', 'Campaign'), name],
                [t('Objetivo', 'Goal'), goalTitle],
                [t('Onde', 'Where'), locations.map((l) => l.name).join(', ')],
                [t('Quem', 'Who'), `${genderLabel}, ${ageMin}–${ageMax} ${t('anos', 'years')}${interests.length ? ` · ${interests.map((i) => i.name).join(', ')}` : ''}`],
                [t('Orçamento', 'Budget'), `${fmt.money(budgetValue)}${t('/dia', '/day')}${endDate ? ` · ${t('até', 'until')} ${new Date(`${endDate}T12:00:00`).toLocaleDateString(locale)}` : ''}`],
                [t('Anúncio', 'Ad'), kinds.find((k) => k.id === kind)?.label ?? ''],
                ...(message.trim() && kind !== 'post' && kind !== 'page_post' ? [[t('Texto', 'Text'), message.trim()]] : []),
                ...(goal === 'whatsapp' && welcome.trim() ? [[t('Mensagem no WhatsApp', 'WhatsApp message'), welcome.trim()]] : []),
                ...(link.trim() && goal !== 'whatsapp' ? [[t('Link', 'Link'), link.trim()]] : []),
              ].map(([k, v]) => (
                <div key={k} className="grid grid-cols-[110px_1fr] gap-2">
                  <dt className="text-ink-4 text-xs pt-0.5">{k}</dt>
                  <dd className="text-ink break-words">{v}</dd>
                </div>
              ))}
              <p className="text-[11px] text-ink-4 pt-2">
                {t('Ao publicar, a Meta analisa o anúncio antes de começar a veicular (normalmente em algumas horas). A cobrança é feita pela Meta na sua conta de anúncios.', 'Once published, Meta reviews the ad before it starts delivering (usually within a few hours). Meta charges your ad account.')}
              </p>
            </dl>
          )}

          {error && <p className="text-xs text-red-400 bg-red-900/15 border border-red-500/20 rounded-lg px-3 py-2">{error}</p>}
        </div>

        <div className="flex gap-2 px-6 pb-6">
          {step > 0 && (
            <button type="button" onClick={() => setStep(step - 1)} disabled={!!submitting}
              className="flex items-center gap-1 px-4 py-2.5 border border-white/[0.08] text-ink-3 hover:text-white text-sm rounded-lg">
              <ChevronLeft size={15} />{t('Voltar', 'Back')}
            </button>
          )}
          {step < 3 ? (
            <button type="button" onClick={() => { setError(''); setStep(step + 1) }} disabled={!validStep[step]}
              className="flex-1 py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 text-white text-sm font-semibold rounded-lg">
              {t('Continuar', 'Continue')}
            </button>
          ) : submitting ? (
            <p className="flex-1 flex items-center justify-center gap-2 text-sm text-ink-3"><Loader2 size={15} className="animate-spin" />{submitting}</p>
          ) : (
            <>
              <button type="button" onClick={() => submit(false)} className="flex-1 py-2.5 border border-white/[0.12] text-ink-2 hover:text-white text-sm font-medium rounded-lg">
                {t('Criar pausada', 'Create paused')}
              </button>
              <button type="button" onClick={() => submit(true)} className="flex-1 py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-semibold rounded-lg">
                {t('Criar e publicar', 'Create and publish')}
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
