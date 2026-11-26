import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Flame, X } from 'lucide-react'
import { WS_BASE } from '../services/api'
import { useI18n } from '../i18n'
import {
  getPrefs, isConversationMuted, playInterestSound, playMessageSound, syncPush, unlockAudio,
} from '../services/notifications'

interface InterestAlert {
  conversation_id: string
  name: string
  text: string
  url: string
}

/** Com o painel aberto: som de mensagem nova e alerta de lead interessado (o celular recebe pelo push). */
export default function NotificationCenter() {
  const { t } = useI18n()
  const navigate = useNavigate()
  const [alerts, setAlerts] = useState<InterestAlert[]>([])

  useEffect(() => {
    syncPush()
    // O navegador só libera som depois de um toque/clique na página.
    const unlock = () => unlockAudio()
    window.addEventListener('pointerdown', unlock, { once: true })
    return () => window.removeEventListener('pointerdown', unlock)
  }, [])

  useEffect(() => {
    let closed = false
    let ws: WebSocket | null = null
    let ping: ReturnType<typeof setInterval> | undefined
    let retry: ReturnType<typeof setTimeout> | undefined

    const connect = () => {
      const token = localStorage.getItem('access_token')
      if (closed || !token) return
      ws = new WebSocket(`${WS_BASE}/ws?token=${token}`)
      ws.onmessage = (ev) => {
        try {
          const { event, data } = JSON.parse(ev.data)
          const prefs = getPrefs()
          if (event === 'new_message' && data?.direction === 'inbound') {
            if (prefs?.messages_enabled !== false && !isConversationMuted(data.conversation_id)) playMessageSound()
          } else if (event === 'lead_interested') {
            if (prefs?.interest_enabled === false) return
            playInterestSound()
            setAlerts((prev) => [data, ...prev.filter((a) => a.conversation_id !== data.conversation_id)].slice(0, 3))
          }
        } catch { /* pong */ }
      }
      ws.onclose = () => {
        clearInterval(ping)
        if (!closed) retry = setTimeout(connect, 3000)
      }
      ping = setInterval(() => { if (ws?.readyState === WebSocket.OPEN) ws.send('ping') }, 25000)
    }
    connect()
    return () => {
      closed = true
      clearInterval(ping)
      clearTimeout(retry)
      ws?.close()
    }
  }, [])

  const dismiss = (id: string) => setAlerts((prev) => prev.filter((a) => a.conversation_id !== id))

  if (!alerts.length) return null
  return (
    <div className="fixed z-[55] right-3 left-3 top-16 sm:left-auto sm:top-auto sm:bottom-6 sm:right-6 sm:w-[360px] space-y-2">
      {alerts.map((a) => (
        <div key={a.conversation_id} className="bg-card border border-orange-400/30 shadow-2xl shadow-orange-500/10 rounded-2xl p-4 flex gap-3">
          <span className="w-9 h-9 shrink-0 rounded-xl bg-gradient-to-br from-orange-500 to-fuchsia-600 flex items-center justify-center">
            <Flame size={18} className="text-white" />
          </span>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold text-white">{t(`Lead interessado: ${a.name}`, `Interested lead: ${a.name}`)}</p>
            {a.text && <p className="text-xs text-ink-3 mt-0.5 line-clamp-2">“{a.text}”</p>}
            <button
              onClick={() => { dismiss(a.conversation_id); navigate(a.url) }}
              className="mt-2 px-3 py-1.5 rounded-lg bg-gradient-to-r from-violet-600 via-fuchsia-500 to-orange-400 text-white text-xs font-semibold"
            >
              {t('Assumir conversa', 'Take over conversation')}
            </button>
          </div>
          <button onClick={() => dismiss(a.conversation_id)} className="text-ink-5 hover:text-ink-3 self-start"><X size={16} /></button>
        </div>
      ))}
    </div>
  )
}
