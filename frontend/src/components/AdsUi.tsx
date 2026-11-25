import { useEffect, useRef, useState } from 'react'
import { ArrowDownRight, ArrowUpRight, HelpCircle } from 'lucide-react'
import { useI18n } from '../i18n'
import { deltaPct } from '../utils/format'

type T = (pt: string, en: string) => string
type Tone = 'ok' | 'warn' | 'error' | 'neutral'

const TONES: Record<Tone, string> = {
  ok: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
  warn: 'bg-amber-500/10 text-amber-300 border-amber-500/25',
  error: 'bg-red-500/10 text-red-300 border-red-500/25',
  neutral: 'bg-white/[0.05] text-ink-3 border-white/[0.06]',
}

/** Status real de entrega (effective_status da Meta) → rótulo e cor. */
export function deliveryInfo(t: T, status: string, effective?: string | null): { label: string; tone: Tone } {
  switch (effective || status) {
    case 'ACTIVE': return { label: t('Veiculando', 'Delivering'), tone: 'ok' }
    case 'PAUSED': return { label: t('Pausado', 'Paused'), tone: 'neutral' }
    case 'CAMPAIGN_PAUSED': return { label: t('Campanha pausada', 'Campaign paused'), tone: 'neutral' }
    case 'ADSET_PAUSED': return { label: t('Conjunto pausado', 'Ad set paused'), tone: 'neutral' }
    case 'PENDING_REVIEW': return { label: t('Em análise', 'In review'), tone: 'warn' }
    case 'IN_PROCESS': return { label: t('Processando', 'Processing'), tone: 'warn' }
    case 'PREAPPROVED': return { label: t('Pré-aprovado', 'Pre-approved'), tone: 'warn' }
    case 'DISAPPROVED': return { label: t('Reprovado', 'Rejected'), tone: 'error' }
    case 'WITH_ISSUES': return { label: t('Com problemas', 'Has issues'), tone: 'error' }
    case 'PENDING_BILLING_INFO': return { label: t('Sem forma de pagamento', 'No payment method'), tone: 'error' }
    case 'ARCHIVED': return { label: t('Arquivado', 'Archived'), tone: 'neutral' }
    case 'DELETED': return { label: t('Excluído', 'Deleted'), tone: 'neutral' }
    default: return { label: effective || status, tone: 'neutral' }
  }
}

export function DeliveryBadge({ status, effective, reasons = [], small = false }: {
  status: string
  effective?: string | null
  reasons?: string[]
  small?: boolean
}) {
  const { t } = useI18n()
  const [open, setOpen] = useState(false)
  const info = deliveryInfo(t, status, effective)
  return (
    <span className="relative inline-flex">
      <button
        type="button"
        onClick={(e) => { e.preventDefault(); e.stopPropagation(); if (reasons.length) setOpen((v) => !v) }}
        className={`inline-flex items-center gap-1 border rounded-full font-semibold shrink-0 ${small ? 'text-[10px] px-2 py-0.5' : 'text-[11px] px-2.5 py-1'} ${TONES[info.tone]} ${reasons.length ? 'cursor-pointer' : 'cursor-default'}`}
        title={reasons.join(' · ') || undefined}
      >
        {info.label}
        {reasons.length > 0 && <HelpCircle size={small ? 10 : 11} />}
      </button>
      {open && reasons.length > 0 && (
        <Popover onClose={() => setOpen(false)}>
          <p className="text-[11px] font-semibold text-ink mb-1">{t('Motivo informado pela Meta', 'Reason given by Meta')}</p>
          <ul className="space-y-1">
            {reasons.map((r) => <li key={r} className="text-[11px] text-ink-3 leading-snug">{r}</li>)}
          </ul>
        </Popover>
      )}
    </span>
  )
}

function Popover({ onClose, children }: { onClose: () => void; children: React.ReactNode }) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const close = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) onClose() }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [onClose])
  return (
    <div ref={ref} onClick={(e) => e.stopPropagation()}
      className="absolute z-30 top-full mt-1.5 left-0 w-64 max-w-[80vw] bg-raised border border-white/[0.1] rounded-lg shadow-xl p-3 text-left">
      {children}
    </div>
  )
}

export type MetricKey =
  | 'spend' | 'results' | 'cost_per_result' | 'roas' | 'reach' | 'frequency'
  | 'impressions' | 'clicks' | 'ctr' | 'cpc' | 'cpm' | 'leads_from_ads'

export function metricHelp(t: T, key: MetricKey): string {
  switch (key) {
    case 'spend': return t('Quanto a Meta cobrou no período.', 'How much Meta charged in the period.')
    case 'results': return t('A conversão principal: leads, conversas no WhatsApp, compras ou cliques no link, conforme o objetivo.', 'The main conversion: leads, WhatsApp conversations, purchases or link clicks, depending on the objective.')
    case 'cost_per_result': return t('Gasto ÷ resultados. Quanto menor, melhor. Compare com quanto um cliente vale para você.', 'Spend ÷ results. Lower is better. Compare it with what a customer is worth to you.')
    case 'roas': return t('Valor das compras registradas pelo pixel ÷ gasto. Acima de 1, o anúncio trouxe mais do que custou. Só aparece com pixel de compras.', 'Purchase value tracked by the pixel ÷ spend. Above 1, the ad brought in more than it cost. Only shows with a purchase pixel.')
    case 'reach': return t('Quantas pessoas diferentes viram o anúncio.', 'How many different people saw the ad.')
    case 'frequency': return t('Quantas vezes, em média, cada pessoa viu o anúncio. Acima de 3 numa semana, o público costuma cansar: troque o criativo ou amplie o público.', 'How many times, on average, each person saw the ad. Above 3 in a week, people tend to tune out: change the creative or widen the audience.')
    case 'impressions': return t('Quantas vezes o anúncio apareceu na tela.', 'How many times the ad was shown.')
    case 'clicks': return t('Todos os cliques no anúncio: link, perfil, curtidas e outros.', 'All clicks on the ad: link, profile, likes and others.')
    case 'ctr': return t('Cliques ÷ impressões. Mostra se o anúncio chama atenção. Abaixo de 1%, vale testar outro criativo.', 'Clicks ÷ impressions. Shows whether the ad catches attention. Below 1%, try another creative.')
    case 'cpc': return t('Custo médio de cada clique.', 'Average cost of each click.')
    case 'cpm': return t('Custo para aparecer 1.000 vezes. Sobe com público pequeno ou muita concorrência.', 'Cost of 1,000 impressions. It rises with small audiences or heavy competition.')
    case 'leads_from_ads': return t('Contatos que chegaram ao Prospecta vindos de um anúncio: WhatsApp, Direct ou formulário.', 'Contacts that reached Prospecta from an ad: WhatsApp, Direct or form.')
  }
}

export function MetricLabel({ label, metric, className = '' }: { label: string; metric: MetricKey; className?: string }) {
  return (
    <span className={`inline-flex items-center gap-1 ${className}`}>
      {label}
      <MetricHelp label={label} metric={metric} />
    </span>
  )
}

/** Só o "?" com a explicação da métrica (para usar ao lado de outro botão). */
export function MetricHelp({ label, metric }: { label: string; metric: MetricKey }) {
  const { t } = useI18n()
  const [open, setOpen] = useState(false)
  return (
    <span className="relative inline-flex">
      <button type="button" aria-label={t('O que é isso?', 'What is this?')} onClick={(e) => { e.preventDefault(); e.stopPropagation(); setOpen((v) => !v) }}
        className="text-ink-5 hover:text-ink-2">
        <HelpCircle size={11} />
      </button>
      {open && (
        <Popover onClose={() => setOpen(false)}>
          <p className="text-[11px] font-semibold text-ink mb-1">{label}</p>
          <p className="text-[11px] text-ink-3 leading-snug normal-case tracking-normal font-normal">{metricHelp(t, metric)}</p>
        </Popover>
      )}
    </span>
  )
}

/** Variação contra o período anterior. good: qual direção é boa ('up', 'down' ou neutra). */
export function Delta({ current, previous, good = 'up' }: { current: number; previous: number; good?: 'up' | 'down' | 'none' }) {
  const { t } = useI18n()
  const d = deltaPct(current, previous)
  if (d === null || !isFinite(d)) return <span className="text-[10px] text-ink-5">{t('sem comparação', 'no comparison')}</span>
  if (Math.abs(d) < 0.5) return <span className="text-[10px] text-ink-4">{t('estável', 'flat')}</span>
  const up = d > 0
  const tone = good === 'none' ? 'text-ink-3' : (up === (good === 'up')) ? 'text-emerald-400' : 'text-red-400'
  const Icon = up ? ArrowUpRight : ArrowDownRight
  return (
    <span className={`inline-flex items-center gap-0.5 text-[10px] font-semibold ${tone}`} title={t('em relação ao período anterior', 'vs. the previous period')}>
      <Icon size={11} />{Math.abs(d).toFixed(0)}%
    </span>
  )
}

export const PERIODS = [7, 14, 30, 90] as const

export function PeriodPicker({ value, onChange }: { value: number; onChange: (d: number) => void }) {
  const { t } = useI18n()
  return (
    <div className="flex gap-1 bg-card border border-white/[0.08] rounded-lg p-1">
      {PERIODS.map((d) => (
        <button key={d} onClick={() => onChange(d)}
          className={`px-2.5 py-1 rounded text-xs font-medium transition-colors ${value === d ? 'bg-indigo-600 text-white' : 'text-ink-4 hover:text-ink-2'}`}>
          {t(`${d} dias`, `${d} days`)}
        </button>
      ))}
    </div>
  )
}

/** Rótulo do resultado vindo da API (em português) no idioma do painel. */
export function resultLabel(t: T, label: string): string {
  switch (label) {
    case 'Compras': return t('Compras', 'Purchases')
    case 'Leads': return t('Leads', 'Leads')
    case 'Conversas': return t('Conversas', 'Conversations')
    case 'Cliques no link': return t('Cliques no link', 'Link clicks')
    case 'Visitas à página': return t('Visitas à página', 'Landing page views')
    default: return label || t('Resultados', 'Results')
  }
}

export function optimizationGoalLabel(t: T, goal: string | null): string {
  switch (goal) {
    case 'REACH': return t('Alcance', 'Reach')
    case 'IMPRESSIONS': return t('Impressões', 'Impressions')
    case 'LINK_CLICKS': return t('Cliques no link', 'Link clicks')
    case 'LANDING_PAGE_VIEWS': return t('Visitas à página', 'Landing page views')
    case 'LEAD_GENERATION': return t('Leads no formulário', 'Form leads')
    case 'QUALITY_LEAD': return t('Leads qualificados', 'Quality leads')
    case 'CONVERSATIONS': return t('Conversas', 'Conversations')
    case 'OFFSITE_CONVERSIONS': return t('Conversões no site', 'Website conversions')
    case 'POST_ENGAGEMENT': return t('Engajamento', 'Engagement')
    case 'THRUPLAY': return t('Visualizações de vídeo', 'Video views')
    case 'VALUE': return t('Valor das compras', 'Purchase value')
    default: return goal || ''
  }
}

export function breakdownLabel(t: T, dim: string, key: string): string {
  if (dim === 'gender') {
    if (key === 'male') return t('Homens', 'Men')
    if (key === 'female') return t('Mulheres', 'Women')
    return t('Não informado', 'Unknown')
  }
  if (dim === 'publisher_platform') {
    const map: Record<string, string> = { facebook: 'Facebook', instagram: 'Instagram', messenger: 'Messenger', audience_network: 'Audience Network', threads: 'Threads' }
    return map[key] || key
  }
  if (dim === 'impression_device') {
    const map: Record<string, string> = {
      desktop: t('Computador', 'Desktop'), iphone: 'iPhone', ipad: 'iPad', android_smartphone: t('Celular Android', 'Android phone'),
      android_tablet: t('Tablet Android', 'Android tablet'), ipod: 'iPod', other: t('Outros', 'Other'),
    }
    return map[key] || key
  }
  if (dim === 'age' && key === 'Unknown') return t('Não informado', 'Unknown')
  return key
}

/** Situação da conta de anúncios (account_status) → aviso para o topo da tela, ou null se estiver tudo certo. */
export function accountWarning(t: T, status?: number | null, reason?: number | null): { tone: Tone; text: string } | null {
  switch (status) {
    case 2: {
      const why = reason === 3 ? t(' Motivo: problema de pagamento.', ' Reason: payment issue.')
        : reason === 1 ? t(' Motivo: violação das políticas de anúncios.', ' Reason: ad policy violation.') : ''
      return { tone: 'error', text: t('A Meta desativou esta conta de anúncios e nada está sendo veiculado.', 'Meta disabled this ad account and nothing is delivering.') + why }
    }
    case 3: return { tone: 'error', text: t('Há um pagamento pendente na Meta. Os anúncios param até o saldo ser quitado no Gerenciador de Anúncios.', 'There is an unpaid balance at Meta. Ads stop until it is settled in Ads Manager.') }
    case 7: return { tone: 'warn', text: t('A Meta está revisando esta conta. Os anúncios podem não rodar até a revisão terminar.', 'Meta is reviewing this account. Ads may not run until the review ends.') }
    case 8: return { tone: 'warn', text: t('Um pagamento está sendo processado pela Meta.', 'A payment is being processed by Meta.') }
    case 9: return { tone: 'warn', text: t('Há um pagamento atrasado e a conta está no período de carência. Regularize para não parar.', 'A payment is overdue and the account is in its grace period. Settle it to avoid a stop.') }
    case 100:
    case 101: return { tone: 'error', text: t('Esta conta de anúncios está fechada.', 'This ad account is closed.') }
    default: return null
  }
}

export function WarningBanner({ tone, children }: { tone: Tone; children: React.ReactNode }) {
  const cls = tone === 'error' ? 'bg-red-900/20 border-red-500/25 text-red-200' : 'bg-amber-900/15 border-amber-500/25 text-amber-200'
  return <div className={`border rounded-xl px-4 py-3 text-sm mb-4 ${cls}`}>{children}</div>
}
