/**
 * Notificações: preferências do usuário (toda mensagem / lead interessado), contatos
 * silenciados, push no aparelho (Web Push) e os sons do painel.
 */
import api from './api'
import { detectPlatform, isInstalledApp } from './pwa'

export interface NotificationPrefs {
  push_enabled: boolean
  public_key: string | null
  messages_enabled: boolean
  interest_enabled: boolean
  muted_conversation_ids: string[]
  devices: number
}

export type PushState = 'on' | 'off' | 'denied' | 'needs-install' | 'not-configured' | 'unsupported'

let prefs: NotificationPrefs | null = null
const listeners = new Set<() => void>()
const emit = () => listeners.forEach((fn) => fn())

export const getPrefs = () => prefs

export function onPrefsChange(fn: () => void): () => void {
  listeners.add(fn)
  return () => { listeners.delete(fn) }
}

export async function loadPrefs(): Promise<NotificationPrefs | null> {
  try {
    const { data } = await api.get<NotificationPrefs>('/push/prefs')
    prefs = data
    emit()
  } catch { /* sem login ou API fora: segue sem preferências */ }
  return prefs
}

export async function updatePrefs(change: Partial<Pick<NotificationPrefs, 'messages_enabled' | 'interest_enabled'>>) {
  const { data } = await api.put<NotificationPrefs>('/push/prefs', change)
  prefs = data
  emit()
}

export const isConversationMuted = (id: string) => !!prefs?.muted_conversation_ids.includes(id)

export async function setConversationMuted(id: string, muted: boolean) {
  await api.put(`/push/mutes/${id}`, { muted })
  if (prefs) {
    const others = prefs.muted_conversation_ids.filter((x) => x !== id)
    prefs = { ...prefs, muted_conversation_ids: muted ? [...others, id] : others }
  }
  emit()
}

// ---------------------------------------------------------------------------
// Push no aparelho
// ---------------------------------------------------------------------------

const pushSupported = () => 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window

function keyBytes(b64: string): Uint8Array<ArrayBuffer> {
  const raw = atob((b64 + '='.repeat((4 - (b64.length % 4)) % 4)).replace(/-/g, '+').replace(/_/g, '/'))
  const out = new Uint8Array(new ArrayBuffer(raw.length))
  for (let i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i)
  return out
}

function sameKey(sub: PushSubscription, key: string): boolean {
  const current = sub.options?.applicationServerKey
  if (!current) return true
  const a = new Uint8Array(current)
  const b = keyBytes(key)
  return a.length === b.length && a.every((v, i) => v === b[i])
}

async function currentSubscription(): Promise<PushSubscription | null> {
  const reg = await navigator.serviceWorker.getRegistration()
  return (await reg?.pushManager.getSubscription()) ?? null
}

export async function pushState(): Promise<PushState> {
  // iPhone/iPad só recebem push com o app instalado na tela de início (iOS 16.4+).
  if (detectPlatform() === 'ios' && !isInstalledApp()) return 'needs-install'
  if (!pushSupported()) return 'unsupported'
  if (!prefs?.push_enabled || !prefs.public_key) return 'not-configured'
  if (Notification.permission === 'denied') return 'denied'
  return Notification.permission === 'granted' && (await currentSubscription()) ? 'on' : 'off'
}

export async function enablePush(): Promise<PushState> {
  if (!prefs) await loadPrefs()
  const state = await pushState()
  if (state === 'needs-install' || state === 'unsupported' || state === 'not-configured') return state
  const permission = await Notification.requestPermission()
  if (permission !== 'granted') return permission === 'denied' ? 'denied' : 'off'
  const reg = (await navigator.serviceWorker.getRegistration()) ?? (await navigator.serviceWorker.register('/sw.js'))
  await navigator.serviceWorker.ready
  let sub = await reg.pushManager.getSubscription()
  if (sub && !sameKey(sub, prefs!.public_key!)) {
    await sub.unsubscribe()
    sub = null
  }
  sub ??= await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: keyBytes(prefs!.public_key!) })
  const { data } = await api.post<NotificationPrefs>('/push/subscribe', sub.toJSON())
  prefs = data
  emit()
  return 'on'
}

export async function disablePush() {
  const sub = pushSupported() ? await currentSubscription() : null
  if (sub) {
    await api.post('/push/unsubscribe', { endpoint: sub.endpoint }).catch(() => {})
    await sub.unsubscribe().catch(() => false)
  }
  await loadPrefs()
}

export async function sendTestPush() {
  await api.post('/push/test')
}

/** Ao abrir o painel: reenvia a inscrição do aparelho (troca de login no mesmo celular). */
export async function syncPush() {
  await loadPrefs()
  try {
    if (!pushSupported() || Notification.permission !== 'granted' || !prefs?.push_enabled) return
    const sub = await currentSubscription()
    if (sub && prefs.public_key && sameKey(sub, prefs.public_key)) {
      const { data } = await api.post<NotificationPrefs>('/push/subscribe', sub.toJSON())
      prefs = data
      emit()
    }
  } catch { /* sem push o painel segue normal */ }
}

// ---------------------------------------------------------------------------
// Sons do painel
// ---------------------------------------------------------------------------

let audio: AudioContext | null = null

export function unlockAudio() {
  try {
    audio ??= new AudioContext()
    if (audio.state === 'suspended') audio.resume().catch(() => {})
  } catch { /* navegador sem áudio */ }
}

function chime(notes: number[], step: number, volume: number) {
  unlockAudio()
  if (!audio) return
  const start = audio.currentTime
  notes.forEach((freq, i) => {
    const osc = audio!.createOscillator()
    const gain = audio!.createGain()
    const t0 = start + i * step
    osc.type = 'sine'
    osc.frequency.value = freq
    gain.gain.setValueAtTime(0.0001, t0)
    gain.gain.exponentialRampToValueAtTime(volume, t0 + 0.015)
    gain.gain.exponentialRampToValueAtTime(0.0001, t0 + step * 1.6)
    osc.connect(gain).connect(audio!.destination)
    osc.start(t0)
    osc.stop(t0 + step * 1.7)
  })
}

export const playMessageSound = () => chime([880, 1320], 0.09, 0.08)
export const playInterestSound = () => chime([660, 880, 1320, 880, 1320], 0.12, 0.14)
