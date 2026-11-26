import { useCallback, useEffect, useState } from 'react'
import { Check, Copy, Loader2, X } from 'lucide-react'
import api, { apiError } from '../services/api'
import { useI18n } from '../i18n'
import { makeFormat } from '../utils/format'

interface PackStatus {
  conversations: number
  price_cents: number
  has_customer: boolean
  is_child: boolean
  pending: { id: string; value: number; invoice_url: string | null; pix_payload: string | null; pix_image: string | null } | null
}

/** Compra de pacote extra de atendimentos com IA (Pix pelo Asaas). */
export default function AIPackDialog({ onClose, onPaid }: { onClose: () => void; onPaid: () => void }) {
  const { t, locale } = useI18n()
  const fmt = makeFormat(locale, 'BRL')
  const [pack, setPack] = useState<PackStatus | null>(null)
  const [name, setName] = useState('')
  const [doc, setDoc] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [copied, setCopied] = useState(false)
  const [hadPending, setHadPending] = useState(false)

  const load = useCallback(async () => {
    try {
      const { data } = await api.get<PackStatus>('/billing/ai-pack')
      setPack(data)
      if (data.pending) setHadPending(true)
      else if (hadPending) onPaid()
    } catch (e) { setError(apiError(e, t('Não foi possível carregar.', 'Could not load.'))) }
  }, [hadPending, onPaid])

  useEffect(() => { load() }, [])
  useEffect(() => {
    if (!pack?.pending) return
    const id = window.setInterval(load, 5000)
    return () => window.clearInterval(id)
  }, [pack?.pending?.id, load])

  async function buy() {
    setBusy(true)
    setError('')
    try {
      const { data } = await api.post<PackStatus>('/billing/ai-pack', pack?.has_customer ? {} : { name: name.trim(), document: doc })
      setPack(data)
      if (data.pending) setHadPending(true)
    } catch (e) { setError(apiError(e, t('Não foi possível gerar a cobrança.', 'Could not create the charge.'))) }
    finally { setBusy(false) }
  }

  const input = 'w-full px-3 py-2 bg-field border border-white/[0.08] text-ink text-sm rounded-lg focus:border-indigo-500 focus:outline-none'
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm px-4">
      <div className="bg-card border border-white/[0.08] rounded-2xl p-6 w-full max-w-sm">
        <div className="flex items-center justify-between mb-1">
          <h3 className="text-base font-semibold text-white">{t('Mais atendimentos com IA', 'More AI conversations')}</h3>
          <button onClick={onClose} aria-label={t('Fechar', 'Close')} className="text-ink-5 hover:text-ink-3"><X size={18} /></button>
        </div>
        {!pack ? (
          <p className="text-sm text-ink-4">{t('Carregando…', 'Loading…')}</p>
        ) : pack.is_child ? (
          <p className="text-sm text-ink-4">{t('A IA desta empresa usa a franquia da agência. Peça à agência para comprar mais.', "This company's AI uses the agency allowance. Ask the agency to buy more.")}</p>
        ) : pack.pending ? (
          <div className="text-center">
            <p className="text-sm text-ink-3 mb-3">{t(`${fmt.money(pack.pending.value)} · +${pack.conversations} atendimentos`, `${fmt.money(pack.pending.value)} · +${pack.conversations} conversations`)}</p>
            {pack.pending.pix_image && <img src={`data:image/png;base64,${pack.pending.pix_image}`} alt="QR Code Pix" className="w-48 h-48 mx-auto rounded-lg bg-white p-2 mb-3" />}
            {pack.pending.pix_payload && (
              <button onClick={async () => { await navigator.clipboard.writeText(pack.pending!.pix_payload!); setCopied(true); window.setTimeout(() => setCopied(false), 2000) }}
                className="w-full py-2 border border-white/[0.1] text-ink-2 hover:text-white text-sm rounded-lg flex items-center justify-center gap-2 mb-2">
                {copied ? <Check size={14} className="text-emerald-400" /> : <Copy size={14} />}{copied ? t('Copiado', 'Copied') : t('Copiar Pix copia e cola', 'Copy Pix code')}
              </button>
            )}
            {pack.pending.invoice_url && <a href={pack.pending.invoice_url} target="_blank" rel="noreferrer" className="block text-xs text-violet-300 underline mb-2">{t('Abrir a cobrança', 'Open the charge')}</a>}
            <p className="text-[11px] text-ink-5 flex items-center justify-center gap-1.5"><Loader2 size={11} className="animate-spin" />{t('Os atendimentos entram assim que o Pix for pago.', 'The conversations are added as soon as the Pix is paid.')}</p>
          </div>
        ) : (
          <>
            <p className="text-sm text-ink-4 mb-4">
              {t(`+${pack.conversations} atendimentos com IA por ${fmt.money(pack.price_cents / 100)}, pagos por Pix. Valem depois da franquia do plano e não vencem.`, `+${pack.conversations} AI conversations for ${fmt.money(pack.price_cents / 100)}, paid by Pix. They are used after the plan allowance and don't expire.`)}
            </p>
            {!pack.has_customer && (
              <>
                <label className="block text-[11px] text-ink-4 mb-1">{t('Nome ou razão social', 'Name or company name')}</label>
                <input value={name} onChange={(e) => setName(e.target.value)} className={`${input} mb-3`} />
                <label className="block text-[11px] text-ink-4 mb-1">CPF ou CNPJ</label>
                <input value={doc} onChange={(e) => setDoc(e.target.value)} inputMode="numeric" className={`${input} mb-4`} />
              </>
            )}
            {error && <p className="text-xs text-red-400 mb-3">{error}</p>}
            <button onClick={buy} disabled={busy || (!pack.has_customer && (name.trim().length < 2 || doc.replace(/\D/g, '').length < 11))}
              className="w-full py-2.5 bg-violet-600 hover:bg-violet-500 disabled:opacity-50 text-white text-sm font-semibold rounded-lg">
              {busy ? t('Gerando o Pix…', 'Creating the Pix…') : t('Gerar Pix', 'Create Pix')}
            </button>
          </>
        )}
      </div>
    </div>
  )
}
