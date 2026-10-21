import { useEffect, useState } from 'react'
import { Plus, Repeat, Trash2, Pencil, X, Info } from 'lucide-react'
import api from '../services/api'
import { useI18n } from '../i18n'
import HelpLink from './HelpLink'

interface Tpl {
  name: string
  language: string
  status?: string
  components?: any[]
}

interface Rule {
  id: string
  name: string
  enabled: boolean
  delay_days: number
  trigger_template: string | null
  template_name: string
  template_language: string
  variables: string[]
  send_hour_start: number
  send_hour_end: number
  sent_count: number
  skipped_count: number
  failed_count: number
  last_sent_at: string | null
}

type Form = Omit<Rule, 'id' | 'sent_count' | 'skipped_count' | 'failed_count' | 'last_sent_at'>

const EMPTY: Form = {
  name: '',
  enabled: true,
  delay_days: 3,
  trigger_template: null,
  template_name: '',
  template_language: 'pt_BR',
  variables: [],
  send_hour_start: 9,
  send_hour_end: 20,
}

const bodyOf = (tpl?: Tpl) => tpl?.components?.find((c) => c.type === 'BODY')?.text || ''
const varCount = (tpl?: Tpl) => {
  const nums = [...bodyOf(tpl).matchAll(/\{\{(\d+)\}\}/g)].map((m) => parseInt(m[1]))
  return nums.length ? Math.max(...nums) : 0
}

export default function AutoFollowUps() {
  const { t, locale } = useI18n()
  const [rules, setRules] = useState<Rule[]>([])
  const [templates, setTemplates] = useState<Tpl[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [editing, setEditing] = useState<string | 'new' | null>(null)
  const [form, setForm] = useState<Form>(EMPTY)
  const [saving, setSaving] = useState(false)
  const [formError, setFormError] = useState('')

  const approved = templates.filter((tpl) => !tpl.status || tpl.status === 'APPROVED')
  const hours = Array.from({ length: 25 }, (_, i) => i)

  async function load() {
    setLoading(true)
    try {
      const [r, tp] = await Promise.all([
        api.get<Rule[]>('/whatsapp/followup-rules'),
        api.get<Tpl[]>('/whatsapp/templates').catch(() => ({ data: [] as Tpl[] })),
      ])
      setRules(r.data)
      setTemplates(Array.isArray(tp.data) ? tp.data : [])
    } catch (err: any) {
      setError(err.response?.status === 404
        ? t('Conecte o WhatsApp para usar o follow-up automático.', 'Connect WhatsApp to use automatic follow-ups.')
        : t('Erro ao carregar as regras.', 'Failed to load rules.'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  function openNew() {
    setForm({ ...EMPTY, name: t('Lembrete após 3 dias', 'Reminder after 3 days') })
    setFormError('')
    setEditing('new')
  }

  function openEdit(rule: Rule) {
    const { id: _id, sent_count: _a, skipped_count: _b, failed_count: _c, last_sent_at: _d, ...rest } = rule
    setForm(rest)
    setFormError('')
    setEditing(rule.id)
  }

  function pickTemplate(name: string) {
    const tpl = approved.find((x) => x.name === name)
    setForm((f) => ({
      ...f,
      template_name: name,
      template_language: tpl?.language || 'pt_BR',
      variables: Array(varCount(tpl)).fill('').map((_, i) => f.variables[i] || ''),
    }))
  }

  async function save(body: Form, id: string | 'new') {
    setSaving(true)
    setFormError('')
    try {
      if (id === 'new') await api.post('/whatsapp/followup-rules', body)
      else await api.put(`/whatsapp/followup-rules/${id}`, body)
      setEditing(null)
      await load()
    } catch (err: any) {
      const detail = err.response?.data?.detail
      setFormError(typeof detail === 'string' ? detail : t('Erro ao salvar a regra.', 'Failed to save the rule.'))
    } finally {
      setSaving(false)
    }
  }

  async function toggle(rule: Rule) {
    const { id, sent_count: _a, skipped_count: _b, failed_count: _c, last_sent_at: _d, ...rest } = rule
    try {
      await api.put(`/whatsapp/followup-rules/${id}`, { ...rest, enabled: !rule.enabled })
      await load()
    } catch (err: any) {
      const detail = err.response?.data?.detail
      setError(typeof detail === 'string' ? detail : t('Erro ao atualizar a regra.', 'Failed to update the rule.'))
    }
  }

  async function remove(rule: Rule) {
    if (!confirm(t(`Excluir a regra "${rule.name}"?`, `Delete the rule "${rule.name}"?`))) return
    try {
      await api.delete(`/whatsapp/followup-rules/${rule.id}`)
      setRules((prev) => prev.filter((r) => r.id !== rule.id))
    } catch (err: any) {
      const detail = err.response?.data?.detail
      setError(typeof detail === 'string' ? detail : t('Erro ao excluir.', 'Failed to delete.'))
    }
  }

  const input = 'w-full px-3 py-2 bg-[#0f0820] border border-white/[0.08] text-[#e2e2e8] text-sm rounded-lg focus:border-indigo-500 focus:outline-none'

  return (
    <div>
      <div className="flex items-start gap-3 bg-violet-900/10 border border-violet-500/20 rounded-xl px-4 py-3 mb-4">
        <Info size={16} className="text-violet-400 shrink-0 mt-0.5" />
        <p className="text-[12px] text-violet-200/80 leading-relaxed">
          {t(
            'O follow-up automático funciona no WhatsApp: se o cliente não responder a um template em X dias, o sistema envia outro template aprovado — só para contatos com opt-in e no máximo uma vez por envio. No Instagram não é possível: a Meta só permite mensagens até 24h depois da última mensagem do cliente.',
            "Automatic follow-up works on WhatsApp: if the customer doesn't reply to a template within X days, the system sends another approved template — only to opted-in contacts and at most once per message. It isn't possible on Instagram: Meta only allows messages within 24 hours of the customer's last message.",
          )}
        </p>
        <HelpLink section="follow-up" className="shrink-0 whitespace-nowrap" />
      </div>

      <div className="flex items-center justify-between mb-3">
        <p className="text-sm font-semibold text-[#e2e2e8]">{t('Regras de follow-up', 'Follow-up rules')}</p>
        <button
          onClick={openNew}
          disabled={!!error && rules.length === 0}
          className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm font-semibold rounded-lg"
        >
          <Plus size={14} /> {t('Nova regra', 'New rule')}
        </button>
      </div>

      {error && <div className="mb-3 bg-red-900/20 border border-red-500/20 text-red-400 text-xs rounded-lg px-4 py-2.5">{error}</div>}

      {loading ? (
        <p className="text-center text-[#555] text-sm py-10">{t('Carregando…', 'Loading…')}</p>
      ) : rules.length === 0 ? (
        <div className="bg-[#170e2c] rounded-xl border border-white/[0.06] p-10 text-center">
          <Repeat size={22} className="text-indigo-400 mx-auto mb-3" />
          <p className="text-[#e2e2e8] text-sm font-medium mb-1">{t('Nenhuma regra ainda', 'No rules yet')}</p>
          <p className="text-[#555] text-xs">{t('Crie uma regra para reenviar automaticamente para quem não respondeu.', "Create a rule to automatically follow up with people who didn't reply.")}</p>
        </div>
      ) : (
        <div className="space-y-2">
          {rules.map((r) => (
            <div key={r.id} className="bg-[#170e2c] rounded-xl border border-white/[0.06] p-4">
              <div className="flex items-start gap-3">
                <button
                  onClick={() => toggle(r)}
                  title={r.enabled ? t('Ativa — clique para pausar', 'Active — click to pause') : t('Pausada — clique para ativar', 'Paused — click to activate')}
                  className={`mt-0.5 w-10 h-5 rounded-full relative transition-colors shrink-0 ${r.enabled ? 'bg-indigo-500' : 'bg-white/[0.1]'}`}
                >
                  <span className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-all ${r.enabled ? 'left-5' : 'left-0.5'}`} />
                </button>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-[#e2e2e8]">{r.name}</p>
                  <p className="text-[12px] text-[#8a8a9e] mt-0.5">
                    {t(`Após ${r.delay_days} dia(s) sem resposta a`, `After ${r.delay_days} day(s) without a reply to`)}{' '}
                    <b className="text-[#c0c0d0]">{r.trigger_template || t('qualquer template', 'any template')}</b>{' '}
                    → {t('envia', 'sends')} <b className="text-[#c0c0d0]">{r.template_name}</b>
                  </p>
                  <p className="text-[11px] text-[#555] mt-1">
                    {t(`Entre ${r.send_hour_start}h e ${r.send_hour_end}h (Brasília)`, `Between ${r.send_hour_start}:00 and ${r.send_hour_end}:00 (Brasília time)`)}
                    {' · '}{t('enviados', 'sent')}: <span className="text-emerald-400">{r.sent_count}</span>
                    {' · '}{t('pulados (sem opt-in)', 'skipped (no opt-in)')}: {r.skipped_count}
                    {r.failed_count > 0 && <> · <span className="text-red-400">{t('falhas', 'failures')}: {r.failed_count}</span></>}
                    {r.last_sent_at && <> · {t('último', 'last')}: {new Date(r.last_sent_at).toLocaleString(locale)}</>}
                  </p>
                </div>
                <button onClick={() => openEdit(r)} title={t('Editar', 'Edit')} className="p-1.5 bg-white/[0.04] text-[#8a8a9e] hover:text-white rounded-lg">
                  <Pencil size={13} />
                </button>
                <button onClick={() => remove(r)} title={t('Excluir', 'Delete')} className="p-1.5 bg-red-900/20 text-red-400 hover:bg-red-900/40 rounded-lg">
                  <Trash2 size={13} />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {editing && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm px-4">
          <div className="bg-[#170e2c] border border-white/[0.08] rounded-2xl p-6 w-full max-w-md max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-base font-semibold text-white">
                {editing === 'new' ? t('Nova regra de follow-up', 'New follow-up rule') : t('Editar regra', 'Edit rule')}
              </h3>
              <button onClick={() => setEditing(null)} className="text-[#444] hover:text-[#888]"><X size={18} /></button>
            </div>

            {formError && <div className="mb-3 bg-red-900/20 border border-red-500/20 text-red-400 text-xs rounded-lg px-4 py-2.5">{formError}</div>}

            <div className="space-y-3">
              <div>
                <label className="block text-[11px] text-[#666] mb-1">{t('Nome', 'Name')}</label>
                <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className={input} />
              </div>

              <div>
                <label className="block text-[11px] text-[#666] mb-1">{t('Quando o cliente não responder a', 'When the customer does not reply to')}</label>
                <select
                  value={form.trigger_template ?? ''}
                  onChange={(e) => setForm({ ...form, trigger_template: e.target.value || null })}
                  className={input}
                >
                  <option value="">{t('Qualquer template enviado', 'Any template sent')}</option>
                  {templates.map((tpl) => <option key={tpl.name} value={tpl.name}>{tpl.name}</option>)}
                </select>
              </div>

              <div>
                <label className="block text-[11px] text-[#666] mb-1">{t('Esperar', 'Wait')}</label>
                <select value={form.delay_days} onChange={(e) => setForm({ ...form, delay_days: parseInt(e.target.value) })} className={input}>
                  {Array.from({ length: 13 }, (_, i) => i + 1).map((d) => (
                    <option key={d} value={d}>{t(`${d} dia(s) sem resposta`, `${d} day(s) without a reply`)}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-[11px] text-[#666] mb-1">{t('Enviar o template (somente aprovados)', 'Send the template (approved only)')}</label>
                <select value={form.template_name} onChange={(e) => pickTemplate(e.target.value)} className={input}>
                  <option value="" disabled>{t('Escolha um template', 'Choose a template')}</option>
                  {approved.map((tpl) => <option key={tpl.name} value={tpl.name}>{tpl.name} ({tpl.language})</option>)}
                </select>
                {form.template_name && (
                  <p className="text-[11px] text-[#555] mt-1.5">{bodyOf(approved.find((x) => x.name === form.template_name))}</p>
                )}
              </div>

              {form.variables.map((v, i) => (
                <div key={i}>
                  <label className="block text-[11px] text-[#666] mb-1">{t('Variável', 'Variable')} {`{{${i + 1}}}`}</label>
                  <input
                    value={v}
                    onChange={(e) => setForm({ ...form, variables: form.variables.map((x, j) => (j === i ? e.target.value : x)) })}
                    className={input}
                  />
                </div>
              ))}

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[11px] text-[#666] mb-1">{t('Enviar a partir de', 'Send from')}</label>
                  <select value={form.send_hour_start} onChange={(e) => setForm({ ...form, send_hour_start: parseInt(e.target.value) })} className={input}>
                    {hours.slice(0, 24).map((h) => <option key={h} value={h}>{h}h</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-[11px] text-[#666] mb-1">{t('Até', 'Until')}</label>
                  <select value={form.send_hour_end} onChange={(e) => setForm({ ...form, send_hour_end: parseInt(e.target.value) })} className={input}>
                    {hours.slice(1).map((h) => <option key={h} value={h}>{h}h</option>)}
                  </select>
                </div>
              </div>
              <p className="text-[10px] text-[#555]">{t('Horário de Brasília. Fora dessa janela os envios esperam o próximo dia.', 'Brasília time. Outside this window, messages wait for the next day.')}</p>

              <label className="flex items-center gap-2 text-sm text-[#c0c0d0] cursor-pointer">
                <input type="checkbox" checked={form.enabled} onChange={(e) => setForm({ ...form, enabled: e.target.checked })} className="accent-indigo-500" />
                {t('Regra ativa', 'Rule active')}
              </label>
            </div>

            <div className="flex gap-2 mt-5">
              <button onClick={() => setEditing(null)} className="flex-1 py-2.5 border border-white/[0.08] text-[#666] hover:text-white text-sm rounded-lg">
                {t('Cancelar', 'Cancel')}
              </button>
              <button
                onClick={() => save(form, editing)}
                disabled={saving || !form.name.trim() || !form.template_name}
                className="flex-1 py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm font-semibold rounded-lg"
              >
                {saving ? t('Salvando…', 'Saving…') : t('Salvar', 'Save')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
