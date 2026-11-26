// Service worker do app instalável. Só trata navegação de páginas (rede primeiro);
// API, WebSocket e arquivos seguem direto para a rede, sem cache.
const CACHE = 'prospecta-shell-v2'

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(CACHE).then((c) => c.add('/')).then(() => self.skipWaiting()))
})

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  )
})

self.addEventListener('fetch', (event) => {
  const req = event.request
  if (req.mode !== 'navigate' || new URL(req.url).origin !== self.location.origin) return
  event.respondWith(
    fetch(req)
      .then((res) => {
        if (res.ok) caches.open(CACHE).then((c) => c.put('/', res.clone()))
        return res
      })
      .catch(() => caches.match('/').then((cached) => cached || Response.error())),
  )
})

// Notificação no celular / computador (Web Push). Com o painel aberto e na frente,
// o próprio painel toca o som (WebSocket); aqui só aparece quando ele está fechado ou em segundo plano.
self.addEventListener('push', (event) => {
  let data = {}
  try {
    data = event.data ? event.data.json() : {}
  } catch {
    data = { body: event.data ? event.data.text() : '' }
  }
  event.waitUntil((async () => {
    const wins = await self.clients.matchAll({ type: 'window', includeUncontrolled: true })
    if (data.kind !== 'test' && wins.some((w) => w.visibilityState === 'visible' && w.focused)) return
    await self.registration.showNotification(data.title || 'Prospecta', {
      body: data.body || '',
      icon: '/icon-192.png',
      badge: '/badge-96.png',
      tag: data.tag,
      renotify: Boolean(data.tag),
      requireInteraction: data.kind === 'interest',
      vibrate: data.kind === 'interest' ? [250, 100, 250, 100, 400] : [150, 80, 150],
      data: { url: data.url || '/app' },
    })
  })())
})

self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  const url = new URL((event.notification.data && event.notification.data.url) || '/app', self.location.origin).href
  event.waitUntil((async () => {
    const wins = await self.clients.matchAll({ type: 'window', includeUncontrolled: true })
    const win = wins.find((w) => new URL(w.url).origin === self.location.origin)
    if (win) {
      await win.focus()
      if ('navigate' in win) {
        try { await win.navigate(url) } catch { /* janela não controlada: fica onde está */ }
      }
      return
    }
    await self.clients.openWindow(url)
  })())
})
