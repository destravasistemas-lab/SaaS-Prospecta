import {
  createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode,
} from 'react'
import { Link } from 'react-router-dom'
import { Mic, MicOff, Phone, PhoneOff, X } from 'lucide-react'
import api, { API_BASE, WS_BASE, apiError } from '../services/api'
import { useI18n } from '../i18n'

export interface IncomingCall {
  id: string
  conversation_id: string
  contact_name: string | null
  contact_wa_id: string | null
  ring_after_ms: number
  expires_at: string
}

interface ActiveCall {
  id: string
  conversation_id: string
  contact_name: string | null
  phase: 'connecting' | 'in_call'
  muted: boolean
  startedAt: number | null
}

interface CallsValue {
  enabled: boolean
  isAdmin: boolean
  incoming: IncomingCall[]
  active: ActiveCall | null
  error: string | null
  answer: (call: IncomingCall) => void
  reject: (call: IncomingCall) => void
  hangUp: () => void
  toggleMute: () => void
  dismissError: () => void
  setFocusedConversation: (id: string | null) => void
}

const noop = () => {}
const CallsContext = createContext<CallsValue>({
  enabled: false, isAdmin: false, incoming: [], active: null, error: null,
  answer: noop, reject: noop, hangUp: noop, toggleMute: noop, dismissError: noop, setFocusedConversation: noop,
})

export const useCalls = () => useContext(CallsContext)

const ENDED = ['completed', 'missed', 'rejected', 'failed']
const ICE_GATHERING_TIMEOUT = 2000
const CONNECT_BEFORE_ACCEPT_TIMEOUT = 6000
const CONNECT_AFTER_ACCEPT_TIMEOUT = 10000

function startRingtone(): () => void {
  let ctx: AudioContext
  try {
    ctx = new AudioContext()
  } catch {
    return noop
  }
  const beep = () => {
    if (ctx.state === 'suspended') ctx.resume().catch(noop)
    const osc = ctx.createOscillator()
    const gain = ctx.createGain()
    osc.frequency.value = 480
    gain.gain.value = 0.06
    osc.connect(gain).connect(ctx.destination)
    osc.start()
    osc.stop(ctx.currentTime + 0.8)
  }
  beep()
  const timer = setInterval(beep, 3000)
  return () => {
    clearInterval(timer)
    ctx.close().catch(noop)
  }
}

/** O SDP vai completo: a Meta não recebe candidatos ICE depois da resposta. */
function waitIceGathering(pc: RTCPeerConnection): Promise<void> {
  if (pc.iceGatheringState === 'complete') return Promise.resolve()
  return new Promise((resolve) => {
    const done = () => {
      clearTimeout(timer)
      pc.removeEventListener('icegatheringstatechange', onChange)
      resolve()
    }
    const onChange = () => { if (pc.iceGatheringState === 'complete') done() }
    const timer = setTimeout(done, ICE_GATHERING_TIMEOUT)
    pc.addEventListener('icegatheringstatechange', onChange)
  })
}

function waitConnected(pc: RTCPeerConnection, timeoutMs: number): Promise<boolean> {
  if (pc.connectionState === 'connected') return Promise.resolve(true)
  return new Promise((resolve) => {
    const done = (connected: boolean) => {
      clearTimeout(timer)
      pc.removeEventListener('connectionstatechange', onChange)
      resolve(connected)
    }
    const onChange = () => {
      if (pc.connectionState === 'connected') done(true)
      else if (pc.connectionState === 'failed' || pc.connectionState === 'closed') done(false)
    }
    const timer = setTimeout(() => done(false), timeoutMs)
    pc.addEventListener('connectionstatechange', onChange)
  })
}

export function CallProvider({ children }: { children: ReactNode }) {
  const { t } = useI18n()
  const [enabled, setEnabled] = useState(false)
  const [isAdmin, setIsAdmin] = useState(false)
  const [incoming, setIncoming] = useState<IncomingCall[]>([])
  const [active, setActiveState] = useState<ActiveCall | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [focusedConversation, setFocusedConversation] = useState<string | null>(null)

  const activeRef = useRef<ActiveCall | null>(null)
  const pcRef = useRef<RTCPeerConnection | null>(null)
  const micRef = useRef<MediaStream | null>(null)
  const audioRef = useRef<HTMLAudioElement>(null)
  const timersRef = useRef(new Map<string, ReturnType<typeof setTimeout>[]>())

  const setActive = useCallback((next: ActiveCall | null) => {
    activeRef.current = next
    setActiveState(next)
  }, [])

  const forgetIncoming = useCallback((id: string) => {
    timersRef.current.get(id)?.forEach(clearTimeout)
    timersRef.current.delete(id)
    setIncoming((prev) => prev.filter((c) => c.id !== id))
  }, [])

  const scheduleIncoming = useCallback((call: IncomingCall) => {
    if (timersRef.current.has(call.id) || activeRef.current?.id === call.id) return
    const show = () => setIncoming((prev) => (prev.some((c) => c.id === call.id) ? prev : [...prev, call]))
    const timers: ReturnType<typeof setTimeout>[] = [
      setTimeout(() => forgetIncoming(call.id), Math.max(0, new Date(call.expires_at).getTime() - Date.now())),
    ]
    if (call.ring_after_ms > 0) timers.push(setTimeout(show, call.ring_after_ms))
    else show()
    timersRef.current.set(call.id, timers)
  }, [forgetIncoming])

  const releaseMedia = useCallback(() => {
    pcRef.current?.close()
    pcRef.current = null
    micRef.current?.getTracks().forEach((track) => track.stop())
    micRef.current = null
    if (audioRef.current) audioRef.current.srcObject = null
    setActive(null)
  }, [setActive])

  useEffect(() => {
    api.get('/auth/me').then(({ data }) => {
      setIsAdmin(data?.role === 'admin')
      setEnabled(!!data?.calling_enabled && (data?.modules ?? []).includes('whatsapp'))
    }).catch(noop)
  }, [])

  // Socket próprio: o alerta precisa chegar em qualquer tela do painel.
  useEffect(() => {
    if (!enabled) return
    let closed = false
    let ws: WebSocket | null = null
    let ping: ReturnType<typeof setInterval> | undefined
    let retry: ReturnType<typeof setTimeout> | undefined

    const connect = async () => {
      // Antes do socket: a chamada à API renova o token, e o que tocou durante a queda volta.
      try {
        const { data } = await api.get<IncomingCall[]>('/whatsapp/calls/active')
        data.forEach(scheduleIncoming)
      } catch { /* o socket ainda pode conectar */ }
      const token = localStorage.getItem('access_token')
      if (closed || !token) return

      ws = new WebSocket(`${WS_BASE}/ws?token=${token}`)
      ws.onmessage = (ev) => {
        try {
          const { event, data } = JSON.parse(ev.data)
          if (event === 'call_incoming') {
            scheduleIncoming(data)
          } else if (event === 'call_updated') {
            if (data.call.status !== 'ringing') forgetIncoming(data.id)
            if (activeRef.current?.id === data.id && ENDED.includes(data.call.status)) releaseMedia()
          }
        } catch { /* mensagem que não é JSON (pong) */ }
      }
      ws.onclose = () => {
        clearInterval(ping)
        if (!closed) retry = setTimeout(connect, 3000)
      }
      ping = setInterval(() => { if (ws?.readyState === WebSocket.OPEN) ws.send('ping') }, 25000)
    }
    connect()

    const timers = timersRef.current
    return () => {
      closed = true
      clearInterval(ping)
      clearTimeout(retry)
      ws?.close()
      timers.forEach((list) => list.forEach(clearTimeout))
      timers.clear()
      releaseMedia()
    }
  }, [enabled, scheduleIncoming, forgetIncoming, releaseMedia])

  const ringing = incoming.length > 0 && !active
  useEffect(() => (ringing ? startRingtone() : undefined), [ringing])

  // Fechar a aba em chamada: encerra na Meta em vez de deixar o cliente em silêncio.
  useEffect(() => {
    const onBeforeUnload = (e: BeforeUnloadEvent) => { if (activeRef.current) e.preventDefault() }
    const onPageHide = () => {
      const call = activeRef.current
      if (!call) return
      fetch(`${API_BASE}/api/v1/whatsapp/calls/${call.id}/terminate`, {
        method: 'POST',
        keepalive: true,
        headers: { Authorization: `Bearer ${localStorage.getItem('access_token')}` },
      }).catch(noop)
    }
    window.addEventListener('beforeunload', onBeforeUnload)
    window.addEventListener('pagehide', onPageHide)
    return () => {
      window.removeEventListener('beforeunload', onBeforeUnload)
      window.removeEventListener('pagehide', onPageHide)
    }
  }, [])

  const hangUpWithError = useCallback(async (callId: string, message: string | null) => {
    try {
      await api.post(`/whatsapp/calls/${callId}/terminate`)
    } catch { /* a chamada já pode ter terminado na Meta */ }
    releaseMedia()
    if (message) setError(message)
  }, [releaseMedia])

  const answer = useCallback(async (call: IncomingCall) => {
    if (activeRef.current) return
    setError(null)

    // Primeiro o microfone: se estiver bloqueado, a chamada continua tocando para os outros.
    let mic: MediaStream
    try {
      if (!navigator.mediaDevices?.getUserMedia) throw new DOMException('', 'NotSupportedError')
      mic = await navigator.mediaDevices.getUserMedia({ audio: true })
    } catch (err: any) {
      setError(
        err?.name === 'NotAllowedError'
          ? t('O microfone está bloqueado. Libere o acesso nas permissões do navegador e clique em Atender de novo.', 'The microphone is blocked. Allow access in your browser permissions and click Answer again.')
          : err?.name === 'NotFoundError'
            ? t('Nenhum microfone encontrado neste computador.', 'No microphone found on this computer.')
            : t('Este navegador não permite usar o microfone aqui.', "This browser can't use the microphone here."),
      )
      return
    }

    let sdpOffer: string
    let iceServers: RTCIceServer[]
    try {
      const { data } = await api.post(`/whatsapp/calls/${call.id}/claim`)
      sdpOffer = data.sdp_offer
      iceServers = data.ice_servers
    } catch (err) {
      mic.getTracks().forEach((track) => track.stop())
      forgetIncoming(call.id)
      setError(apiError(err, t('Não foi possível atender a chamada.', 'Could not answer the call.')))
      return
    }

    forgetIncoming(call.id)
    micRef.current = mic
    setActive({
      id: call.id, conversation_id: call.conversation_id, contact_name: call.contact_name || call.contact_wa_id,
      phase: 'connecting', muted: false, startedAt: null,
    })

    try {
      const pc = new RTCPeerConnection({ iceServers })
      pcRef.current = pc
      const track = mic.getAudioTracks()[0]
      // A Meta pede áudio só depois do 200 OK do accept: antes disso o microfone fica mudo.
      track.enabled = false
      pc.addTrack(track, mic)
      pc.ontrack = (ev) => {
        if (audioRef.current) {
          audioRef.current.srcObject = ev.streams[0] ?? new MediaStream([ev.track])
          audioRef.current.play().catch(noop)
        }
      }

      await pc.setRemoteDescription({ type: 'offer', sdp: sdpOffer })
      await pc.setLocalDescription(await pc.createAnswer())
      await waitIceGathering(pc)
      const sdp = pc.localDescription!.sdp

      await api.post(`/whatsapp/calls/${call.id}/pre-accept`, { sdp })
      const connected = await waitConnected(pc, CONNECT_BEFORE_ACCEPT_TIMEOUT)
      await api.post(`/whatsapp/calls/${call.id}/accept`, { sdp })
      // O cliente pode ter desligado durante o accept.
      const current = activeRef.current as ActiveCall | null
      if (current?.id !== call.id) return

      track.enabled = true
      setActive({ ...current, phase: 'in_call', startedAt: Date.now() })

      const noAudio = t(
        'O áudio não conectou. Sua rede pode estar bloqueando a chamada: tente outra rede ou fale com o administrador.',
        'The audio did not connect. Your network may be blocking the call: try another network or talk to your administrator.',
      )
      if (!connected && !(await waitConnected(pc, CONNECT_AFTER_ACCEPT_TIMEOUT))) {
        await hangUpWithError(call.id, noAudio)
        return
      }
      pc.addEventListener('connectionstatechange', () => {
        if (pc.connectionState === 'failed' && activeRef.current?.id === call.id) hangUpWithError(call.id, noAudio)
      })
    } catch (err) {
      await hangUpWithError(call.id, apiError(err, t('Não foi possível conectar o áudio.', 'Could not connect the audio.')))
    }
  }, [t, forgetIncoming, setActive, hangUpWithError])

  const reject = useCallback(async (call: IncomingCall) => {
    setError(null)
    try {
      await api.post(`/whatsapp/calls/${call.id}/reject`)
      forgetIncoming(call.id)
    } catch (err: any) {
      if (err?.response?.status === 409) forgetIncoming(call.id)
      setError(apiError(err, t('Não foi possível recusar a chamada.', 'Could not decline the call.')))
    }
  }, [t, forgetIncoming])

  const hangUp = useCallback(() => {
    if (activeRef.current) hangUpWithError(activeRef.current.id, null)
  }, [hangUpWithError])

  const toggleMute = useCallback(() => {
    const call = activeRef.current
    const track = micRef.current?.getAudioTracks()[0]
    if (!call || !track || call.phase !== 'in_call') return
    track.enabled = call.muted
    setActive({ ...call, muted: !call.muted })
  }, [setActive])

  const dismissError = useCallback(() => setError(null), [])

  const value = useMemo<CallsValue>(() => ({
    enabled, isAdmin, incoming, active, error, answer, reject, hangUp, toggleMute, dismissError, setFocusedConversation,
  }), [enabled, isAdmin, incoming, active, error, answer, reject, hangUp, toggleMute, dismissError])

  const floating = incoming.filter((c) => c.conversation_id !== focusedConversation)

  return (
    <CallsContext.Provider value={value}>
      {children}
      {enabled && (
        <>
          <audio ref={audioRef} autoPlay playsInline className="hidden" />
          <div className="fixed bottom-6 right-6 z-[60] flex flex-col gap-3 w-80 max-w-[calc(100vw-2rem)]">
            {error && (
              <div role="alert" className="flex items-start gap-2 bg-[#20153a] border border-red-500/30 rounded-xl p-3 shadow-xl">
                <p className="flex-1 text-xs text-red-300 leading-relaxed">{error}</p>
                <button onClick={dismissError} title={t('Fechar', 'Close')} className="text-[#666] hover:text-white">
                  <X size={14} />
                </button>
              </div>
            )}
            {active && <ActiveCallCard call={active} onHangUp={hangUp} onToggleMute={toggleMute} />}
            {floating.map((call) => (
              <div key={call.id} className="bg-[#20153a] border border-emerald-500/30 rounded-xl p-3 shadow-xl">
                <div className="flex items-center gap-2 mb-2.5">
                  <Phone size={15} className="text-emerald-400 animate-pulse shrink-0" />
                  <div className="min-w-0 flex-1">
                    <p className="text-[13px] font-medium text-white truncate">{call.contact_name || call.contact_wa_id}</p>
                    <p className="text-[11px] text-[#8a8a9e]">{t('Chamada recebida no WhatsApp', 'Incoming WhatsApp call')}</p>
                  </div>
                  <Link to={`/app/whatsapp?conv=${call.conversation_id}`} className="text-[11px] text-violet-400 hover:text-violet-300 shrink-0">
                    {t('Abrir conversa', 'Open chat')}
                  </Link>
                </div>
                <CallButtons call={call} />
              </div>
            ))}
          </div>
        </>
      )}
    </CallsContext.Provider>
  )
}

function ActiveCallCard({ call, onHangUp, onToggleMute }: { call: ActiveCall; onHangUp: () => void; onToggleMute: () => void }) {
  const { t } = useI18n()
  const [now, setNow] = useState(Date.now())
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(timer)
  }, [])

  const elapsed = call.startedAt ? Math.max(0, Math.floor((now - call.startedAt) / 1000)) : 0
  const clock = `${String(Math.floor(elapsed / 60)).padStart(2, '0')}:${String(elapsed % 60).padStart(2, '0')}`

  return (
    <div className="bg-[#20153a] border border-indigo-500/30 rounded-xl p-3 shadow-xl">
      <div className="flex items-center gap-2 mb-2.5">
        <Phone size={15} className="text-indigo-400 shrink-0" />
        <div className="min-w-0 flex-1">
          <p className="text-[13px] font-medium text-white truncate">{call.contact_name}</p>
          <p className="text-[11px] text-[#8a8a9e]">
            {call.phase === 'connecting' ? t('Conectando o áudio…', 'Connecting audio…') : clock}
          </p>
        </div>
        <Link to={`/app/whatsapp?conv=${call.conversation_id}`} className="text-[11px] text-violet-400 hover:text-violet-300 shrink-0">
          {t('Abrir conversa', 'Open chat')}
        </Link>
      </div>
      <div className="flex gap-2">
        <button
          onClick={onToggleMute}
          disabled={call.phase !== 'in_call'}
          className="flex-1 flex items-center justify-center gap-1.5 py-1.5 rounded-lg bg-white/[0.06] hover:bg-white/[0.1] disabled:opacity-40 text-[#e2e2e8] text-xs font-medium transition-colors"
        >
          {call.muted ? <MicOff size={13} /> : <Mic size={13} />}
          {call.muted ? t('Ativar microfone', 'Unmute') : t('Mudo', 'Mute')}
        </button>
        <button
          onClick={onHangUp}
          className="flex-1 flex items-center justify-center gap-1.5 py-1.5 rounded-lg bg-red-600 hover:bg-red-500 text-white text-xs font-semibold transition-colors"
        >
          <PhoneOff size={13} />
          {t('Encerrar', 'Hang up')}
        </button>
      </div>
    </div>
  )
}

function CallButtons({ call }: { call: IncomingCall }) {
  const { t } = useI18n()
  const { answer, reject, active } = useCalls()
  return (
    <div className="flex gap-2">
      <button
        onClick={() => answer(call)}
        disabled={!!active}
        title={active ? t('Encerre a chamada atual para atender', 'End the current call to answer') : undefined}
        className="flex-1 flex items-center justify-center gap-1.5 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:opacity-40 text-white text-xs font-semibold transition-colors"
      >
        <Phone size={13} />
        {t('Atender', 'Answer')}
      </button>
      <button
        onClick={() => reject(call)}
        className="flex-1 flex items-center justify-center gap-1.5 py-1.5 rounded-lg bg-red-600/80 hover:bg-red-500 text-white text-xs font-semibold transition-colors"
      >
        <PhoneOff size={13} />
        {t('Recusar', 'Decline')}
      </button>
    </div>
  )
}

/** Alerta dentro da conversa do contato; enquanto aparece aqui, o cartão flutuante some. */
export function CallBanner({ conversationId }: { conversationId: string }) {
  const { t } = useI18n()
  const { incoming, setFocusedConversation } = useCalls()

  useEffect(() => {
    setFocusedConversation(conversationId)
    return () => setFocusedConversation(null)
  }, [conversationId, setFocusedConversation])

  const call = incoming.find((c) => c.conversation_id === conversationId)
  if (!call) return null

  return (
    <div className="mx-3 mt-3 flex flex-wrap items-center justify-between gap-3 bg-emerald-900/15 border border-emerald-500/30 rounded-xl px-4 py-2.5">
      <p className="flex items-center gap-2 text-emerald-300 text-[13px] font-medium">
        <Phone size={15} className="animate-pulse" />
        {t('Chamada recebida', 'Incoming call')}
      </p>
      <div className="w-56 max-w-full">
        <CallButtons call={call} />
      </div>
    </div>
  )
}
