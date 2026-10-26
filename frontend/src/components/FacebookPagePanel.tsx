import { useCallback, useEffect, useState } from 'react'
import { ExternalLink, Flag, Webhook } from 'lucide-react'
import api, { apiError } from '../services/api'
import { useI18n } from '../i18n'

interface FbPage {
  id: string
  name: string
  category: string | null
  picture_url: string | null
  tasks: string[]
  selected: boolean
}

interface WebhookStatus {
  page_id: string
  subscribed: boolean
  fields: string[]
}

interface PagePost {
  id: string
  message: string | null
  picture_url: string | null
  permalink: string | null
  created_time: string | null
}

/** Página do Facebook usada nos anúncios: escolha da Página, webhook de Lead Ads e posts recentes. */
export default function FacebookPagePanel() {
  const { t, locale } = useI18n()
  const [pages, setPages] = useState<FbPage[]>([])
  const [pageId, setPageId] = useState('')
  const [hook, setHook] = useState<WebhookStatus | null>(null)
  const [posts, setPosts] = useState<PagePost[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const loadPageData = useCallback(async (id: string) => {
    setHook(null)
    setPosts([])
    const [h, p] = await Promise.allSettled([
      api.get<WebhookStatus>(`/marketing/pages/${id}/webhooks`),
      api.get<PagePost[]>('/marketing/page-posts', { params: { page_id: id } }),
    ])
    if (h.status === 'fulfilled') setHook(h.value.data)
    if (p.status === 'fulfilled') setPosts(p.value.data)
    else setError(apiError(p.reason, t('Não foi possível carregar os posts da Página.', 'Could not load the Page posts.')))
  }, [])

  useEffect(() => {
    api.get<FbPage[]>('/marketing/pages')
      .then(({ data }) => {
        setPages(data)
        const current = data.find((p) => p.selected) ?? data[0]
        if (current) {
          setPageId(current.id)
          loadPageData(current.id)
        }
      })
      .catch(() => { /* sem conexão de anúncios — a tela de campanhas já mostra o aviso */ })
  }, [loadPageData])

  async function selectPage(id: string) {
    if (!id || id === pageId) return
    setBusy(true)
    setError('')
    try {
      await api.put('/marketing/page', { page_id: id })
      setPageId(id)
      setPages((prev) => prev.map((p) => ({ ...p, selected: p.id === id })))
      await loadPageData(id)
    } catch (err: any) {
      setError(apiError(err, t('Erro ao trocar de Página.', 'Failed to switch Page.')))
    } finally {
      setBusy(false)
    }
  }

  async function toggleWebhook() {
    if (!hook) return
    setBusy(true)
    setError('')
    try {
      const { data } = hook.subscribed
        ? await api.delete<WebhookStatus>(`/marketing/pages/${pageId}/webhooks`)
        : await api.post<WebhookStatus>(`/marketing/pages/${pageId}/webhooks`)
      setHook(data)
    } catch (err: any) {
      setError(apiError(err, t('Erro ao atualizar o webhook da Página.', 'Failed to update the Page webhook.')))
    } finally {
      setBusy(false)
    }
  }

  if (pages.length === 0) return null
  const page = pages.find((p) => p.id === pageId)

  return (
    <div className="bg-[#170e2c] rounded-xl border border-white/[0.06] p-5 mb-8 max-w-4xl">
      <div className="flex items-center gap-2 mb-4">
        <Flag size={15} className="text-indigo-400" />
        <h3 className="text-sm font-semibold text-[#e2e2e8]">{t('Página do Facebook', 'Facebook Page')}</h3>
      </div>

      {error && <p className="text-red-400 text-xs mb-3">{error}</p>}

      <div className="flex flex-wrap items-center gap-4">
        <div className="flex items-center gap-3 min-w-0">
          {page?.picture_url && <img src={page.picture_url} alt="" className="w-10 h-10 rounded-full object-cover" />}
          <div>
            <select
              value={pageId}
              onChange={(e) => selectPage(e.target.value)}
              disabled={busy}
              className="bg-[#0f0820] border border-white/[0.08] text-[#e2e2e8] text-sm rounded-lg px-3 py-1.5 outline-none disabled:opacity-50"
            >
              {pages.map((p) => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
            <p className="text-[10px] text-[#555] mt-1">
              {page?.category} · ID {pageId} · {t(`${pages.length} Página(s) que você gerencia`, `${pages.length} Page(s) you manage`)}
            </p>
          </div>
        </div>

        {hook && (
          <div className="flex items-center gap-2 ml-auto">
            <Webhook size={14} className="text-[#5a5a6e]" />
            <span className="text-xs text-[#8a8a9e]">{t('Webhook de Lead Ads', 'Lead Ads webhook')}:</span>
            <span className={`text-[11px] font-bold px-2 py-0.5 rounded-full ${
              hook.subscribed ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
            }`}>
              {hook.subscribed ? t('Inscrito', 'Subscribed') : t('Não inscrito', 'Not subscribed')}
            </span>
            <button
              onClick={toggleWebhook}
              disabled={busy}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors disabled:opacity-50 ${
                hook.subscribed ? 'bg-white/[0.05] text-[#c0c0d0] hover:bg-white/[0.09]' : 'bg-indigo-600 hover:bg-indigo-500 text-white'
              }`}
            >
              {hook.subscribed ? t('Cancelar inscrição', 'Unsubscribe') : t('Inscrever', 'Subscribe')}
            </button>
          </div>
        )}
      </div>

      {posts.length > 0 && (
        <div className="mt-5">
          <p className="text-xs font-medium text-[#8a8a9e] mb-2">{t('Posts recentes da Página', 'Recent Page posts')}</p>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {posts.slice(0, 8).map((p) => (
              <div key={p.id} className="bg-white/[0.03] rounded-lg overflow-hidden flex flex-col">
                {p.picture_url ? (
                  <img src={p.picture_url} alt="" className="w-full h-28 object-cover" />
                ) : (
                  <div className="w-full h-28 flex items-center justify-center text-[#444] text-xs">{t('Sem imagem', 'No image')}</div>
                )}
                <div className="p-2 flex-1 flex flex-col">
                  <p className="text-[#e2e2e8] text-xs line-clamp-2 flex-1">{p.message || t('Sem texto', 'No text')}</p>
                  <div className="flex items-center justify-between mt-1">
                    {p.created_time && <span className="text-[#555] text-[10px]">{new Date(p.created_time).toLocaleDateString(locale)}</span>}
                    {p.permalink && (
                      <a href={p.permalink} target="_blank" rel="noreferrer" className="text-violet-300 hover:text-violet-200" title={t('Ver no Facebook', 'View on Facebook')}>
                        <ExternalLink size={12} />
                      </a>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
          <p className="text-[10px] text-[#555] mt-2">
            {t('Para impulsionar um destes posts, crie um anúncio numa campanha e escolha "Post FB".', 'To boost one of these posts, create an ad in a campaign and choose "FB post".')}
          </p>
        </div>
      )}
    </div>
  )
}
