import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { AlertTriangle, Info, TrendingUp, Lightbulb } from 'lucide-react'
import api from '../services/api'
import { useI18n } from '../i18n'
import { makeFormat } from '../utils/format'
import { resultLabel } from './AdsUi'

type Fmt = ReturnType<typeof makeFormat>
type T = (pt: string, en: string) => string

export interface Diagnostic {
  code: string
  severity: 'warning' | 'info' | 'good'
  campaign_id: string | null
  campaign_name: string | null
  values: Record<string, number | string>
}

function diagnosticText(t: T, fmt: Fmt, d: Diagnostic): { title: string; detail?: string; action: string } {
  const name = d.campaign_name || ''
  const v = d.values as Record<string, number>
  const label = resultLabel(t, String(d.values.label ?? '')).toLowerCase()
  switch (d.code) {
    case 'not_delivering': return {
      title: t(`"${name}" está ativa, mas não entregou nada`, `"${name}" is active but delivered nothing`),
      detail: t('Nenhuma impressão no período.', 'No impressions in the period.'),
      action: t('Confira se os conjuntos e anúncios estão ativos e aprovados e se há orçamento.', 'Check that ad sets and ads are active and approved and that there is budget.'),
    }
    case 'no_results': return {
      title: t(`"${name}" gastou ${fmt.money(v.spend)} sem nenhum resultado`, `"${name}" spent ${fmt.money(v.spend)} with no results`),
      action: t('Revise o público e o criativo, ou pause para não desperdiçar verba.', 'Review the audience and creative, or pause it to stop wasting budget.'),
    }
    case 'cpr_up': return {
      title: t(`Custo por resultado subiu ${Math.round(v.pct)}% em "${name}"`, `Cost per result rose ${Math.round(v.pct)}% in "${name}"`),
      detail: t(`De ${fmt.money(v.previous)} para ${fmt.money(v.cpr)}.`, `From ${fmt.money(v.previous)} to ${fmt.money(v.cpr)}.`),
      action: t('Veja se a frequência subiu ou se algum anúncio piorou e teste um criativo novo.', 'Check whether frequency went up or an ad got worse, and test a new creative.'),
    }
    case 'cpr_down': return {
      title: t(`Custo por resultado caiu ${Math.round(v.pct)}% em "${name}"`, `Cost per result dropped ${Math.round(v.pct)}% in "${name}"`),
      detail: t(`De ${fmt.money(v.previous)} para ${fmt.money(v.cpr)}.`, `From ${fmt.money(v.previous)} to ${fmt.money(v.cpr)}.`),
      action: t('Está funcionando: considere aumentar o orçamento aos poucos, até 20% por vez.', 'It is working: consider raising the budget gradually, up to 20% at a time.'),
    }
    case 'fatigue': return {
      title: t(`Público cansado em "${name}"`, `Audience fatigue in "${name}"`),
      detail: t(`Cada pessoa viu os anúncios ${fmt.dec(v.frequency)} vezes, em média.`, `Each person saw the ads ${fmt.dec(v.frequency)} times on average.`),
      action: t('Troque o criativo ou amplie o público.', 'Change the creative or widen the audience.'),
    }
    case 'low_ctr': return {
      title: t(`Poucos cliques em "${name}"`, `Few clicks in "${name}"`),
      detail: t(`CTR de ${fmt.pct(v.ctr)}.`, `CTR of ${fmt.pct(v.ctr)}.`),
      action: t('Teste outra imagem ou vídeo, ou uma chamada mais direta no começo do texto.', 'Test another image or video, or a more direct hook at the start of the text.'),
    }
    case 'best': return {
      title: t(`"${name}" tem o menor custo por resultado`, `"${name}" has the lowest cost per result`),
      detail: t(`${fmt.money(v.cpr)} por resultado (${label}), entre as campanhas com o mesmo tipo de resultado.`, `${fmt.money(v.cpr)} per result (${label}), among campaigns with the same kind of result.`),
      action: t('Boa candidata para receber mais orçamento.', 'A good candidate for more budget.'),
    }
    default: return { title: d.code, action: '' }
  }
}

const STYLE = {
  warning: { icon: AlertTriangle, box: 'border-amber-500/25 bg-amber-900/10', icon_cls: 'text-amber-300' },
  info: { icon: Info, box: 'border-sky-500/20 bg-sky-900/10', icon_cls: 'text-sky-300' },
  good: { icon: TrendingUp, box: 'border-emerald-500/20 bg-emerald-900/10', icon_cls: 'text-emerald-300' },
}

export function Diagnostics({ days, fmt }: { days: number; fmt: Fmt }) {
  const { t } = useI18n()
  const [items, setItems] = useState<Diagnostic[] | null>(null)
  useEffect(() => {
    setItems(null)
    api.get<Diagnostic[]>('/marketing/diagnostics', { params: { days } }).then(({ data }) => setItems(data)).catch(() => setItems([]))
  }, [days])
  if (!items || items.length === 0) return null
  return (
    <div className="mb-6">
      <h3 className="flex items-center gap-2 text-sm font-semibold text-ink mb-2">
        <Lightbulb size={15} className="text-amber-300" /> {t('O que o sistema notou', 'What the system noticed')}
      </h3>
      <div className="grid md:grid-cols-2 gap-2">
        {items.map((d, i) => {
          const s = STYLE[d.severity]
          const text = diagnosticText(t, fmt, d)
          const Icon = s.icon
          return (
            <div key={`${d.code}-${d.campaign_id}-${i}`} className={`border rounded-xl p-3 flex gap-3 ${s.box}`}>
              <Icon size={16} className={`shrink-0 mt-0.5 ${s.icon_cls}`} />
              <div className="min-w-0">
                <p className="text-sm text-ink font-medium">{text.title}</p>
                {text.detail && <p className="text-xs text-ink-3 mt-0.5">{text.detail}</p>}
                <p className="text-xs text-ink-2 mt-1">{text.action}</p>
                {d.campaign_id && (
                  <Link to={`/app/marketing/${d.campaign_id}`} className="text-[11px] text-indigo-300 hover:text-indigo-200 mt-1 inline-block">
                    {t('Abrir campanha', 'Open campaign')} →
                  </Link>
                )}
              </div>
            </div>
          )
        })}
      </div>
      <p className="text-[10px] text-ink-5 mt-1.5">{t('Sugestões automáticas a partir dos números do período. Confira antes de mudar algo.', 'Automatic suggestions based on the period’s numbers. Double-check before changing anything.')}</p>
    </div>
  )
}

interface FunnelRow {
  ad_id: string
  ad_name: string | null
  campaign_name: string | null
  spend: number
  leads: number
  buyers: number
  sales: number
  revenue: number
  cost_per_lead: number
  cost_per_sale: number
  roas: number
}

export function Funnel({ days, fmt }: { days: number; fmt: Fmt }) {
  const { t } = useI18n()
  const [data, setData] = useState<{ totals: FunnelRow; rows: FunnelRow[] } | null>(null)
  useEffect(() => {
    setData(null)
    api.get('/marketing/funnel', { params: { days } }).then(({ data }) => setData(data)).catch(() => setData({ totals: null as any, rows: [] }))
  }, [days])
  if (!data) return null

  const roas = (r: FunnelRow) => !r.revenue ? <span className="text-ink-5">—</span>
    : <span className={r.roas >= 1 ? 'text-emerald-400 font-semibold' : 'text-red-400 font-semibold'}>{fmt.dec(r.roas)}×</span>
  const rows = data.rows.filter((r) => r.spend || r.leads || r.sales)

  return (
    <div className="bg-card rounded-2xl border border-white/[0.06] p-5 mb-8">
      <h3 className="text-sm font-semibold text-ink">{t('Do anúncio à venda', 'From ad to sale')}</h3>
      <p className="text-ink-4 text-xs mt-1 mb-4">
        {t(
          'Leads que chegaram por anúncio (WhatsApp, Direct ou formulário) neste período e as vendas registradas neles com "Fechou venda". É o retorno real, sem depender do pixel.',
          'Leads that came from ads (WhatsApp, Direct or form) in this period and the sales recorded on them with "Closed sale". This is the real return, without relying on the pixel.',
        )}
      </p>
      {rows.length === 0 ? (
        <p className="text-sm text-ink-4">{t('Quando chegarem leads de anúncios e você registrar vendas, o retorno de cada anúncio aparece aqui.', 'Once ad leads arrive and you record sales, each ad’s return shows up here.')}</p>
      ) : (
        <>
          <div className="max-md:hidden overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-ink-4 text-[11px] uppercase tracking-wide">
                  <th className="pb-2 pr-3 text-left font-medium">{t('Anúncio', 'Ad')}</th>
                  <th className="pb-2 px-2 text-right font-medium">{t('Gasto', 'Spend')}</th>
                  <th className="pb-2 px-2 text-right font-medium">Leads</th>
                  <th className="pb-2 px-2 text-right font-medium">{t('Custo por lead', 'Cost per lead')}</th>
                  <th className="pb-2 px-2 text-right font-medium">{t('Vendas', 'Sales')}</th>
                  <th className="pb-2 px-2 text-right font-medium">{t('Faturamento', 'Revenue')}</th>
                  <th className="pb-2 pl-2 text-right font-medium" title={t('Faturamento ÷ gasto', 'Revenue ÷ spend')}>{t('Retorno', 'Return')}</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.ad_id} className="border-t border-white/[0.06]">
                    <td className="py-2.5 pr-3">
                      <p className="text-ink">{r.ad_name || `${t('Anúncio', 'Ad')} ${r.ad_id}`}</p>
                      {r.campaign_name && <p className="text-[11px] text-ink-5">{r.campaign_name}</p>}
                    </td>
                    <td className="py-2.5 px-2 text-right text-ink-2">{r.spend ? fmt.money(r.spend) : '—'}</td>
                    <td className="py-2.5 px-2 text-right text-ink-2">{fmt.int(r.leads)}</td>
                    <td className="py-2.5 px-2 text-right text-ink-2">{r.cost_per_lead ? fmt.money(r.cost_per_lead) : '—'}</td>
                    <td className="py-2.5 px-2 text-right text-ink-2">{r.sales ? fmt.int(r.sales) : '—'}</td>
                    <td className="py-2.5 px-2 text-right text-ink-2">{r.revenue ? fmt.money(r.revenue) : '—'}</td>
                    <td className="py-2.5 pl-2 text-right">{roas(r)}</td>
                  </tr>
                ))}
                <tr className="border-t border-white/[0.12] font-semibold">
                  <td className="py-2.5 pr-3 text-ink">{t('Total', 'Total')}</td>
                  <td className="py-2.5 px-2 text-right text-ink">{fmt.money(data.totals.spend)}</td>
                  <td className="py-2.5 px-2 text-right text-ink">{fmt.int(data.totals.leads)}</td>
                  <td className="py-2.5 px-2 text-right text-ink">{data.totals.cost_per_lead ? fmt.money(data.totals.cost_per_lead) : '—'}</td>
                  <td className="py-2.5 px-2 text-right text-ink">{data.totals.sales ? fmt.int(data.totals.sales) : '—'}</td>
                  <td className="py-2.5 px-2 text-right text-ink">{data.totals.revenue ? fmt.money(data.totals.revenue) : '—'}</td>
                  <td className="py-2.5 pl-2 text-right">{roas(data.totals)}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div className="md:hidden space-y-2">
            {[...rows, { ...data.totals, ad_name: t('Total', 'Total'), campaign_name: null }].map((r) => (
              <div key={r.ad_id} className={`rounded-xl border p-3 ${r.ad_id === 'total' ? 'border-white/[0.14]' : 'border-white/[0.06]'}`}>
                <p className="text-sm text-ink font-medium">{r.ad_name || `${t('Anúncio', 'Ad')} ${r.ad_id}`}</p>
                {r.campaign_name && <p className="text-[11px] text-ink-5">{r.campaign_name}</p>}
                <div className="grid grid-cols-3 gap-2 mt-2 text-xs">
                  <div><p className="text-ink-5">{t('Gasto', 'Spend')}</p><p className="text-ink-2">{r.spend ? fmt.money(r.spend) : '—'}</p></div>
                  <div><p className="text-ink-5">Leads</p><p className="text-ink-2">{fmt.int(r.leads)}</p></div>
                  <div><p className="text-ink-5">{t('Custo por lead', 'Cost per lead')}</p><p className="text-ink-2">{r.cost_per_lead ? fmt.money(r.cost_per_lead) : '—'}</p></div>
                  <div><p className="text-ink-5">{t('Vendas', 'Sales')}</p><p className="text-ink-2">{r.sales ? fmt.int(r.sales) : '—'}</p></div>
                  <div><p className="text-ink-5">{t('Faturamento', 'Revenue')}</p><p className="text-ink-2">{r.revenue ? fmt.money(r.revenue) : '—'}</p></div>
                  <div><p className="text-ink-5">{t('Retorno', 'Return')}</p><p>{roas(r)}</p></div>
                </div>
              </div>
            ))}
          </div>
          <p className="text-[10px] text-ink-5 mt-3">
            {t('Retorno = faturamento ÷ gasto. Acima de 1×, o anúncio pagou o que custou. Só conta vendas registradas com "Fechou venda" em leads que vieram de anúncio.', 'Return = revenue ÷ spend. Above 1×, the ad paid for itself. Only counts sales recorded with "Closed sale" on leads that came from an ad.')}
          </p>
        </>
      )}
    </div>
  )
}
