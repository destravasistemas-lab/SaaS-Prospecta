import { useEffect, useState } from 'react'
import { Gift, Clock3, Save, Plus } from 'lucide-react'
import api, { apiError } from '../services/api'
import { useI18n } from '../i18n'
import { makeFormat } from '../utils/format'
import { parseAmount } from './SaleDialog'
import type { Plan } from '../pages/Pricing'

export interface TenantBillingInfo {
  status: 'unmanaged' | 'courtesy' | 'trial' | 'active' | 'past_due' | 'canceled' | 'blocked'
  until: string | null
  days_left: number | null
  plan: string | null
  subscribed: boolean
  note: string | null
}

interface AdminPlan extends Plan { active: boolean; sort: number }

const input = 'px-3 py-2 bg-field border border-line text-ink text-sm rounded-lg focus:border-violet-500 focus:outline-none'

export function useStatusLabel() {
  const { t } = useI18n()
  return (s: TenantBillingInfo['status']) => ({
    unmanaged: [t('Fora da cobrança', 'Not billed'), 'text-ink-4 border-line'],
    courtesy: [t('Cortesia', 'Courtesy'), 'text-sky-300 border-sky-500/30'],
    trial: [t('Teste grátis', 'Free trial'), 'text-amber-300 border-amber-500/30'],
    active: [t('Pago', 'Paid'), 'text-emerald-300 border-emerald-500/30'],
    past_due: [t('Em atraso', 'Overdue'), 'text-red-300 border-red-500/30'],
    canceled: [t('Cancelado', 'Canceled'), 'text-ink-3 border-line'],
    blocked: [t('Bloqueado', 'Blocked'), 'text-red-300 border-red-500/40'],
  }[s])
}

/** Cobrança de uma conta no Super Admin: situação, plano e ações sem cobrança. */
export function TenantBilling({ tenantId, info, plans, onChange }: {
  tenantId: string
  info: TenantBillingInfo
  plans: AdminPlan[]
  onChange: (tenant: any) => void
}) {
  const { t, locale } = useI18n()
  const label = useStatusLabel()
  const [mode, setMode] = useState<'courtesy' | 'trial' | null>(null)
  const [until, setUntil] = useState('')
  const [days, setDays] = useState('7')
  const [plan, setPlan] = useState(info.plan || '')
  const [note, setNote] = useState(info.note || '')
  const [busy, setBusy] = useState(false)

  async function act(body: Record<string, unknown>) {
    setBusy(true)
    try {
      onChange((await api.post(`/admin/tenants/${tenantId}/billing`, body)).data)
      setMode(null)
    } catch (e) {
      alert(apiError(e, t('Erro ao salvar.', 'Failed to save.')))
    } finally { setBusy(false) }
  }

  const [text, cls] = label(info.status)
  const date = info.until ? new Date(info.until).toLocaleDateString(locale) : ''
  return (
    <div className="mt-3 pt-3 border-t border-line">
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span className={`px-2 py-0.5 rounded-full border font-semibold ${cls}`}>{text}</span>
        {info.status === 'courtesy' && <span className="text-ink-4">{date ? t(`até ${date}`, `until ${date}`) : t('sem prazo', 'no end date')}</span>}
        {['trial', 'active', 'past_due', 'canceled'].includes(info.status) && date && <span className="text-ink-4">{t(`até ${date}`, `until ${date}`)}</span>}
        {info.plan && <span className="text-ink-4">· {plans.find((p) => p.code === info.plan)?.name || info.plan}</span>}
        {info.subscribed && <span className="text-emerald-400/80">· {t('assinatura no Asaas', 'Asaas subscription')}</span>}
        {info.note && <span className="text-ink-5 italic">· {info.note}</span>}
        <span className="flex-1" />
        <button onClick={() => setMode(mode === 'courtesy' ? null : 'courtesy')} className="flex items-center gap-1 px-2.5 py-1 rounded-lg border border-sky-500/30 text-sky-300 hover:bg-sky-500/10">
          <Gift size={12} />{t('Liberar teste sem cobrança', 'Grant free access')}
        </button>
        <button onClick={() => setMode(mode === 'trial' ? null : 'trial')} className="flex items-center gap-1 px-2.5 py-1 rounded-lg border border-amber-500/30 text-amber-300 hover:bg-amber-500/10">
          <Clock3 size={12} />{t('Dar teste grátis', 'Give free trial')}
        </button>
        {info.status === 'courtesy' && (
          <button onClick={() => act({ action: 'end_courtesy' })} disabled={busy} className="px-2.5 py-1 rounded-lg border border-line text-ink-3 hover:text-red-300">
            {t('Encerrar cortesia', 'End courtesy')}
          </button>
        )}
      </div>

      {mode && (
        <div className="mt-3 flex flex-wrap items-end gap-2 bg-white/[0.02] border border-line rounded-lg p-3">
          {mode === 'courtesy' ? (
            <label className="text-[11px] text-ink-4">{t('Até (vazio = sem prazo)', 'Until (empty = no end date)')}
              <input type="date" value={until} onChange={(e) => setUntil(e.target.value)} className={`${input} block mt-1`} />
            </label>
          ) : (
            <label className="text-[11px] text-ink-4">{t('Dias de teste a partir de hoje', 'Trial days from today')}
              <input type="number" min={1} max={365} value={days} onChange={(e) => setDays(e.target.value)} className={`${input} block mt-1 w-28`} />
            </label>
          )}
          <label className="text-[11px] text-ink-4">{t('Plano (limites e módulos)', 'Plan (limits and modules)')}
            <select value={plan} onChange={(e) => setPlan(e.target.value)} className={`${input} block mt-1`}>
              <option value="">{t('Manter', 'Keep')}</option>
              {plans.map((p) => <option key={p.code} value={p.code}>{p.name}</option>)}
            </select>
          </label>
          <label className="text-[11px] text-ink-4 flex-1 min-w-[10rem]">{t('Observação', 'Note')}
            <input value={note} onChange={(e) => setNote(e.target.value)} maxLength={500} placeholder={t('Ex.: parceiro, piloto até março', 'E.g. partner, pilot until March')} className={`${input} block mt-1 w-full`} />
          </label>
          <button disabled={busy} onClick={() => act(mode === 'courtesy'
            ? { action: 'courtesy', until: until || null, plan: plan || null, note }
            : { action: 'trial', days: Number(days) || 7, plan: plan || null, note })}
            className="px-3 py-2 bg-violet-600 hover:bg-violet-500 disabled:opacity-50 text-white rounded-lg text-xs font-semibold">
            {busy ? t('Salvando…', 'Saving…') : t('Confirmar', 'Confirm')}
          </button>
        </div>
      )}
    </div>
  )
}

/** Editor dos planos: preço, limites, módulos e itens extras. */
export function PlansEditor({ plans, reload }: { plans: AdminPlan[]; reload: () => void }) {
  const { t, locale } = useI18n()
  const [drafts, setDrafts] = useState<Record<string, AdminPlan & { priceText: string; extrasText: string }>>({})
  const [newCode, setNewCode] = useState('')
  const [saving, setSaving] = useState<string | null>(null)
  const fmt = makeFormat(locale, 'BRL')

  useEffect(() => {
    setDrafts(Object.fromEntries(plans.map((p) => [p.code, {
      ...p, priceText: fmt.dec(p.price_cents / 100), extrasText: p.extras.join('\n'),
    }])))
  }, [plans])

  const set = (code: string, patch: Partial<AdminPlan & { priceText: string; extrasText: string }>) =>
    setDrafts((d) => ({ ...d, [code]: { ...d[code], ...patch } }))
  const setLimit = (code: string, key: 'users' | 'clients' | 'ai_tokens' | 'scheduled_posts' | 'storage_mb' | 'automations', raw: string) =>
    set(code, { limits: { ...drafts[code].limits, [key]: raw === '' ? null : key === 'ai_tokens' ? Math.round(Number(raw) * perConv(code)) : Number(raw) } })
  const perConv = (code: string) => Math.max(1, drafts[code]?.tokens_per_conversation || 20000)

  async function save(code: string) {
    const d = drafts[code]
    setSaving(code)
    try {
      await api.put(`/admin/plans/${code}`, {
        name: d.name, description: d.description, price_cents: Math.round(parseAmount(d.priceText) * 100),
        limits: d.limits, modules: d.modules, extras: d.extrasText.split('\n'), highlight: d.highlight,
        active: d.active, sort: d.sort,
      })
      reload()
    } catch (e) {
      alert(apiError(e, t('Erro ao salvar.', 'Failed to save.')))
    } finally { setSaving(null) }
  }

  function addPlan() {
    const code = newCode.trim().toLowerCase().replace(/[^a-z0-9_]/g, '_')
    if (!code || drafts[code]) return
    set(code, { code, name: newCode.trim(), description: '', price_cents: 0, priceText: '0,00', limits: { users: 1, clients: 0, ai_tokens: 1_000_000, scheduled_posts: 30, storage_mb: 500, automations: 20 },
      modules: ['whatsapp'], extras: [], extrasText: '', highlight: false, active: false, sort: plans.length + 1,
      ai_conversations: 50, tokens_per_conversation: plans[0]?.tokens_per_conversation || 20000 })
    setNewCode('')
  }

  return (
    <div className="space-y-4">
      <p className="text-xs text-ink-4">
        {t('O preço novo vale para as próximas assinaturas e trocas de plano. Quem já assina continua com o valor atual até trocar de plano. Vazio nos limites = sem limite.', 'New prices apply to new subscriptions and plan changes. Current subscribers keep their price until they switch plans. Empty limits = unlimited.')}
      </p>
      {Object.values(drafts).map((d) => (
        <div key={d.code} className="bg-card border border-line rounded-xl p-4 space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <input value={d.name} onChange={(e) => set(d.code, { name: e.target.value })} className={`${input} font-semibold w-44`} />
            <span className="text-[11px] text-ink-5">{d.code}</span>
            <span className="flex-1" />
            <label className="flex items-center gap-1.5 text-xs text-ink-3"><input type="checkbox" checked={d.highlight} onChange={(e) => set(d.code, { highlight: e.target.checked })} className="accent-violet-500" />{t('Destaque', 'Highlight')}</label>
            <label className="flex items-center gap-1.5 text-xs text-ink-3"><input type="checkbox" checked={d.active} onChange={(e) => set(d.code, { active: e.target.checked })} className="accent-violet-500" />{t('À venda', 'On sale')}</label>
          </div>
          <input value={d.description || ''} onChange={(e) => set(d.code, { description: e.target.value })} placeholder={t('Descrição curta', 'Short description')} className={`${input} w-full`} />
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            <label className="text-[11px] text-ink-4">{t('Preço por mês (R$)', 'Price per month (R$)')}<input value={d.priceText} onChange={(e) => set(d.code, { priceText: e.target.value })} className={`${input} block mt-1 w-full`} /></label>
            <label className="text-[11px] text-ink-4">{t('Usuários', 'Users')}<input type="number" min={0} value={d.limits.users ?? ''} onChange={(e) => setLimit(d.code, 'users', e.target.value)} className={`${input} block mt-1 w-full`} /></label>
            <label className="text-[11px] text-ink-4">{t('Empresas clientes', 'Client companies')}<input type="number" min={0} value={d.limits.clients ?? ''} onChange={(e) => setLimit(d.code, 'clients', e.target.value)} className={`${input} block mt-1 w-full`} /></label>
            <label className="text-[11px] text-ink-4">{t('IA (atendimentos/mês)', 'AI (conversations/month)')}<input type="number" min={0} step={50} value={d.limits.ai_tokens == null ? '' : Math.round(d.limits.ai_tokens / perConv(d.code))} onChange={(e) => setLimit(d.code, 'ai_tokens', e.target.value)} className={`${input} block mt-1 w-full`} /></label>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            <label className="text-[11px] text-ink-4">{t('Posts agendados por vez', 'Scheduled posts at a time')}<input type="number" min={0} value={d.limits.scheduled_posts ?? ''} onChange={(e) => setLimit(d.code, 'scheduled_posts', e.target.value)} className={`${input} block mt-1 w-full`} /></label>
            <label className="text-[11px] text-ink-4">{t('Mídia guardada (MB)', 'Stored media (MB)')}<input type="number" min={0} step={100} value={d.limits.storage_mb ?? ''} onChange={(e) => setLimit(d.code, 'storage_mb', e.target.value)} className={`${input} block mt-1 w-full`} /></label>
            <label className="text-[11px] text-ink-4">{t('Automações ativas', 'Active automations')}<input type="number" min={0} value={d.limits.automations ?? ''} onChange={(e) => setLimit(d.code, 'automations', e.target.value)} className={`${input} block mt-1 w-full`} /></label>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {[['whatsapp', 'WhatsApp'], ['instagram', 'Instagram'], ['ads', 'Meta Ads'], ['ia', 'IA']].map(([key, name]) => {
              const on = d.modules.includes(key)
              return (
                <button key={key} onClick={() => set(d.code, { modules: on ? d.modules.filter((m) => m !== key) : [...d.modules, key] })}
                  className={`px-3 py-1.5 rounded-lg border text-xs font-medium ${on ? 'bg-green-600/10 border-green-500/40 text-green-300' : 'bg-field border-line text-ink-5 line-through'}`}>
                  {name}
                </button>
              )
            })}
          </div>
          <label className="block text-[11px] text-ink-4">{t('Itens extras no card (um por linha)', 'Extra items on the card (one per line)')}
            <textarea value={d.extrasText} onChange={(e) => set(d.code, { extrasText: e.target.value })} rows={2} className={`${input} block mt-1 w-full`} />
          </label>
          <button onClick={() => save(d.code)} disabled={saving === d.code} className="flex items-center gap-1.5 px-3 py-2 bg-violet-600 hover:bg-violet-500 disabled:opacity-50 text-white rounded-lg text-xs font-semibold">
            <Save size={12} />{saving === d.code ? t('Salvando…', 'Saving…') : t('Salvar plano', 'Save plan')}
          </button>
        </div>
      ))}
      <div className="flex gap-2">
        <input value={newCode} onChange={(e) => setNewCode(e.target.value)} placeholder={t('Nome do novo plano', 'New plan name')} className={`${input} flex-1`} />
        <button onClick={addPlan} className="flex items-center gap-1.5 px-3 py-2 border border-line text-ink-2 hover:text-white rounded-lg text-xs font-semibold">
          <Plus size={13} />{t('Novo plano', 'New plan')}
        </button>
      </div>
    </div>
  )
}

interface AIUsageData {
  days: number
  keys: number
  limits: { key_rpm: number; account_rpm: number; slot_wait_seconds: number; tokens_per_conversation: number }
  totals: { replies: number; fallbacks: number; rate_limited: number; platform_tokens: number; cost_brl: number; avg_wait_ms: number }
  accounts: { account_id: string; name: string; replies: number; fallbacks: number; rate_limited: number; platform_tokens: number; cost: number; conversations: number }[]
}

/** Consumo e saúde da IA do Prospecta (custo estimado, 429 e espera na fila). */
export function AIUsagePanel() {
  const { t, locale } = useI18n()
  const fmt = makeFormat(locale, 'BRL')
  const [days, setDays] = useState(30)
  const [data, setData] = useState<AIUsageData | null>(null)
  useEffect(() => {
    setData(null)
    api.get<AIUsageData>('/admin/ai-usage', { params: { days } }).then(({ data }) => setData(data)).catch(() => {})
  }, [days])
  if (!data) return <p className="text-sm text-ink-4">{t('Carregando…', 'Loading…')}</p>
  const tot = data.totals
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        {[7, 30, 90].map((d) => (
          <button key={d} onClick={() => setDays(d)} className={`px-3 py-1.5 rounded-lg text-xs border ${days === d ? 'border-violet-500/50 bg-violet-600/15 text-violet-200' : 'border-line text-ink-4'}`}>
            {t(`${d} dias`, `${d} days`)}
          </button>
        ))}
        <span className="text-xs text-ink-4 ml-auto">
          {data.keys === 0 ? t('Nenhuma chave do Prospecta configurada (GEMINI_API_KEYS).', 'No Prospecta key configured (GEMINI_API_KEYS).')
            : t(`${data.keys} chave(s) · ${data.limits.key_rpm}/min por chave · ${data.limits.account_rpm}/min por conta`, `${data.keys} key(s) · ${data.limits.key_rpm}/min per key · ${data.limits.account_rpm}/min per account`)}
        </span>
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
        {([
          [t('Respostas da IA', 'AI replies'), fmt.int(tot.replies)],
          [t('Custo estimado (chaves do Prospecta)', 'Estimated cost (Prospecta keys)'), fmt.money(tot.cost_brl)],
          [t('Atendimentos consumidos', 'Conversations used'), fmt.int(Math.floor(tot.platform_tokens / Math.max(1, data.limits.tokens_per_conversation)))],
          [t('Limite do Google (429)', 'Google rate limit (429)'), fmt.int(tot.rate_limited)],
          [t('Espera média na fila', 'Average queue wait'), `${(tot.avg_wait_ms / 1000).toFixed(1)} s`],
          [t('Foram para o humano', 'Handed to a human'), fmt.int(tot.fallbacks)],
        ] as [string, string][]).map(([label, value]) => (
          <div key={label} className="bg-card border border-line rounded-xl p-3">
            <p className="text-[11px] text-ink-4">{label}</p>
            <p className="text-lg font-bold text-ink">{value}</p>
          </div>
        ))}
      </div>
      {tot.rate_limited > 0 && (
        <p className="text-xs text-amber-300">{t('Houve limite do Google no período. Se acontecer com frequência, acrescente outra chave em GEMINI_API_KEYS ou suba o nível da conta no Google.', 'Google rate limits happened in the period. If it is frequent, add another key to GEMINI_API_KEYS or raise the Google account tier.')}</p>
      )}
      <div className="bg-card border border-line rounded-xl p-4 overflow-x-auto">
        <p className="text-sm font-semibold text-ink mb-2">{t('Contas que mais usam a IA do Prospecta', 'Accounts using Prospecta AI the most')}</p>
        {data.accounts.length === 0 ? <p className="text-xs text-ink-4">{t('Sem uso no período.', 'No usage in the period.')}</p> : (
          <table className="w-full text-xs">
            <thead><tr className="text-ink-4 text-left">
              <th className="pb-2 pr-2 font-medium">{t('Conta', 'Account')}</th>
              <th className="pb-2 px-2 text-right font-medium">{t('Atendimentos', 'Conversations')}</th>
              <th className="pb-2 px-2 text-right font-medium">{t('Respostas', 'Replies')}</th>
              <th className="pb-2 px-2 text-right font-medium">{t('Custo', 'Cost')}</th>
              <th className="pb-2 pl-2 text-right font-medium">429</th>
            </tr></thead>
            <tbody>
              {data.accounts.map((a) => (
                <tr key={a.account_id} className="border-t border-line">
                  <td className="py-2 pr-2 text-ink">{a.name}</td>
                  <td className="py-2 px-2 text-right text-ink-2">{fmt.int(a.conversations)}</td>
                  <td className="py-2 px-2 text-right text-ink-2">{fmt.int(a.replies)}</td>
                  <td className="py-2 px-2 text-right text-ink-2">{fmt.money(a.cost)}</td>
                  <td className="py-2 pl-2 text-right text-ink-2">{a.rate_limited}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
      <p className="text-[11px] text-ink-5">{t('O custo é estimado com os preços configurados no servidor (AI_PRICE_*, USD_BRL). Confira a fatura do Google Cloud.', 'Cost is estimated with the prices configured on the server (AI_PRICE_*, USD_BRL). Check your Google Cloud invoice.')}</p>
    </div>
  )
}
