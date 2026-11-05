import { useEffect, useState } from 'react'
import api, { apiError } from '../services/api'
import { useI18n } from '../i18n'
import { useCalls } from './CallProvider'

interface WeeklyHours {
  day_of_week: string
  open_time: string
  close_time: string
}

interface CallHours {
  status: string
  timezone_id?: string
  weekly_operating_hours?: WeeklyHours[]
}

interface CallingSettings {
  connected: boolean
  enabled: boolean
  messaging_limit: string | null
  meets_messaging_limit: boolean | null
  call_hours: CallHours | null
  restrictions: { type: string; expiration?: number }[]
}

const DEFAULT_TIMEZONE = 'America/Sao_Paulo'

const toInput = (time: string) => `${time.slice(0, 2)}:${time.slice(2)}`
const fromInput = (time: string) => time.replace(':', '')

/** Toggle "Receber ligações" e horário de atendimento do número (Conexões Meta → WhatsApp). */
export default function CallingSettingsPanel() {
  const { t, locale } = useI18n()
  const { enabled: callingOn, isAdmin } = useCalls()

  const days = [
    { id: 'MONDAY', label: t('Seg', 'Mon') },
    { id: 'TUESDAY', label: t('Ter', 'Tue') },
    { id: 'WEDNESDAY', label: t('Qua', 'Wed') },
    { id: 'THURSDAY', label: t('Qui', 'Thu') },
    { id: 'FRIDAY', label: t('Sex', 'Fri') },
    { id: 'SATURDAY', label: t('Sáb', 'Sat') },
    { id: 'SUNDAY', label: t('Dom', 'Sun') },
  ]

  const [settings, setSettings] = useState<CallingSettings | null>(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const [hoursOn, setHoursOn] = useState(false)
  const [timezone, setTimezone] = useState(DEFAULT_TIMEZONE)
  const [selectedDays, setSelectedDays] = useState<string[]>(['MONDAY', 'TUESDAY', 'WEDNESDAY', 'THURSDAY', 'FRIDAY'])
  const [openTime, setOpenTime] = useState('09:00')
  const [closeTime, setCloseTime] = useState('18:00')

  function apply(data: CallingSettings) {
    setSettings(data)
    const hours = data.call_hours
    if (!hours) return
    setHoursOn(hours.status === 'ENABLED')
    if (hours.timezone_id) setTimezone(hours.timezone_id)
    const weekly = hours.weekly_operating_hours ?? []
    if (weekly.length) {
      setSelectedDays([...new Set(weekly.map((w) => w.day_of_week))])
      setOpenTime(toInput(weekly[0].open_time))
      setCloseTime(toInput(weekly[0].close_time))
    }
  }

  useEffect(() => {
    if (!callingOn) return
    api.get<CallingSettings>('/whatsapp/calling/settings')
      .then(({ data }) => apply(data))
      .catch((err) => setError(apiError(err, t('Não foi possível ler as configurações de ligação.', 'Could not read the calling settings.'))))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [callingOn])

  async function save(body: { enabled: boolean; call_hours?: object }) {
    setSaving(true)
    setError('')
    try {
      const { data } = await api.put<CallingSettings>('/whatsapp/calling/settings', body)
      apply(data)
    } catch (err) {
      setError(apiError(err, t('Não foi possível salvar.', 'Could not save.')))
    } finally {
      setSaving(false)
    }
  }

  function saveHours(e: React.FormEvent) {
    e.preventDefault()
    if (!settings) return
    save({
      enabled: settings.enabled,
      call_hours: {
        status: hoursOn ? 'ENABLED' : 'DISABLED',
        timezone_id: timezone,
        weekly_operating_hours: selectedDays.map((day) => ({
          day_of_week: day, open_time: fromInput(openTime), close_time: fromInput(closeTime),
        })),
      },
    })
  }

  function restrictionText(type: string): string {
    if (type === 'RESTRICTED_BUSINESS_INITIATED_CALLING') {
      return t('A Meta pausou as ligações feitas pela empresa.', 'Meta paused calls made by the business.')
    }
    if (type === 'RESTRICTED_USER_INITIATED_CALLING_CALL_BUTTON_HIDDEN') {
      return t('A Meta escondeu o botão de ligar por muitas chamadas não atendidas.', 'Meta hid the call button because of too many unanswered calls.')
    }
    if (type === 'RESTRICTED_USER_INITIATED_CALLING') {
      return t('A Meta pausou o recebimento de ligações.', 'Meta paused incoming calls.')
    }
    return type
  }

  if (!callingOn) return null

  const readOnly = !isAdmin || saving || !settings?.connected

  return (
    <div className="mt-4 pt-4 border-t border-white/[0.06] space-y-3">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-sm font-medium text-[#e2e2e8]">{t('Receber ligações', 'Receive calls')}</p>
          <p className="text-[11px] text-[#64748b] mt-0.5">
            {t(
              'Mostra o botão de ligar no WhatsApp da empresa. As chamadas tocam no painel de quem tem acesso ao WhatsApp, e o áudio não é gravado.',
              'Shows the call button on the business WhatsApp. Calls ring in the panel of everyone with WhatsApp access, and the audio is not recorded.',
            )}
          </p>
        </div>
        <button
          type="button"
          role="switch"
          aria-checked={!!settings?.enabled}
          aria-label={t('Receber ligações', 'Receive calls')}
          disabled={readOnly}
          onClick={() => settings && save({ enabled: !settings.enabled })}
          className={`relative shrink-0 w-10 h-5 rounded-full transition-colors disabled:opacity-50 ${settings?.enabled ? 'bg-emerald-500' : 'bg-white/[0.12]'}`}
        >
          <span className={`absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white transition-transform ${settings?.enabled ? 'translate-x-5' : ''}`} />
        </button>
      </div>

      {!isAdmin && (
        <p className="text-[11px] text-[#64748b]">{t('Só um admin da conta pode alterar.', 'Only an account admin can change this.')}</p>
      )}

      {settings?.meets_messaging_limit === false && (
        <p className="text-[11px] text-amber-400/90 bg-amber-900/15 border border-amber-500/20 rounded-lg px-3 py-2">
          {t(
            `A Meta só ativa ligações com limite de 2.000 destinatários por dia ou mais. O limite atual é ${settings.messaging_limit}.`,
            `Meta only enables calling with a limit of 2,000 recipients per day or more. The current limit is ${settings.messaging_limit}.`,
          )}
        </p>
      )}

      {settings?.restrictions.map((r) => (
        <p key={r.type} className="text-[11px] text-red-300 bg-red-900/15 border border-red-500/20 rounded-lg px-3 py-2">
          {restrictionText(r.type)}
          {r.expiration ? ` ${t('Até', 'Until')} ${new Date(r.expiration * 1000).toLocaleString(locale)}.` : ''}
        </p>
      ))}

      {settings?.enabled && (
        <form onSubmit={saveHours} className="space-y-2.5">
          <label className="flex items-center gap-2 text-xs text-[#c0c0d0]">
            <input type="checkbox" checked={hoursOn} disabled={readOnly} onChange={(e) => setHoursOn(e.target.checked)} />
            {t('Atender só em horários definidos', 'Only take calls during set hours')}
          </label>
          {hoursOn && (
            <>
              <div className="flex flex-wrap gap-1.5">
                {days.map((day) => {
                  const on = selectedDays.includes(day.id)
                  return (
                    <button
                      key={day.id}
                      type="button"
                      aria-pressed={on}
                      disabled={readOnly}
                      onClick={() => setSelectedDays(on ? selectedDays.filter((d) => d !== day.id) : [...selectedDays, day.id])}
                      className={`px-2 py-1 rounded-md text-[11px] border transition-colors ${
                        on ? 'bg-indigo-600/30 border-indigo-500/40 text-indigo-200' : 'bg-white/[0.03] border-white/[0.08] text-[#666]'
                      }`}
                    >
                      {day.label}
                    </button>
                  )
                })}
              </div>
              <div className="flex flex-wrap items-center gap-2 text-xs text-[#8a8a9e]">
                <input type="time" required value={openTime} disabled={readOnly} onChange={(e) => setOpenTime(e.target.value)}
                  className="px-2 py-1 bg-[#0f0820] border border-white/[0.08] text-[#e2e2e8] rounded-md" />
                {t('até', 'to')}
                <input type="time" required value={closeTime} disabled={readOnly} onChange={(e) => setCloseTime(e.target.value)}
                  className="px-2 py-1 bg-[#0f0820] border border-white/[0.08] text-[#e2e2e8] rounded-md" />
                <input type="text" required value={timezone} disabled={readOnly} onChange={(e) => setTimezone(e.target.value)}
                  aria-label={t('Fuso horário', 'Time zone')}
                  className="px-2 py-1 bg-[#0f0820] border border-white/[0.08] text-[#e2e2e8] rounded-md w-44" />
              </div>
            </>
          )}
          {(hoursOn || settings.call_hours?.status === 'ENABLED') && (
            <button
              type="submit"
              disabled={readOnly || selectedDays.length === 0}
              className="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-lg text-xs font-semibold transition-colors"
            >
              {saving ? t('Salvando…', 'Saving…') : t('Salvar horário', 'Save hours')}
            </button>
          )}
        </form>
      )}

      {error && <p className="text-[11px] text-red-400">{error}</p>}
    </div>
  )
}
