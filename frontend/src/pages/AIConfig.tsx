import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Bot, KeyRound, FileText, Trash2, RefreshCw, Upload, Eye,
  CreditCard, AlertTriangle, Save,
} from 'lucide-react'
import api from '../services/api'

interface AIConfigData {
  enabled: boolean
  has_api_key: boolean
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
  tokens_used_month: number
  token_limit_monthly: number
  series: UsagePoint[]
  fallback_rate: number
}

const statusLabel: Record<string, { label: string; color: string }> = {
  processing: { label: 'Processando…', color: 'text-amber-400' },
  ready: { label: 'Pronto', color: 'text-green-400' },
  failed: { label: 'Falhou', color: 'text-red-400' },
}

export default function AIConfig() {
  const navigate = useNavigate()
  const [cfg, setCfg] = useState<AIConfigData | null>(null)
  const [usage, setUsage] = useState<Usage | null>(null)
  const [docs, setDocs] = useState<KnowledgeDoc[]>([])
  const [apiKey, setApiKey] = useState('')
  const [saving, setSaving] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
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
      setError('Erro ao carregar a configuração da IA.')
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
      setSuccess('Configuração salva!')
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Erro ao salvar.')
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
      setSuccess('PDF enviado — indexando em segundo plano.')
      setDocs((await api.get<KnowledgeDoc[]>('/ai/knowledge')).data)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Erro no upload do PDF.')
    } finally { setUploading(false) }
  }

  async function deleteDoc(id: string) {
    if (!confirm('Remover este documento da base de conhecimento?')) return
    try {
      await api.delete(`/ai/knowledge/${id}`)
      setDocs((prev) => prev.filter((d) => d.id !== id))
    } catch { setError('Erro ao remover documento.') }
  }

  async function reindexDoc(id: string) {
    try {
      await api.post(`/ai/knowledge/${id}/reindex`)
      setDocs((await api.get<KnowledgeDoc[]>('/ai/knowledge')).data)
    } catch (err: any) { setError(err.response?.data?.detail || 'Erro ao reindexar.') }
  }

  async function viewChunks(doc: KnowledgeDoc) {
    try {
      const { data } = await api.get(`/ai/knowledge/${doc.id}/chunks`)
      setChunksOf({ doc, chunks: data })
    } catch { setError('Erro ao carregar os chunks.') }
  }

  if (!cfg) return <div className="text-[#555] text-sm">Carregando…</div>

  const pct = Math.min(100, Math.round((cfg.tokens_used_month / Math.max(1, cfg.token_limit_monthly)) * 100))
  const nearLimit = pct >= 80
  const maxDayTokens = Math.max(1, ...(usage?.series.map((p) => p.tokens) ?? [1]))

  return (
    <div>
      <h2 className="text-2xl font-bold text-[#e2e2e8] mb-2 flex items-center gap-2">
        <Bot size={22} className="text-indigo-400" /> IA de Atendimento
      </h2>
      <p className="text-[#555] text-sm mb-6">
        Gemini 2.5 Flash + sua base de conhecimento (RAG). A IA responde no WhatsApp quando o bot da conversa está ativo;
        se ficar indisponível, a conversa vai automaticamente para a fila humana.
      </p>

      {error && <div className="mb-4 bg-red-900/20 border border-red-500/20 text-red-400 text-sm rounded-lg px-4 py-3">{error}</div>}
      {success && <div className="mb-4 bg-green-900/20 border border-green-500/20 text-green-400 text-sm rounded-lg px-4 py-3">{success}</div>}

      <div className="grid xl:grid-cols-2 gap-6 items-start">
        {/* ---------- Coluna 1: configuração ---------- */}
        <div className="space-y-6">
          <div className="bg-[#111118] rounded-xl border border-white/[0.06] p-6 space-y-5">
            {/* Toggle global */}
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-[#e2e2e8] font-semibold text-sm">IA ativa</h3>
                <p className="text-[#555] text-xs mt-0.5">Desligada, as conversas seguem para os bots por palavra-chave e a fila humana.</p>
              </div>
              <button
                onClick={() => save({ enabled: !cfg.enabled })}
                disabled={saving}
                className={`w-12 h-6 rounded-full relative transition-colors shrink-0 ${cfg.enabled ? 'bg-indigo-500' : 'bg-white/[0.1]'}`}
              >
                <span className={`absolute top-0.5 w-5 h-5 rounded-full bg-white transition-all ${cfg.enabled ? 'left-6' : 'left-0.5'}`} />
              </button>
            </div>

            {/* API key */}
            <div>
              <label className="block text-xs font-medium text-[#666] mb-1 flex items-center gap-1.5">
                <KeyRound size={12} /> API key da Gemini {cfg.has_api_key && <span className="text-green-400">• configurada</span>}
              </label>
              <div className="flex gap-2">
                <input
                  type="password"
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder={cfg.has_api_key ? '•••••••••••• (só preencha para trocar)' : 'Cole a API key do Google AI Studio'}
                  className="flex-1 px-3 py-2 bg-[#0a0a0f] border border-white/[0.08] text-[#e2e2e8] rounded-lg text-sm focus:border-indigo-500 focus:outline-none placeholder-[#333]"
                />
                <button
                  onClick={() => apiKey.trim() && save({ gemini_api_key: apiKey.trim() })}
                  disabled={saving || !apiKey.trim()}
                  className="px-3 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 text-white rounded-lg text-sm font-medium"
                >
                  Salvar
                </button>
              </div>
            </div>

            {/* System prompt */}
            <div>
              <label className="block text-xs font-medium text-[#666] mb-1">
                System prompt (regras fixas — injetado em toda resposta)
              </label>
              <textarea
                value={cfg.system_prompt}
                onChange={(e) => setCfg({ ...cfg, system_prompt: e.target.value })}
                rows={6}
                className="w-full px-3 py-2 bg-[#0a0a0f] border border-white/[0.08] text-[#e2e2e8] rounded-lg text-sm resize-none focus:border-indigo-500 focus:outline-none"
              />
            </div>

            <div className="grid grid-cols-3 gap-3">
              <div>
                <label className="block text-xs font-medium text-[#666] mb-1">Temperatura</label>
                <input
                  type="number" step="0.1" min="0" max="2"
                  value={cfg.temperature}
                  onChange={(e) => setCfg({ ...cfg, temperature: parseFloat(e.target.value) || 0 })}
                  className="w-full px-3 py-2 bg-[#0a0a0f] border border-white/[0.08] text-[#e2e2e8] rounded-lg text-sm focus:border-indigo-500 focus:outline-none"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-[#666] mb-1">Top-K do RAG</label>
                <input
                  type="number" min="1" max="10"
                  value={cfg.rag_top_k}
                  onChange={(e) => setCfg({ ...cfg, rag_top_k: parseInt(e.target.value) || 4 })}
                  className="w-full px-3 py-2 bg-[#0a0a0f] border border-white/[0.08] text-[#e2e2e8] rounded-lg text-sm focus:border-indigo-500 focus:outline-none"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-[#666] mb-1" title="Anti-loop: acima disso a IA ignora o remetente por 1 min">Msgs/min por contato</label>
                <input
                  type="number" min="1" max="200"
                  value={cfg.sender_rate_limit_per_min}
                  onChange={(e) => setCfg({ ...cfg, sender_rate_limit_per_min: parseInt(e.target.value) || 20 })}
                  className="w-full px-3 py-2 bg-[#0a0a0f] border border-white/[0.08] text-[#e2e2e8] rounded-lg text-sm focus:border-indigo-500 focus:outline-none"
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
              <Save size={15} /> {saving ? 'Salvando…' : 'Salvar configuração'}
            </button>
          </div>

          {/* Uso de tokens */}
          <div className="bg-[#111118] rounded-xl border border-white/[0.06] p-6">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-[#e2e2e8] font-semibold text-sm">Uso de tokens (mês)</h3>
              <button
                onClick={() => navigate('/pricing')}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-300 rounded-lg text-xs font-semibold"
              >
                <CreditCard size={13} /> Comprar mais créditos
              </button>
            </div>
            <div className="flex items-baseline gap-2 mb-2">
              <span className="text-xl font-bold text-white">{cfg.tokens_used_month.toLocaleString()}</span>
              <span className="text-[#555] text-sm">/ {cfg.token_limit_monthly.toLocaleString()} tokens</span>
              {nearLimit && (
                <span className="flex items-center gap-1 text-amber-400 text-xs font-medium">
                  <AlertTriangle size={12} /> {pct}% da cota
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
                <p className="text-[#555] text-xs mb-2">
                  Últimos 14 dias · taxa de fallback: <b className={usage.fallback_rate > 10 ? 'text-amber-400' : 'text-[#8a8a9e]'}>{usage.fallback_rate}%</b>
                </p>
                <div className="flex items-end gap-1 h-16">
                  {usage.series.map((p) => (
                    <div
                      key={p.day}
                      title={`${p.day}: ${p.tokens.toLocaleString()} tokens · ${p.messages} respostas · ${p.fallbacks} fallbacks`}
                      className="flex-1 bg-indigo-500/60 hover:bg-indigo-400 rounded-t min-w-[4px] transition-colors"
                      style={{ height: `${Math.max(3, (p.tokens / maxDayTokens) * 100)}%` }}
                    />
                  ))}
                </div>
              </>
            )}
          </div>
        </div>

        {/* ---------- Coluna 2: base de conhecimento ---------- */}
        <div className="bg-[#111118] rounded-xl border border-white/[0.06] p-6">
          <h3 className="text-[#e2e2e8] font-semibold text-sm mb-1 flex items-center gap-2">
            <FileText size={15} className="text-emerald-400" /> Base de conhecimento (RAG)
          </h3>
          <p className="text-[#555] text-xs mb-4">
            Envie PDFs (catálogo, FAQ, políticas). O conteúdo vira contexto e a IA responde com as informações do seu negócio.
          </p>

          <label className={`flex items-center justify-center gap-2 w-full border border-dashed rounded-lg px-3 py-6 text-sm cursor-pointer transition-colors mb-4 ${
            uploading ? 'border-indigo-500/40 text-indigo-300' : 'border-white/[0.12] text-[#888] hover:border-indigo-500/40 hover:text-[#e2e2e8]'
          }`}>
            <input type="file" accept="application/pdf" onChange={handleUpload} disabled={uploading} className="hidden" />
            <Upload size={16} />
            {uploading ? 'Enviando…' : 'Enviar PDF (máx. 20 MB)'}
          </label>

          {docs.length === 0 ? (
            <p className="text-[#555] text-sm text-center py-4">Nenhum documento indexado ainda.</p>
          ) : (
            <div className="space-y-2.5">
              {docs.map((d) => (
                <div key={d.id} className="bg-[#0a0a0f] border border-white/[0.05] rounded-lg p-3 flex items-center gap-3">
                  <FileText size={16} className="text-[#555] shrink-0" />
                  <div className="min-w-0 flex-1">
                    <p className="text-[#e2e2e8] text-sm truncate">{d.filename}</p>
                    <p className="text-xs mt-0.5">
                      <span className={statusLabel[d.status]?.color || 'text-[#555]'}>{statusLabel[d.status]?.label || d.status}</span>
                      {d.status === 'ready' && <span className="text-[#555]"> · {d.chunk_count} chunks</span>}
                      {d.error && <span className="text-red-400"> · {d.error}</span>}
                    </p>
                  </div>
                  <div className="flex gap-1.5 shrink-0">
                    {d.status === 'ready' && (
                      <button onClick={() => viewChunks(d)} title="Ver chunks"
                        className="w-8 h-8 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] text-[#888] flex items-center justify-center">
                        <Eye size={14} />
                      </button>
                    )}
                    <button onClick={() => reindexDoc(d.id)} title="Reindexar"
                      className="w-8 h-8 rounded-lg bg-white/[0.04] hover:bg-indigo-500/20 text-[#888] hover:text-indigo-400 flex items-center justify-center">
                      <RefreshCw size={14} />
                    </button>
                    <button onClick={() => deleteDoc(d.id)} title="Remover"
                      className="w-8 h-8 rounded-lg bg-white/[0.04] hover:bg-red-500/20 text-[#888] hover:text-red-400 flex items-center justify-center">
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
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm px-4 py-8" onClick={() => setChunksOf(null)}>
          <div className="bg-[#111118] border border-white/[0.08] rounded-2xl p-6 w-full max-w-2xl max-h-[80vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-base font-semibold text-white mb-1">{chunksOf.doc.filename}</h3>
            <p className="text-[#555] text-xs mb-4">{chunksOf.chunks.length} chunks indexados</p>
            <div className="space-y-2">
              {chunksOf.chunks.map((c) => (
                <div key={c.index} className="bg-[#0a0a0f] border border-white/[0.05] rounded-lg p-3">
                  <p className="text-[10px] uppercase tracking-wider text-[#444] mb-1">Chunk {c.index + 1}</p>
                  <p className="text-[#c0c0d0] text-xs leading-relaxed">{c.content.slice(0, 400)}{c.content.length > 400 ? '…' : ''}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
