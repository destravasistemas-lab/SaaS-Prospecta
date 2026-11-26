import { Link, useLocation } from 'react-router-dom'
import { useI18n } from '../i18n'
import type { Me } from './MeContext'

/** Aviso no topo do painel: fim do teste, pagamento atrasado, cancelamento ou acesso pausado. */
export default function BillingBanner({ me }: { me: Me | null }) {
  const { t, locale } = useI18n()
  const location = useLocation()
  const b = me?.billing
  if (!b || location.pathname.startsWith('/app/planos')) return null
  const date = b.until ? new Date(b.until).toLocaleDateString(locale) : ''

  let tone: 'amber' | 'red' | null = null
  let text = ''
  if (b.status === 'trial' && b.days_left !== null && b.days_left <= 3) {
    tone = 'amber'
    text = b.days_left === 0
      ? t('Seu teste grátis termina hoje. Escolha um plano para não perder o acesso.', 'Your free trial ends today. Pick a plan to keep access.')
      : t(`Seu teste grátis termina em ${b.days_left} dia(s). Escolha um plano para não perder o acesso.`, `Your free trial ends in ${b.days_left} day(s). Pick a plan to keep access.`)
  } else if (b.status === 'past_due') {
    tone = 'red'
    text = t(`Pagamento em atraso. Pague até ${date} para não pausar o acesso.`, `Payment overdue. Pay by ${date} to keep access.`)
  } else if (b.status === 'blocked') {
    tone = 'red'
    text = t('Seu teste ou plano terminou. Escolha um plano para continuar usando o Prospecta.', 'Your trial or plan has ended. Pick a plan to keep using Prospecta.')
  } else if (b.status === 'canceled' && b.days_left !== null && b.days_left <= 5) {
    tone = 'amber'
    text = t(`Assinatura cancelada. O acesso vai até ${date}.`, `Subscription canceled. Access lasts until ${date}.`)
  }
  if (!tone) return null

  const cls = tone === 'red' ? 'bg-red-950/40 border-red-500/30 text-red-100' : 'bg-amber-950/30 border-amber-500/30 text-amber-100'
  return (
    <div className={`border rounded-xl px-4 py-3 mb-5 flex flex-wrap items-center justify-between gap-2 text-sm ${cls}`}>
      <span>{text}</span>
      <Link to="/app/planos" className="px-3 py-1.5 rounded-lg bg-white/10 hover:bg-white/20 text-white text-xs font-semibold no-underline">
        {t('Ver planos', 'See plans')}
      </Link>
    </div>
  )
}
