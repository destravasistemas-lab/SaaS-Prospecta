import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Clock, MessageSquare, CheckCircle2, AlertCircle, Link2, ArrowRight,
  Send, Upload, Users, X,
} from 'lucide-react'
import api from '../services/api'
import { useI18n, tr } from '../i18n'

interface Lead {
  id: string
  name: string | null
  phone: string | null
  instagram_handle: string
  whatsapp_opt_in?: boolean
  whatsapp_opted_out_at?: string | null
}

interface Tpl {
  name: string
  language: string
  components?: any[]
}

interface PendingItem {
  conversation_id: string
  customer_name: string
  phone: string | null
  template_name: string
  sent_at: string
  days_since: number
}

interface RespondedItem {
  conversation_id: string
  customer_name: string
  phone: string | null
  template_name: string
  sent_at: string
  replied_at: string
}

const fmtDate = (iso: string) =>
  new Date(iso).toLocaleDateString(tr('pt-BR', 'en-US'), { day: '2-digit', month: '2-digit' })

const fmtPhone = (p: string | null) => {
  if (!p) return ''
  if (p.startsWith('55') && (p.length === 12 || p.length === 13)) {
    const ddd = p.slice(2, 4)
    const rest = p.slice(4)
    return `+55 (${ddd}) ${rest.slice(0, rest.length - 4)}-${rest.slice(-4)}`
  }
  return p
}

type Tab = 'disparar' | 'pending' | 'responded'

export default function FollowUps() {
  const { t } = useI18n()
  const [withoutOptIn, setWithoutOptIn] = useState(0)
  const navigate = useNavigate()
  const [tab, setTab] = useState<Tab>('disparar')

  // Disparo
  const [leads, setLeads] = useState<Lead[]>([])
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [importing, setImporting] = useState(false)
  const [importMsg, setImportMsg] = useState('')
  const fileRef = useRef<HTMLInputElement>(null)

  // Modal de disparo
  const [showDispatch, setShowDispatch] = useState(false)
  const [tpls, setTpls] = useState<Tpl[]>([])
  const [pickedTpl, setPickedTpl] = useState<Tpl | null>(null)
  const [tplVars, setTplVars] = useState<string[]>([])
  const [dispatching, setDispatching] = useState(false)
  const [dispatchResult, setDispatchResult] = useState('')

  // Follow-ups
  const [pending, setPending] = useState<PendingItem[]>([])
  const [responded, setResponded] = useState<RespondedItem[]>([])
  const [loading, setLoading] = useState(true)
  const [noConnection, setNoConnection] = useState(false)

  useEffect(() => {
    loadLeads()
    api.get('/whatsapp/followups')
      .then(({ data }) => {
        setPending(data.pending || [])
        setResponded(data.responded || [])
      })
      .catch((err) => {
        if (err.response?.status === 404) setNoConnection(true)
      })
      .finally(() => setLoading(false))
  }, [])

  async function loadLeads() {
    try {
      const { data } = await api.get('/leads')
      const withPhone = (data as Lead[]).filter((l) => l.phone)
      const eligible = withPhone.filter((l) => l.whatsapp_opt_in && !l.whatsapp_opted_out_at)
      setLeads(eligible)
      setWithoutOptIn(withPhone.length - eligible.length)
    } catch { /* ignore */ }
  }

  function toggle(id: string) {
    setSelected((prev) => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  function toggleAll() {
    setSelected((prev) => (prev.size === leads.length ? new Set() : new Set(leads.map((l) => l.id))))
  }

  async function handleImport(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    setImporting(true)
    setImportMsg('')
    try {
      const form = new FormData()
      form.append('file', file)
      const { data } = await api.post('/leads/import', form, {
        headers: { 'Content-Type': undefined as any },
      })
      setImportMsg(t(
        `Importados: ${data.created} · já existiam: ${data.skipped} · inválidos: ${data.invalid}`,
        `Imported: ${data.created} · already existed: ${data.skipped} · invalid: ${data.invalid}`,
      ))
      await loadLeads()
    } catch (err: any) {
      setImportMsg(err.response?.data?.detail || t('Erro ao importar CSV.', 'Failed to import CSV.'))
    } finally {
      setImporting(false)
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  async function openDispatch() {
    setShowDispatch(true)
    setPickedTpl(null)
    setDispatchResult('')
    try {
      const { data } = await api.get('/whatsapp/templates')
      setTpls(Array.isArray(data) ? data : [])
    } catch { setTpls([]) }
  }

  function pickTpl(tpl: Tpl) {
    setPickedTpl(tpl)
    const body = tpl.components?.find((c) => c.type === 'BODY')?.text || ''
    const nums = [...body.matchAll(/\{\{(\d+)\}\}/g)].map((m) => parseInt(m[1]))
    setTplVars(Array(nums.length ? Math.max(...nums) : 0).fill(''))
  }

  async function runDispatch() {
    if (!pickedTpl) return
    setDispatching(true)
    setDispatchResult('')
    try {
      const { data } = await api.post('/whatsapp/broadcast', {
        template_name: pickedTpl.name,
        language: pickedTpl.language || 'pt_BR',
        variables: tplVars,
        lead_ids: selected.size > 0 ? [...selected] : leads.map((l) => l.id),
      })
      setDispatchResult(t(`Disparo: ${data.sent} enviados · ${data.failed} falharam (de ${data.total}).`, `Broadcast: ${data.sent} sent · ${data.failed} failed (of ${data.total}).`))
    } catch (err: any) {
      setDispatchResult(err.response?.data?.detail || t('Erro no disparo.', 'Broadcast failed.'))
    } finally {
      setDispatching(false)
    }
  }

  function openConversation(convId: string) {
    navigate(`/app/whatsapp?conv=${convId}`)
  }

  return (
    <div className="max-w-3xl mx-auto">
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-[#e2e2e8] flex items-center gap-2">
          <Clock size={20} className="text-amber-400" />
          Follow-ups
        </h1>
        <p className="text-[#555] text-sm mt-0.5">
          {t('Envie templates para contatos com opt-in e acompanhe quem respondeu e quem não.', "Send templates to opted-in contacts and track who replied and who didn't.")}
        </p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-[#111118] border border-white/[0.06] rounded-xl p-1 mb-5 w-fit flex-wrap">
        <button
          onClick={() => setTab('disparar')}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            tab === 'disparar' ? 'bg-indigo-500/15 text-indigo-300' : 'text-[#5a5a6e] hover:text-[#c0c0d0]'
          }`}
        >
          <Send size={14} />
          {t('Disparar', 'Send')}
          <span className="text-[10px] bg-white/10 rounded px-1.5">{leads.length}</span>
        </button>
        <button
          onClick={() => setTab('pending')}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            tab === 'pending' ? 'bg-amber-500/15 text-amber-300' : 'text-[#5a5a6e] hover:text-[#c0c0d0]'
          }`}
        >
          <Clock size={14} />
          {t('Aguardando', 'Awaiting reply')}
          <span className="text-[10px] bg-white/10 rounded px-1.5">{pending.length}</span>
        </button>
        <button
          onClick={() => setTab('responded')}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            tab === 'responded' ? 'bg-emerald-500/15 text-emerald-300' : 'text-[#5a5a6e] hover:text-[#c0c0d0]'
          }`}
        >
          <CheckCircle2 size={14} />
          {t('Responderam', 'Replied')}
          <span className="text-[10px] bg-white/10 rounded px-1.5">{responded.length}</span>
        </button>
      </div>

      {/* ---------- Aba DISPARAR ---------- */}
      {tab === 'disparar' && (
        <>
          <div className="flex items-center justify-between mb-3 gap-2 flex-wrap">
            <div className="flex items-center gap-2">
              <input ref={fileRef} type="file" accept=".csv" onChange={handleImport} className="hidden" />
              <button
                onClick={() => fileRef.current?.click()}
                disabled={importing}
                className="flex items-center gap-2 px-3 py-2 border border-white/[0.08] text-[#c0c0d0] hover:text-white text-sm font-medium rounded-lg transition-colors disabled:opacity-50"
              >
                <Upload size={14} />
                {importing ? t('Importando…', 'Importing…') : t('Importar CSV', 'Import CSV')}
              </button>
              <span className="text-[11px] text-[#555]">{t('colunas: nome, telefone, opt_in (sim/não)', 'columns: name, phone, opt_in (yes/no)')}</span>
            </div>
            <button
              onClick={openDispatch}
              disabled={leads.length === 0}
              className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm font-semibold rounded-lg transition-colors"
            >
              <Send size={14} />
              {t('Disparar', 'Send')} {selected.size > 0 ? `(${selected.size})` : t('(todos)', '(all)')}
            </button>
          </div>

          {withoutOptIn > 0 && (
            <div className="mb-3 bg-amber-900/10 border border-amber-500/20 text-amber-400/90 text-[11px] rounded-lg px-4 py-2">
              {t(
                `${withoutOptIn} contato(s) com telefone não aparecem aqui por não terem opt-in para WhatsApp. Registre o consentimento na página Leads.`,
                `${withoutOptIn} contact(s) with a phone number are hidden because they have no WhatsApp opt-in. Record consent on the Leads page.`,
              )}
            </div>
          )}

          {importMsg && (
            <div className="mb-3 bg-white/[0.04] border border-white/[0.08] text-[#c0c0d0] text-xs rounded-lg px-4 py-2.5">{importMsg}</div>
          )}

          {leads.length === 0 ? (
            <div className="bg-[#111118] rounded-xl border border-white/[0.06] p-10 text-center">
              <div className="w-12 h-12 rounded-2xl bg-indigo-500/10 flex items-center justify-center mx-auto mb-3">
                <Users size={22} className="text-indigo-400" />
              </div>
              <p className="text-[#e2e2e8] text-sm font-medium mb-1">{t('Nenhum contato com opt-in', 'No opted-in contacts')}</p>
              <p className="text-[#555] text-xs">{t('Importe um CSV (nome, telefone, opt_in) ou registre o opt-in na página Leads.', 'Import a CSV (name, phone, opt_in) or record opt-in on the Leads page.')}</p>
            </div>
          ) : (
            <div className="bg-[#111118] rounded-xl border border-white/[0.06] overflow-hidden">
              <label className="flex items-center gap-3 px-4 py-2.5 border-b border-white/[0.06] cursor-pointer">
                <input type="checkbox" checked={selected.size === leads.length} onChange={toggleAll} className="accent-indigo-600" />
                <span className="text-xs font-medium text-[#8a8a9e]">
                  {selected.size > 0 ? t(`${selected.size} selecionados`, `${selected.size} selected`) : t('Selecionar todos', 'Select all')}
                </span>
              </label>
              <div className="max-h-[420px] overflow-y-auto">
                {leads.map((l) => (
                  <label key={l.id} className="flex items-center gap-3 px-4 py-2.5 border-b border-white/[0.03] hover:bg-white/[0.02] cursor-pointer">
                    <input type="checkbox" checked={selected.has(l.id)} onChange={() => toggle(l.id)} className="accent-indigo-600" />
                    <div className="w-8 h-8 rounded-full bg-white/[0.05] flex items-center justify-center text-[10px] font-bold text-[#8a8a9e] shrink-0">
                      {(l.name || '?').charAt(0).toUpperCase()}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-[#e2e2e8] truncate">{l.name || t('Sem nome', 'No name')}</p>
                      <p className="text-[11px] text-[#555]">{fmtPhone(l.phone)}</p>
                    </div>
                  </label>
                ))}
              </div>
            </div>
          )}
        </>
      )}

      {/* ---------- Aba AGUARDANDO ---------- */}
      {tab === 'pending' && (
        noConnection ? (
          <NoConnection />
        ) : loading ? (
          <p className="text-center text-[#555] text-sm py-10">{t('Carregando…', 'Loading…')}</p>
        ) : pending.length === 0 ? (
          <div className="bg-[#111118] rounded-xl border border-white/[0.06] p-10 text-center">
            <p className="text-[#e2e2e8] text-sm font-medium mb-1">{t('Nenhum follow-up pendente 🎉', 'No pending follow-ups 🎉')}</p>
            <p className="text-[#555] text-xs">{t('Envios sem resposta aparecem aqui após 3 dias (e saem após 14).', 'Unanswered messages show up here after 3 days (and leave after 14).')}</p>
          </div>
        ) : (
          <div className="space-y-2">
            {pending.map((p) => (
              <div key={p.conversation_id} className="bg-[#111118] rounded-xl border border-white/[0.06] p-4 flex items-center gap-3">
                <div className="w-9 h-9 rounded-full bg-amber-500/10 flex items-center justify-center text-xs font-bold text-amber-400 shrink-0">
                  {p.customer_name.charAt(0).toUpperCase()}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-[#e2e2e8] truncate">{p.customer_name}</p>
                  <p className="text-[11px] text-[#555]">
                    Template <span className="text-[#8a8a9e]">{p.template_name}</span> {t('em', 'on')} {fmtDate(p.sent_at)} ·{' '}
                    <span className="text-amber-400 font-medium">{t(`${p.days_since} dias sem resposta`, `${p.days_since} days without reply`)}</span>
                  </p>
                </div>
                <button onClick={() => openConversation(p.conversation_id)} className="flex items-center gap-1.5 px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-semibold transition-colors shrink-0">
                  <MessageSquare size={12} /> {t('Abrir', 'Open')} <ArrowRight size={11} />
                </button>
              </div>
            ))}
          </div>
        )
      )}

      {/* ---------- Aba RESPONDERAM ---------- */}
      {tab === 'responded' && (
        noConnection ? (
          <NoConnection />
        ) : responded.length === 0 ? (
          <div className="bg-[#111118] rounded-xl border border-white/[0.06] p-10 text-center">
            <p className="text-[#e2e2e8] text-sm font-medium mb-1">{t('Ninguém respondeu ainda', 'Nobody has replied yet')}</p>
            <p className="text-[#555] text-xs">{t('Clientes que responderem aos envios aparecem aqui.', 'Customers who reply to your messages show up here.')}</p>
          </div>
        ) : (
          <div className="space-y-2">
            {responded.map((r) => (
              <div key={r.conversation_id} className="bg-[#111118] rounded-xl border border-white/[0.06] p-4 flex items-center gap-3">
                <div className="w-9 h-9 rounded-full bg-emerald-500/10 flex items-center justify-center text-xs font-bold text-emerald-400 shrink-0">
                  {r.customer_name.charAt(0).toUpperCase()}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-[#e2e2e8] truncate">{r.customer_name}</p>
                  <p className="text-[11px] text-[#555]">
                    Template <span className="text-[#8a8a9e]">{r.template_name}</span> {t('em', 'on')} {fmtDate(r.sent_at)} ·{' '}
                    <span className="text-emerald-400 font-medium">{t('respondeu em', 'replied on')} {fmtDate(r.replied_at)}</span>
                  </p>
                </div>
                <button onClick={() => openConversation(r.conversation_id)} className="flex items-center gap-1.5 px-3 py-1.5 bg-emerald-600/15 border border-emerald-500/30 text-emerald-400 hover:bg-emerald-600/25 rounded-lg text-xs font-semibold transition-colors shrink-0">
                  <MessageSquare size={12} /> {t('Atender', 'Reply')}
                </button>
              </div>
            ))}
          </div>
        )
      )}

      {/* Modal de disparo */}
      {showDispatch && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm px-4">
          <div className="bg-[#111118] border border-white/[0.08] rounded-2xl p-6 w-full max-w-md max-h-[85vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-base font-semibold text-white">{t('Enviar template', 'Send template')}</h3>
              <button onClick={() => setShowDispatch(false)} className="text-[#444] hover:text-[#888]"><X size={18} /></button>
            </div>

            <div className="flex items-center gap-2 text-sm text-[#c0c0d0] mb-4">
              <Users size={15} className="text-indigo-400" />
              <span>{t('Enviando para', 'Sending to')} <b className="text-white">{selected.size > 0 ? selected.size : leads.length}</b> {t('contatos com opt-in', 'opted-in contacts')}</span>
            </div>

            {!pickedTpl ? (
              tpls.length === 0 ? (
                <p className="text-[#5a5a6e] text-sm text-center py-6">{t('Nenhum template disponível. Crie em Templates.', 'No templates available. Create one in Templates.')}</p>
              ) : (
                <div className="space-y-1.5">
                  {tpls.map((tpl) => (
                    <button key={tpl.name} onClick={() => pickTpl(tpl)} className="w-full text-left px-3 py-2.5 rounded-lg bg-[#0a0a0f] border border-white/[0.06] hover:border-indigo-500/40 transition-colors">
                      <p className="text-sm font-medium text-[#e2e2e8]">{tpl.name}</p>
                      <p className="text-xs text-[#555] truncate">{tpl.components?.find((c) => c.type === 'BODY')?.text}</p>
                    </button>
                  ))}
                </div>
              )
            ) : (
              <div>
                <div className="bg-[#0a0a0f] border border-white/[0.06] rounded-lg p-3 mb-3">
                  <p className="text-sm font-medium text-[#e2e2e8]">{pickedTpl.name}</p>
                  <p className="text-xs text-[#555] mt-1">{pickedTpl.components?.find((c) => c.type === 'BODY')?.text}</p>
                </div>
                {tplVars.length > 0 && (
                  <div className="space-y-2 mb-3">
                    {tplVars.map((v, i) => (
                      <div key={i}>
                        <label className="block text-[11px] text-[#666] mb-1">{t('Variável', 'Variable')} {`{{${i + 1}}}`}</label>
                        <input value={v} onChange={(e) => setTplVars((prev) => prev.map((x, j) => (j === i ? e.target.value : x)))} className="w-full px-3 py-2 bg-[#0a0a0f] border border-white/[0.08] text-[#e2e2e8] text-sm rounded-lg focus:border-indigo-500 focus:outline-none" />
                      </div>
                    ))}
                  </div>
                )}
                {dispatchResult && (
                  <div className="bg-white/[0.04] border border-white/[0.08] text-[#c0c0d0] text-xs rounded-lg px-4 py-3 mb-3">{dispatchResult}</div>
                )}
                <div className="flex gap-2">
                  <button onClick={() => (dispatchResult ? setShowDispatch(false) : setPickedTpl(null))} className="flex-1 py-2.5 border border-white/[0.08] text-[#666] hover:text-white text-sm rounded-lg transition-colors">
                    {dispatchResult ? t('Fechar', 'Close') : t('Voltar', 'Back')}
                  </button>
                  {!dispatchResult && (
                    <button onClick={runDispatch} disabled={dispatching} className="flex-1 py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm font-semibold rounded-lg transition-colors">
                      {dispatching ? t('Enviando…', 'Sending…') : t('Enviar', 'Send')}
                    </button>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

function NoConnection() {
  const { t } = useI18n()
  return (
    <div className="bg-[#111118] rounded-xl border border-white/[0.06] p-12 text-center">
      <div className="w-14 h-14 rounded-2xl bg-amber-500/10 flex items-center justify-center mx-auto mb-4">
        <AlertCircle size={24} className="text-amber-400" />
      </div>
      <h3 className="text-base font-semibold text-[#e2e2e8] mb-2">{t('Nenhum WhatsApp conectado', 'No WhatsApp connected')}</h3>
      <p className="text-[#555] text-sm max-w-sm mx-auto mb-5">
        {t('Conecte um número WhatsApp Business para acompanhar follow-ups.', 'Connect a WhatsApp Business number to track follow-ups.')}
      </p>
      <a href="/app/conexao" className="inline-flex items-center gap-2 px-5 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-semibold rounded-lg transition-colors no-underline">
        <Link2 size={15} />
        {t('Ir para Conexões Meta', 'Go to Meta Connections')}
      </a>
    </div>
  )
}
