import { useEffect, useState } from 'react'
import { Send } from 'lucide-react'
import api from '../services/api'

type Tab = 'publish_auto' | 'scheduled' | 'media'
type TriggerType = 'comment' | 'dm' | 'both'

interface Schedule {
  id: string
  ig_user_id: string
  media_type: string
  media_url: string
  caption: string | null
  hashtags: string | null
  thumbnail_url: string | null
  scheduled_for: string
  published_at: string | null
  status: string
  error_message: string | null
  media_id_response: string | null
  created_at: string
}

interface MediaItem {
  id: string
  media_type: string
  media_url: string | null
  thumbnail_url: string | null
  caption: string | null
  timestamp: string | null
  like_count: number
  comments_count: number
}

interface AutomationConfig {
  id: string
  keyword: string
  auto_reply_message: string
  trigger_type: TriggerType
  media_id: string | null
  comment_reply_message: string | null
  dm_message: string | null
  link_message: string | null
  is_active: boolean
}

const triggerLabel: Record<TriggerType, string> = {
  comment: 'Comentário',
  dm: 'DM / WhatsApp',
  both: 'Comentário + DM/WhatsApp',
}

// Janela de agendamento: de agora até 15 dias à frente (formato datetime-local).
const MAX_SCHEDULE_DAYS = 15
const toLocalInput = (d: Date) => {
  const off = d.getTimezoneOffset() * 60000
  return new Date(d.getTime() - off).toISOString().slice(0, 16)
}
const minScheduleDate = () => toLocalInput(new Date())
const maxScheduleDate = () =>
  toLocalInput(new Date(Date.now() + MAX_SCHEDULE_DAYS * 86400000))

export default function PublicarInstagram() {
  const [tab, setTab] = useState<Tab>('publish_auto')
  const [igUserId, setIgUserId] = useState('')
  const [mediaUrl, setMediaUrl] = useState('')
  const [mediaType, setMediaType] = useState('IMAGE')
  const [caption, setCaption] = useState('')
  const [hashtags, setHashtags] = useState('')
  const [scheduledFor, setScheduledFor] = useState('')
  const [publishing, setPublishing] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [uploadedName, setUploadedName] = useState('')
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  // Automação de comentário deste post (funil criado junto com a publicação)
  const [autoEnabled, setAutoEnabled] = useState(false)
  const [autoKeyword, setAutoKeyword] = useState('')
  const [autoCommentReply, setAutoCommentReply] = useState('')
  const [autoDmMessage, setAutoDmMessage] = useState('')
  const [autoLinkMessage, setAutoLinkMessage] = useState('')

  const [schedules, setSchedules] = useState<Schedule[]>([])
  const [mediaList, setMediaList] = useState<MediaItem[]>([])
  const [loadingSchedules, setLoadingSchedules] = useState(false)
  const [loadingMedia, setLoadingMedia] = useState(false)
  const [insights, setInsights] = useState<any>(null)
  const [loadingInsights, setLoadingInsights] = useState(false)
  const [stories, setStories] = useState<any[]>([])
  const [loadingStories, setLoadingStories] = useState(false)

  // Lista de automações cadastradas (visualizar / pausar / remover)
  const [automations, setAutomations] = useState<AutomationConfig[]>([])
  const [loadingAutomations, setLoadingAutomations] = useState(false)

  useEffect(() => {
    if (tab === 'scheduled') loadSchedules()
    if (tab === 'media') { loadMedia(); loadInsights(); loadStories() }
    if (tab === 'publish_auto') { loadAutomations(); loadMedia() }
  }, [tab])

  useEffect(() => {
    const stored = localStorage.getItem('tenant_id')
    if (stored) loadIgUserId(stored)
  }, [])

  async function loadIgUserId(_tid?: string) {
    try {
      const res = await api.get('/auth/meta/connections')
      const ig = res.data.find((c: any) => c.provider === 'instagram' && c.status === 'active')
      if (ig) setIgUserId(ig.ig_business_account_id || ig.meta_user_id || '')
    } catch {}
  }

  async function handleFileUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return
    setError(''); setSuccess(''); setUploading(true)
    try {
      const form = new FormData()
      form.append('file', file)
      const res = await api.post('/instagram/upload-media', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      setMediaUrl(res.data.media_url)
      setMediaType(res.data.media_type)
      setUploadedName(file.name)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Erro ao enviar o arquivo.')
    } finally {
      setUploading(false)
    }
  }

  function automationPayload() {
    if (!autoEnabled || !autoKeyword.trim()) return {}
    return {
      automation_keyword: autoKeyword.trim(),
      automation_comment_reply: autoCommentReply.trim() || null,
      automation_dm_message: autoDmMessage.trim() || null,
      automation_link_message: autoLinkMessage.trim() || null,
    }
  }

  function resetForm() {
    setMediaUrl(''); setCaption(''); setHashtags(''); setUploadedName('')
    setAutoEnabled(false); setAutoKeyword(''); setAutoCommentReply('')
    setAutoDmMessage(''); setAutoLinkMessage('')
  }

  async function handlePublish() {
    if (!mediaUrl) { setError('URL da mídia é obrigatória.'); return }
    setError(''); setSuccess(''); setPublishing(true)
    try {
      const res = await api.post('/instagram/publish', {
        ig_user_id: igUserId,
        media_url: mediaUrl,
        media_type: mediaType,
        caption,
        hashtags,
        ...automationPayload(),
      })
      setSuccess(`Publicado com sucesso! ID: ${res.data.media_id}`)
      resetForm()
      loadAutomations()
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Erro ao publicar.')
    } finally { setPublishing(false) }
  }

  async function handleSchedule() {
    if (!mediaUrl) { setError('URL da mídia é obrigatória.'); return }
    if (!scheduledFor) { setError('Data de agendamento é obrigatória.'); return }
    setError(''); setSuccess(''); setPublishing(true)
    try {
      await api.post('/instagram/schedule', {
        ig_user_id: igUserId,
        media_url: mediaUrl,
        media_type: mediaType,
        caption,
        hashtags,
        scheduled_for: new Date(scheduledFor).toISOString(),
        ...automationPayload(),
      })
      setSuccess('Agendado com sucesso!')
      resetForm(); setScheduledFor('')
      loadSchedules()
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Erro ao agendar.')
    } finally { setPublishing(false) }
  }

  async function loadSchedules() {
    setLoadingSchedules(true)
    try {
      const res = await api.get('/instagram/schedule')
      setSchedules(res.data)
    } catch {} finally { setLoadingSchedules(false) }
  }

  async function loadMedia() {
    setLoadingMedia(true)
    try {
      const res = await api.get('/instagram/media', { params: { ig_user_id: igUserId, limit: 20 } })
      setMediaList(res.data)
    } catch {} finally { setLoadingMedia(false) }
  }

  async function loadInsights() {
    setLoadingInsights(true)
    try {
      const res = await api.get('/instagram/insights', { params: { ig_user_id: igUserId } })
      setInsights(res.data)
    } catch {} finally { setLoadingInsights(false) }
  }

  async function loadStories() {
    setLoadingStories(true)
    try {
      const res = await api.get('/instagram/stories-insights', { params: { ig_user_id: igUserId, limit: 10 } })
      setStories(res.data.stories || [])
    } catch {} finally { setLoadingStories(false) }
  }

  async function handlePublishNow(id: string) {
    try {
      await api.post(`/instagram/schedule/${id}/publish-now`)
      setSuccess('Publicado agora!')
      loadSchedules()
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Erro ao publicar.')
    }
  }

  async function handleDeleteSchedule(id: string) {
    if (!confirm('Remover este agendamento?')) return
    try {
      await api.delete(`/instagram/schedule/${id}`)
      loadSchedules()
    } catch {}
  }

  const statusLabel: Record<string, { label: string; color: string }> = {
    scheduled: { label: 'Agendado', color: 'text-blue-400' },
    published: { label: 'Publicado', color: 'text-green-400' },
    failed: { label: 'Falhou', color: 'text-red-400' },
  }

  async function loadAutomations() {
    setLoadingAutomations(true)
    try {
      const res = await api.get<AutomationConfig[]>('/automations')
      setAutomations(res.data)
    } catch {} finally { setLoadingAutomations(false) }
  }

  async function toggleAutomation(a: AutomationConfig) {
    try {
      await api.put(`/automations/${a.id}`, { is_active: !a.is_active })
      loadAutomations()
    } catch { setError('Erro ao atualizar automação.') }
  }

  async function deleteAutomation(id: string) {
    if (!confirm('Remover esta automação?')) return
    try {
      await api.delete(`/automations/${id}`)
      loadAutomations()
    } catch { setError('Erro ao remover automação.') }
  }

  return (
    <div>
      <h2 className="text-2xl font-bold text-[#e2e2e8] mb-2">Instagram</h2>
      <p className="text-[#555] text-sm mb-6">Publique, agende e automatize as respostas do seu Instagram — tudo em uma tela só.</p>

      <div className="flex gap-1 mb-6 bg-[#111118] rounded-lg p-1 border border-white/[0.06] w-fit">
        {(['publish_auto', 'scheduled', 'media'] as Tab[]).map(t => (
          <button key={t} onClick={() => setTab(t)}
            className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${tab === t ? 'bg-indigo-600 text-white' : 'text-[#666] hover:text-[#e2e2e8]'}`}>
            {t === 'publish_auto' ? 'Publicar & Automação' : t === 'scheduled' ? 'Agendados' : 'Mídias & Métricas'}
          </button>
        ))}
      </div>

      {error && <div className="mb-4 bg-red-900/20 border border-red-500/20 text-red-400 text-sm rounded-lg px-4 py-3">{error}</div>}
      {success && <div className="mb-4 bg-green-900/20 border border-green-500/20 text-green-400 text-sm rounded-lg px-4 py-3">{success}</div>}

      {tab === 'publish_auto' && (
        <div className="grid xl:grid-cols-2 gap-6 items-start">
          {/* ---------- Coluna 1: publicar / agendar post (com automação inline do post) ---------- */}
          <div className="bg-[#111118] rounded-xl border border-white/[0.06] p-6">
            <h3 className="text-[#e2e2e8] font-semibold text-sm mb-4 flex items-center gap-2"><Send size={15} className="text-indigo-400" /> Publicar ou agendar post</h3>
            <div className="mb-4">
              <label className="block text-[#666] text-xs font-medium mb-1">Tipo de Mídia</label>
              <select value={mediaType} onChange={e => setMediaType(e.target.value)}
                className="w-full bg-[#0a0a0f] border border-white/[0.08] rounded-lg px-3 py-2 text-sm text-[#e2e2e8]">
                <option value="IMAGE">Imagem</option>
                <option value="VIDEO">Vídeo / Reel</option>
              </select>
            </div>
            <div className="mb-4">
              <label className="block text-[#666] text-xs font-medium mb-1">Mídia</label>
              <label className={`flex items-center justify-center gap-2 w-full border border-dashed rounded-lg px-3 py-4 text-sm cursor-pointer transition-colors ${
                uploading ? 'border-indigo-500/40 text-indigo-300' : 'border-white/[0.12] text-[#888] hover:border-indigo-500/40 hover:text-[#e2e2e8]'
              }`}>
                <input
                  type="file"
                  accept="image/jpeg,image/png,image/webp,video/mp4,video/quicktime"
                  onChange={handleFileUpload}
                  disabled={uploading}
                  className="hidden"
                />
                {uploading
                  ? 'Enviando arquivo…'
                  : uploadedName
                    ? `✓ ${uploadedName} — clique para trocar`
                    : 'Enviar foto ou vídeo do computador'}
              </label>
              {mediaType === 'IMAGE' && mediaUrl && (
                <img src={mediaUrl} alt="" className="mt-2 max-h-40 rounded-lg object-contain" />
              )}
              <p className="text-[#444] text-[11px] mt-2">Ou informe a URL pública de uma mídia já hospedada:</p>
              <input type="url" value={mediaUrl} onChange={e => { setMediaUrl(e.target.value); setUploadedName('') }}
                placeholder="https://exemplo.com/imagem.jpg"
                className="w-full mt-1 bg-[#0a0a0f] border border-white/[0.08] rounded-lg px-3 py-2 text-sm text-[#e2e2e8] placeholder-[#333]" />
            </div>
            <div className="mb-4">
              <label className="block text-[#666] text-xs font-medium mb-1">Legenda</label>
              <textarea value={caption} onChange={e => setCaption(e.target.value)} rows={3}
                placeholder="Escreva a legenda do post..."
                className="w-full bg-[#0a0a0f] border border-white/[0.08] rounded-lg px-3 py-2 text-sm text-[#e2e2e8] placeholder-[#333] resize-none" />
            </div>
            <div className="mb-4">
              <label className="block text-[#666] text-xs font-medium mb-1">Hashtags</label>
              <input type="text" value={hashtags} onChange={e => setHashtags(e.target.value)}
                placeholder="#marketing #instagram #negocios"
                className="w-full bg-[#0a0a0f] border border-white/[0.08] rounded-lg px-3 py-2 text-sm text-[#e2e2e8] placeholder-[#333]" />
            </div>

            {/* Automação de comentário deste post */}
            <div className="mb-4 border border-white/[0.08] rounded-lg overflow-hidden">
              <button type="button" onClick={() => setAutoEnabled(!autoEnabled)}
                className="w-full flex items-center justify-between px-3 py-2.5 bg-white/[0.02] hover:bg-white/[0.04] transition-colors">
                <span className="flex items-center gap-2 text-[13px] text-[#e2e2e8]">
                  <span className={`w-8 h-4 rounded-full relative transition-colors ${autoEnabled ? 'bg-indigo-500' : 'bg-white/[0.1]'}`}>
                    <span className={`absolute top-0.5 w-3 h-3 rounded-full bg-white transition-all ${autoEnabled ? 'left-4' : 'left-0.5'}`} />
                  </span>
                  🤖 Automação de comentário neste post
                </span>
                <span className="text-[#555] text-xs">{autoEnabled ? 'Ativada' : 'Desativada'}</span>
              </button>

              {autoEnabled && (
                <div className="p-3 space-y-3 border-t border-white/[0.06]">
                  <p className="text-[11px] text-[#666]">
                    Quando alguém comentar a palavra-chave <b>neste post</b>, o bot responde e manda um DM.
                    O funil já nasce amarrado à publicação que você está criando agora.
                  </p>
                  <div>
                    <label className="block text-[#666] text-xs font-medium mb-1">Palavra-chave do comentário</label>
                    <input type="text" value={autoKeyword} onChange={e => setAutoKeyword(e.target.value)}
                      placeholder="Ex: QUERO"
                      className="w-full bg-[#0a0a0f] border border-white/[0.08] rounded-lg px-3 py-2 text-sm text-[#e2e2e8] placeholder-[#333]" />
                  </div>
                  <div>
                    <label className="block text-[#666] text-xs font-medium mb-1">Resposta pública no comentário (opcional)</label>
                    <input type="text" value={autoCommentReply} onChange={e => setAutoCommentReply(e.target.value)}
                      placeholder="Te chamei no direto, {{primeiro_nome}}! 📩"
                      className="w-full bg-[#0a0a0f] border border-white/[0.08] rounded-lg px-3 py-2 text-sm text-[#e2e2e8] placeholder-[#333]" />
                  </div>
                  <div>
                    <label className="block text-[#666] text-xs font-medium mb-1">1ª mensagem no direto (o gancho)</label>
                    <textarea value={autoDmMessage} onChange={e => setAutoDmMessage(e.target.value)} rows={2}
                      placeholder="Oi {{primeiro_nome}}! Responde SIM aqui que eu te mando o link 👇"
                      className="w-full bg-[#0a0a0f] border border-white/[0.08] rounded-lg px-3 py-2 text-sm text-[#e2e2e8] placeholder-[#333] resize-none" />
                  </div>
                  <div>
                    <label className="block text-[#666] text-xs font-medium mb-1">2ª mensagem com o link (opcional)</label>
                    <textarea value={autoLinkMessage} onChange={e => setAutoLinkMessage(e.target.value)} rows={2}
                      placeholder="Perfeito, {{primeiro_nome}}! 🎉 Aqui está: seusite.com.br"
                      className="w-full bg-[#0a0a0f] border border-white/[0.08] rounded-lg px-3 py-2 text-sm text-[#e2e2e8] placeholder-[#333] resize-none" />
                    <p className="text-[10px] text-[#555] mt-1">
                      Enviada só depois que a pessoa responder (a Meta não permite link no 1º contato).
                      {' '}<b>Se deixar vazio</b>, o bot dispara a 1ª mensagem uma vez e passa direto para o atendente.
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    <span className="text-[10px] text-[#555]">Variáveis:</span>
                    {['{{primeiro_nome}}', '{{nome}}', '{{usuario}}'].map(v => (
                      <code key={v} className="text-[10px] bg-black/30 text-indigo-200 px-1.5 py-0.5 rounded">{v}</code>
                    ))}
                  </div>
                </div>
              )}
            </div>

            <div className="mb-4">
              <label className="block text-[#666] text-xs font-medium mb-1">Agendar para (opcional · até {MAX_SCHEDULE_DAYS} dias)</label>
              <input type="datetime-local" value={scheduledFor} onChange={e => setScheduledFor(e.target.value)}
                min={minScheduleDate()} max={maxScheduleDate()}
                className="w-full bg-[#0a0a0f] border border-white/[0.08] rounded-lg px-3 py-2 text-sm text-[#e2e2e8]" />
            </div>
            <div className="flex gap-3">
              <button onClick={handlePublish} disabled={publishing}
                className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:bg-indigo-600/50 text-white rounded-lg text-sm font-semibold transition-colors">
                {publishing ? 'Publicando...' : 'Publicar Agora'}
              </button>
              <button onClick={handleSchedule} disabled={publishing || !scheduledFor}
                className="px-4 py-2 bg-[#111118] border border-white/[0.06] hover:bg-white/[0.04] disabled:opacity-50 text-[#666] rounded-lg text-sm font-semibold transition-colors">
                {publishing ? 'Salvando...' : 'Agendar'}
              </button>
            </div>
          </div>

          {/* ---------- Coluna 2: automações cadastradas (ver / pausar / remover) ---------- */}
          <div>
            <h3 className="text-[#e2e2e8] font-semibold text-sm mb-3">Automações cadastradas</h3>
            <p className="text-[#555] text-xs mb-3">Funis criados ao publicar um post (ative a automação ao lado). Aqui você acompanha, pausa ou remove.</p>
            {loadingAutomations ? (
              <div className="text-[#555] text-sm">Carregando...</div>
            ) : automations.length === 0 ? (
              <div className="bg-[#111118] rounded-xl border border-white/[0.06] p-8 text-center">
                <p className="text-[#555] text-sm">Nenhuma automação cadastrada ainda.</p>
              </div>
            ) : (
              <div className="space-y-3">
                {automations.map((a) => (
                  <div key={a.id} className="bg-[#111118] rounded-xl border border-white/[0.06] p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2 flex-wrap mb-1">
                          <span className="text-sm font-semibold text-[#e2e2e8]">"{a.keyword}"</span>
                          <span className="text-xs px-2 py-0.5 rounded bg-white/[0.04] text-[#888]">{triggerLabel[a.trigger_type]}</span>
                          {a.media_id && <span className="text-xs px-2 py-0.5 rounded bg-white/[0.04] text-[#888]">1 post específico</span>}
                          <span className={`text-xs font-medium ${a.is_active ? 'text-green-400' : 'text-[#555]'}`}>
                            {a.is_active ? 'Ativa' : 'Inativa'}
                          </span>
                        </div>
                        <p className="text-[#888] text-xs truncate">{a.auto_reply_message}</p>
                        {a.dm_message && <p className="text-[#666] text-xs truncate mt-1">📩 DM: {a.dm_message}</p>}
                      </div>
                      <div className="flex gap-2 flex-shrink-0">
                        <button onClick={() => toggleAutomation(a)}
                          className="px-2.5 py-1.5 bg-white/[0.04] hover:bg-white/[0.08] text-[#888] rounded-lg text-xs font-medium transition-colors">
                          {a.is_active ? 'Pausar' : 'Ativar'}
                        </button>
                        <button onClick={() => deleteAutomation(a.id)}
                          className="px-2.5 py-1.5 bg-red-900/20 hover:bg-red-900/40 text-red-400 rounded-lg text-xs font-medium transition-colors">
                          Remover
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {tab === 'scheduled' && (
        <div>
          {loadingSchedules ? (
            <div className="text-[#555] text-sm">Carregando agendamentos...</div>
          ) : schedules.length === 0 ? (
            <div className="bg-[#111118] rounded-xl border border-white/[0.06] p-8 text-center">
              <p className="text-[#555] text-sm">Nenhum agendamento encontrado.</p>
            </div>
          ) : (
            <div className="grid gap-4 max-w-2xl">
              {schedules.map(s => (
                <div key={s.id} className="bg-[#111118] rounded-xl border border-white/[0.06] p-4">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-xs font-medium px-2 py-0.5 rounded bg-white/[0.04] text-[#666]">{s.media_type}</span>
                        <span className={`text-xs font-medium ${statusLabel[s.status]?.color || 'text-[#555]'}`}>
                          {statusLabel[s.status]?.label || s.status}
                        </span>
                        {s.media_id_response && <span className="text-xs text-[#444]">ID: {s.media_id_response}</span>}
                      </div>
                      <p className="text-[#e2e2e8] text-sm truncate">{s.caption || 'Sem legenda'}</p>
                      {s.hashtags && <p className="text-[#555] text-xs truncate mt-0.5">{s.hashtags}</p>}
                      <div className="flex gap-4 mt-2 text-xs text-[#444]">
                        <span>Agendado: {new Date(s.scheduled_for).toLocaleString('pt-BR')}</span>
                        {s.published_at && <span>Publicado: {new Date(s.published_at).toLocaleString('pt-BR')}</span>}
                      </div>
                      {s.error_message && <p className="text-red-400 text-xs mt-1">Erro: {s.error_message}</p>}
                    </div>
                    <div className="flex gap-2 flex-shrink-0">
                      {s.status === 'scheduled' && (
                        <button onClick={() => handlePublishNow(s.id)}
                          className="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-medium transition-colors">
                          Publicar Agora
                        </button>
                      )}
                      <button onClick={() => handleDeleteSchedule(s.id)}
                        className="px-3 py-1.5 bg-red-900/20 text-red-400 rounded-lg text-xs font-medium hover:bg-red-900/40 transition-colors">
                        Remover
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {tab === 'media' && (
        <div className="space-y-6">
          {loadingInsights ? (
            <div className="text-[#555] text-sm">Carregando métricas...</div>
          ) : insights && (
            <div className="bg-[#111118] rounded-xl border border-white/[0.06] p-6">
              <h3 className="text-[#e2e2e8] font-semibold text-sm mb-4">Métricas do Instagram (últimos 30 dias)</h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                {[
                  { label: 'Seguidores', value: insights.followers_count },
                  { label: 'Seguindo', value: insights.follows_count },
                  { label: 'Posts', value: insights.media_count },
                  { label: 'Alcance', value: insights.reach },
                  { label: 'Impressões', value: insights.impressions },
                  { label: 'Engajamento', value: `${insights.engagement}%` },
                  { label: 'Visitas ao Perfil', value: insights.profile_views },
                  { label: 'Cliques em Links', value: insights.website_clicks },
                ].map(m => (
                  <div key={m.label} className="bg-white/[0.03] rounded-lg p-3">
                    <p className="text-[#555] text-xs">{m.label}</p>
                    <p className="text-[#e2e2e8] text-lg font-bold">{m.value}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {loadingStories ? (
            <div className="text-[#555] text-sm">Carregando stories...</div>
          ) : stories.length > 0 && (
            <div className="bg-[#111118] rounded-xl border border-white/[0.06] p-6">
              <h3 className="text-[#e2e2e8] font-semibold text-sm mb-4">Stories Recentes</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-[#555] text-xs text-left">
                      <th className="pb-2 pr-4">Tipo</th>
                      <th className="pb-2 pr-4">Alcance</th>
                      <th className="pb-2 pr-4">Impressões</th>
                      <th className="pb-2 pr-4">Saídas</th>
                      <th className="pb-2 pr-4">Respostas</th>
                      <th className="pb-2 pr-4">Toques p/ Frente</th>
                      <th className="pb-2 pr-4">Toques p/ Trás</th>
                      <th className="pb-2">Data</th>
                    </tr>
                  </thead>
                  <tbody>
                    {stories.map((s: any) => (
                      <tr key={s.id} className="border-t border-white/[0.06] text-[#888]">
                        <td className="py-2 pr-4">{s.media_type}</td>
                        <td className="py-2 pr-4">{s.reach}</td>
                        <td className="py-2 pr-4">{s.impressions}</td>
                        <td className="py-2 pr-4">{s.exits}</td>
                        <td className="py-2 pr-4">{s.replies}</td>
                        <td className="py-2 pr-4">{s.taps_forward}</td>
                        <td className="py-2 pr-4">{s.taps_back}</td>
                        <td className="py-2">{s.timestamp ? new Date(s.timestamp as string).toLocaleDateString('pt-BR') : '-'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {loadingMedia ? (
            <div className="text-[#555] text-sm">Carregando mídias...</div>
          ) : mediaList.length === 0 ? (
            <div className="bg-[#111118] rounded-xl border border-white/[0.06] p-8 text-center">
              <p className="text-[#555] text-sm">Nenhuma mídia encontrada.</p>
            </div>
          ) : (
            <div className="bg-[#111118] rounded-xl border border-white/[0.06] p-6">
              <h3 className="text-[#e2e2e8] font-semibold text-sm mb-4">Mídias Recentes</h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                {mediaList.map(m => (
                  <div key={m.id} className="bg-white/[0.03] rounded-lg overflow-hidden">
                    {m.thumbnail_url || m.media_url ? (
                      <img src={m.thumbnail_url || m.media_url || undefined} alt={m.caption || undefined} className="w-full h-40 object-cover" />
                    ) : (
                      <div className="w-full h-40 flex items-center justify-center text-[#444] text-xs">{m.media_type}</div>
                    )}
                    <div className="p-2">
                      <p className="text-[#e2e2e8] text-xs truncate">{m.caption || 'Sem legenda'}</p>
                      <div className="flex gap-3 mt-1 text-[#555] text-xs">
                        <span>❤️ {m.like_count}</span>
                        <span>💬 {m.comments_count}</span>
                      </div>
                      {m.timestamp && <p className="text-[#444] text-xs mt-1">{new Date(m.timestamp).toLocaleDateString('pt-BR')}</p>}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
