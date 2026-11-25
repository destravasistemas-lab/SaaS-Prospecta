import { useEffect, useState } from 'react'
import { BadgeDollarSign, X } from 'lucide-react'
import api, { apiError } from '../services/api'
import { useI18n } from '../i18n'

export interface SaleSummary {
  lead_status: string
  total: number
  sales: { id: string; amount: number; description: string | null; status: string; sold_at: string }[]
}

const brl = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' })

export function parseAmount(raw: string): number {
  let s = raw.replace(/R\$|\s/g, '')
  if (s.includes(',')) s = s.replace(/\./g, '').replace(',', '.')
  else if (/^\d{1,3}(\.\d{3})+$/.test(s)) s = s.replace(/\./g, '')
  const n = Number(s)
  return s && Number.isFinite(n) ? n : NaN
}

export default function SaleDialog({ leadId, name, onClose, onChanged }: {
  leadId: string
  name: string
  onClose: () => void
  onChanged?: (s: SaleSummary) => void
}) {
  const { t } = useI18n()
  const [summary, setSummary] = useState<SaleSummary | null>(null)
  const [amount, setAmount] = useState('')
  const [description, setDescription] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [done, setDone] = useState(false)

  useEffect(() => {
    api.get(`/leads/${leadId}/sales`)
      .then((r) => setSummary(r.data))
      .catch((e) => setError(apiError(e, t('Não foi possível carregar as vendas.', 'Could not load sales.'))))
  }, [leadId])

  function apply(s: SaleSummary) {
    setSummary(s)
    onChanged?.(s)
  }

  async function save() {
    const value = parseAmount(amount)
    if (!(value > 0)) {
      setError(t('Informe o valor da venda (ex.: 1.500,00).', 'Enter the sale amount (e.g. 1500.00).'))
      return
    }
    setSaving(true)
    setError('')
    try {
      const r = await api.post(`/leads/${leadId}/sales`, { amount: value, description: description.trim() || null })
      apply(r.data)
      setAmount('')
      setDescription('')
      setDone(true)
    } catch (e) {
      setError(apiError(e, t('Não foi possível registrar a venda.', 'Could not record the sale.')))
    } finally {
      setSaving(false)
    }
  }

  async function cancel(id: string) {
    if (!confirm(t('Desfazer esta venda? Ela sai da receita.', 'Undo this sale? It will be removed from revenue.'))) return
    try {
      apply((await api.post(`/leads/${leadId}/sales/${id}/cancel`)).data)
      setDone(false)
    } catch (e) {
      setError(apiError(e, t('Não foi possível desfazer.', 'Could not undo.')))
    }
  }

  const active = summary?.sales.filter((s) => s.status === 'completed') ?? []

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center max-lg:[align-items:safe_center] max-lg:overflow-y-auto max-lg:py-4 bg-black/70 backdrop-blur-sm px-4">
      <div className="bg-card border border-white/[0.08] rounded-2xl p-6 w-full max-w-md max-h-[85vh] overflow-y-auto">
        <div className="flex items-center justify-between mb-1">
          <h3 className="text-base font-semibold text-white flex items-center gap-2">
            <BadgeDollarSign size={18} className="text-emerald-400" />
            {t('Fechou venda', 'Closed sale')}
          </h3>
          <button onClick={onClose} aria-label={t('Fechar', 'Close')} className="text-ink-5 hover:text-ink-3"><X size={18} /></button>
        </div>
        <p className="text-xs text-ink-4 mb-4">{name}</p>

        {done && (
          <div className="bg-emerald-900/20 border border-emerald-500/25 text-emerald-300 text-xs rounded-lg px-3 py-2 mb-4">
            {t(
              'Venda registrada. O lead virou cliente, entrou na receita do painel e não recebe mais follow-up automático.',
              'Sale recorded. The lead is now a customer, counts toward revenue and gets no more automatic follow-ups.',
            )}
          </div>
        )}

        {active.length > 0 && (
          <div className="mb-4">
            <div className="flex items-baseline justify-between mb-2">
              <span className="text-[11px] uppercase tracking-wide text-ink-5">{t('Vendas deste cliente', 'Sales from this customer')}</span>
              <span className="text-sm font-semibold text-emerald-300">{brl.format(summary!.total)}</span>
            </div>
            <ul className="space-y-1.5">
              {active.map((s) => (
                <li key={s.id} className="flex items-center gap-2 text-xs bg-white/[0.03] border border-white/[0.06] rounded-lg px-3 py-2">
                  <span className="font-medium text-ink">{brl.format(s.amount)}</span>
                  <span className="text-ink-4 truncate flex-1">
                    {s.description || '—'} · {new Date(s.sold_at).toLocaleDateString('pt-BR')}
                  </span>
                  <button onClick={() => cancel(s.id)} className="text-ink-5 hover:text-red-400 shrink-0">
                    {t('Desfazer', 'Undo')}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}

        <label className="block text-xs text-ink-3 mb-1">{t('Valor da venda', 'Sale amount')}</label>
        <input
          autoFocus
          inputMode="decimal"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && save()}
          placeholder="R$ 0,00"
          className="w-full px-3 py-2 mb-3 bg-field border border-white/[0.08] text-ink text-sm rounded-lg focus:border-indigo-500 focus:outline-none"
        />
        <label className="block text-xs text-ink-3 mb-1">{t('O que foi vendido (opcional)', 'What was sold (optional)')}</label>
        <input
          value={description}
          maxLength={500}
          onChange={(e) => setDescription(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && save()}
          placeholder={t('Ex.: Plano anual', 'E.g. Annual plan')}
          className="w-full px-3 py-2 mb-4 bg-field border border-white/[0.08] text-ink text-sm rounded-lg focus:border-indigo-500 focus:outline-none"
        />

        {error && <p className="text-xs text-red-400 mb-3">{error}</p>}

        <div className="flex gap-2">
          <button onClick={onClose} className="flex-1 py-2 rounded-lg border border-white/[0.08] text-ink-3 hover:text-white text-sm">
            {done ? t('Concluir', 'Done') : t('Cancelar', 'Cancel')}
          </button>
          <button
            onClick={save}
            disabled={saving}
            className="flex-1 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-sm font-semibold"
          >
            {saving ? t('Salvando…', 'Saving…') : active.length ? t('Registrar outra venda', 'Record another sale') : t('Registrar venda', 'Record sale')}
          </button>
        </div>
      </div>
    </div>
  )
}
