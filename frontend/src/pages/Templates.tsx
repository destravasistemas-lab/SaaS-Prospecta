import { useState, useEffect } from 'react'
import { FileText, Plus, RefreshCw, Trash2, X, Link2, AlertCircle, Send, Users } from 'lucide-react'
import api from '../services/api'
import { useI18n } from '../i18n'

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
const CATEGORIES: Record<string, { pt: string; en: string; cost: number; badge: string }> = {
  UTILITY: { pt: 'Utilidade', en: 'Utility', cost: 0.12, badge: 'text-blue-400 bg-blue-900/20 border-blue-500/20' },
  MARKETING: { pt: 'Marketing', en: 'Marketing', cost: 0.33, badge: 'text-purple-400 bg-purple-900/20 border-purple-500/20' },
  AUTHENTICATION: { pt: 'Autenticação', en: 'Authentication', cost: 0.15, badge: 'text-amber-400 bg-amber-900/20 border-amber-500/20' },
}

const LANGUAGES = [
  { code: 'pt_BR', label: 'Português (BR)' },
  { code: 'en_US', label: 'English (US)' },
  { code: 'es', label: 'Español' },
]

const STATUS_BADGE: Record<string, string> = {
  APPROVED: 'text-green-400 bg-green-900/20 border-green-500/20',
  PENDING: 'text-amber-400 bg-amber-900/20 border-amber-500/20',
  REJECTED: 'text-red-400 bg-red-900/20 border-red-500/20',
}

const brl = (v: number) => `R$ ${v.toFixed(2).replace('.', ',')}`

export default function Templates() {
  const { t, lang } = useI18n()
  const catLabel = (c: { pt: string; en: string }) => t(c.pt, c.en)
  const [templates, setTemplates] = useState<Template[]>([])
  const [loading, setLoading] = useState(true)
  const [noConnection, setNoConnection] = useState(false)
  const [syncing, setSyncing] = useState(false)
  const [costs, setCosts] = useState<CostData | null>(null)

  const [showCreate, setShowCreate] = useState(false)
  const [name, setName] = useState('')
  const [category, setCategory] = useState('UTILITY')
  const [tplLang, setTplLang] = useState(lang === 'en' ? 'en_US' : 'pt_BR')
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
  const [noOptIn, setNoOptIn] = useState(0)
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
      setFormError(t('Nome inválido: use só letras minúsculas, números e _ (ex: confirmacao_pedido).', 'Invalid name: use only lowercase letters, numbers and _ (e.g. order_confirmation).'))
      return
    }
    if (!bodyText.trim()) {
      setFormError(t('O corpo do template é obrigatório.', 'The template body is required.'))
      return
    }
    setCreating(true)
    try {
      const { data } = await api.post('/whatsapp/templates', {
        name: name.trim(),
        category,
        language: tplLang,
        header_text: headerText.trim() || null,
        body_text: bodyText.trim(),
        footer_text: footerText.trim() || null,
      })
      if (data?.error) {
        setFormError(data.error?.error_user_msg || data.error?.message || t('A Meta recusou o template.', 'Meta rejected the template.'))
      } else {
        setFormOk(t('Template enviado para aprovação da Meta (fica PENDING até ser aprovado).', 'Template submitted for Meta approval (it stays PENDING until approved).'))
        setName(''); setHeaderText(''); setBodyText(''); setFooterText('')
        setTimeout(() => { setShowCreate(false); setFormOk(''); load() }, 1600)
      }
    } catch (err: any) {
      setFormError(err.response?.data?.detail || t('Erro ao criar template.', 'Failed to create template.'))
    } finally {
      setCreating(false)
    }
  }

  function bodyOf(tpl: Template): string {
    return tpl.components?.find((c) => c.type === 'BODY')?.text || ''
  }

  async function openBroadcast(tpl: Template) {
    setBcTpl(tpl)
    setBcResult('')
    const nums = [...bodyOf(tpl).matchAll(/\{\{(\d+)\}\}/g)].map((m) => parseInt(m[1]))
    setBcVars(Array(nums.length ? Math.max(...nums) : 0).fill(''))
    setAudience(null)
    try {
      const { data } = await api.get('/whatsapp/broadcast/audience')
      setAudience(data.count)
      setNoOptIn(data.without_opt_in ?? 0)
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
      setBcResult(t(
        `Disparo concluído: ${data.sent} enviados · ${data.failed} falharam (de ${data.total}).`,
        `Broadcast finished: ${data.sent} sent · ${data.failed} failed (of ${data.total}).`,
      ))
    } catch (err: any) {
      setBcResult(err.response?.data?.detail || t('Erro no disparo em massa.', 'Broadcast failed.'))
    } finally {
      setBroadcasting(false)
    }
  }

  async function handleDelete(tplName: string) {
    if (!confirm(t(`Deletar o template "${tplName}"?`, `Delete the template "${tplName}"?`))) return
    try {
      await api.delete(`/whatsapp/templates/${tplName}`)
      await load()
    } catch { alert(t('Erro ao deletar.', 'Failed to delete.')) }
  }

  return (
    <div className="max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold text-[#e2e2e8] flex items-center gap-2">
            <FileText size={20} className="text-emerald-400" />
            {t('Templates de WhatsApp', 'WhatsApp Templates')}
          </h1>
          <p className="text-[#555] text-sm mt-0.5">
            {t('Mensagens aprovadas pela Meta para iniciar conversas ou falar fora da janela de 24h (somente com opt-in).', 'Meta-approved messages to start conversations or talk outside the 24h window (opt-in contacts only).')}
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
              {t('Sincronizar', 'Sync')}
            </button>
            <button
              onClick={() => { setShowCreate(true); setFormError(''); setFormOk('') }}
              className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-semibold rounded-lg transition-colors"
            >
              <Plus size={15} />
              {t('Novo Template', 'New Template')}
            </button>
          </div>
        )}
      </div>

      {/* Custo estimado do mês */}
      <div className="bg-[#111118] border border-white/[0.06] rounded-xl p-4 mb-6">
        <div className="flex items-center justify-between mb-3">
          <p className="text-xs font-medium text-[#888]">{t('Custo estimado do mês (WhatsApp) — valores de referência; a cobrança é feita pela Meta', 'Estimated cost this month (WhatsApp) — reference values; billing is done by Meta')}</p>
          <p className="text-lg font-semibold text-[#e2e2e8]">{brl(costs?.total ?? 0)}</p>
        </div>
        <div className="grid grid-cols-3 gap-3">
          {(['UTILITY', 'MARKETING', 'AUTHENTICATION'] as const).map((key) => {
            const c = CATEGORIES[key]
            const b = costs?.breakdown[key.toLowerCase()]
            return (
              <div key={key} className="bg-[#0a0a0f] border border-white/[0.05] rounded-lg p-3">
                <p className={`text-[10px] font-medium px-1.5 py-0.5 rounded border w-fit ${c.badge}`}>{catLabel(c)}</p>
                <p className="text-sm font-semibold text-[#e2e2e8] mt-2 leading-none">
                  {brl(c.cost)}<span className="text-[10px] text-[#444] font-normal"> {t('/mensagem', '/message')}</span>
                </p>
                {b && (
                  <p className="text-[11px] text-[#666] mt-1.5">
                    {b.count} {t('mensagens', 'messages')} · <span className="text-[#c0c0d0]">{brl(b.subtotal)}</span>
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
          <h3 className="text-base font-semibold text-[#e2e2e8] mb-2">{t('Nenhum WhatsApp conectado', 'No WhatsApp connected')}</h3>
          <p className="text-[#555] text-sm max-w-sm mx-auto mb-5">
            {t('Conecte um número WhatsApp Business para criar e gerenciar templates.', 'Connect a WhatsApp Business number to create and manage templates.')}
          </p>
          <a
            href="/app/conexao"
            className="inline-flex items-center gap-2 px-5 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-semibold rounded-lg transition-colors no-underline"
          >
            <Link2 size={15} />
            {t('Ir para Conexões Meta', 'Go to Meta Connections')}
          </a>
        </div>
      ) : loading ? (
        <p className="text-center text-[#555] text-sm py-10">{t('Carregando…', 'Loading…')}</p>
      ) : templates.length === 0 ? (
        <div className="bg-[#111118] rounded-xl border border-white/[0.06] p-12 text-center">
          <div className="w-14 h-14 rounded-2xl bg-emerald-500/10 flex items-center justify-center mx-auto mb-4">
            <FileText size={24} className="text-emerald-400" />
          </div>
          <h3 className="text-base font-semibold text-[#e2e2e8] mb-2">{t('Nenhum template ainda', 'No templates yet')}</h3>
          <p className="text-[#555] text-sm max-w-sm mx-auto mb-5">
            {t('Crie seu primeiro template ou sincronize os que já existem na Meta.', 'Create your first template or sync the ones that already exist at Meta.')}
          </p>
          <button
            onClick={() => setShowCreate(true)}
            className="px-5 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-semibold rounded-lg transition-colors"
          >
            {t('Criar template', 'Create template')}
          </button>
        </div>
      ) : (
        <div className="space-y-2">
          {templates.map((tpl) => {
            const cat = tpl.category ? CATEGORIES[tpl.category] : undefined
            const body = tpl.components?.find((c) => c.type === 'BODY')?.text
            return (
              <div key={tpl.name} className="bg-[#111118] rounded-xl border border-white/[0.06] p-4 hover:border-white/[0.1] transition-colors">
                <div className="flex items-start gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap mb-1">
                      <h3 className="text-sm font-semibold text-[#e2e2e8]">{tpl.name}</h3>
                      {cat && <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded border ${cat.badge}`}>{catLabel(cat)} · {brl(cat.cost)}</span>}
                      {tpl.status && <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded border ${STATUS_BADGE[tpl.status] ?? 'text-[#555] bg-white/[0.03] border-white/[0.05]'}`}>{tpl.status}</span>}
                      <span className="text-[10px] text-[#444]">{tpl.language}</span>
                    </div>
                    {body && <p className="text-xs text-[#666] truncate">{body}</p>}
                  </div>
                  <div className="flex gap-2 shrink-0">
                    <button
                      onClick={() => openBroadcast(tpl)}
                      disabled={tpl.status !== undefined && tpl.status !== 'APPROVED'}
                      title={tpl.status && tpl.status !== 'APPROVED' ? t('Só templates aprovados podem ser enviados', 'Only approved templates can be sent') : undefined}
                      className="flex items-center gap-1.5 px-3 py-1.5 bg-emerald-600/15 border border-emerald-500/30 text-emerald-400 rounded-lg text-xs font-semibold hover:bg-emerald-600/25 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                    >
                      <Send size={12} />
                      {t('Disparar', 'Broadcast')}
                    </button>
                    <button
                      onClick={() => handleDelete(tpl.name)}
                      title={t('Excluir', 'Delete')}
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
              <h3 className="text-base font-semibold text-white">{t('Novo Template', 'New Template')}</h3>
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
                <label className="block text-xs font-medium text-[#666] mb-1.5">{t('Nome (snake_case) *', 'Name (snake_case) *')}</label>
                <input
                  value={name}
                  onChange={(e) => setName(e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, '_'))}
                  placeholder={t('ex: confirmacao_pedido', 'e.g. order_confirmation')}
                  className="w-full px-4 py-2.5 bg-[#0a0a0f] border border-white/[0.08] text-[#e2e2e8] text-sm rounded-lg focus:border-indigo-500 focus:outline-none placeholder-[#333]"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-[#666] mb-1.5">{t('Idioma *', 'Language *')}</label>
                <select
                  value={tplLang}
                  onChange={(e) => setTplLang(e.target.value)}
                  className="w-full px-4 py-2.5 bg-[#0a0a0f] border border-white/[0.08] text-[#e2e2e8] text-sm rounded-lg focus:border-indigo-500 focus:outline-none"
                >
                  {LANGUAGES.map((l) => <option key={l.code} value={l.code}>{l.label}</option>)}
                </select>
              </div>

              <div>
                <label className="block text-xs font-medium text-[#666] mb-1.5">{t('Categoria *', 'Category *')}</label>
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
                      {catLabel(c)}
                      <span className="block text-[10px] opacity-70">{brl(c.cost)}</span>
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-[#666] mb-1.5">{t('Cabeçalho (opcional)', 'Header (optional)')}</label>
                <input
                  value={headerText}
                  onChange={(e) => setHeaderText(e.target.value)}
                  placeholder={t('Ex: Seu pedido foi confirmado!', 'E.g. Your order is confirmed!')}
                  className="w-full px-4 py-2.5 bg-[#0a0a0f] border border-white/[0.08] text-[#e2e2e8] text-sm rounded-lg focus:border-indigo-500 focus:outline-none placeholder-[#333]"
                />
              </div>

              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <label className="text-xs font-medium text-[#666]">{t('Corpo *', 'Body *')}</label>
                  <button type="button" onClick={insertVar} className="text-[11px] text-indigo-400 hover:text-indigo-300">+ {t('variável', 'variable')} {'{{n}}'}</button>
                </div>
                <textarea
                  value={bodyText}
                  onChange={(e) => setBodyText(e.target.value)}
                  rows={4}
                  placeholder={t('Olá {{1}}, seu pedido {{2}} está a caminho!', 'Hi {{1}}, your order {{2}} is on its way!')}
                  className="w-full px-4 py-2.5 bg-[#0a0a0f] border border-white/[0.08] text-[#e2e2e8] text-sm rounded-lg focus:border-indigo-500 focus:outline-none placeholder-[#333] resize-none"
                />
                <p className="text-[10px] text-[#444] mt-1">{t('Use {{1}}, {{2}}… para variáveis que você preenche no envio.', 'Use {{1}}, {{2}}… for variables you fill in when sending.')}</p>
              </div>

              <div>
                <label className="block text-xs font-medium text-[#666] mb-1.5">{t('Rodapé (opcional)', 'Footer (optional)')}</label>
                <input
                  value={footerText}
                  onChange={(e) => setFooterText(e.target.value)}
                  placeholder={t('Ex: Equipe Minha Empresa', 'E.g. My Company Team')}
                  className="w-full px-4 py-2.5 bg-[#0a0a0f] border border-white/[0.08] text-[#e2e2e8] text-sm rounded-lg focus:border-indigo-500 focus:outline-none placeholder-[#333]"
                />
              </div>

              <div className="flex gap-3 pt-1">
                <button type="button" onClick={() => setShowCreate(false)} className="flex-1 py-2.5 border border-white/[0.08] text-[#666] hover:text-white text-sm font-medium rounded-lg transition-colors">
                  {t('Cancelar', 'Cancel')}
                </button>
                <button type="submit" disabled={creating} className="flex-1 py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm font-semibold rounded-lg transition-colors">
                  {creating ? t('Enviando…', 'Submitting…') : t('Enviar para aprovação', 'Submit for approval')}
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
              <h3 className="text-base font-semibold text-white">{t('Disparo em massa', 'Broadcast')}</h3>
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
                ? t('Calculando público…', 'Calculating audience…')
                : <span><b className="text-white">{audience}</b> {t('contatos com opt-in vão receber', 'opted-in contacts will receive it')}</span>}
            </div>

            {bcVars.length > 0 && (
              <div className="space-y-2 mb-4">
                {bcVars.map((v, i) => (
                  <div key={i}>
                    <label className="block text-[11px] text-[#666] mb-1">{t('Variável', 'Variable')} {`{{${i + 1}}}`}</label>
                    <input
                      value={v}
                      onChange={(e) => setBcVars((prev) => prev.map((x, j) => (j === i ? e.target.value : x)))}
                      placeholder={t(`valor para {{${i + 1}}}`, `value for {{${i + 1}}}`)}
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
                {t(
                  'Envia o template somente para contatos com opt-in registrado para WhatsApp. Quem pediu para sair (opt-out) nunca recebe. Cada envio é cobrado pela Meta conforme a categoria.',
                  'Sends the template only to contacts with a recorded WhatsApp opt-in. Contacts who opted out never receive it. Each message is billed by Meta according to its category.',
                )}
                {noOptIn > 0 && (
                  <span className="block mt-1">
                    {t(`${noOptIn} contato(s) com telefone sem opt-in foram excluídos.`, `${noOptIn} contact(s) with a phone number but no opt-in were excluded.`)}
                  </span>
                )}
              </div>
            )}

            <div className="flex gap-3">
              <button onClick={() => setBcTpl(null)} className="flex-1 py-2.5 border border-white/[0.08] text-[#666] hover:text-white text-sm font-medium rounded-lg transition-colors">
                {bcResult ? t('Fechar', 'Close') : t('Cancelar', 'Cancel')}
              </button>
              {!bcResult && (
                <button
                  onClick={runBroadcast}
                  disabled={broadcasting || !audience}
                  className="flex-1 py-2.5 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-sm font-semibold rounded-lg transition-colors"
                >
                  {broadcasting ? t('Disparando…', 'Sending…') : t(`Disparar para ${audience ?? 0}`, `Send to ${audience ?? 0}`)}
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
