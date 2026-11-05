import { useEffect, useState } from 'react'
import { Phone, PhoneIncoming, PhoneMissed, X } from 'lucide-react'
import api, { apiError } from '../services/api'
import { useI18n, tr } from '../i18n'

export interface CallInfo {
  status: string
  duration_seconds?: number | null
  answered_by?: string | null
  rejected_by?: string | null
}

/** Sem o terminate da Meta, a chamada não pode parecer "tocando" para sempre. */
const STALE_AFTER_MS = 2 * 60 * 1000

function formatDuration(seconds: number): string {
  return `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`
}

function describe(call: CallInfo, createdAt: string): { label: string; missed: boolean } {
  const stale = Date.now() - new Date(createdAt).getTime() > STALE_AFTER_MS
  const person = call.answered_by ? tr(` por ${call.answered_by}`, ` by ${call.answered_by}`) : ''
  switch (call.status) {
    case 'ringing':
    case 'claimed':
      return stale
        ? { label: tr('Chamada perdida', 'Missed call'), missed: true }
        : { label: tr('Chamada recebida', 'Incoming call'), missed: false }
    case 'connected':
      return { label: tr(`Em chamada${person}`, `On a call${person}`), missed: false }
    case 'completed': {
      const duration = call.duration_seconds != null ? ` · ${formatDuration(call.duration_seconds)}` : ''
      return { label: tr(`Chamada atendida${person}${duration}`, `Call answered${person}${duration}`), missed: false }
    }
    case 'rejected': {
      const by = call.rejected_by ? tr(` por ${call.rejected_by}`, ` by ${call.rejected_by}`) : ''
      return { label: tr(`Chamada recusada${by}`, `Call declined${by}`), missed: true }
    }
    case 'failed':
      return { label: tr('Chamada com falha', 'Call failed'), missed: true }
    default:
      return { label: tr('Chamada perdida', 'Missed call'), missed: true }
  }
}

/** Linha da chamada no histórico da conversa. */
export function CallLogLine({ call, createdAt }: { call: CallInfo | undefined; createdAt: string }) {
  if (!call) return null
  const { label, missed } = describe(call, createdAt)
  const Icon = missed ? PhoneMissed : PhoneIncoming
  return (
    <p className={`flex items-center gap-1.5 text-[13px] ${missed ? 'text-red-300' : 'text-emerald-300'}`}>
      <Icon size={14} className="shrink-0" />
      {label}
    </p>
  )
}

interface LeadCall extends CallInfo {
  id: string
  created_at: string
}

/** Histórico de chamadas de um lead. */
export function LeadCallsModal({ leadId, leadName, onClose }: { leadId: string; leadName: string; onClose: () => void }) {
  const { t, locale } = useI18n()
  const [calls, setCalls] = useState<LeadCall[] | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api.get<LeadCall[]>(`/whatsapp/leads/${leadId}/calls`)
      .then(({ data }) => setCalls(data))
      .catch((err) => setError(apiError(err, t('Não foi possível carregar as chamadas.', 'Could not load the calls.'))))
  }, [leadId, t])

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center max-lg:[align-items:safe_center] max-lg:overflow-y-auto max-lg:py-4 bg-black/70 backdrop-blur-sm px-4">
      <div className="bg-[#170e2c] border border-white/[0.08] rounded-2xl p-6 w-full max-w-md max-h-[80vh] flex flex-col">
        <div className="flex items-center justify-between mb-4 gap-3">
          <h3 className="text-base font-semibold text-white flex items-center gap-2 min-w-0">
            <Phone size={16} className="text-indigo-400 shrink-0" />
            <span className="truncate">{t('Chamadas', 'Calls')} · {leadName}</span>
          </h3>
          <button onClick={onClose} className="text-[#444] hover:text-[#888] transition-colors"><X size={18} /></button>
        </div>
        <div className="overflow-y-auto space-y-2">
          {error && <p className="text-xs text-red-400">{error}</p>}
          {!error && calls === null && <p className="text-xs text-[#666]">{t('Carregando…', 'Loading…')}</p>}
          {calls?.length === 0 && <p className="text-xs text-[#666]">{t('Nenhuma chamada registrada.', 'No calls recorded.')}</p>}
          {calls?.map((call) => (
            <div key={call.id} className="flex items-center justify-between gap-3 bg-white/[0.03] rounded-lg px-3 py-2">
              <CallLogLine call={call} createdAt={call.created_at} />
              <span className="text-[11px] text-[#666] shrink-0">{new Date(call.created_at).toLocaleString(locale)}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
