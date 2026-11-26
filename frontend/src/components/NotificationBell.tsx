import { useEffect, useState, type ReactElement } from 'react'
import { Link } from 'react-router-dom'
import { Bell, BellOff, BellRing, Smartphone, X } from 'lucide-react'
import { useI18n } from '../i18n'
import { apiError } from '../services/api'
import {
  disablePush, enablePush, getPrefs, onPrefsChange, pushState, sendTestPush, updatePrefs,
  type NotificationPrefs, type PushState,
} from '../services/notifications'

function Toggle({ on, onChange, label, hint }: { on: boolean; onChange: (v: boolean) => void; label: string; hint: string }) {
  return (
    <button type="button" onClick={() => onChange(!on)} className="w-full flex items-start gap-3 text-left py-2">
      <span className="flex-1 min-w-0">
        <span className="block text-sm text-ink">{label}</span>
        <span className="block text-[11px] text-ink-4">{hint}</span>
      </span>
      <span className={`mt-0.5 w-10 h-5 rounded-full relative shrink-0 transition-colors ${on ? 'bg-violet-500' : 'bg-white/[0.12]'}`}>
        <span className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-all ${on ? 'left-[22px]' : 'left-0.5'}`} />
      </span>
    </button>
  )
}

/** Sino do painel: notificação no aparelho, "silenciar todos" e aviso de lead interessado. */
export default function NotificationBell({ placement }: { placement: 'sidebar' | 'header' }) {
  const { t } = useI18n()
  const [open, setOpen] = useState(false)
  const [prefs, setPrefs] = useState<NotificationPrefs | null>(getPrefs())
  const [push, setPush] = useState<PushState | null>(null)
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState('')

  useEffect(() => onPrefsChange(() => setPrefs(getPrefs())), [])
  useEffect(() => {
    if (open) pushState().then(setPush)
  }, [open, prefs])

  async function run(fn: () => Promise<unknown>, ok?: string) {
    setBusy(true)
    setMsg('')
    try {
      await fn()
      if (ok) setMsg(ok)
    } catch (err) {
      setMsg(apiError(err, t('Não deu certo. Tente de novo.', 'That did not work. Try again.')))
    } finally {
      setBusy(false)
      setPush(await pushState())
    }
  }

  const silenced = prefs ? !prefs.messages_enabled : false
  const Icon = silenced ? BellOff : Bell

  const pushBox: Record<PushState, ReactElement> = {
    on: (
      <div className="flex flex-wrap gap-2">
        <span className="text-xs text-emerald-300 flex items-center gap-1.5 w-full"><BellRing size={13} /> {t('Ativas neste aparelho', 'On for this device')}</span>
        <button disabled={busy} onClick={() => run(sendTestPush, t('Enviado! Deve chegar em segundos.', 'Sent! It should arrive in seconds.'))} className="px-2.5 py-1.5 rounded-lg bg-white/[0.06] text-xs text-ink-2 hover:bg-white/[0.1]">{t('Testar', 'Test')}</button>
        <button disabled={busy} onClick={() => run(disablePush)} className="px-2.5 py-1.5 rounded-lg text-xs text-ink-4 hover:text-ink-2">{t('Desativar neste aparelho', 'Turn off on this device')}</button>
      </div>
    ),
    off: (
      <button disabled={busy} onClick={() => run(enablePush)} className="w-full py-2 rounded-lg bg-gradient-to-r from-violet-600 via-fuchsia-500 to-orange-400 text-white text-sm font-semibold disabled:opacity-60">
        {t('Ativar notificações neste aparelho', 'Turn on notifications on this device')}
      </button>
    ),
    denied: <p className="text-xs text-amber-300">{t('As notificações foram bloqueadas no navegador. Libere nas configurações do site (cadeado na barra de endereço) e volte aqui.', 'Notifications are blocked in the browser. Allow them in the site settings (padlock in the address bar) and come back.')}</p>,
    'needs-install': (
      <p className="text-xs text-ink-3">
        {t('No iPhone, as notificações só funcionam com o app instalado: no Safari, toque em Compartilhar → "Adicionar à Tela de Início" e abra pelo ícone.', 'On iPhone, notifications only work with the app installed: in Safari, tap Share → "Add to Home Screen" and open it from the icon.')}{' '}
        <Link to="/instalar" className="text-violet-300 underline" onClick={() => setOpen(false)}>{t('Ver passo a passo', 'See how')}</Link>
      </p>
    ),
    'not-configured': <p className="text-xs text-ink-4">{t('As notificações no celular ainda não foram ligadas no servidor (chaves VAPID).', 'Phone notifications are not enabled on the server yet (VAPID keys).')}</p>,
    unsupported: <p className="text-xs text-ink-4">{t('Este navegador não recebe notificações. Use Chrome, Edge ou o app instalado.', 'This browser cannot receive notifications. Use Chrome, Edge or the installed app.')}</p>,
  }

  const panelPos = placement === 'sidebar' ? 'lg:left-[16.5rem] lg:top-3' : 'right-3 top-16'

  return (
    <>
      <button
        onClick={() => setOpen((v) => !v)}
        aria-label={t('Notificações', 'Notifications')}
        className={`w-9 h-9 flex items-center justify-center rounded-lg hover:bg-white/[0.06] ${silenced ? 'text-ink-5' : 'text-ink-3'}`}
      >
        <Icon size={18} />
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-[60]" onClick={() => setOpen(false)} />
          <div className={`fixed z-[61] w-[320px] max-w-[calc(100vw-1.5rem)] bg-card border border-white/[0.1] rounded-2xl shadow-2xl p-4 ${panelPos}`}>
            <div className="flex items-center justify-between mb-3">
              <p className="text-sm font-semibold text-white">{t('Notificações', 'Notifications')}</p>
              <button onClick={() => setOpen(false)} className="text-ink-5 hover:text-ink-3"><X size={16} /></button>
            </div>

            <div className="rounded-xl bg-white/[0.03] border border-white/[0.06] p-3 mb-3">
              <p className="text-[11px] font-medium text-ink-4 mb-2 flex items-center gap-1.5"><Smartphone size={12} /> {t('Celular e computador', 'Phone and computer')}</p>
              {push ? pushBox[push] : <p className="text-xs text-ink-5">…</p>}
            </div>

            {prefs && (
              <div className="divide-y divide-white/[0.06]">
                <Toggle
                  on={prefs.messages_enabled}
                  onChange={(v) => run(() => updatePrefs({ messages_enabled: v }))}
                  label={t('Toda mensagem nova', 'Every new message')}
                  hint={prefs.messages_enabled ? t('Desligue para silenciar todos.', 'Turn off to mute everyone.') : t('Silenciado: nenhum aviso de mensagem.', 'Muted: no message alerts.')}
                />
                <Toggle
                  on={prefs.interest_enabled}
                  onChange={(v) => run(() => updatePrefs({ interest_enabled: v }))}
                  label={t('🔥 Lead interessado', '🔥 Interested lead')}
                  hint={t('Quando a IA percebe interesse e chama você. Toca mesmo com o resto silenciado.', 'When the AI detects interest and calls you. Rings even with everything else muted.')}
                />
              </div>
            )}
            <p className="text-[11px] text-ink-5 mt-2">{t('Para silenciar só um contato, abra a conversa e toque no sino dela.', 'To mute a single contact, open the conversation and tap its bell.')}</p>
            {msg && <p className="text-[11px] text-ink-3 mt-2">{msg}</p>}
          </div>
        </>
      )}
    </>
  )
}
