import { useState, useEffect } from 'react'
import { FileText, Plus, RefreshCw, Trash2, X, Link2, AlertCircle, Send, Users } from 'lucide-react'
import api from '../services/api'

interface Template {
  name: string
  language: string
  status?: string
  category?: string
  components?: any[]
}

interface CostData {
  total: number
  breakdown: Record<string, { count: number; unit_cost: number; subtotal: number }>
}

// Categorias da Meta + custo estimado por conversa (configurável — a Meta muda os valores).
const CATEGORIES: Record<string, { label: string; cost: number; badge: string }> = {
  UTILITY: { label: 'Utilidade', cost: 0.12, badge: 'text-blue-400 bg-blue-900/20 border-blue-500/20' },
  MARKETING: { label: 'Marketing', cost: 0.33, badge: 'text-purple-400 bg-purple-900/20 border-purple-500/20' },
  AUTHENTICATION: { label: 'Autenticação', cost: 0.15, badge: 'text-amber-400 bg-amber-900/20 border-amber-500/20' },
}

const STATUS_BADGE: Record<string, string> = {
  APPROVED: 'text-green-400 bg-green-900/20 border-green-500/20',
  PENDING: 'text-amber-400 bg-amber-900/20 border-amber-500/20',
  REJECTED: 'text-red-400 bg-red-900/20 border-red-500/20',
}

const brl = (v: number) => `R$ ${v.toFixed(2).replace('.', ',')}`

export default function Templates() {
  const [templates, setTemplates] = useState<Template[]>([])
  const [loading, setLoading] = useState(true)
  const [noConnection, setNoConnection] = useState(false)
  const [syncing, setSyncing] = useState(false)
  const [costs, setCosts] = useState<CostData | null>(null)

  const [showCreate, setShowCreate] = useState(false)
  const [name, setName] = useState('')
  const [category, setCategory] = useState('UTILITY')
  const [headerText, setHeaderText] = useState('')
  const [bodyText, setBodyText] = useState('')
  const [footerText, setFooterText] = useState('')
  const [creating, setCreating] = useState(false)
  const [formError, setFormError] = useState('')
  const [formOk, setFormOk] = useState('')

  // Disparo em massa
  const [bcTpl, setBcTpl] = useState<Template | null>(null)
  const [bcVars, setBcVars] = useState<string[]>([])
  const [audience, setAudience] = useState<number | null>(null)
  const [broadcasting, setBroadcasting] = useState(false)
  const [bcResult, setBcResult] = useState('')

  useEffect(() => { load() }, [])

  async function load() {
    setLoading(true)
    setNoConnection(false)
    try {
      const { data } = await api.get('/whatsapp/templates')
      setTemplates(Array.isArray(data) ? data : [])
      try {
        const c = await api.get('/whatsapp/costs')
        setCosts(c.data)
      } catch { setCosts(null) }
    } catch (err: any) {
      if (err.response?.status === 404) setNoConnection(true)
    } finally {
      setLoading(false)
    }
  }

  async function sync() {
    setSyncing(true)
    try {
      await api.post('/whatsapp/templates/sync')
      await load()
    } catch { /* ignore */ } finally { setSyncing(false) }
  }

  function insertVar() {
    const nums = [...bodyText.matchAll(/\{\{(\d+)\}\}/g)].map((m) => parseInt(m[1]))
    const next = nums.length ? Math.max(...nums) + 1 : 1
    setBodyText((b) => `${b}{{${next}}}`)
  }

  async function handleCreate(e: React.SyntheticEvent) {
    e.preventDefault()
    setFormError('')
    setFormOk('')
    if (!/^[a-z0-9_]+$/.test(name)) {
      setFormError('Nome inválido: use só letras minúsculas, números e _ (ex: confirmacao_pedido).')
      return
    }
    if (!bodyText.trim()) {
      setFormError('O corpo do template é obrigatório.')
      return
    }
    setCreating(true)
    try {
      const { data } = await api.post('/whatsapp/templates', {
        name: name.trim(),
        category,
        language: 'pt_BR',
        header_text: headerText.trim() || null,
        body_text: bodyText.trim(),
        footer_text: footerText.trim() || null,
      })
      if (data?.error) {
        setFormError(data.error?.error_user_msg || data.error?.message || 'A Meta recusou o template.')
      } else {
        setFormOk('Template enviado para aprovação da Meta (fica PENDING até ser aprovado).')
        setName(''); setHeaderText(''); setBodyText(''); setFooterText('')
        setTimeout(() => { setShowCreate(false); setFormOk(''); load() }, 1600)
      }
    } catch (err: any) {
      setFormError(err.response?.data?.detail || 'Erro ao criar template.')
    } finally {
      setCreating(false)
    }
  }

  function bodyOf(t: Template): string {
    return t.components?.find((c) => c.type === 'BODY')?.text || ''
  }

  async function openBroadcast(t: Template) {
    setBcTpl(t)
    setBcResult('')
    const nums = [...bodyOf(t).matchAll(/\{\{(\d+)\}\}/g)].map((m) => parseInt(m[1]))
    setBcVars(Array(nums.length ? Math.max(...nums) : 0).fill(''))
    setAudience(null)
    try {
      const { data } = await api.get('/whatsapp/broadcast/audience')
      setAudience(data.count)
    } catch { setAudience(0) }
  }

  async function runBroadcast() {
    if (!bcTpl) return
    setBroadcasting(true)
    setBcResult('')
    try {
      const { data } = await api.post('/whatsapp/broadcast', {
        template_name: bcTpl.name,
        language: bcTpl.language || 'pt_BR',
        variables: bcVars,
      })
      setBcResult(`Disparo concluído: ${data.sent} enviados · ${data.failed} falharam (de ${data.total}).`)
    } catch (err: any) {
      setBcResult(err.response?.data?.detail || 'Erro no disparo em massa.')
    } finally {
      setBroadcasting(false)
    }
  }

  async function handleDelete(tplName: string) {
    if (!confirm(`Deletar o template "${tplName}"?`)) return
    try {
      await api.delete(`/whatsapp/templates/${tplName}`)
      await load()
    } catch { alert('Erro ao deletar.') }
  }

  return (
    <div className="max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold text-[#e2e2e8] flex items-center gap-2">
            <FileText size={20} className="text-emerald-400" />
            Templates de WhatsApp
          </h1>
          <p className="text-[#555] text-sm mt-0.5">
            Mensagens pré-aprovadas para falar fora da janela de 24h.
          </p>
        </div>
        {!noConnection && (
          <div className="flex gap-2">
            <button
              onClick={sync}
              disabled={syncing}
              className="flex items-center gap-2 px-3 py-2 border border-white/[0.08] text-[#c0c0d0] hover:text-white text-sm font-medium rounded-lg transition-colors disabled:opacity-50"
            >
              <RefreshCw size={14} className={syncing ? 'animate-spin' : ''} />
              Sincronizar
            </button>
            <button
              onClick={() => { setShowCreate(true); setFormError(''); setFormOk('') }}
              className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-semibold rounded-lg transition-colors"
            >
              <Plus size={15} />
              Novo Template
            </button>
          </div>
        )}
      </div>

      {/* Custo estimado do mês */}
      <div className="bg-[#111118] border border-white/[0.06] rounded-xl p-4 mb-6">
        <div className="flex items-center justify-between mb-3">
          <p className="text-xs font-medium text-[#888]">Custo estimado do mês (WhatsApp)</p>
          <p className="text-lg font-semibold text-[#e2e2e8]">{brl(costs?.total ?? 0)}</p>
        </div>
        <div className="grid grid-cols-3 gap-3">
          {(['UTILITY', 'MARKETING', 'AUTHENTICATION'] as const).map((key) => {
            const c = CATEGORIES[key]
            const b = costs?.breakdown[key.toLowerCase()]
            return (
              <div key={key} className="bg-[#0a0a0f] border border-white/[0.05] rounded-lg p-3">
                <p className={`text-[10px] font-medium px-1.5 py-0.5 rounded border w-fit ${c.badge}`}>{c.label}</p>
                <p className="text-sm font-semibold text-[#e2e2e8] mt-2 leading-none">
                  {brl(c.cost)}<span className="text-[10px] text-[#444] font-normal"> /conversa</span>
                </p>
                {b && (
                  <p className="text-[11px] text-[#666] mt-1.5">
                    {b.count} conversas · <span className="text-[#c0c0d0]">{brl(b.subtotal)}</span>
                  </p>
                )}
              </div>
            )
          })}
        </div>
      </div>

      {/* Estados */}
      {noConnection ? (
        <div className="bg-[#111118] rounded-xl border border-white/[0.06] p-12 text-center">
          <div className="w-14 h-14 rounded-2xl bg-amber-500/10 flex items-center justify-center mx-auto mb-4">
            <AlertCircle size={24} className="text-amber-400" />
          </div>
          <h3 className="text-base font-semibold text-[#e2e2e8] mb-2">Nenhum WhatsApp conectado</h3>
          <p className="text-[#555] text-sm max-w-sm mx-auto mb-5">
            Conecte um número WhatsApp Business para criar e gerenciar templates.
          </p>
          <a
            href="/app/conexao"
            className="inline-flex items-center gap-2 px-5 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-semibold rounded-lg transition-colors no-underline"
          >
            <Link2 size={15} />
            Ir para Conexão Meta
          </a>
        </div>
      ) : loading ? (
        <p className="text-center text-[#555] text-sm py-10">Carregando…</p>
      ) : templates.length === 0 ? (
        <div className="bg-[#111118] rounded-xl border border-white/[0.06] p-12 text-center">
          <div className="w-14 h-14 rounded-2xl bg-emerald-500/10 flex items-center justify-center mx-auto mb-4">
            <FileText size={24} className="text-emerald-400" />
          </div>
          <h3 className="text-base font-semibold text-[#e2e2e8] mb-2">Nenhum template ainda</h3>
          <p className="text-[#555] text-sm max-w-sm mx-auto mb-5">
            Crie seu primeiro template ou sincronize os que já existem na Meta.
          </p>
          <button
            onClick={() => setShowCreate(true)}
            className="px-5 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-semibold rounded-lg transition-colors"
          >
            Criar template
          </button>
        </div>
      ) : (
        <div className="space-y-2">
          {templates.map((t) => {
            const cat = t.category ? CATEGORIES[t.category] : undefined
            const body = t.components?.find((c) => c.type === 'BODY')?.text
            return (
              <div key={t.name} className="bg-[#111118] rounded-xl border border-white/[0.06] p-4 hover:border-white/[0.1] transition-colors">
                <div className="flex items-start gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap mb-1">
                      <h3 className="text-sm font-semibold text-[#e2e2e8]">{t.name}</h3>
                      {cat && <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded border ${cat.badge}`}>{cat.label} · {brl(cat.cost)}</span>}
                      {t.status && <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded border ${STATUS_BADGE[t.status] ?? 'text-[#555] bg-white/[0.03] border-white/[0.05]'}`}>{t.status}</span>}
                      <span className="text-[10px] text-[#444]">{t.language}</span>
                    </div>
                    {body && <p className="text-xs text-[#666] truncate">{body}</p>}
                  </div>
                  <div className="flex gap-2 shrink-0">
                    <button
                      onClick={() => openBroadcast(t)}
                      className="flex items-center gap-1.5 px-3 py-1.5 bg-emerald-600/15 border border-emerald-500/30 text-emerald-400 rounded-lg text-xs font-semibold hover:bg-emerald-600/25 transition-colors"
                    >
                      <Send size={12} />
                      Disparar
                    </button>
                    <button
                      onClick={() => handleDelete(t.name)}
                      className="p-1.5 bg-red-900/20 text-red-400 rounded-lg hover:bg-red-900/40 transition-colors"
                    >
                      <Trash2 size={13} />
                    </button>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* Modal criar */}
      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm px-4">
          <div className="bg-[#111118] border border-white/[0.08] rounded-2xl p-6 w-full max-w-lg max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-5">
              <h3 className="text-base font-semibold text-white">Novo Template</h3>
              <button onClick={() => setShowCreate(false)} className="text-[#444] hover:text-[#888]"><X size={18} /></button>
            </div>

            <form onSubmit={handleCreate} className="space-y-4">
              {formError && (
                <div className="bg-red-900/20 border border-red-500/20 text-red-400 text-xs rounded-lg px-4 py-3">{formError}</div>
              )}
              {formOk && (
                <div className="bg-green-900/20 border border-green-500/20 text-green-400 text-xs rounded-lg px-4 py-3">{formOk}</div>
              )}

              <div>
                <label className="block text-xs font-medium text-[#666] mb-1.5">Nome (snake_case) *</label>
                <input
                  value={name}
                  onChange={(e) => setName(e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, '_'))}
                  placeholder="ex: confirmacao_pedido"
                  className="w-full px-4 py-2.5 bg-[#0a0a0f] border border-white/[0.08] text-[#e2e2e8] text-sm rounded-lg focus:border-indigo-500 focus:outline-none placeholder-[#333]"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-[#666] mb-1.5">Categoria *</label>
                <div className="grid grid-cols-3 gap-2">
                  {Object.entries(CATEGORIES).map(([key, c]) => (
                    <button
                      type="button"
                      key={key}
                      onClick={() => setCategory(key)}
                      className={`px-2 py-2 rounded-lg border text-xs font-medium transition-colors ${
                        category === key
                          ? 'bg-indigo-600/15 border-indigo-500/40 text-indigo-300'
                          : 'bg-[#0a0a0f] border-white/[0.08] text-[#666] hover:text-[#c0c0d0]'
                      }`}
                    >
                      {c.label}
                      <span className="block text-[10px] opacity-70">{brl(c.cost)}</span>
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-[#666] mb-1.5">Cabeçalho (opcional)</label>
                <input
                  value={headerText}
                  onChange={(e) => setHeaderText(e.target.value)}
                  placeholder="Ex: Seu pedido foi confirmado!"
                  className="w-full px-4 py-2.5 bg-[#0a0a0f] border border-white/[0.08] text-[#e2e2e8] text-sm rounded-lg focus:border-indigo-500 focus:outline-none placeholder-[#333]"
                />
              </div>

              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <label className="text-xs font-medium text-[#666]">Corpo *</label>
                  <button type="button" onClick={insertVar} className="text-[11px] text-indigo-400 hover:text-indigo-300">+ variável {'{{n}}'}</button>
                </div>
                <textarea
                  value={bodyText}
                  onChange={(e) => setBodyText(e.target.value)}
                  rows={4}
                  placeholder={'Olá {{1}}, seu pedido {{2}} está a caminho!'}
                  className="w-full px-4 py-2.5 bg-[#0a0a0f] border border-white/[0.08] text-[#e2e2e8] text-sm rounded-lg focus:border-indigo-500 focus:outline-none placeholder-[#333] resize-none"
                />
                <p className="text-[10px] text-[#444] mt-1">Use {'{{1}}, {{2}}'}… para variáveis que você preenche no envio.</p>
              </div>

              <div>
                <label className="block text-xs font-medium text-[#666] mb-1.5">Rodapé (opcional)</label>
                <input
                  value={footerText}
                  onChange={(e) => setFooterText(e.target.value)}
                  placeholder="Ex: Equipe Minha Empresa"
                  className="w-full px-4 py-2.5 bg-[#0a0a0f] border border-white/[0.08] text-[#e2e2e8] text-sm rounded-lg focus:border-indigo-500 focus:outline-none placeholder-[#333]"
                />
              </div>

              <div className="flex gap-3 pt-1">
                <button type="button" onClick={() => setShowCreate(false)} className="flex-1 py-2.5 border border-white/[0.08] text-[#666] hover:text-white text-sm font-medium rounded-lg transition-colors">
                  Cancelar
                </button>
                <button type="submit" disabled={creating} className="flex-1 py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm font-semibold rounded-lg transition-colors">
                  {creating ? 'Enviando…' : 'Enviar para aprovação'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal disparo em massa */}
      {bcTpl && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm px-4">
          <div className="bg-[#111118] border border-white/[0.08] rounded-2xl p-6 w-full max-w-md">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-base font-semibold text-white">Disparo em massa</h3>
              <button onClick={() => setBcTpl(null)} className="text-[#444] hover:text-[#888]"><X size={18} /></button>
            </div>

            <div className="bg-[#0a0a0f] border border-white/[0.06] rounded-lg p-3 mb-4">
              <p className="text-[11px] text-[#666]">Template</p>
              <p className="text-sm font-medium text-[#e2e2e8]">{bcTpl.name}</p>
              {bodyOf(bcTpl) && <p className="text-xs text-[#555] mt-1">{bodyOf(bcTpl)}</p>}
            </div>

            <div className="flex items-center gap-2 text-sm text-[#c0c0d0] mb-4">
              <Users size={15} className="text-indigo-400" />
              {audience === null
                ? 'Calculando público…'
                : <span><b className="text-white">{audience}</b> leads com número vão receber</span>}
            </div>

            {bcVars.length > 0 && (
              <div className="space-y-2 mb-4">
                {bcVars.map((v, i) => (
                  <div key={i}>
                    <label className="block text-[11px] text-[#666] mb-1">Variável {`{{${i + 1}}}`}</label>
                    <input
                      value={v}
                      onChange={(e) => setBcVars((prev) => prev.map((x, j) => (j === i ? e.target.value : x)))}
                      placeholder={`valor para {{${i + 1}}}`}
                      className="w-full px-3 py-2 bg-[#0a0a0f] border border-white/[0.08] text-[#e2e2e8] text-sm rounded-lg focus:border-indigo-500 focus:outline-none placeholder-[#333]"
                    />
                  </div>
                ))}
              </div>
            )}

            {bcResult ? (
              <div className="bg-white/[0.04] border border-white/[0.08] text-[#c0c0d0] text-xs rounded-lg px-4 py-3 mb-4">{bcResult}</div>
            ) : (
              <div className="bg-amber-900/15 border border-amber-500/20 text-amber-400/90 text-[11px] rounded-lg px-3 py-2 mb-4">
                Envia o template para <b>todos</b> os leads com número. Cada envio é cobrado pela categoria do template.
              </div>
            )}

            <div className="flex gap-3">
              <button onClick={() => setBcTpl(null)} className="flex-1 py-2.5 border border-white/[0.08] text-[#666] hover:text-white text-sm font-medium rounded-lg transition-colors">
                {bcResult ? 'Fechar' : 'Cancelar'}
              </button>
              {!bcResult && (
                <button
                  onClick={runBroadcast}
                  disabled={broadcasting || !audience}
                  className="flex-1 py-2.5 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-sm font-semibold rounded-lg transition-colors"
                >
                  {broadcasting ? 'Disparando…' : `Disparar para ${audience ?? 0}`}
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
