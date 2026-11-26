import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Bot, KeyRound, FileText, Trash2, RefreshCw, Upload, Eye,
  CreditCard, AlertTriangle, Save,
} from 'lucide-react'
import api, { apiError } from '../services/api'
import { useI18n } from '../i18n'
import AIPackDialog from '../components/AIPackDialog'
import HelpLink from '../components/HelpLink'

interface AIConfigData {
  enabled: boolean
  has_api_key: boolean
  platform_available: boolean
  use_own_key: boolean
  system_prompt: string
  temperature: number
  rag_top_k: number
  sender_rate_limit_per_min: number
  token_limit_monthly: number
  tokens_used_month: number
}

interface KnowledgeDoc {
  id: string
  filename: string
  status: string
  chunk_count: number
  error: string | null
  created_at: string
}

interface UsagePoint { day: string; tokens: number; messages: number; fallbacks: number }
interface Usage {
  own_key: boolean
  included_tokens: number | null
  extra_tokens: number
  platform_used_tokens: number
  conversations_included: number | null
  conversations_left: number | null
  tokens_per_conversation: number
  tokens_used_month: number
  token_limit_monthly: number
  series: UsagePoint[]
  fallback_rate: number
}

export default function AIConfig() {
  const { t, locale } = useI18n()
  const statusLabel: Record<string, { label: string; color: string }> = {
    processing: { label: t('Processando…', 'Processing…'), color: 'text-amber-400' },
    ready: { label: t('Pronto', 'Ready'), color: 'text-green-400' },
    failed: { label: t('Falhou', 'Failed'), color: 'text-red-400' },
  }
  const navigate = useNavigate()
  const [cfg, setCfg] = useState<AIConfigData | null>(null)
  const [usage, setUsage] = useState<Usage | null>(null)
  const [docs, setDocs] = useState<KnowledgeDoc[]>([])
  const [apiKey, setApiKey] = useState('')
  const [saving, setSaving] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [showPack, setShowPack] = useState(false)
  const [chunksOf, setChunksOf] = useState<{ doc: KnowledgeDoc; chunks: { index: number; content: string }[] } | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const load = useCallback(async () => {
    try {
      const [c, u, d] = await Promise.all([
        api.get<AIConfigData>('/ai/config'),
        api.get<Usage>('/ai/usage'),
        api.get<KnowledgeDoc[]>('/ai/knowledge'),
      ])
      setCfg(c.data); setUsage(u.data); setDocs(d.data)
    } catch {
      setError(t('Erro ao carregar a configuração da IA.', 'Failed to load the AI settings.'))
    }
  }, [])

  useEffect(() => { load() }, [load])

  // Enquanto houver doc "processing", faz polling do status
  useEffect(() => {
    const hasProcessing = docs.some((d) => d.status === 'processing')
    if (hasProcessing && !pollRef.current) {
      pollRef.current = setInterval(async () => {
        try { setDocs((await api.get<KnowledgeDoc[]>('/ai/knowledge')).data) } catch {}
      }, 4000)
    }
    if (!hasProcessing && pollRef.current) {
      clearInterval(pollRef.current); pollRef.current = null
    }
    return () => { if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null } }
  }, [docs])

  async function save(partial: Partial<AIConfigData> & { gemini_api_key?: string }) {
    setSaving(true); setError(''); setSuccess('')
    try {
      const { data } = await api.put<AIConfigData>('/ai/config', partial)
      setCfg(data)
      setApiKey('')
      setSuccess(t('Configuração salva!', 'Settings saved!'))
    } catch (err: any) {
      setError(apiError(err, t('Erro ao salvar.', 'Failed to save.')))
    } finally { setSaving(false) }
  }

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return
    setUploading(true); setError(''); setSuccess('')
    try {
      const form = new FormData()
      form.append('file', file)
      await api.post('/ai/knowledge/upload', form, { headers: { 'Content-Type': 'multipart/form-data' } })
      setSuccess(t('PDF enviado — indexando em segundo plano.', 'PDF uploaded — indexing in the background.'))
      setDocs((await api.get<KnowledgeDoc[]>('/ai/knowledge')).data)
    } catch (err: any) {
      setError(apiError(err, t('Erro no upload do PDF.', 'PDF upload failed.')))
    } finally { setUploading(false) }
  }

  async function deleteDoc(id: string) {
    if (!confirm(t('Remover este documento da base de conhecimento?', 'Remove this document from the knowledge base?'))) return
    try {
      await api.delete(`/ai/knowledge/${id}`)
      setDocs((prev) => prev.filter((d) => d.id !== id))
    } catch { setError(t('Erro ao remover documento.', 'Failed to remove document.')) }
  }

  async function reindexDoc(id: string) {
    try {
      await api.post(`/ai/knowledge/${id}/reindex`)
      setDocs((await api.get<KnowledgeDoc[]>('/ai/knowledge')).data)
    } catch (err: any) { setError(apiError(err, t('Erro ao reindexar.', 'Failed to reindex.'))) }
  }

  async function viewChunks(doc: KnowledgeDoc) {
    try {
      const { data } = await api.get(`/ai/knowledge/${doc.id}/chunks`)
      setChunksOf({ doc, chunks: data })
    } catch { setError(t('Erro ao carregar os trechos.', 'Failed to load the chunks.')) }
  }

  if (!cfg) return <div className="text-ink-4 text-sm">{error || t('Carregando…', 'Loading…')}</div>

  const pct = Math.min(100, Math.round((cfg.tokens_used_month / Math.max(1, cfg.token_limit_monthly)) * 100))
  const nearLimit = pct >= 80
  const maxDayTokens = Math.max(1, ...(usage?.series.map((p) => p.tokens) ?? [1]))

  return (
    <div>
      <h2 className="text-2xl font-bold text-ink mb-2 flex items-center gap-2">
        <Bot size={22} className="text-indigo-400" /> {t('Assistente de IA', 'AI Assistant')}
      </h2>
      <p className="text-ink-4 text-sm mb-3">
        {t(
          'Gemini 2.5 Flash + sua base de conhecimento (RAG). A IA responde no WhatsApp quando o bot da conversa está ativo; se ficar indisponível, a conversa vai automaticamente para a fila humana.',
          'Gemini 2.5 Flash + your knowledge base (RAG). The AI replies on WhatsApp when the conversation bot is on; if it is unavailable, the conversation automatically goes to the human queue.',
        )}
      </p>
      <HelpLink section="ia" className="mb-3" />
      <div className="mb-6 bg-violet-900/10 border border-violet-500/20 rounded-lg px-4 py-3 text-[12px] text-violet-200/80 max-w-3xl">
        {t(
          'Regras fixas da plataforma (aplicadas a todo prompt): o assistente responde só sobre o seu negócio, se identifica como automatizado quando perguntado, transfere para um humano quando o cliente pedir e nunca solicita senhas ou dados de cartão. Quem envia SAIR/STOP não recebe resposta automática.',
          'Fixed platform rules (applied to every prompt): the assistant only answers about your business, identifies itself as automated when asked, hands off to a human when the customer asks, and never requests passwords or card data. Contacts who send STOP get no automated reply.',
        )}
      </div>

      {error && <div className="mb-4 bg-red-900/20 border border-red-500/20 text-red-400 text-sm rounded-lg px-4 py-3">{error}</div>}
      {success && <div className="mb-4 bg-green-900/20 border border-green-500/20 text-green-400 text-sm rounded-lg px-4 py-3">{success}</div>}

      <div className="grid xl:grid-cols-2 gap-6 items-start">
        {/* ---------- Coluna 1: configuração ---------- */}
        <div className="space-y-6">
          <div className="bg-card rounded-xl border border-white/[0.06] p-6 space-y-5">
            {/* Toggle global */}
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-ink font-semibold text-sm">{t('IA ativa', 'AI enabled')}</h3>
                <p className="text-ink-4 text-xs mt-0.5">{t('Desligada, as conversas seguem para os bots por palavra-chave e a fila humana.', 'When off, conversations go to keyword bots and the human queue.')}</p>
              </div>
              <button
                onClick={() => save({ enabled: !cfg.enabled })}
                disabled={saving}
                className={`w-12 h-6 rounded-full relative transition-colors shrink-0 ${cfg.enabled ? 'bg-indigo-500' : 'bg-white/[0.1]'}`}
              >
                <span className={`absolute top-0.5 w-5 h-5 rounded-full bg-white transition-all ${cfg.enabled ? 'left-6' : 'left-0.5'}`} />
              </button>
            </div>

            {/* Qual IA usar */}
            <div>
              <p className="text-xs font-medium text-ink-4 mb-2">{t('Qual IA usar', 'Which AI to use')}</p>
              <div className="grid sm:grid-cols-2 gap-2">
                <button onClick={() => cfg.use_own_key && save({ use_own_key: false })} disabled={saving || !cfg.platform_available}
                  className={`text-left p-3 rounded-lg border text-xs disabled:opacity-40 ${!cfg.use_own_key ? 'border-indigo-500/60 bg-indigo-600/10' : 'border-white/[0.08]'}`}>
                  <span className="block text-sm font-semibold text-ink">{t('IA do Prospecta', 'Prospecta AI')}</span>
                  <span className="text-ink-4">{cfg.platform_available ? t('Já incluída no plano. Não precisa configurar nada.', 'Included in your plan. Nothing to set up.') : t('Ainda não disponível.', 'Not available yet.')}</span>
                </button>
                <button onClick={() => !cfg.use_own_key && cfg.has_api_key ? save({ use_own_key: true }) : undefined} disabled={saving}
                  className={`text-left p-3 rounded-lg border text-xs ${cfg.use_own_key ? 'border-indigo-500/60 bg-indigo-600/10' : 'border-white/[0.08]'}`}>
                  <span className="block text-sm font-semibold text-ink">{t('Minha chave da Gemini', 'My own Gemini key')}</span>
                  <span className="text-ink-4">{t('Sem limite do plano; o Google cobra direto de você.', 'No plan limit; Google bills you directly.')}</span>
                </button>
              </div>
            </div>

            {/* API key */}
            {(cfg.use_own_key || !cfg.platform_available || cfg.has_api_key) && <div>
              <label className="block text-xs font-medium text-ink-4 mb-1 flex items-center gap-1.5">
                <KeyRound size={12} /> {t('API key da Gemini', 'Gemini API key')} {cfg.has_api_key && <span className="text-green-400">• {t('configurada', 'configured')}</span>}
              </label>
              <div className="flex gap-2">
                <input
                  type="password"
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder={cfg.has_api_key ? t('•••••••••••• (só preencha para trocar)', '•••••••••••• (fill in only to change)') : t('Cole a API key do Google AI Studio', 'Paste your Google AI Studio API key')}
                  className="flex-1 px-3 py-2 bg-field border border-white/[0.08] text-ink rounded-lg text-sm focus:border-indigo-500 focus:outline-none placeholder-ink-5"
                />
                <button
                  onClick={() => apiKey.trim() && save({ gemini_api_key: apiKey.trim() })}
                  disabled={saving || !apiKey.trim()}
                  className="px-3 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 text-white rounded-lg text-sm font-medium"
                >
                  {t('Salvar', 'Save')}
                </button>
              </div>
            </div>}

            {/* System prompt */}
            <div>
              <label className="block text-xs font-medium text-ink-4 mb-1">
                {t('Instruções do assistente (system prompt)', 'Assistant instructions (system prompt)')}
              </label>
              <textarea
                value={cfg.system_prompt}
                onChange={(e) => setCfg({ ...cfg, system_prompt: e.target.value })}
                rows={6}
                className="w-full px-3 py-2 bg-field border border-white/[0.08] text-ink rounded-lg text-sm resize-none focus:border-indigo-500 focus:outline-none"
              />
            </div>

            <div className="grid grid-cols-3 gap-3">
              <div>
                <label className="block text-xs font-medium text-ink-4 mb-1">{t('Temperatura', 'Temperature')}</label>
                <input
                  type="number" step="0.1" min="0" max="2"
                  value={cfg.temperature}
                  onChange={(e) => setCfg({ ...cfg, temperature: parseFloat(e.target.value) || 0 })}
                  className="w-full px-3 py-2 bg-field border border-white/[0.08] text-ink rounded-lg text-sm focus:border-indigo-500 focus:outline-none"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-ink-4 mb-1">{t('Top-K do RAG', 'RAG Top-K')}</label>
                <input
                  type="number" min="1" max="10"
                  value={cfg.rag_top_k}
                  onChange={(e) => setCfg({ ...cfg, rag_top_k: parseInt(e.target.value) || 4 })}
                  className="w-full px-3 py-2 bg-field border border-white/[0.08] text-ink rounded-lg text-sm focus:border-indigo-500 focus:outline-none"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-ink-4 mb-1" title={t('Anti-loop: acima disso a IA ignora o remetente por 1 min', 'Anti-loop: above this the AI ignores the sender for 1 min')}>{t('Msgs/min por contato', 'Msgs/min per contact')}</label>
                <input
                  type="number" min="1" max="200"
                  value={cfg.sender_rate_limit_per_min}
                  onChange={(e) => setCfg({ ...cfg, sender_rate_limit_per_min: parseInt(e.target.value) || 20 })}
                  className="w-full px-3 py-2 bg-field border border-white/[0.08] text-ink rounded-lg text-sm focus:border-indigo-500 focus:outline-none"
                />
              </div>
            </div>

            <button
              onClick={() => save({
                system_prompt: cfg.system_prompt,
                temperature: cfg.temperature,
                rag_top_k: cfg.rag_top_k,
                sender_rate_limit_per_min: cfg.sender_rate_limit_per_min,
              })}
              disabled={saving}
              className="w-full py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white font-semibold rounded-lg text-sm flex items-center justify-center gap-2"
            >
              <Save size={15} /> {saving ? t('Salvando…', 'Saving…') : t('Salvar configuração', 'Save settings')}
            </button>
          </div>

          {/* Uso: franquia de atendimentos (IA do Prospecta) */}
          {usage && !usage.own_key && (() => {
            const per = Math.max(1, usage.tokens_per_conversation)
            const used = Math.floor(usage.platform_used_tokens / per)
            const total = usage.conversations_included
            const p = total ? Math.min(100, Math.round((used / Math.max(1, total)) * 100)) : 0
            return (
              <div className="bg-card rounded-xl border border-white/[0.06] p-6">
                <div className="flex items-center justify-between mb-3 gap-2 flex-wrap">
                  <h3 className="text-ink font-semibold text-sm">{t('Atendimentos com IA neste mês', 'AI conversations this month')}</h3>
                  <button onClick={() => setShowPack(true)}
                    className="flex items-center gap-1.5 px-3 py-1.5 bg-violet-600/20 hover:bg-violet-600/30 text-violet-200 rounded-lg text-xs font-semibold">
                    <CreditCard size={13} /> {t('Comprar mais', 'Buy more')}
                  </button>
                </div>
                <div className="flex items-baseline gap-2 mb-2">
                  <span className="text-xl font-bold text-white">{used.toLocaleString(locale)}</span>
                  <span className="text-ink-4 text-sm">{total === null ? t('· sem limite', '· no limit') : `/ ${total.toLocaleString(locale)}`}</span>
                  {p >= 80 && <span className="flex items-center gap-1 text-amber-400 text-xs font-medium"><AlertTriangle size={12} /> {p}%</span>}
                </div>
                {total !== null && (
                  <div className="w-full h-2 rounded-full bg-white/[0.05] overflow-hidden mb-2">
                    <div className={`h-full rounded-full ${p >= 80 ? 'bg-amber-500' : 'bg-violet-500'}`} style={{ width: `${p}%` }} />
                  </div>
                )}
                <p className="text-[11px] text-ink-5">
                  {t(`Cada atendimento conta em média ${per.toLocaleString(locale)} tokens.`, `Each conversation counts about ${per.toLocaleString(locale)} tokens on average.`)}
                  {usage.extra_tokens > 0 && ' ' + t(`Inclui ${Math.floor(usage.extra_tokens / per).toLocaleString(locale)} de pacotes extras.`, `Includes ${Math.floor(usage.extra_tokens / per).toLocaleString(locale)} from extra packs.`)}
                  {' '}{t('Ao acabar, as conversas vão para a fila humana.', 'When it runs out, conversations go to the human queue.')}
                </p>
              </div>
            )
          })()}

          {/* Uso de tokens (chave própria) */}
          {(!usage || usage.own_key) && <div className="bg-card rounded-xl border border-white/[0.06] p-6">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-ink font-semibold text-sm">{t('Uso de tokens (mês)', 'Token usage (month)')}</h3>
              <button
                onClick={() => navigate('/pricing')}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-300 rounded-lg text-xs font-semibold"
              >
                <CreditCard size={13} /> {t('Ver planos', 'See plans')}
              </button>
            </div>
            <div className="flex items-baseline gap-2 mb-2">
              <span className="text-xl font-bold text-white">{cfg.tokens_used_month.toLocaleString()}</span>
              <span className="text-ink-4 text-sm">/ {cfg.token_limit_monthly.toLocaleString()} tokens</span>
              {nearLimit && (
                <span className="flex items-center gap-1 text-amber-400 text-xs font-medium">
                  <AlertTriangle size={12} /> {pct}% {t('da cota', 'of quota')}
                </span>
              )}
            </div>
            <div className="w-full h-2 rounded-full bg-white/[0.05] overflow-hidden mb-5">
              <div
                className={`h-full rounded-full transition-all ${nearLimit ? 'bg-amber-500' : 'bg-indigo-500'}`}
                style={{ width: `${pct}%` }}
              />
            </div>

            {usage && (
              <>
                <p className="text-ink-4 text-xs mb-2">
                  {t('Últimos 14 dias · taxa de transferência para humano', 'Last 14 days · human handoff rate')}: <b className={usage.fallback_rate > 10 ? 'text-amber-400' : 'text-ink-3'}>{usage.fallback_rate}%</b>
                </p>
                <div className="flex items-end gap-1 h-16">
                  {usage.series.map((p) => (
                    <div
                      key={p.day}
                      title={`${p.day}: ${p.tokens.toLocaleString()} tokens · ${p.messages} ${t('respostas', 'replies')} · ${p.fallbacks} ${t('transferências', 'handoffs')}`}
                      className="flex-1 bg-indigo-500/60 hover:bg-indigo-400 rounded-t min-w-[4px] transition-colors"
                      style={{ height: `${Math.max(3, (p.tokens / maxDayTokens) * 100)}%` }}
                    />
                  ))}
                </div>
              </>
            )}
          </div>}
        </div>

        {/* ---------- Coluna 2: base de conhecimento ---------- */}
        <div className="bg-card rounded-xl border border-white/[0.06] p-6">
          <h3 className="text-ink font-semibold text-sm mb-1 flex items-center gap-2">
            <FileText size={15} className="text-emerald-400" /> {t('Base de conhecimento (RAG)', 'Knowledge base (RAG)')}
          </h3>
          <p className="text-ink-4 text-xs mb-4">
            {t('Envie PDFs (catálogo, FAQ, políticas). O conteúdo vira contexto e a IA responde com as informações do seu negócio.', 'Upload PDFs (catalog, FAQ, policies). The content becomes context and the AI answers with your business information.')}
          </p>

          <label className={`flex items-center justify-center gap-2 w-full border border-dashed rounded-lg px-3 py-6 text-sm cursor-pointer transition-colors mb-4 ${
            uploading ? 'border-indigo-500/40 text-indigo-300' : 'border-white/[0.12] text-ink-3 hover:border-indigo-500/40 hover:text-ink'
          }`}>
            <input type="file" accept="application/pdf" onChange={handleUpload} disabled={uploading} className="hidden" />
            <Upload size={16} />
            {uploading ? t('Enviando…', 'Uploading…') : t('Enviar PDF (máx. 20 MB)', 'Upload PDF (max 20 MB)')}
          </label>

          {docs.length === 0 ? (
            <p className="text-ink-4 text-sm text-center py-4">{t('Nenhum documento indexado ainda.', 'No documents indexed yet.')}</p>
          ) : (
            <div className="space-y-2.5">
              {docs.map((d) => (
                <div key={d.id} className="bg-field border border-white/[0.05] rounded-lg p-3 flex items-center gap-3">
                  <FileText size={16} className="text-ink-4 shrink-0" />
                  <div className="min-w-0 flex-1">
                    <p className="text-ink text-sm truncate">{d.filename}</p>
                    <p className="text-xs mt-0.5">
                      <span className={statusLabel[d.status]?.color || 'text-ink-4'}>{statusLabel[d.status]?.label || d.status}</span>
                      {d.status === 'ready' && <span className="text-ink-4"> · {d.chunk_count} {t('trechos', 'chunks')}</span>}
                      {d.error && <span className="text-red-400"> · {d.error}</span>}
                    </p>
                  </div>
                  <div className="flex gap-1.5 shrink-0">
                    {d.status === 'ready' && (
                      <button onClick={() => viewChunks(d)} title={t('Ver trechos', 'View chunks')}
                        className="w-8 h-8 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] text-ink-3 flex items-center justify-center">
                        <Eye size={14} />
                      </button>
                    )}
                    <button onClick={() => reindexDoc(d.id)} title={t('Reindexar', 'Reindex')}
                      className="w-8 h-8 rounded-lg bg-white/[0.04] hover:bg-indigo-500/20 text-ink-3 hover:text-indigo-400 flex items-center justify-center">
                      <RefreshCw size={14} />
                    </button>
                    <button onClick={() => deleteDoc(d.id)} title={t('Remover', 'Remove')}
                      className="w-8 h-8 rounded-lg bg-white/[0.04] hover:bg-red-500/20 text-ink-3 hover:text-red-400 flex items-center justify-center">
                      <Trash2 size={14} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Modal: chunks do documento */}
      {chunksOf && (
        <div className="fixed inset-0 z-50 flex items-center justify-center max-lg:[align-items:safe_center] max-lg:overflow-y-auto max-lg:py-4 bg-black/70 backdrop-blur-sm px-4 py-8" onClick={() => setChunksOf(null)}>
          <div className="bg-card border border-white/[0.08] rounded-2xl p-6 w-full max-w-2xl max-h-[80vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-base font-semibold text-white mb-1">{chunksOf.doc.filename}</h3>
            <p className="text-ink-4 text-xs mb-4">{chunksOf.chunks.length} {t('trechos indexados', 'indexed chunks')}</p>
            <div className="space-y-2">
              {chunksOf.chunks.map((c) => (
                <div key={c.index} className="bg-field border border-white/[0.05] rounded-lg p-3">
                  <p className="text-[10px] uppercase tracking-wider text-ink-5 mb-1">{t('Trecho', 'Chunk')} {c.index + 1}</p>
                  <p className="text-ink-2 text-xs leading-relaxed">{c.content.slice(0, 400)}{c.content.length > 400 ? '…' : ''}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
      {showPack && <AIPackDialog onClose={() => setShowPack(false)} onPaid={() => { setShowPack(false); load() }} />}
    </div>
  )
}
