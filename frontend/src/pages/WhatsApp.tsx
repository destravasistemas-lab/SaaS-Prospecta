import { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import {
  Bot, Clock, UserCheck, Send, Power, MessageSquare, Check, CheckCheck,
  FileText, X, Paperclip, Reply, SmilePlus, LayoutList, Download, Plus, Trash2,
} from 'lucide-react'
import api, { WS_BASE } from '../services/api'
import { useI18n, tr } from '../i18n'

interface Conversation {
  id: string
  customer_id: string | null
  atendente_id: string | null
  atendimento_status: string
  status: string
  unread_count: number
  bot_active: boolean
  customer_name: string | null
  last_updated: string
}

interface MsgPayload {
  filename?: string
  customer_reaction?: string | null
  agent_reaction?: string | null
  error?: string
  [key: string]: any
}

interface Message {
  id: number
  conversation_id: string
  sender: string
  text: string | null
  direction: string
  status: string
  wa_id?: string | null
  message_id?: string | null
  media_type?: string | null
  media_url?: string | null
  context_text?: string | null
  payload?: MsgPayload | null
  created_at: string
}

interface Tpl {
  name: string
  language: string
  status?: string
  components?: any[]
}

type Queue = 'bot' | 'espera' | 'minhas'

const QUEUES: { id: Queue; pt: string; en: string; icon: typeof Bot; color: string }[] = [
  { id: 'bot', pt: 'Bot', en: 'Bot', icon: Bot, color: 'text-emerald-400' },
  { id: 'espera', pt: 'Espera', en: 'Waiting', icon: Clock, color: 'text-amber-400' },
  { id: 'minhas', pt: 'Minhas', en: 'Mine', icon: UserCheck, color: 'text-indigo-400' },
]

export function statusText(s: string): string {
  const map: Record<string, [string, string]> = {
    aberto: ['Aberto', 'Open'],
    em_atendimento: ['Em atendimento', 'In progress'],
    aguardando: ['Aguardando', 'Waiting'],
    resolvido: ['Resolvido', 'Resolved'],
  }
  const v = map[s]
  return v ? tr(v[0], v[1]) : s
}

const REACTION_EMOJIS = ['👍', '❤️', '😂', '😮', '😢', '🙏']

// Janela de atendimento do WhatsApp (24h após a última mensagem do cliente)
const WINDOW_MS = 24 * 60 * 60 * 1000

function fmtTime(iso: string): string {
  const d = new Date(iso)
  return d.toLocaleTimeString(tr('pt-BR', 'en-US'), { hour: '2-digit', minute: '2-digit' })
}

function MsgStatus({ status, error }: { status: string; error?: string }) {
  if (status === 'read') return <CheckCheck size={13} className="text-sky-400" />
  if (status === 'delivered') return <CheckCheck size={13} className="text-white/40" />
  if (status === 'failed')
    return (
      <span className="text-red-400 text-[10px]" title={error || tr('Falha no envio', 'Send failed')}>
        {tr('falhou', 'failed')}
      </span>
    )
  return <Check size={13} className="text-white/40" />
}

/** Mídia do chat: busca via proxy autenticado do backend e renderiza por tipo. */
function MediaContent({ m }: { m: Message }) {
  const [src, setSrc] = useState<string | null>(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    let objectUrl: string | null = null
    let cancelled = false

    async function load() {
      if (!m.media_url) return
      if (m.media_url.startsWith('/whatsapp/media/')) {
        try {
          const { data } = await api.get(m.media_url, { responseType: 'blob' })
          if (cancelled) return
          objectUrl = URL.createObjectURL(data)
          setSrc(objectUrl)
        } catch {
          if (!cancelled) setError(true)
        }
      } else {
        setSrc(m.media_url)
      }
    }
    load()
    return () => {
      cancelled = true
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [m.media_url])

  if (error)
    return <p className="text-[11px] italic opacity-60">{tr('Mídia indisponível', 'Media unavailable')}</p>
  if (!src)
    return <p className="text-[11px] italic opacity-60 animate-pulse">{tr('Carregando mídia…', 'Loading media…')}</p>

  switch (m.media_type) {
    case 'image':
      return <img src={src} className="rounded-lg max-w-full max-h-72 object-contain" alt="" />
    case 'sticker':
      return <img src={src} className="w-28 h-28 object-contain" alt="" />
    case 'video':
      return <video src={src} controls className="rounded-lg max-w-full max-h-72" />
    case 'audio':
      return <audio src={src} controls className="max-w-full h-10" />
    default:
      return (
        <a
          href={src}
          download={m.payload?.filename || tr('documento', 'document')}
          className="flex items-center gap-2 text-[12px] underline decoration-white/30 hover:decoration-white"
        >
          <Download size={14} />
          {m.payload?.filename || tr('Baixar documento', 'Download document')}
        </a>
      )
  }
}

interface IntButton { id: string; title: string }
interface IntRow { id: string; title: string; description: string }

export default function WhatsApp() {
  const { t } = useI18n()
  const myId = localStorage.getItem('user_id') || ''
  const [searchParams] = useSearchParams()

  const [convs, setConvs] = useState<Conversation[]>([])
  const [queue, setQueue] = useState<Queue>('espera')
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [text, setText] = useState('')
  const [sending, setSending] = useState(false)
  const [loadingMsgs, setLoadingMsgs] = useState(false)

  // Responder citando (quote)
  const [replyTo, setReplyTo] = useState<Message | null>(null)
  // Reações: id da mensagem com o picker aberto
  const [reactingId, setReactingId] = useState<number | null>(null)
  // Anexo pendente
  const [attaching, setAttaching] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // Envio de template
  const [showTpl, setShowTpl] = useState(false)
  const [tpls, setTpls] = useState<Tpl[]>([])
  const [pickedTpl, setPickedTpl] = useState<Tpl | null>(null)
  const [tplVars, setTplVars] = useState<string[]>([])
  const [sendingTpl, setSendingTpl] = useState(false)
  const [tplOptIn, setTplOptIn] = useState(false)

  // Mensagem interativa (botões / lista)
  const [showInt, setShowInt] = useState(false)
  const [intKind, setIntKind] = useState<'buttons' | 'list'>('buttons')
  const [intBody, setIntBody] = useState('')
  const [intButtons, setIntButtons] = useState<IntButton[]>([{ id: 'opt_1', title: '' }])
  const [intListButton, setIntListButton] = useState(tr('Ver opções', 'See options'))
  const [intRows, setIntRows] = useState<IntRow[]>([{ id: 'row_1', title: '', description: '' }])
  const [sendingInt, setSendingInt] = useState(false)

  // Relógio para recalcular a janela de 24h a cada minuto
  const [nowTick, setNowTick] = useState(Date.now())
  useEffect(() => {
    const timer = setInterval(() => setNowTick(Date.now()), 60_000)
    return () => clearInterval(timer)
  }, [])

  const threadRef = useRef<HTMLDivElement>(null)
  const selectedIdRef = useRef<string | null>(null)
  const lastTypingSent = useRef(0)
  useEffect(() => { selectedIdRef.current = selectedId }, [selectedId])

  const selected = convs.find((c) => c.id === selectedId) || null
  const recipientWaId = messages.find((m) => m.wa_id)?.wa_id || null

  // ---- Janela de 24h ----
  const windowInfo = useMemo(() => {
    const lastInbound = [...messages].reverse().find((m) => m.direction === 'inbound')
    if (!lastInbound) return { open: false, remainingMs: 0, neverOpened: true }
    const elapsed = nowTick - new Date(lastInbound.created_at).getTime()
    return { open: elapsed < WINDOW_MS, remainingMs: Math.max(0, WINDOW_MS - elapsed), neverOpened: false }
  }, [messages, nowTick])

  const windowLabel = useMemo(() => {
    if (!windowInfo.open) return null
    const h = Math.floor(windowInfo.remainingMs / 3_600_000)
    const min = Math.floor((windowInfo.remainingMs % 3_600_000) / 60_000)
    return h > 0 ? `${h}h ${min}min` : `${min}min`
  }, [windowInfo])

  function queueOf(c: Conversation): Queue {
    if (c.atendente_id && c.atendente_id === myId) return 'minhas'
    if (c.bot_active) return 'bot'
    return 'espera'
  }

  const counts: Record<Queue, number> = { bot: 0, espera: 0, minhas: 0 }
  convs.forEach((c) => { counts[queueOf(c)]++ })
  const visible = convs.filter((c) => queueOf(c) === queue)

  const loadConvs = useCallback(async () => {
    try {
      const { data } = await api.get('/conversations', {
        params: { status: 'active', channel: 'whatsapp', limit: 200 },
      })
      setConvs(data)
    } catch { /* ignore */ }
  }, [])

  const loadMessages = useCallback(async (id: string) => {
    setLoadingMsgs(true)
    try {
      const { data } = await api.get(`/conversations/${id}/messages`, { params: { limit: 200 } })
      setMessages(data)
    } catch {
      setMessages([])
    } finally {
      setLoadingMsgs(false)
    }
  }, [])

  useEffect(() => { loadConvs() }, [loadConvs])

  // Deep-link: /app/whatsapp?conv=<id> abre a conversa direto (ex: vindo do Follow-ups)
  const deepLinkApplied = useRef(false)
  useEffect(() => {
    if (deepLinkApplied.current) return
    const convParam = searchParams.get('conv')
    if (!convParam || convs.length === 0) return
    const target = convs.find((c) => c.id === convParam)
    if (target) {
      deepLinkApplied.current = true
      setQueue(queueOf(target))
      setSelectedId(target.id)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [convs, searchParams])

  useEffect(() => {
    setReplyTo(null)
    setReactingId(null)
    if (selectedId) {
      loadMessages(selectedId)
      // Abriu a conversa: zera não-lidas + envia confirmação de leitura (ticks azuis)
      api.post(`/conversations/${selectedId}/read`).then(() => loadConvs()).catch(() => {})
    } else {
      setMessages([])
    }
  }, [selectedId, loadMessages, loadConvs])

  useEffect(() => {
    threadRef.current?.scrollTo({ top: threadRef.current.scrollHeight })
  }, [messages])

  // Real-time updates via WebSocket
  useEffect(() => {
    const token = localStorage.getItem('access_token')
    if (!token) return
    const ws = new WebSocket(`${WS_BASE}/ws?token=${token}`)

    ws.onmessage = (ev) => {
      try {
        const { event, data } = JSON.parse(ev.data)
        if (event === 'new_message') {
          if (data.conversation_id === selectedIdRef.current) {
            setMessages((prev) => (prev.some((m) => m.id === data.id) ? prev : [...prev, data]))
          }
          loadConvs()
        } else if (event === 'message_status_updated') {
          setMessages((prev) => prev.map((m) =>
            m.message_id === data.message_id
              ? { ...m, status: data.status, payload: data.error ? { ...m.payload, error: data.error } : m.payload }
              : m,
          ))
        } else if (event === 'message_reaction') {
          if (data.conversation_id === selectedIdRef.current) {
            const key = data.from === 'agent' ? 'agent_reaction' : 'customer_reaction'
            setMessages((prev) => prev.map((m) =>
              m.id === data.message_db_id ? { ...m, payload: { ...m.payload, [key]: data.emoji } } : m,
            ))
          }
        } else if (event === 'conversation_updated' || event === 'conversation_created') {
          loadConvs()
        }
      } catch { /* ignore */ }
    }

    const ping = setInterval(() => { if (ws.readyState === WebSocket.OPEN) ws.send('ping') }, 25000)
    return () => { clearInterval(ping); ws.close() }
  }, [loadConvs])

  function handleSendError(err: any, fallback: string) {
    const detail = err?.response?.data?.detail
    if (detail?.code === 'outside_24h_window') {
      alert(detail.message)
      openTplPicker()
    } else {
      alert(typeof detail === 'string' ? detail : fallback)
    }
  }

  async function sendReply() {
    const body = text.trim()
    if (!body || !selected || sending) return
    setSending(true)
    setText('')
    try {
      const { data } = await api.post(`/conversations/${selected.id}/messages`, {
        text: body,
        direction: 'outbound',
        reply_to_message_id: replyTo?.id ?? null,
      })
      setReplyTo(null)
      setMessages((prev) => (prev.some((m) => m.id === data.id) ? prev : [...prev, data]))
      loadConvs()
    } catch (err) {
      setText(body)
      handleSendError(err, t('Erro ao enviar mensagem.', 'Failed to send message.'))
    } finally {
      setSending(false)
    }
  }

  // "Digitando..." para o cliente — no máximo 1 chamada a cada 20s
  function notifyTyping() {
    if (!selectedIdRef.current || !windowInfo.open) return
    const now = Date.now()
    if (now - lastTypingSent.current < 20_000) return
    lastTypingSent.current = now
    api.post(`/conversations/${selectedIdRef.current}/typing`).catch(() => {})
  }

  async function handlePickFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file || !selected || attaching) return
    setAttaching(true)
    try {
      const form = new FormData()
      form.append('file', file)
      const { data: up } = await api.post('/whatsapp/media/upload', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      const caption = ['image', 'video', 'document'].includes(up.media_type) ? text.trim() || null : null
      const { data: msg } = await api.post(`/conversations/${selected.id}/messages`, {
        text: caption,
        direction: 'outbound',
        media_id: up.media_id,
        media_type: up.media_type,
        media_filename: up.filename,
        reply_to_message_id: replyTo?.id ?? null,
      })
      if (caption) setText('')
      setReplyTo(null)
      setMessages((prev) => (prev.some((m) => m.id === msg.id) ? prev : [...prev, msg]))
      loadConvs()
    } catch (err) {
      handleSendError(err, t('Erro ao enviar o arquivo.', 'Failed to send the file.'))
    } finally {
      setAttaching(false)
    }
  }

  async function sendReaction(m: Message, emoji: string) {
    if (!selected) return
    const current = m.payload?.agent_reaction
    const next = current === emoji ? '' : emoji // repetir o mesmo emoji remove
    setReactingId(null)
    try {
      await api.post('/whatsapp/react', {
        conversation_id: selected.id,
        message_db_id: m.id,
        emoji: next,
      })
      setMessages((prev) => prev.map((x) =>
        x.id === m.id ? { ...x, payload: { ...x.payload, agent_reaction: next || null } } : x,
      ))
    } catch {
      alert(t('Não foi possível reagir à mensagem.', 'Could not react to the message.'))
    }
  }

  async function toggleBot() {
    if (!selected) return
    try {
      await api.patch(`/conversations/${selected.id}`, { bot_active: !selected.bot_active })
      loadConvs()
    } catch { /* ignore */ }
  }

  async function assumir() {
    if (!selected) return
    try {
      await api.patch(`/conversations/${selected.id}`, {
        atendente_id: myId,
        atendimento_status: 'em_atendimento',
        bot_active: false,
      })
      loadConvs()
    } catch { /* ignore */ }
  }

  async function openTplPicker() {
    setShowTpl(true)
    setPickedTpl(null)
    setTplOptIn(false)
    try {
      const { data } = await api.get('/whatsapp/templates')
      setTpls(Array.isArray(data) ? data : [])
    } catch { setTpls([]) }
  }

  function pickTpl(tpl: Tpl) {
    setPickedTpl(tpl)
    const body = tpl.components?.find((c) => c.type === 'BODY')?.text || ''
    const nums = [...body.matchAll(/\{\{(\d+)\}\}/g)].map((m) => parseInt(m[1]))
    setTplVars(Array(nums.length ? Math.max(...nums) : 0).fill(''))
  }

  async function sendTemplate() {
    if (!pickedTpl || !selected) return
    setSendingTpl(true)
    try {
      await api.post('/whatsapp/send-template', {
        to: recipientWaId || '',
        template_name: pickedTpl.name,
        language: pickedTpl.language || 'pt_BR',
        variables: tplVars,
        conversation_id: selected.id,
        opt_in_confirmed: tplOptIn,
      })
      setShowTpl(false)
      setPickedTpl(null)
      loadMessages(selected.id)
    } catch (err: any) {
      const detail = err?.response?.data?.detail
      alert(detail?.message || (typeof detail === 'string' ? detail : t('Erro ao enviar template.', 'Failed to send template.')))
    } finally {
      setSendingTpl(false)
    }
  }

  function openInteractive() {
    setIntKind('buttons')
    setIntBody('')
    setIntButtons([{ id: 'opt_1', title: '' }])
    setIntListButton(t('Ver opções', 'See options'))
    setIntRows([{ id: 'row_1', title: '', description: '' }])
    setShowInt(true)
  }

  const intValid = intBody.trim().length > 0 && (
    intKind === 'buttons'
      ? intButtons.some((b) => b.title.trim())
      : intListButton.trim() && intRows.some((r) => r.title.trim())
  )

  async function sendInteractive() {
    if (!selected || !intValid || sendingInt) return
    setSendingInt(true)
    try {
      const base = { conversation_id: selected.id, body: intBody.trim(), kind: intKind }
      const payload = intKind === 'buttons'
        ? { ...base, buttons: intButtons.filter((b) => b.title.trim()).map((b, i) => ({ id: b.id || `opt_${i + 1}`, title: b.title.trim() })) }
        : {
            ...base,
            button_text: intListButton.trim(),
            sections: [{
              rows: intRows.filter((r) => r.title.trim()).map((r, i) => ({
                id: r.id || `row_${i + 1}`,
                title: r.title.trim(),
                description: r.description.trim() || null,
              })),
            }],
          }
      await api.post('/whatsapp/send-interactive', payload)
      setShowInt(false)
      loadMessages(selected.id)
      loadConvs()
    } catch (err) {
      handleSendError(err, t('Erro ao enviar mensagem interativa.', 'Failed to send interactive message.'))
    } finally {
      setSendingInt(false)
    }
  }

  function getConvName(): string {
    return selected?.customer_name || t('Sem nome', 'No name')
  }

  const composerDisabled = !windowInfo.open

  return (
    <div className="flex gap-4 h-[calc(100vh-4rem)]">
      {/* ---------- Coluna esquerda: filas + lista ---------- */}
      <div className="w-80 shrink-0 flex flex-col bg-[#0d0d13] border border-white/[0.06] rounded-xl overflow-hidden">
        <div className="px-4 pt-4 pb-3 border-b border-white/[0.06] flex items-center justify-between">
          <h1 className="text-sm font-semibold text-[#e2e2e8] flex items-center gap-2">
            <MessageSquare size={16} className="text-emerald-400" />
            WhatsApp
          </h1>
          <Link
            to="/app/templates"
            className="flex items-center gap-1.5 text-[11px] text-[#5a5a6e] hover:text-[#c0c0d0] transition-colors no-underline"
            title={t('Templates de WhatsApp', 'WhatsApp templates')}
          >
            <FileText size={13} />
            Templates
          </Link>
        </div>

        {/* Filas */}
        <div className="flex gap-1 p-2 border-b border-white/[0.06]">
          {QUEUES.map((q) => {
            const Icon = q.icon
            const active = queue === q.id
            return (
              <button
                key={q.id}
                onClick={() => setQueue(q.id)}
                className={`flex-1 flex flex-col items-center gap-1 py-2 rounded-lg text-[11px] font-medium transition-colors ${
                  active ? 'bg-white/[0.06] text-[#e2e2e8]' : 'text-[#5a5a6e] hover:bg-white/[0.03]'
                }`}
              >
                <Icon size={15} className={active ? q.color : ''} />
                <span className="flex items-center gap-1">
                  {t(q.pt, q.en)}
                  <span className={`px-1 rounded ${active ? 'bg-white/10 text-[#c0c0d0]' : 'text-[#444]'}`}>
                    {counts[q.id]}
                  </span>
                </span>
              </button>
            )
          })}
        </div>

        {/* Lista de conversas */}
        <div className="flex-1 overflow-y-auto">
          {visible.length === 0 ? (
            <div className="p-6 text-center text-[#4a4a5a] text-xs mt-8">
              {t('Nenhuma conversa nesta fila.', 'No conversations in this queue.')}
            </div>
          ) : (
            visible.map((c) => {
              const isSel = c.id === selectedId
              return (
                <button
                  key={c.id}
                  onClick={() => setSelectedId(c.id)}
                  className={`w-full flex items-center gap-3 px-3 py-3 border-b border-white/[0.03] text-left transition-colors ${
                    isSel ? 'bg-indigo-600/10' : 'hover:bg-white/[0.03]'
                  }`}
                >
                  <div className="w-9 h-9 rounded-full bg-white/[0.06] flex items-center justify-center text-xs font-bold text-[#8a8a9e] shrink-0">
                    {(c.customer_name || '?').charAt(0).toUpperCase()}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-[13px] font-medium text-[#e2e2e8] truncate">
                      {c.customer_name || t('Sem nome', 'No name')}
                    </p>
                    <p className="text-[11px] text-[#5a5a6e] truncate">{statusText(c.atendimento_status)}</p>
                  </div>
                  {c.unread_count > 0 && (
                    <span className="bg-emerald-500 text-white text-[10px] font-bold rounded-full min-w-[18px] h-[18px] flex items-center justify-center px-1 shrink-0">
                      {c.unread_count}
                    </span>
                  )}
                </button>
              )
            })
          )}
        </div>
      </div>

      {/* ---------- Coluna direita: thread ---------- */}
      <div className="flex-1 flex flex-col bg-[#0d0d13] border border-white/[0.06] rounded-xl overflow-hidden">
        {!selected ? (
          <div className="flex-1 flex flex-col items-center justify-center text-center px-6">
            <div className="w-16 h-16 rounded-2xl bg-emerald-500/10 flex items-center justify-center mb-4">
              <MessageSquare size={28} className="text-emerald-400/70" />
            </div>
            <p className="text-[#e2e2e8] font-medium mb-1">{t('Selecione uma conversa', 'Select a conversation')}</p>
            <p className="text-[#5a5a6e] text-sm max-w-xs">
              {t('As conversas aparecem aqui quando um cliente manda mensagem no WhatsApp.', 'Conversations show up here when a customer messages you on WhatsApp.')}
            </p>
          </div>
        ) : (
          <>
            {/* Header da conversa */}
            <div className="flex items-center gap-3 px-4 py-3 border-b border-white/[0.06]">
              <div className="w-9 h-9 rounded-full bg-white/[0.06] flex items-center justify-center text-xs font-bold text-[#8a8a9e] shrink-0">
                {getConvName().charAt(0).toUpperCase()}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-[#e2e2e8] truncate">{getConvName()}</p>
                <p className="text-[11px] text-[#5a5a6e]">
                  {statusText(selected.atendimento_status)}
                  {windowLabel && (
                    <span className="text-emerald-400/70"> · {t('janela de 24h', '24h window')}: {windowLabel}</span>
                  )}
                </p>
              </div>

              {/* Assumir */}
              {selected.atendente_id !== myId && (
                <button
                  onClick={assumir}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold transition-colors"
                >
                  <UserCheck size={13} />
                  {t('Assumir', 'Take over')}
                </button>
              )}

              {/* Toggle bot */}
              <button
                onClick={toggleBot}
                title={selected.bot_active ? t('Bot ligado — clique para desligar', 'Bot on — click to turn off') : t('Bot desligado — clique para ligar', 'Bot off — click to turn on')}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors border ${
                  selected.bot_active
                    ? 'bg-emerald-500/15 border-emerald-500/30 text-emerald-400'
                    : 'bg-white/[0.04] border-white/[0.08] text-[#5a5a6e]'
                }`}
              >
                <Power size={13} />
                Bot {selected.bot_active ? 'ON' : 'OFF'}
              </button>
            </div>

            {/* Thread */}
            <div ref={threadRef} className="flex-1 overflow-y-auto px-4 py-4 space-y-2">
              {loadingMsgs ? (
                <p className="text-center text-[#4a4a5a] text-xs mt-8">{t('Carregando…', 'Loading…')}</p>
              ) : messages.length === 0 ? (
                <p className="text-center text-[#4a4a5a] text-xs mt-8">{t('Nenhuma mensagem ainda.', 'No messages yet.')}</p>
              ) : (
                messages.map((m) => {
                  const out = m.direction === 'outbound'
                  const reactions = [m.payload?.customer_reaction, m.payload?.agent_reaction].filter(Boolean) as string[]
                  return (
                    <div key={m.id} className={`flex ${out ? 'justify-end' : 'justify-start'}`}>
                      <div className={`group relative max-w-[70%] ${reactions.length ? 'mb-3' : ''}`}>
                        {/* Ações no hover: responder + reagir */}
                        <div
                          className={`absolute top-1 ${out ? '-left-16' : '-right-16'} hidden group-hover:flex items-center gap-1 z-10`}
                        >
                          <button
                            onClick={() => { setReplyTo(m); setReactingId(null) }}
                            title={t('Responder', 'Reply')}
                            className="w-7 h-7 rounded-full bg-[#1a1a24] border border-white/[0.08] text-[#8a8a9e] hover:text-white flex items-center justify-center"
                          >
                            <Reply size={13} />
                          </button>
                          <button
                            onClick={() => setReactingId(reactingId === m.id ? null : m.id)}
                            title={t('Reagir', 'React')}
                            className="w-7 h-7 rounded-full bg-[#1a1a24] border border-white/[0.08] text-[#8a8a9e] hover:text-white flex items-center justify-center"
                          >
                            <SmilePlus size={13} />
                          </button>
                        </div>

                        {/* Picker de reação */}
                        {reactingId === m.id && (
                          <div
                            className={`absolute -top-9 ${out ? 'right-0' : 'left-0'} flex gap-0.5 bg-[#1a1a24] border border-white/[0.1] rounded-full px-1.5 py-1 shadow-xl z-20`}
                          >
                            {REACTION_EMOJIS.map((e) => (
                              <button
                                key={e}
                                onClick={() => sendReaction(m, e)}
                                className={`text-base hover:scale-125 transition-transform px-0.5 ${
                                  m.payload?.agent_reaction === e ? 'bg-white/10 rounded-full' : ''
                                }`}
                              >
                                {e}
                              </button>
                            ))}
                          </div>
                        )}

                        <div
                          className={`rounded-2xl px-3.5 py-2 ${
                            out
                              ? 'bg-indigo-600 text-white rounded-br-sm'
                              : 'bg-white/[0.06] text-[#e2e2e8] rounded-bl-sm'
                          }`}
                        >
                          {/* Quote (mensagem citada) */}
                          {m.context_text && (
                            <div className={`mb-1.5 px-2 py-1 rounded-lg border-l-2 text-[11px] ${
                              out ? 'bg-white/10 border-white/40 text-white/70' : 'bg-black/20 border-emerald-400/60 text-[#8a8a9e]'
                            }`}>
                              <p className="truncate">{m.context_text}</p>
                            </div>
                          )}

                          {m.media_type && <div className="mb-1"><MediaContent m={m} /></div>}
                          {m.text && (
                            <p className="text-[13px] whitespace-pre-wrap break-words">{m.text}</p>
                          )}
                          <div className={`flex items-center gap-1 justify-end mt-0.5 ${out ? 'text-white/60' : 'text-[#5a5a6e]'}`}>
                            <span className="text-[10px]">{fmtTime(m.created_at)}</span>
                            {out && <MsgStatus status={m.status} error={m.payload?.error} />}
                          </div>
                        </div>

                        {/* Reações aplicadas */}
                        {reactions.length > 0 && (
                          <div className={`absolute -bottom-3 ${out ? 'right-2' : 'left-2'} flex gap-0.5`}>
                            <span className="bg-[#1a1a24] border border-white/[0.1] rounded-full px-1.5 py-px text-[11px] shadow">
                              {reactions.join(' ')}
                            </span>
                          </div>
                        )}
                      </div>
                    </div>
                  )
                })
              )}
            </div>

            {/* Banner: janela de 24h expirada */}
            {composerDisabled && !loadingMsgs && (
              <div className="mx-3 mb-2 flex items-center justify-between gap-3 bg-amber-900/15 border border-amber-500/20 rounded-xl px-4 py-2.5">
                <p className="text-amber-400/90 text-[12px]">
                  {windowInfo.neverOpened
                    ? t('O cliente ainda não escreveu — envie um template aprovado (exige opt-in) para iniciar a conversa.', "The customer hasn't written yet — send an approved template (opt-in required) to start the conversation.")
                    : t('Janela de 24h expirada. Envie um template aprovado para reabrir a conversa.', '24-hour window expired. Send an approved template to reopen the conversation.')}
                </p>
                <button
                  onClick={openTplPicker}
                  className="shrink-0 px-3 py-1.5 bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 rounded-lg text-xs font-semibold transition-colors"
                >
                  {t('Enviar template', 'Send template')}
                </button>
              </div>
            )}

            {/* Barra de resposta (quote) */}
            {replyTo && (
              <div className="mx-3 mb-1 flex items-center gap-2 bg-white/[0.04] border-l-2 border-indigo-500 rounded-lg px-3 py-2">
                <div className="flex-1 min-w-0">
                  <p className="text-[10px] text-indigo-400 font-semibold">
                    {t('Respondendo', 'Replying to')} {replyTo.direction === 'inbound' ? getConvName() : t('você', 'yourself')}
                  </p>
                  <p className="text-[11px] text-[#8a8a9e] truncate">
                    {replyTo.text || `[${replyTo.media_type || t('mídia', 'media')}]`}
                  </p>
                </div>
                <button onClick={() => setReplyTo(null)} className="text-[#5a5a6e] hover:text-white shrink-0">
                  <X size={14} />
                </button>
              </div>
            )}

            {/* Caixa de resposta */}
            <div className="p-3 border-t border-white/[0.06]">
              <div className="flex items-end gap-2">
                <button
                  onClick={openTplPicker}
                  title={t('Enviar template (fora da janela de 24h)', 'Send template (outside the 24h window)')}
                  className="w-10 h-10 shrink-0 rounded-xl bg-white/[0.05] border border-white/[0.08] text-[#8a8a9e] hover:text-white flex items-center justify-center transition-colors"
                >
                  <FileText size={16} />
                </button>
                <button
                  onClick={openInteractive}
                  disabled={composerDisabled}
                  title={t('Mensagem interativa (botões ou lista)', 'Interactive message (buttons or list)')}
                  className="w-10 h-10 shrink-0 rounded-xl bg-white/[0.05] border border-white/[0.08] text-[#8a8a9e] hover:text-white disabled:opacity-30 flex items-center justify-center transition-colors"
                >
                  <LayoutList size={16} />
                </button>
                <button
                  onClick={() => fileInputRef.current?.click()}
                  disabled={composerDisabled || attaching}
                  title={t('Anexar arquivo (imagem, vídeo, áudio ou documento)', 'Attach file (image, video, audio or document)')}
                  className="w-10 h-10 shrink-0 rounded-xl bg-white/[0.05] border border-white/[0.08] text-[#8a8a9e] hover:text-white disabled:opacity-30 flex items-center justify-center transition-colors"
                >
                  <Paperclip size={16} className={attaching ? 'animate-pulse' : ''} />
                </button>
                <input
                  ref={fileInputRef}
                  type="file"
                  className="hidden"
                  onChange={handlePickFile}
                  accept="image/*,video/*,audio/*,application/pdf,.doc,.docx,.xls,.xlsx,.csv,.txt"
                />
                <textarea
                  value={text}
                  onChange={(e) => { setText(e.target.value); notifyTyping() }}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendReply() }
                  }}
                  rows={1}
                  disabled={composerDisabled}
                  placeholder={
                    composerDisabled
                      ? t('Janela de 24h fechada — use um template.', '24h window closed — use a template.')
                      : t('Escreva uma mensagem…  (Enter envia, Shift+Enter quebra linha)', 'Type a message…  (Enter sends, Shift+Enter for a new line)')
                  }
                  className="flex-1 resize-none max-h-32 px-3.5 py-2.5 bg-[#0a0a0f] border border-white/[0.08] text-[#e2e2e8] text-[13px] rounded-xl outline-none focus:border-indigo-500/60 placeholder-[#3a3a4a] disabled:opacity-50"
                />
                <button
                  onClick={sendReply}
                  disabled={!text.trim() || sending || composerDisabled}
                  className="w-10 h-10 shrink-0 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 text-white flex items-center justify-center transition-colors"
                >
                  <Send size={16} />
                </button>
              </div>
            </div>
          </>
        )}
      </div>

      {/* Modal: enviar template */}
      {showTpl && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm px-4">
          <div className="bg-[#111118] border border-white/[0.08] rounded-2xl p-6 w-full max-w-md max-h-[85vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-base font-semibold text-white">{t('Enviar template', 'Send template')}</h3>
              <button onClick={() => setShowTpl(false)} className="text-[#444] hover:text-[#888]"><X size={18} /></button>
            </div>

            {!recipientWaId && (
              <div className="bg-amber-900/15 border border-amber-500/20 text-amber-400/90 text-[11px] rounded-lg px-3 py-2 mb-3">
                {t('Número do cliente não identificado nesta conversa — o envio pode falhar.', "Customer number not identified in this conversation — sending may fail.")}
              </div>
            )}

            {!pickedTpl ? (
              tpls.length === 0 ? (
                <p className="text-[#5a5a6e] text-sm text-center py-6">
                  {t('Nenhum template. Crie na página', 'No templates. Create one on the')}{' '}
                  <Link to="/app/templates" className="text-indigo-400">Templates</Link>{t('.', ' page.')}
                </p>
              ) : (
                <div className="space-y-1.5">
                  {tpls.map((tpl) => (
                    <button
                      key={tpl.name}
                      onClick={() => pickTpl(tpl)}
                      className="w-full text-left px-3 py-2.5 rounded-lg bg-[#0a0a0f] border border-white/[0.06] hover:border-indigo-500/40 transition-colors"
                    >
                      <p className="text-sm font-medium text-[#e2e2e8]">{tpl.name}</p>
                      <p className="text-xs text-[#555] truncate">{tpl.components?.find((c) => c.type === 'BODY')?.text}</p>
                    </button>
                  ))}
                </div>
              )
            ) : (
              <div>
                <div className="bg-[#0a0a0f] border border-white/[0.06] rounded-lg p-3 mb-3">
                  <p className="text-sm font-medium text-[#e2e2e8]">{pickedTpl.name}</p>
                  <p className="text-xs text-[#555] mt-1">{pickedTpl.components?.find((c) => c.type === 'BODY')?.text}</p>
                </div>
                {tplVars.length > 0 && (
                  <div className="space-y-2 mb-3">
                    {tplVars.map((v, i) => (
                      <div key={i}>
                        <label className="block text-[11px] text-[#666] mb-1">{t('Variável', 'Variable')} {`{{${i + 1}}}`}</label>
                        <input
                          value={v}
                          onChange={(e) => setTplVars((prev) => prev.map((x, j) => (j === i ? e.target.value : x)))}
                          className="w-full px-3 py-2 bg-[#0a0a0f] border border-white/[0.08] text-[#e2e2e8] text-sm rounded-lg focus:border-indigo-500 focus:outline-none"
                        />
                      </div>
                    ))}
                  </div>
                )}
                <label className="flex items-start gap-2 mb-3 text-[11px] text-[#8a8a9e] cursor-pointer">
                  <input type="checkbox" checked={tplOptIn} onChange={(e) => setTplOptIn(e.target.checked)} className="mt-0.5 accent-indigo-500" />
                  <span>
                    {t(
                      'Confirmo que este contato aceitou receber mensagens da empresa no WhatsApp (opt-in). O consentimento fica registrado no lead.',
                      'I confirm this contact agreed to receive messages from the business on WhatsApp (opt-in). The consent is recorded on the lead.',
                    )}
                  </span>
                </label>
                <div className="flex gap-2">
                  <button onClick={() => setPickedTpl(null)} className="flex-1 py-2.5 border border-white/[0.08] text-[#666] hover:text-white text-sm rounded-lg transition-colors">{t('Voltar', 'Back')}</button>
                  <button onClick={sendTemplate} disabled={sendingTpl} className="flex-1 py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm font-semibold rounded-lg transition-colors">
                    {sendingTpl ? t('Enviando…', 'Sending…') : t('Enviar', 'Send')}
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Modal: mensagem interativa (botões / lista) */}
      {showInt && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm px-4">
          <div className="bg-[#111118] border border-white/[0.08] rounded-2xl p-6 w-full max-w-md max-h-[85vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-base font-semibold text-white">{t('Mensagem interativa', 'Interactive message')}</h3>
              <button onClick={() => setShowInt(false)} className="text-[#444] hover:text-[#888]"><X size={18} /></button>
            </div>

            {/* Tipo */}
            <div className="flex gap-2 mb-4">
              {(['buttons', 'list'] as const).map((k) => (
                <button
                  key={k}
                  onClick={() => setIntKind(k)}
                  className={`flex-1 py-2 rounded-lg text-xs font-semibold border transition-colors ${
                    intKind === k
                      ? 'bg-indigo-600/20 border-indigo-500/50 text-indigo-300'
                      : 'bg-white/[0.03] border-white/[0.08] text-[#5a5a6e] hover:text-white'
                  }`}
                >
                  {k === 'buttons' ? t('Botões (até 3)', 'Buttons (up to 3)') : t('Lista (até 10)', 'List (up to 10)')}
                </button>
              ))}
            </div>

            <label className="block text-[11px] text-[#666] mb-1">{t('Texto da mensagem', 'Message text')}</label>
            <textarea
              value={intBody}
              onChange={(e) => setIntBody(e.target.value)}
              rows={3}
              maxLength={1024}
              placeholder={t('Ex.: Como podemos te ajudar hoje?', 'E.g. How can we help you today?')}
              className="w-full mb-3 px-3 py-2 bg-[#0a0a0f] border border-white/[0.08] text-[#e2e2e8] text-sm rounded-lg focus:border-indigo-500 focus:outline-none resize-none"
            />

            {intKind === 'buttons' ? (
              <div className="space-y-2 mb-4">
                <label className="block text-[11px] text-[#666]">{t('Botões de resposta rápida', 'Quick reply buttons')}</label>
                {intButtons.map((b, i) => (
                  <div key={i} className="flex gap-2">
                    <input
                      value={b.title}
                      maxLength={20}
                      onChange={(e) => setIntButtons((prev) => prev.map((x, j) => (j === i ? { ...x, title: e.target.value } : x)))}
                      placeholder={t(`Botão ${i + 1} (máx. 20 caracteres)`, `Button ${i + 1} (max 20 characters)`)}
                      className="flex-1 px-3 py-2 bg-[#0a0a0f] border border-white/[0.08] text-[#e2e2e8] text-sm rounded-lg focus:border-indigo-500 focus:outline-none"
                    />
                    {intButtons.length > 1 && (
                      <button
                        onClick={() => setIntButtons((prev) => prev.filter((_, j) => j !== i))}
                        className="w-9 shrink-0 text-[#5a5a6e] hover:text-red-400 flex items-center justify-center"
                      >
                        <Trash2 size={14} />
                      </button>
                    )}
                  </div>
                ))}
                {intButtons.length < 3 && (
                  <button
                    onClick={() => setIntButtons((prev) => [...prev, { id: `opt_${prev.length + 1}`, title: '' }])}
                    className="flex items-center gap-1.5 text-[11px] text-indigo-400 hover:text-indigo-300"
                  >
                    <Plus size={13} /> {t('Adicionar botão', 'Add button')}
                  </button>
                )}
              </div>
            ) : (
              <div className="space-y-2 mb-4">
                <label className="block text-[11px] text-[#666]">{t('Texto do botão que abre a lista', 'Text of the button that opens the list')}</label>
                <input
                  value={intListButton}
                  maxLength={20}
                  onChange={(e) => setIntListButton(e.target.value)}
                  className="w-full px-3 py-2 bg-[#0a0a0f] border border-white/[0.08] text-[#e2e2e8] text-sm rounded-lg focus:border-indigo-500 focus:outline-none"
                />
                <label className="block text-[11px] text-[#666] pt-1">{t('Opções da lista', 'List options')}</label>
                {intRows.map((r, i) => (
                  <div key={i} className="flex gap-2">
                    <div className="flex-1 space-y-1">
                      <input
                        value={r.title}
                        maxLength={24}
                        onChange={(e) => setIntRows((prev) => prev.map((x, j) => (j === i ? { ...x, title: e.target.value } : x)))}
                        placeholder={t(`Opção ${i + 1} (máx. 24 caracteres)`, `Option ${i + 1} (max 24 characters)`)}
                        className="w-full px-3 py-2 bg-[#0a0a0f] border border-white/[0.08] text-[#e2e2e8] text-sm rounded-lg focus:border-indigo-500 focus:outline-none"
                      />
                      <input
                        value={r.description}
                        maxLength={72}
                        onChange={(e) => setIntRows((prev) => prev.map((x, j) => (j === i ? { ...x, description: e.target.value } : x)))}
                        placeholder={t('Descrição (opcional)', 'Description (optional)')}
                        className="w-full px-3 py-1.5 bg-[#0a0a0f] border border-white/[0.06] text-[#8a8a9e] text-xs rounded-lg focus:border-indigo-500 focus:outline-none"
                      />
                    </div>
                    {intRows.length > 1 && (
                      <button
                        onClick={() => setIntRows((prev) => prev.filter((_, j) => j !== i))}
                        className="w-9 shrink-0 text-[#5a5a6e] hover:text-red-400 flex items-center justify-center"
                      >
                        <Trash2 size={14} />
                      </button>
                    )}
                  </div>
                ))}
                {intRows.length < 10 && (
                  <button
                    onClick={() => setIntRows((prev) => [...prev, { id: `row_${prev.length + 1}`, title: '', description: '' }])}
                    className="flex items-center gap-1.5 text-[11px] text-indigo-400 hover:text-indigo-300"
                  >
                    <Plus size={13} /> {t('Adicionar opção', 'Add option')}
                  </button>
                )}
              </div>
            )}

            <div className="flex gap-2">
              <button
                onClick={() => setShowInt(false)}
                className="flex-1 py-2.5 border border-white/[0.08] text-[#666] hover:text-white text-sm rounded-lg transition-colors"
              >
                {t('Cancelar', 'Cancel')}
              </button>
              <button
                onClick={sendInteractive}
                disabled={!intValid || sendingInt}
                className="flex-1 py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm font-semibold rounded-lg transition-colors"
              >
                {sendingInt ? t('Enviando…', 'Sending…') : t('Enviar', 'Send')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
