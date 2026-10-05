import { useEffect, useState } from 'react'
import api from '../services/api'
import type { DashboardData } from '../types'

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
    <div className="bg-[#111118] border border-white/[0.06] rounded-xl p-4 flex flex-col gap-0 hover:border-white/[0.12] transition-colors">
      <div className="w-9 h-9 rounded-lg flex items-center justify-center mb-3"
        style={{ background: col.bg, color: col.text }}>
        <Icon d={icons[icon]} size={17} />
      </div>
      <div className="text-xl font-semibold text-[#e2e2e8] leading-tight mb-0.5">{value}</div>
      <div className="text-xs text-[#555]">{label}</div>
      {sub && <div className="text-[10px] text-[#444] mt-1">{sub}</div>}
      {trend && (
        <div className={`inline-flex items-center gap-1 text-[10px] mt-1.5 px-1.5 py-0.5 rounded self-start ${
          trend === 'up' ? 'bg-green-900/20 text-green-400' : trend === 'down' ? 'bg-red-900/20 text-red-400' : 'bg-white/[0.04] text-[#555]'
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
    <div className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-wider text-[#555] mb-3">
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

function CreditCard({ remaining, total }: { remaining: number; total: number }) {
  const pct = total > 0 ? Math.round((remaining / total) * 100) : 0
  return (
    <div className="bg-[#111118] border border-white/[0.06] rounded-xl p-4 hover:border-white/[0.12] transition-colors">
      <div className="w-9 h-9 rounded-lg flex items-center justify-center mb-3"
        style={{ background: palette.green.bg, color: palette.green.text }}>
        <Icon d="M12 12m-9 0a9 9 0 1 0 18 0 9 9 0 0 0-18 0zM14.8 9A2 2 0 0 0 13 8h-2a2 2 0 0 0 0 4h2a2 2 0 0 1 0 4h-2a2 2 0 0 1-1.8-1M12 7v1m0 8v1" size={17} />
      </div>
      <div className="text-xl font-semibold text-green-400 leading-tight mb-0.5">{remaining}</div>
      <div className="text-xs text-[#555] mb-2.5">Créditos Restantes</div>
      <div className="h-1 bg-white/[0.06] rounded-full">
        <div className="h-full rounded-full bg-green-400" style={{ width: `${pct}%` }} />
      </div>
      <div className="text-[10px] text-[#444] mt-1">{remaining}/{total} disponíveis</div>
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
  const [data, setData] = useState<DashboardData>(emptyData)
  const [period, setPeriod] = useState('30d')
  const [waCosts, setWaCosts] = useState<{
    total: number
    breakdown: Record<string, { count: number; unit_cost: number; subtotal: number }>
  } | null>(null)

  useEffect(() => {
    const accountId = localStorage.getItem('account_id') ?? ''
    api.get('/dashboard', { params: { account_id: accountId } })
      .then((res) => setData(res.data))
      .catch(() => {})
    api.get('/whatsapp/costs')
      .then((res) => setWaCosts(res.data))
      .catch(() => setWaCosts(null))
  }, [])

  const creditsRemaining = data.credits_total - data.credits_used
  const creditsPercent = data.credits_total > 0 ? Math.round((data.credits_used / data.credits_total) * 100) : 0

  return (
    <div>
      <div className="flex items-center justify-between mb-7">
        <h1 className="text-lg font-semibold text-[#e2e2e8]">Dashboard</h1>
        <div className="flex items-center gap-2.5">
          <div className="flex items-center gap-1.5 bg-[#111118] border border-white/[0.06] rounded-lg px-3 py-1.5 text-xs text-[#555]">
            <Icon d="M3 4h18v18H3zM16 2v4M8 2v4M3 10h18" size={13} />
            Jun 2026
          </div>
          <div className="flex gap-1">
            {['7d', '30d', '90d'].map(p => (
              <button key={p} onClick={() => setPeriod(p)}
                className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-colors ${
                  period === p ? 'bg-indigo-600 text-white' : 'bg-transparent text-[#555] border border-white/[0.06] hover:border-white/[0.12]'
                }`}>
                {p}
              </button>
            ))}
          </div>
        </div>
      </div>

      <SectionLabel>Anúncios</SectionLabel>
      <CardsGrid>
        <MetricCard icon="dollar" iconColor="green" value={`R$ ${data.ads_spent.toFixed(2)}`} label="Investimento Total" trend="neutral" />
        <MetricCard icon="eye" iconColor="purple" value={data.ads_impressions} label="Impressões" trend="neutral" />
        <MetricCard icon="cursor" iconColor="blue" value={data.ads_clicks} label="Cliques" trend="neutral" />
        <MetricCard icon="percent" iconColor="teal" value={`${data.ads_ctr.toFixed(2)}%`} label="CTR" trend="neutral" />
        <MetricCard icon="chartLine" iconColor="orange" value={`R$ ${data.ads_cpm.toFixed(2)}`} label="CPM" trend="neutral" />
        <MetricCard icon="target" iconColor="pink" value={`${data.ads_roas.toFixed(2)}x`} label="ROAS" trend="neutral" />
      </CardsGrid>

      <SectionLabel>Instagram</SectionLabel>
      <CardsGrid minWidth={140}>
        <MetricCard icon="photo" iconColor="pink" value={data.instagram_posts} label="Posts (30 dias)" />
        <MetricCard icon="users" iconColor="purple" value={data.instagram_reach} label="Alcance Total" />
        <MetricCard icon="heart" iconColor="red" value={data.instagram_engagement} label="Engajamento Médio" />
        <MetricCard icon="userPlus" iconColor="orange" value={data.instagram_followers_delta} label="Seguidores" />
      </CardsGrid>

      <SectionLabel>Vídeos Gerados</SectionLabel>
      <CardsGrid minWidth={140}>
        <MetricCard icon="video" iconColor="blue" value={data.videos_generated_month} label="Vídeos no Mês" />
        <CreditCard remaining={creditsRemaining} total={data.credits_total} />
        <MetricCard icon="donut" iconColor="indigo" value={`${creditsPercent}%`} label="Créditos Usados" sub={`${data.credits_used} / ${data.credits_total}`} />
        <MetricCard icon="play" iconColor="teal" value={data.last_video_title || 'Nenhum'} label="Último Vídeo" sub={data.last_video_created_at ? new Date(data.last_video_created_at).toLocaleDateString('pt-BR') : ''} />
      </CardsGrid>

      {waCosts && (
        <>
          <SectionLabel>WhatsApp — Custo do mês</SectionLabel>
          <CardsGrid minWidth={140}>
            <MetricCard icon="coins" iconColor="green" value={`R$ ${waCosts.total.toFixed(2)}`} label="Custo total (mês)" />
            <MetricCard icon="receipt" iconColor="blue" value={`R$ ${(waCosts.breakdown.utility?.subtotal ?? 0).toFixed(2)}`} label="Utilidade" sub={`${waCosts.breakdown.utility?.count ?? 0} conversas`} />
            <MetricCard icon="receipt" iconColor="purple" value={`R$ ${(waCosts.breakdown.marketing?.subtotal ?? 0).toFixed(2)}`} label="Marketing" sub={`${waCosts.breakdown.marketing?.count ?? 0} conversas`} />
            <MetricCard icon="receipt" iconColor="orange" value={`R$ ${(waCosts.breakdown.authentication?.subtotal ?? 0).toFixed(2)}`} label="Autenticação" sub={`${waCosts.breakdown.authentication?.count ?? 0} conversas`} />
          </CardsGrid>
        </>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div>
          <SectionLabel>Clientes</SectionLabel>
          <div className="grid grid-cols-2 gap-2.5">
            <MetricCard icon="users" iconColor="blue" value={data.total_customers} label="Total de Clientes" />
            <MetricCard icon="userPlus" iconColor="green" value={data.new_customers_30d} label="Novos (30 dias)" />
            <MetricCard icon="target" iconColor="indigo" value={`${data.conversion_rate}%`} label="Taxa de Conversão" />
            <MetricCard icon="magnet" iconColor="orange" value={data.total_leads} label="Leads Captados" />
          </div>
        </div>
        <div>
          <SectionLabel>Faturamento</SectionLabel>
          <div className="grid grid-cols-2 gap-2.5">
            <MetricCard icon="dollar" iconColor="green" value={`R$ ${data.total_revenue.toFixed(2)}`} label="Faturamento Total" />
            <MetricCard icon="calStats" iconColor="teal" value={`R$ ${data.monthly_revenue.toFixed(2)}`} label="Faturamento (mês)" />
            <MetricCard icon="receipt" iconColor="purple" value={`R$ ${data.average_ticket.toFixed(2)}`} label="Ticket Médio" />
            <MetricCard icon="trending" iconColor="orange" value={`R$ ${data.projected_revenue.toFixed(2)}`} label="Receita Projetada" />
          </div>
        </div>
      </div>
    </div>
  )
}
