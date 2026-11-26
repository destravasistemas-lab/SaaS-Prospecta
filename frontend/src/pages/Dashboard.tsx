import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Camera, Check, ChevronRight, Megaphone, MessageSquare, Sparkles } from 'lucide-react'
import api from '../services/api'
import HelpLink from '../components/HelpLink'
import { useMe } from '../components/MeContext'
import type { DashboardData } from '../types'
import { useI18n } from '../i18n'

type Connection = { provider: string; status: string }

/** Primeiros passos: some quando tudo estiver feito. */
function SetupChecklist({ connected, automations }: { connected: Set<string>; automations: number }) {
  const { t } = useI18n()
  const steps = [
    { done: connected.has('instagram'), icon: Camera, to: '/app/conexao',
      title: t('Conectar o Instagram', 'Connect Instagram'),
      text: t('Para responder o Direct e ligar a automação de comentários.', 'To answer Direct messages and turn on comment automation.') },
    { done: connected.has('whatsapp'), icon: MessageSquare, to: '/app/conexao',
      title: t('Conectar o WhatsApp', 'Connect WhatsApp'),
      text: t('Para atender, disparar templates e receber os leads dos anúncios.', 'To answer, send templates and receive leads from ads.') },
    { done: connected.has('ads'), icon: Megaphone, to: '/app/conexao',
      title: t('Conectar a conta de anúncios', 'Connect your ad account'),
      text: t('Para ver investimento, resultados e criar campanhas.', 'To see spend and results and create campaigns.') },
    { done: automations > 0, icon: Sparkles, to: '/app/publicar',
      title: t('Criar a primeira automação', 'Create your first automation'),
      text: t('Quem comentar a palavra-chave recebe sua mensagem no Direct.', 'Whoever comments the keyword gets your message in Direct.') },
  ]
  const done = steps.filter((s) => s.done).length
  if (done === steps.length) return null
  const next = steps.findIndex((s) => !s.done)

  return (
    <section className="mb-8 rounded-2xl border border-violet-400/20 bg-gradient-to-br from-violet-600/[0.08] to-transparent p-5 sm:p-6">
      <div className="flex flex-wrap items-end justify-between gap-3 mb-5">
        <div>
          <h2 className="text-base font-semibold text-white">{t('Comece por aqui', 'Start here')}</h2>
          <p className="text-sm text-ink-3 mt-0.5">{t('Quatro passos para o Prospecta começar a trabalhar por você.', 'Four steps to get Prospecta working for you.')}</p>
        </div>
        <span className="text-xs font-medium text-violet-200">{done} {t('de', 'of')} {steps.length}</span>
      </div>
      <div className="h-1.5 rounded-full bg-white/[0.06] mb-5 overflow-hidden">
        <div className="h-full rounded-full bg-violet-400 transition-all" style={{ width: `${(done / steps.length) * 100}%` }} />
      </div>
      <ol className="grid gap-2 sm:grid-cols-2">
        {steps.map((s, i) => {
          const Icon = s.icon
          return (
            <li key={s.title}>
              <Link
                to={s.to}
                className={`flex items-start gap-3 rounded-xl border p-3.5 transition-colors ${
                  s.done ? 'border-line bg-white/[0.02]'
                    : i === next ? 'border-violet-400/40 bg-violet-500/10 hover:bg-violet-500/15'
                    : 'border-line bg-card hover:border-white/[0.14]'
                }`}
              >
                <span className={`w-8 h-8 shrink-0 rounded-lg flex items-center justify-center ${
                  s.done ? 'bg-emerald-500/15 text-emerald-300' : 'bg-white/[0.06] text-ink-2'
                }`}>
                  {s.done ? <Check size={16} /> : <Icon size={16} />}
                </span>
                <span className="flex-1 min-w-0">
                  <span className={`block text-sm font-medium ${s.done ? 'text-ink-4 line-through' : 'text-ink'}`}>{s.title}</span>
                  {!s.done && <span className="block text-xs text-ink-4 mt-0.5">{s.text}</span>}
                </span>
                {!s.done && <ChevronRight size={16} className="text-ink-4 mt-1.5 shrink-0" />}
              </Link>
            </li>
          )
        })}
      </ol>
    </section>
  )
}

const palette = {
  green: { bg: 'rgba(35,134,54,0.15)', text: '#3fb950' },
  purple: { bg: 'rgba(88,101,242,0.15)', text: '#818cf8' },
  blue: { bg: 'rgba(56,139,253,0.15)', text: '#60a5fa' },
  orange: { bg: 'rgba(210,153,34,0.15)', text: '#fbbf24' },
  pink: { bg: 'rgba(219,97,162,0.15)', text: '#f472b6' },
  teal: { bg: 'rgba(56,189,193,0.15)', text: '#2dd4bf' },
  red: { bg: 'rgba(248,81,73,0.15)', text: '#f87171' },
  indigo: { bg: 'rgba(121,88,212,0.15)', text: '#a78bfa' },
}

function Icon({ d, size = 18 }: { d: string; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round">
      <path d={d} />
    </svg>
  )
}

function MetricCard({ icon, iconColor = 'blue', value, label, sub, trend }: {
  icon: string; iconColor?: string; value: string | number; label: string; sub?: string; trend?: string
}) {
  const col = palette[iconColor as keyof typeof palette]
  const icons: Record<string, string> = {
    dollar: 'M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6',
    eye: 'M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8zM12 12m-3 0a3 3 0 1 0 6 0 3 3 0 0 0-6 0',
    cursor: 'M4 4l7.07 17 2.51-7.39L21 11.07z',
    percent: 'M19 5L5 19M6.5 6.5m0 0a1 1 0 1 0 2 0 1 1 0 0 0-2 0zM15.5 15.5m0 0a1 1 0 1 0 2 0 1 1 0 0 0-2 0',
    chartLine: 'M3 3v18h18M18 9l-5 5-4-4-3 3',
    target: 'M12 12m-1 0a1 1 0 1 0 2 0 1 1 0 0 0-2 0zM12 12m-5 0a5 5 0 1 0 10 0 5 5 0 0 0-10 0zM12 12m-9 0a9 9 0 1 0 18 0 9 9 0 0 0-18 0',
    photo: 'M15 8h.01M3 6a3 3 0 0 1 3-3h12a3 3 0 0 1 3 3v12a3 3 0 0 1-3 3H6a3 3 0 0 1-3-3zm16 5-3.5-3.5L12 16l-3-3-3 3',
    users: 'M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75',
    heart: 'M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z',
    userPlus: 'M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM19 8v6M22 11h-6',
    video: 'M15 10l4.553-2.069A1 1 0 0 1 21 8.87v6.26a1 1 0 0 1-1.447.894L15 14M3 8a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z',
    coins: 'M12 12m-9 0a9 9 0 1 0 18 0 9 9 0 0 0-18 0zM14.8 9A2 2 0 0 0 13 8h-2a2 2 0 0 0 0 4h2a2 2 0 0 1 0 4h-2a2 2 0 0 1-1.8-1M12 7v1m0 8v1',
    donut: 'M10 2a8 8 0 1 0 8 8h-8z',
    play: 'M5 3l14 9-14 9z',
    magnet: 'M6 15a6 6 0 1 0 12 0v-3H6zM6 12H4M20 12h-2M12 3v4',
    receipt: 'M4 2h16v20l-2-1-2 1-2-1-2 1-2-1-2 1-2-1-2 1V2zM9 7h6M9 11h6M9 15h4',
    trending: 'M23 6l-9.5 9.5-5-5L1 18',
    calStats: 'M3 4h18M3 9h18M3 14h9M3 19h5M14 14l2 2 4-4',
    calendar: 'M3 4h18v18H3zM16 2v4M8 2v4M3 10h18',
    minus: 'M5 12h14',
    arrowUp: 'M12 19V5M5 12l7-7 7 7',
    arrowDown: 'M12 5v14M19 12l-7 7-7-7',
  }
  return (
    <div className="bg-card border border-white/[0.06] rounded-xl p-4 flex flex-col gap-0 hover:border-white/[0.12] transition-colors">
      <div className="w-9 h-9 rounded-lg flex items-center justify-center mb-3"
        style={{ background: col.bg, color: col.text }}>
        <Icon d={icons[icon]} size={17} />
      </div>
      <div className="text-xl font-semibold text-ink leading-tight mb-0.5">{value}</div>
      <div className="text-xs text-ink-4">{label}</div>
      {sub && <div className="text-[10px] text-ink-5 mt-1">{sub}</div>}
      {trend && (
        <div className={`inline-flex items-center gap-1 text-[10px] mt-1.5 px-1.5 py-0.5 rounded self-start ${
          trend === 'up' ? 'bg-green-900/20 text-green-400' : trend === 'down' ? 'bg-red-900/20 text-red-400' : 'bg-white/[0.04] text-ink-4'
        }`}>
          <Icon d={trend === 'up' ? icons.arrowUp : trend === 'down' ? icons.arrowDown : icons.minus} size={9} />
          {trend === 'neutral' ? '—' : trend === 'up' ? '+0%' : '-0%'}
        </div>
      )}
    </div>
  )
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-wider text-ink-4 mb-3">
      {children}
      <div className="flex-1 h-px bg-white/[0.06]" />
    </div>
  )
}

function CardsGrid({ children, minWidth = 160 }: { children: React.ReactNode; minWidth?: number }) {
  return (
    <div className="grid gap-2.5 mb-6"
      style={{ gridTemplateColumns: `repeat(auto-fit, minmax(${minWidth}px, 1fr))` }}>
      {children}
    </div>
  )
}

const emptyData: DashboardData = {
  total_leads: 0, total_customers: 0, new_customers_30d: 0, conversion_rate: 0,
  total_revenue: 0, monthly_revenue: 0, average_ticket: 0, projected_revenue: 0,
  ads_spent: 0, ads_impressions: 0, ads_clicks: 0, ads_ctr: 0, ads_cpm: 0, ads_roas: 0,
  instagram_posts: 0, instagram_reach: 0, instagram_engagement: 0, instagram_followers_delta: 0,
  videos_generated_month: 0, credits_total: 50, credits_used: 0,
  last_video_title: null, last_video_created_at: null,
  performance: [], recent_activity: [], alerts: [],
}

export default function Dashboard() {
  const { t, locale } = useI18n()
  const [data, setData] = useState<DashboardData>(emptyData)
  const monthLabel = new Date().toLocaleDateString(locale, { month: 'short', year: 'numeric' })
  const money = (v: number) => v.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })
  const usd = (v: number | undefined) => `US$ ${(v ?? 0).toFixed(2)}`
  const [waCosts, setWaCosts] = useState<{
    total: number
    total_usd?: number
    breakdown: Record<string, { count: number; unit_cost: number; subtotal: number; subtotal_usd?: number }>
  } | null>(null)
  const waSub = (key: string) => {
    const b = waCosts?.breakdown[key]
    return `${usd(b?.subtotal_usd)} · ${b?.count ?? 0} ${t('mensagens', 'messages')}`
  }

  const me = useMe()
  const [connected, setConnected] = useState<Set<string> | null>(null)
  const [automations, setAutomations] = useState(0)

  useEffect(() => {
    api.get<Connection[]>('/auth/meta/connections')
      .then(({ data }) => setConnected(new Set(data.filter((c) => c.status === 'active').map((c) => c.provider))))
      .catch(() => setConnected(new Set()))
    api.get('/automations')
      .then(({ data }) => setAutomations(Array.isArray(data) ? data.length : 0))
      .catch(() => {})
    api.get('/dashboard')
      .then((res) => setData(res.data))
      .catch(() => {})
    api.get('/whatsapp/costs')
      .then((res) => setWaCosts(res.data.connected ? res.data : null))
      .catch(() => setWaCosts(null))
  }, [])

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3 mb-7">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-semibold text-white">
              {t('Olá', 'Hi')}{me?.full_name ? `, ${me.full_name.split(' ')[0]}` : ''}
            </h1>
            <HelpLink section="inicio" />
          </div>
          <p className="text-sm text-ink-4 mt-0.5">{t('Resumo da sua operação neste mês.', 'Your summary for this month.')}</p>
        </div>
        <div className="flex items-center gap-2.5">
          <div className="flex items-center gap-1.5 bg-card border border-white/[0.06] rounded-lg px-3 py-1.5 text-xs text-ink-4">
            <Icon d="M3 4h18v18H3zM16 2v4M8 2v4M3 10h18" size={13} />
            {monthLabel}
          </div>
        </div>
      </div>

      {connected && <SetupChecklist connected={connected} automations={automations} />}

      {/* Anúncios e Instagram só aparecem com a conta conectada (sem ela seriam só zeros). */}
      {connected && (<>
      {connected.has('ads') && (<>
      <SectionLabel>{t('Anúncios (Meta Ads)', 'Ads (Meta Ads)')}</SectionLabel>
      <CardsGrid>
        <MetricCard icon="dollar" iconColor="green" value={money(data.ads_spent)} label={t('Investimento Total', 'Total Spend')} />
        <MetricCard icon="eye" iconColor="purple" value={data.ads_impressions} label={t('Impressões', 'Impressions')} />
        <MetricCard icon="cursor" iconColor="blue" value={data.ads_clicks} label={t('Cliques', 'Clicks')} />
        <MetricCard icon="percent" iconColor="teal" value={`${data.ads_ctr.toFixed(2)}%`} label="CTR" />
        <MetricCard icon="chartLine" iconColor="orange" value={money(data.ads_cpm)} label="CPM" />
        <MetricCard icon="target" iconColor="pink" value={`${data.ads_roas.toFixed(2)}x`} label="ROAS" />
      </CardsGrid>
      </>)}

      {connected.has('instagram') && (<>
      <SectionLabel>Instagram</SectionLabel>
      <CardsGrid minWidth={140}>
        <MetricCard icon="photo" iconColor="pink" value={data.instagram_posts} label={t('Posts (30 dias)', 'Posts (30 days)')} />
        <MetricCard icon="users" iconColor="purple" value={data.instagram_reach} label={t('Alcance Total', 'Total Reach')} />
        <MetricCard icon="heart" iconColor="red" value={data.instagram_engagement} label={t('Engajamento Médio', 'Average Engagement')} />
        <MetricCard icon="userPlus" iconColor="orange" value={data.instagram_followers_delta} label={t('Seguidores', 'Followers')} />
      </CardsGrid>
      </>)}

      {waCosts && (
        <>
          <SectionLabel>{t('WhatsApp — Custo estimado do mês', 'WhatsApp — Estimated cost this month')}</SectionLabel>
          <CardsGrid minWidth={140}>
            <MetricCard icon="coins" iconColor="green" value={money(waCosts.total)} label={t('Custo total (mês)', 'Total cost (month)')} sub={usd(waCosts.total_usd)} />
            <MetricCard icon="receipt" iconColor="blue" value={money(waCosts.breakdown.utility?.subtotal ?? 0)} label={t('Utilidade', 'Utility')} sub={waSub('utility')} />
            <MetricCard icon="receipt" iconColor="purple" value={money(waCosts.breakdown.marketing?.subtotal ?? 0)} label="Marketing" sub={waSub('marketing')} />
            <MetricCard icon="receipt" iconColor="orange" value={money(waCosts.breakdown.authentication?.subtotal ?? 0)} label={t('Autenticação', 'Authentication')} sub={waSub('authentication')} />
          </CardsGrid>
        </>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div>
          <SectionLabel>{t('Clientes', 'Customers')}</SectionLabel>
          <div className="grid grid-cols-2 gap-2.5">
            <MetricCard icon="users" iconColor="blue" value={data.total_customers} label={t('Total de Clientes', 'Total Customers')} />
            <MetricCard icon="userPlus" iconColor="green" value={data.new_customers_30d} label={t('Novos (30 dias)', 'New (30 days)')} />
            <MetricCard icon="target" iconColor="indigo" value={`${data.conversion_rate}%`} label={t('Taxa de Conversão', 'Conversion Rate')} />
            <MetricCard icon="magnet" iconColor="orange" value={data.total_leads} label={t('Leads Captados', 'Leads Captured')} />
          </div>
        </div>
        <div>
          <SectionLabel>{t('Faturamento', 'Revenue')}</SectionLabel>
          <div className="grid grid-cols-2 gap-2.5">
            <MetricCard icon="dollar" iconColor="green" value={money(data.total_revenue)} label={t('Faturamento Total', 'Total Revenue')} />
            <MetricCard icon="calStats" iconColor="teal" value={money(data.monthly_revenue)} label={t('Faturamento (mês)', 'Revenue (month)')} />
            <MetricCard icon="receipt" iconColor="purple" value={money(data.average_ticket)} label={t('Ticket Médio', 'Average Ticket')} />
            <MetricCard icon="trending" iconColor="orange" value={money(data.projected_revenue)} label={t('Receita Projetada', 'Projected Revenue')} />
          </div>
        </div>
      </div>
      </>)}
    </div>
  )
}
