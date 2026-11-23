import { useI18n } from '../i18n'

interface BreakdownRow {
  key: string
  spend: number
  impressions: number
}

export interface SyncedOverview {
  synced_at: string | null
  campaign_counts: Record<string, { ad_sets: number; ads: number }>
  breakdowns: Record<string, BreakdownRow[]>
}

/** Público dos últimos 7 dias, lido do sync periódico (sem chamada à Meta ao abrir a tela). */
export default function AdsSyncPanel({ overview }: { overview: SyncedOverview }) {
  const { t, locale } = useI18n()

  const columns = [
    { dimension: 'age', title: t('Idade', 'Age') },
    { dimension: 'gender', title: t('Gênero', 'Gender') },
    { dimension: 'publisher_platform', title: t('Plataforma', 'Platform') },
  ]
  const labels: Record<string, string> = {
    male: t('Masculino', 'Male'),
    female: t('Feminino', 'Female'),
    unknown: t('Não informado', 'Unknown'),
    facebook: 'Facebook',
    instagram: 'Instagram',
    messenger: 'Messenger',
    audience_network: 'Audience Network',
  }

  if (!overview.synced_at || !columns.some((c) => overview.breakdowns[c.dimension]?.length)) return null

  return (
    <div className="bg-card rounded-xl border border-white/[0.06] p-5 mb-8">
      <div className="flex flex-wrap items-baseline justify-between gap-2 mb-4">
        <h3 className="text-sm font-semibold text-ink">{t('Público · últimos 7 dias', 'Audience · last 7 days')}</h3>
        <p className="text-[11px] text-ink-4">
          {t('Atualizado em', 'Updated')} {new Date(overview.synced_at).toLocaleString(locale)}
        </p>
      </div>
      <div className="grid md:grid-cols-3 gap-6">
        {columns.map(({ dimension, title }) => {
          const rows = overview.breakdowns[dimension] ?? []
          const max = Math.max(1, ...rows.map((r) => r.impressions))
          return (
            <div key={dimension}>
              <p className="text-xs font-medium text-ink-3 mb-2">{title}</p>
              {rows.length === 0 && <p className="text-xs text-ink-4">—</p>}
              <div className="space-y-2">
                {rows.map((r) => (
                  <div key={r.key}>
                    <div className="flex justify-between gap-2 text-xs">
                      <span className="text-ink-2 truncate">{labels[r.key] ?? r.key}</span>
                      <span className="text-ink-4 shrink-0">
                        {r.impressions.toLocaleString(locale)} · R$ {r.spend.toFixed(2)}
                      </span>
                    </div>
                    <div className="h-1.5 mt-1 rounded-full bg-white/[0.05]">
                      <div className="h-full rounded-full bg-violet-500" style={{ width: `${(r.impressions / max) * 100}%` }} />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
