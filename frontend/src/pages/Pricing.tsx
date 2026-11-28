import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Check, Copy, Loader2, X, Sparkles, Bot, Repeat } from 'lucide-react'
import api, { apiError } from '../services/api'
import { useI18n, LanguageToggle } from '../i18n'
import HelpLink from '../components/HelpLink'
import LegalEntity from '../components/LegalEntity'
import AIPackDialog from '../components/AIPackDialog'
import { makeFormat } from '../utils/format'

export interface Plan {
  code: string
  name: string
  description: string | null
  price_cents: number
  limits: { users?: number | null; clients?: number | null; ai_tokens?: number | null; scheduled_posts?: number | null; storage_mb?: number | null; automations?: number | null }
  modules: string[]
  extras: string[]
  highlight: boolean
  ai_conversations: number | null
  tokens_per_conversation: number
}

interface Pending {
  payment_id: string
  value: number
  due_date: string
  invoice_url: string | null
  pix_payload: string | null
  pix_image: string | null
  auto_debit: boolean
}

type PixAutomatic = 'CREATED' | 'ACTIVE' | 'CANCELLED' | 'EXPIRED' | 'REFUSED' | 'DISABLED'

interface Status {
  status: 'unmanaged' | 'courtesy' | 'trial' | 'active' | 'past_due' | 'canceled' | 'blocked'
  allowed: boolean
  enforced: boolean
  until: string | null
  days_left: number | null
  plan: string | null
  plan_name: string | null
  subscribed: boolean
  pending: Pending | null
  is_child: boolean
  trial_days: number
  pix_automatic: PixAutomatic | null
}

type T = (pt: string, en: string) => string

/** O que o plano inclui, montado a partir dos limites e módulos (traduzível). */
export function planFeatures(t: T, fmt: ReturnType<typeof makeFormat>, p: Plan): string[] {
  const out: string[] = []
  const users = p.limits.users
  out.push(users == null ? t('Usuários ilimitados', 'Unlimited users')
    : users === 1 ? t('1 usuário', '1 user') : t(`Até ${users} usuários`, `Up to ${users} users`))
  const clients = p.limits.clients
  if (clients == null) out.push(t('Empresas clientes ilimitadas', 'Unlimited client companies'))
  else if (clients > 0) out.push(t(`Até ${clients} empresas clientes`, `Up to ${clients} client companies`))
  if (p.modules.includes('whatsapp')) out.push(t('WhatsApp: atendimento, disparos, follow-ups e ligações', 'WhatsApp: inbox, broadcasts, follow-ups and calls'))
  if (p.modules.includes('instagram')) {
    out.push(t('Instagram: Direct, comentários e posts', 'Instagram: Direct, comments and posts'))
    const posts = p.limits.scheduled_posts
    const autos = p.limits.automations
    if (posts != null) out.push(t(`Até ${posts} posts agendados por vez`, `Up to ${posts} scheduled posts at a time`))
    if (autos != null) out.push(t(`Até ${autos} automações de Instagram ativas`, `Up to ${autos} active Instagram automations`))
  }
  if (p.modules.includes('ads')) out.push(t('Anúncios: diagnóstico e retorno por venda', 'Ads: diagnosis and return per sale'))
  if (p.modules.includes('ia')) {
    out.push(p.ai_conversations == null
      ? t('IA que responde no WhatsApp, sem limite de atendimentos', 'AI that replies on WhatsApp, unlimited conversations')
      : t(`IA que responde no WhatsApp: até ${fmt.int(p.ai_conversations)} atendimentos por mês`, `AI that replies on WhatsApp: up to ${fmt.int(p.ai_conversations)} conversations a month`))
  }
  return [...out, ...p.extras]
}

export default function Pricing({ embedded = false }: { embedded?: boolean }) {
  const { t, locale } = useI18n()
  const navigate = useNavigate()
  const fmt = makeFormat(locale, 'BRL')
  const logged = !!localStorage.getItem('access_token')
  const [plans, setPlans] = useState<Plan[] | null>(null)
  const [status, setStatus] = useState<Status | null>(null)
  const [buying, setBuying] = useState<Plan | null>(null)
  const [error, setError] = useState('')
  const [canceling, setCanceling] = useState(false)
  const [pack, setPack] = useState<{ conversations: number; price_cents: number } | null>(null)
  const [showPack, setShowPack] = useState(false)

  useEffect(() => {
    if (!embedded || !logged) return
    api.get('/billing/ai-pack').then(({ data }) => {
      if (!data?.is_child) setPack({ conversations: data.conversations, price_cents: data.price_cents })
    }).catch(() => {})
  }, [embedded, logged])

  const loadStatus = useCallback(async () => {
    if (!logged || !embedded) return
    try { setStatus((await api.get<Status>('/billing/status')).data) } catch { /* sem status */ }
  }, [logged, embedded])

  useEffect(() => {
    api.get<Plan[]>('/billing/plans').then(({ data }) => setPlans(data)).catch(() => setPlans([]))
    loadStatus()
  }, [loadStatus])

  // Enquanto há cobrança para pagar aqui, confere o pagamento a cada 5 s (débito automático não).
  useEffect(() => {
    if (!status?.pending || status.pending.auto_debit) return
    const id = window.setInterval(loadStatus, 5000)
    return () => window.clearInterval(id)
  }, [status?.pending?.payment_id, status?.pending?.auto_debit, loadStatus])

  async function cancel() {
    if (!confirm(t('Cancelar a renovação? O acesso continua até o fim do período pago.', 'Cancel renewal? Access continues until the end of the paid period.'))) return
    setCanceling(true)
    setError('')
    try { setStatus((await api.post<Status>('/billing/cancel')).data) } catch (e) {
      setError(apiError(e, t('Não foi possível cancelar.', 'Could not cancel.')))
    } finally { setCanceling(false) }
  }

  // Vencimento do Asaas vem só com a data (AAAA-MM-DD): lido como UTC, mostraria o dia anterior no Brasil.
  const date = (iso: string | null) =>
    iso ? new Date(/^\d{4}-\d{2}-\d{2}$/.test(iso) ? `${iso}T12:00:00` : iso).toLocaleDateString(locale) : ''
  const isCurrent = (p: Plan) => !!status && status.plan === p.code && ['active', 'past_due', 'trial', 'courtesy'].includes(status.status)
  const canBuy = embedded && status && !status.is_child

  return (
    <div className={embedded ? '' : 'min-h-screen bg-canvas py-12 px-4'}>
      <div className="max-w-6xl mx-auto">
        {!embedded && (
          <div className="flex justify-between items-center mb-8">
            <Link to="/" className="text-sm text-ink-4 hover:text-white">← {t('Página inicial', 'Home page')}</Link>
            <LanguageToggle compact />
          </div>
        )}
        <div className={embedded ? 'mb-6' : 'text-center mb-10'}>
          <h1 className={embedded ? 'text-2xl font-semibold text-white' : 'text-4xl font-bold text-white'}>{t('Planos e Preços', 'Plans & Pricing')}</h1>
          <p className="text-ink-4 mt-2">
            {t(`Teste grátis por ${status?.trial_days ?? 7} dias, sem cartão. Depois, pagamento mensal por Pix, boleto ou cartão.`, `${status?.trial_days ?? 7}-day free trial, no card. Then monthly payment by Pix, bank slip or card.`)}
          </p>
          {embedded && <HelpLink section="planos" className="mt-2" />}
        </div>

        {embedded && status && status.status !== 'unmanaged' && (
          <StatusCard status={status} date={date} canceling={canceling} onCancel={cancel} fmt={fmt} />
        )}
        {error && <p className="text-sm text-red-400 mb-4">{error}</p>}

        {plans === null ? (
          <p className="text-ink-4 text-sm">{t('Carregando planos...', 'Loading plans...')}</p>
        ) : (
          <div className="grid md:grid-cols-3 gap-5">
            {plans.map((p) => (
              <div key={p.code} className={`relative rounded-2xl border p-6 flex flex-col ${p.highlight ? 'border-violet-500/60 bg-violet-950/20' : 'border-white/[0.08] bg-card'}`}>
                {p.highlight && (
                  <span className="absolute -top-3 left-6 flex items-center gap-1 bg-violet-600 text-white text-[11px] font-semibold px-2.5 py-1 rounded-full">
                    <Sparkles size={11} />{t('Mais escolhido', 'Most popular')}
                  </span>
                )}
                <h3 className="text-xl font-bold text-white">{p.name}</h3>
                {p.description && <p className="text-sm text-ink-4 mt-1 min-h-[40px]">{p.description}</p>}
                <p className="mt-4">
                  <span className="text-3xl font-bold text-white">{fmt.money(p.price_cents / 100)}</span>
                  <span className="text-ink-4 text-sm">{t('/mês', '/month')}</span>
                </p>
                <ul className="mt-5 space-y-2 flex-1">
                  {planFeatures(t, fmt, p).map((f) => (
                    <li key={f} className="flex gap-2 text-sm text-ink-2"><Check size={15} className="text-emerald-400 shrink-0 mt-0.5" />{f}</li>
                  ))}
                </ul>
                <div className="mt-6">
                  {!embedded ? (
                    <button onClick={() => navigate(logged ? '/app/planos' : '/login?mode=signup')}
                      className={`w-full py-2.5 rounded-lg text-sm font-semibold ${p.highlight ? 'bg-violet-600 hover:bg-violet-500 text-white' : 'border border-white/[0.12] text-ink-2 hover:text-white'}`}>
                      {t('Começar teste grátis', 'Start free trial')}
                    </button>
                  ) : status?.subscribed && status.plan === p.code && status.pending ? (
                    <p className="text-center text-sm text-amber-300 font-medium py-2.5">{t('Aguardando pagamento', 'Awaiting payment')}</p>
                  ) : isCurrent(p) && status?.subscribed ? (
                    <p className="text-center text-sm text-emerald-300 font-medium py-2.5">{t('Seu plano atual', 'Your current plan')}</p>
                  ) : canBuy ? (
                    <button onClick={() => { setError(''); setBuying(p) }}
                      className={`w-full py-2.5 rounded-lg text-sm font-semibold ${p.highlight ? 'bg-violet-600 hover:bg-violet-500 text-white' : 'border border-white/[0.12] text-ink-2 hover:text-white'}`}>
                      {status?.subscribed ? t('Mudar para este plano', 'Switch to this plan') : t('Assinar', 'Subscribe')}
                    </button>
                  ) : status?.is_child ? (
                    <p className="text-center text-xs text-ink-4 py-2.5">{t('A assinatura desta empresa é feita pela agência.', "This company's subscription is handled by the agency.")}</p>
                  ) : null}
                </div>
              </div>
            ))}
          </div>
        )}

        {pack && (
          <div className="mt-10">
            <h2 className="text-lg font-bold text-white mb-3">{t('Avulsos', 'Add-ons')}</h2>
            <div className="bg-card border border-white/[0.08] rounded-2xl p-5 flex flex-wrap sm:flex-nowrap items-center gap-4 max-w-3xl">
              <span className="w-11 h-11 shrink-0 rounded-xl bg-violet-600/20 flex items-center justify-center">
                <Bot size={20} className="text-violet-300" />
              </span>
              <div className="flex-1 min-w-0">
                <p className="text-white font-semibold">{t(`Pacote de IA: +${pack.conversations} atendimentos`, `AI pack: +${pack.conversations} conversations`)}</p>
                <p className="text-ink-4 text-sm">{t('Usado depois da franquia do plano. Pago por Pix e não vence.', 'Used after the plan allowance. Paid by Pix and never expires.')}</p>
              </div>
              <div className="flex items-center gap-3 max-sm:w-full max-sm:justify-between">
                <span className="text-white font-bold">{fmt.money(pack.price_cents / 100)}</span>
                <button onClick={() => setShowPack(true)} className="px-4 py-2 rounded-lg bg-violet-600 hover:bg-violet-500 text-white text-sm font-semibold">
                  {t('Comprar', 'Buy')}
                </button>
              </div>
            </div>
          </div>
        )}

        <div className="mt-12 max-w-3xl mx-auto space-y-5">
          <h2 className="text-lg font-bold text-white">{t('Perguntas Frequentes', 'FAQ')}</h2>
          {[
            [t('Como funciona o teste grátis?', 'How does the free trial work?'),
              t('Depois que seu cadastro é aprovado, você usa tudo por alguns dias sem pagar nada e sem cartão. Antes de terminar, o painel avisa para você escolher um plano.', 'Once your sign-up is approved, you use everything for a few days without paying and without a card. Before it ends, the panel reminds you to pick a plan.')],
            [t('Como eu pago?', 'How do I pay?'),
              t('A cobrança é mensal pelo Asaas: Pix, boleto ou cartão. O acesso é liberado assim que o pagamento é confirmado.', 'Billing is monthly through Asaas: Pix, bank slip or card. Access is released as soon as payment is confirmed.')],
            [t('Posso trocar de plano ou cancelar?', 'Can I switch plans or cancel?'),
              t('Sim, quando quiser. Ao cancelar, o acesso continua até o fim do período já pago.', 'Yes, anytime. If you cancel, access continues until the end of the period you already paid.')],
            [t('O plano inclui as mensagens do WhatsApp e os anúncios?', 'Does the plan include WhatsApp messages and ads?'),
              t('Não. A Meta cobra direto na sua conta as mensagens do WhatsApp (por mensagem entregue; o painel mostra o custo estimado do mês) e o que você investe em anúncios.', 'No. Meta charges your account directly for WhatsApp messages (per delivered message; the panel shows the estimated monthly cost) and what you spend on ads.')],
          ].map(([q, a]) => (
            <div key={q}>
              <h3 className="text-ink font-semibold mb-1">{q}</h3>
              <p className="text-ink-4 text-sm">{a}</p>
            </div>
          ))}
        </div>
        {!embedded && <LegalEntity className="mt-12 text-center text-xs text-ink-4" />}
      </div>

      {showPack && <AIPackDialog onClose={() => setShowPack(false)} onPaid={() => setShowPack(false)} />}
      {buying && (
        <SubscribeDialog plan={buying} fmt={fmt} onClose={() => setBuying(null)}
          onDone={(s) => { setBuying(null); setStatus(s) }} />
      )}
    </div>
  )
}

function StatusCard({ status, date, canceling, onCancel, fmt }: {
  status: Status
  date: (iso: string | null) => string
  canceling: boolean
  onCancel: () => void
  fmt: ReturnType<typeof makeFormat>
}) {
  const { t } = useI18n()
  const [copied, setCopied] = useState(false)
  const s = status
  const text = {
    courtesy: s.until ? t(`Acesso liberado como cortesia até ${date(s.until)}.`, `Access granted as a courtesy until ${date(s.until)}.`) : t('Acesso liberado como cortesia, sem prazo.', 'Access granted as a courtesy, with no end date.'),
    trial: s.days_left === 0 ? t('Seu teste grátis termina hoje.', 'Your free trial ends today.') : t(`Teste grátis: faltam ${s.days_left} dia(s), até ${date(s.until)}.`, `Free trial: ${s.days_left} day(s) left, until ${date(s.until)}.`),
    active: t(`Plano ${s.plan_name ?? ''} ativo até ${date(s.until)}.`, `${s.plan_name ?? ''} plan active until ${date(s.until)}.`),
    past_due: t(`Pagamento em atraso. Pague até ${date(s.until)} para não pausar o acesso.`, `Payment overdue. Pay by ${date(s.until)} to keep access.`),
    canceled: s.until ? t(`Assinatura cancelada. Acesso até ${date(s.until)}.`, `Subscription canceled. Access until ${date(s.until)}.`) : t('Assinatura cancelada.', 'Subscription canceled.'),
    blocked: t('Seu acesso está pausado. Escolha um plano para continuar.', 'Your access is paused. Choose a plan to continue.'),
    unmanaged: '',
  }[s.status]
  const tone = s.status === 'blocked' || s.status === 'past_due' ? 'border-red-500/30 bg-red-950/20 text-red-200'
    : s.status === 'trial' ? 'border-amber-500/30 bg-amber-950/15 text-amber-200'
    : 'border-emerald-500/25 bg-emerald-950/15 text-emerald-200'

  return (
    <div className={`border rounded-2xl p-5 mb-6 ${tone}`}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm font-medium">{text}</p>
        {s.subscribed && !s.is_child && (
          <button onClick={onCancel} disabled={canceling} className="text-xs text-ink-4 hover:text-red-300 underline disabled:opacity-50">
            {t('Cancelar renovação', 'Cancel renewal')}
          </button>
        )}
      </div>
      {s.pix_automatic === 'ACTIVE' && (
        <p className="mt-3 flex items-center gap-1.5 text-xs text-emerald-300">
          <Repeat size={13} className="shrink-0" />
          {t('Pix Automático ativo: as mensalidades são debitadas no vencimento, sem precisar pagar aqui.', 'Automatic Pix is on: monthly fees are debited on the due date, no need to pay here.')}
        </p>
      )}
      {s.subscribed && (s.pix_automatic === 'CANCELLED' || s.pix_automatic === 'EXPIRED' || s.pix_automatic === 'REFUSED') && (
        <p className="mt-3 flex items-center gap-1.5 text-xs text-ink-3">
          <Repeat size={13} className="shrink-0" />
          {t('Pix Automático desligado. As próximas mensalidades aparecem aqui para pagar por Pix, boleto ou cartão.', 'Automatic Pix is off. Upcoming monthly fees show up here to pay by Pix, bank slip or card.')}
        </p>
      )}
      {s.pending?.auto_debit && (
        <div className="mt-4 flex items-center gap-2.5 bg-black/20 rounded-xl p-4 text-sm text-ink-2">
          <Repeat size={16} className="text-emerald-400 shrink-0" />
          {t(`A mensalidade de ${fmt.money(s.pending.value)} será debitada pelo Pix Automático em ${date(s.pending.due_date)}. Não precisa pagar aqui.`,
             `The ${fmt.money(s.pending.value)} monthly fee will be debited by Automatic Pix on ${date(s.pending.due_date)}. No need to pay here.`)}
        </div>
      )}
      {s.pending && !s.pending.auto_debit && (
        <div className="mt-4 flex flex-col sm:flex-row gap-4 items-start bg-black/20 rounded-xl p-4">
          {s.pending.pix_image && <img src={`data:image/png;base64,${s.pending.pix_image}`} alt="QR Code Pix" className="w-36 h-36 rounded-lg bg-white p-1.5 shrink-0" />}
          <div className="text-sm text-ink-2 space-y-2">
            <p className="font-semibold text-white">{t(`Cobrança de ${fmt.money(s.pending.value)} · vence ${date(s.pending.due_date)}`, `Charge of ${fmt.money(s.pending.value)} · due ${date(s.pending.due_date)}`)}</p>
            {s.pending.pix_payload && (
              <button onClick={async () => { await navigator.clipboard.writeText(s.pending!.pix_payload!); setCopied(true); window.setTimeout(() => setCopied(false), 2000) }}
                className="flex items-center gap-1.5 px-3 py-1.5 border border-white/[0.12] rounded-lg text-xs hover:text-white">
                {copied ? <Check size={13} className="text-emerald-400" /> : <Copy size={13} />}{copied ? t('Copiado', 'Copied') : t('Copiar Pix copia e cola', 'Copy Pix code')}
              </button>
            )}
            {s.pix_automatic === 'CREATED' && s.pending.pix_payload && (
              <p className="flex items-start gap-1.5 text-xs text-emerald-200 bg-emerald-500/10 border border-emerald-500/20 rounded-lg px-2.5 py-2 max-w-sm">
                <Repeat size={13} className="mt-0.5 shrink-0" />
                {t('Pague pelo app do banco e aceite o Pix Automático quando ele aparecer no final: as próximas mensalidades saem sozinhas no vencimento. Dá para cancelar quando quiser no app do banco.',
                   'Pay in your bank app and accept Automatic Pix when it shows up at the end: upcoming monthly fees are paid on the due date by themselves. You can cancel anytime in your bank app.')}
              </p>
            )}
            {s.pending.invoice_url && (
              <a href={s.pending.invoice_url} target="_blank" rel="noreferrer" className="block text-xs text-violet-300 underline">
                {t('Pagar com cartão ou boleto', 'Pay by card or bank slip')}
              </a>
            )}
            <p className="flex items-center gap-1.5 text-[11px] text-ink-4"><Loader2 size={11} className="animate-spin" />{t('A tela atualiza sozinha quando o pagamento for confirmado.', 'This screen updates by itself when payment is confirmed.')}</p>
          </div>
        </div>
      )}
    </div>
  )
}

function SubscribeDialog({ plan, fmt, onClose, onDone }: {
  plan: Plan
  fmt: ReturnType<typeof makeFormat>
  onClose: () => void
  onDone: (s: Status) => void
}) {
  const { t } = useI18n()
  const [name, setName] = useState('')
  const [doc, setDoc] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const input = 'w-full px-3 py-2 bg-field border border-white/[0.08] text-ink text-sm rounded-lg focus:border-indigo-500 focus:outline-none'

  async function submit() {
    setSaving(true)
    setError('')
    try {
      onDone((await api.post<Status>('/billing/subscribe', { plan: plan.code, name: name.trim(), document: doc })).data)
    } catch (e) {
      setError(apiError(e, t('Não foi possível assinar agora.', 'Could not subscribe right now.')))
    } finally { setSaving(false) }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm px-4">
      <div className="bg-card border border-white/[0.08] rounded-2xl p-6 w-full max-w-sm">
        <div className="flex items-center justify-between mb-1">
          <h3 className="text-base font-semibold text-white">{t(`Assinar o plano ${plan.name}`, `Subscribe to ${plan.name}`)}</h3>
          <button onClick={onClose} aria-label={t('Fechar', 'Close')} className="text-ink-5 hover:text-ink-3"><X size={18} /></button>
        </div>
        <p className="text-sm text-ink-4 mb-4">{t(`${fmt.money(plan.price_cents / 100)} por mês. Os dados abaixo vão na cobrança.`, `${fmt.money(plan.price_cents / 100)} a month. The details below go on the invoice.`)}</p>
        <label className="block text-[11px] text-ink-4 mb-1">{t('Nome ou razão social', 'Name or company name')}</label>
        <input value={name} onChange={(e) => setName(e.target.value)} className={`${input} mb-3`} />
        <label className="block text-[11px] text-ink-4 mb-1">CPF ou CNPJ</label>
        <input value={doc} onChange={(e) => setDoc(e.target.value)} inputMode="numeric" className={`${input} mb-4`} />
        {error && <p className="text-xs text-red-400 mb-3">{error}</p>}
        <button onClick={submit} disabled={saving || name.trim().length < 2 || doc.replace(/\D/g, '').length < 11}
          className="w-full py-2.5 bg-violet-600 hover:bg-violet-500 disabled:opacity-50 text-white text-sm font-semibold rounded-lg">
          {saving ? t('Gerando a cobrança…', 'Creating the charge…') : t('Gerar cobrança', 'Create charge')}
        </button>
      </div>
    </div>
  )
}
