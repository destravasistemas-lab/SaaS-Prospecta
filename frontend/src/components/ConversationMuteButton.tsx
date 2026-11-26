import { useEffect, useState } from 'react'
import { Bell, BellOff } from 'lucide-react'
import { useI18n } from '../i18n'
import { isConversationMuted, onPrefsChange, setConversationMuted } from '../services/notifications'

/** Sino da conversa: silencia os avisos de mensagem deste contato (só para você). */
export default function ConversationMuteButton({ conversationId }: { conversationId: string }) {
  const { t } = useI18n()
  const [muted, setMuted] = useState(isConversationMuted(conversationId))
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    setMuted(isConversationMuted(conversationId))
    return onPrefsChange(() => setMuted(isConversationMuted(conversationId)))
  }, [conversationId])

  async function toggle() {
    setBusy(true)
    try {
      await setConversationMuted(conversationId, !muted)
    } catch { /* mantém o estado anterior */ } finally {
      setBusy(false)
    }
  }

  const label = muted
    ? t('Contato silenciado — toque para voltar a avisar', 'Contact muted — tap to get alerts again')
    : t('Silenciar este contato', 'Mute this contact')
  return (
    <button
      onClick={toggle}
      disabled={busy}
      title={label}
      aria-label={label}
      aria-pressed={muted}
      className={`shrink-0 w-9 h-9 flex items-center justify-center rounded-lg border transition-colors ${
        muted ? 'border-white/[0.08] text-ink-5 bg-white/[0.03]' : 'border-transparent text-ink-3 hover:bg-white/[0.06]'
      }`}
    >
      {muted ? <BellOff size={16} /> : <Bell size={16} />}
    </button>
  )
}
