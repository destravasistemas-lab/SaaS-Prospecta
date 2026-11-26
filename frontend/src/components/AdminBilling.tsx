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
  const setLimit = (code: string, key: 'users' | 'clients' | 'ai_tokens', raw: string) =>
    set(code, { limits: { ...drafts[code].limits, [key]: raw === '' ? null : key === 'ai_tokens' ? Math.round(Number(raw) * 1_000_000) : Number(raw) } })

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
    set(code, { code, name: newCode.trim(), description: '', price_cents: 0, priceText: '0,00', limits: { users: 1, clients: 0, ai_tokens: 1_000_000 },
      modules: ['whatsapp'], extras: [], extrasText: '', highlight: false, active: false, sort: plans.length + 1 })
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
            <label className="text-[11px] text-ink-4">{t('IA (milhões de tokens/mês)', 'AI (million tokens/month)')}<input type="number" min={0} step={0.5} value={d.limits.ai_tokens == null ? '' : d.limits.ai_tokens / 1_000_000} onChange={(e) => setLimit(d.code, 'ai_tokens', e.target.value)} className={`${input} block mt-1 w-full`} /></label>
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
