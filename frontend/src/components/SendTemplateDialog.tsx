import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { X } from 'lucide-react'
import api from '../services/api'
import { useI18n } from '../i18n'
import OptInRisk from './OptInRisk'

interface Tpl {
  name: string
  language: string
  status?: string
  components?: { type: string; text?: string }[]
}

const bodyOf = (tpl: Tpl) => tpl.components?.find((c) => c.type === 'BODY')?.text || ''

/**
 * Envia um template aprovado para um contato: do chat (número + conversa) ou da lista
 * de Leads (só o lead; o backend usa o telefone dele e cria a conversa se precisar).
 */
export default function SendTemplateDialog({ to, conversationId, leadId, recipient, warnNoNumber, onClose, onSent }: {
  to?: string
  conversationId?: string
  leadId?: string
  recipient?: string
  warnNoNumber?: boolean
  onClose: () => void
  onSent?: () => void
}) {
  const { t } = useI18n()
  const [tpls, setTpls] = useState<Tpl[] | null>(null)
  const [picked, setPicked] = useState<Tpl | null>(null)
  const [vars, setVars] = useState<string[]>([])
  const [sending, setSending] = useState(false)
  const [optIn, setOptIn] = useState(false)
  const [risk, setRisk] = useState<string | null>(null)
  const [riskOk, setRiskOk] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [sent, setSent] = useState(false)

  useEffect(() => {
    api.get('/whatsapp/templates')
      .then(({ data }) => setTpls(Array.isArray(data) ? data : []))
      .catch(() => setTpls([]))
  }, [])

  function pick(tpl: Tpl) {
    setPicked(tpl)
    setError(null)
    const nums = [...bodyOf(tpl).matchAll(/\{\{(\d+)\}\}/g)].map((m) => parseInt(m[1]))
    setVars(Array(nums.length ? Math.max(...nums) : 0).fill(''))
  }

  function back() {
    setPicked(null)
    setRisk(null)
    setRiskOk(false)
    setError(null)
  }

  async function send() {
    if (!picked) return
    setSending(true)
    setError(null)
    try {
      await api.post('/whatsapp/send-template', {
        to: to || '',
        template_name: picked.name,
        language: picked.language || 'pt_BR',
        variables: vars,
        conversation_id: conversationId,
        lead_id: leadId,
        opt_in_confirmed: optIn,
        accept_no_opt_in_risk: riskOk,
      })
      setSent(true)
      window.setTimeout(() => (onSent ?? onClose)(), 900)
    } catch (err: any) {
      const detail = err?.response?.data?.detail
      if (detail?.can_accept_risk) {
        setRisk(detail.message)
        return
      }
      setError(detail?.message || (typeof detail === 'string' ? detail : t('Erro ao enviar template.', 'Failed to send template.')))
    } finally {
      setSending(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center max-lg:[align-items:safe_center] max-lg:overflow-y-auto max-lg:py-4 bg-black/70 backdrop-blur-sm px-4">
      <div className="bg-card border border-white/[0.08] rounded-2xl p-6 w-full max-w-md max-h-[85vh] overflow-y-auto">
        <div className="flex items-start justify-between gap-3 mb-4">
          <div className="min-w-0">
            <h3 className="text-base font-semibold text-white">{t('Enviar template', 'Send template')}</h3>
            {recipient && <p className="text-xs text-ink-4 mt-0.5 truncate">{t('Para', 'To')} {recipient}</p>}
          </div>
          <button onClick={onClose} className="text-ink-5 hover:text-ink-3 shrink-0"><X size={18} /></button>
        </div>

        {warnNoNumber && (
          <div className="bg-amber-900/15 border border-amber-500/20 text-amber-400/90 text-[11px] rounded-lg px-3 py-2 mb-3">
            {t('Número do cliente não identificado nesta conversa — o envio pode falhar.', 'Customer number not identified in this conversation — sending may fail.')}
          </div>
        )}

        {sent ? (
          <p className="text-emerald-400 text-sm text-center py-6">{t('Template enviado.', 'Template sent.')}</p>
        ) : !picked ? (
          tpls === null ? (
            <p className="text-ink-4 text-sm text-center py-6">{t('Carregando templates…', 'Loading templates…')}</p>
          ) : tpls.length === 0 ? (
            <p className="text-ink-4 text-sm text-center py-6">
              {t('Nenhum template. Crie na página', 'No templates. Create one on the')}{' '}
              <Link to="/app/templates" className="text-indigo-400">{t('Templates', 'Templates')}</Link>{t('.', ' page.')}
            </p>
          ) : (
            <div className="space-y-1.5">
              {tpls.map((tpl) => (
                <button
                  key={`${tpl.name}-${tpl.language}`}
                  onClick={() => pick(tpl)}
                  className="w-full text-left px-3 py-2.5 rounded-lg bg-field border border-white/[0.06] hover:border-indigo-500/40 transition-colors"
                >
                  <p className="text-sm font-medium text-ink">{tpl.name}</p>
                  <p className="text-xs text-ink-4 truncate">{bodyOf(tpl)}</p>
                </button>
              ))}
            </div>
          )
        ) : (
          <div>
            <div className="bg-field border border-white/[0.06] rounded-lg p-3 mb-3">
              <p className="text-sm font-medium text-ink">{picked.name}</p>
              <p className="text-xs text-ink-4 mt-1 whitespace-pre-line">{bodyOf(picked)}</p>
            </div>
            {vars.length > 0 && (
              <div className="space-y-2 mb-3">
                {vars.map((v, i) => (
                  <div key={i}>
                    <label className="block text-[11px] text-ink-4 mb-1">{t('Variável', 'Variable')} {`{{${i + 1}}}`}</label>
                    <input
                      value={v}
                      onChange={(e) => setVars((prev) => prev.map((x, j) => (j === i ? e.target.value : x)))}
                      className="w-full px-3 py-2 bg-field border border-white/[0.08] text-ink text-sm rounded-lg focus:border-indigo-500 focus:outline-none"
                    />
                  </div>
                ))}
              </div>
            )}
            <label className="flex items-start gap-2 mb-3 text-[11px] text-ink-3 cursor-pointer">
              <input type="checkbox" checked={optIn} onChange={(e) => setOptIn(e.target.checked)} className="mt-0.5 accent-indigo-500" />
              <span>
                {t(
                  'Confirmo que este contato aceitou receber mensagens da empresa no WhatsApp (opt-in). O consentimento fica registrado no lead.',
                  'I confirm this contact agreed to receive messages from the business on WhatsApp (opt-in). The consent is recorded on the lead.',
                )}
              </span>
            </label>
            {risk && !optIn && (
              <OptInRisk
                title={t('Este contato não tem opt-in', 'This contact has no opt-in')}
                message={risk}
                checked={riskOk}
                onChange={setRiskOk}
                label={t('Entendo os riscos e quero enviar mesmo assim.', 'I understand the risks and want to send anyway.')}
              />
            )}
            {error && (
              <div className="bg-red-900/20 border border-red-500/20 text-red-300 text-xs rounded-lg px-3 py-2 mb-3">{error}</div>
            )}
            <div className="flex gap-2">
              <button onClick={back} className="flex-1 py-2.5 border border-white/[0.08] text-ink-4 hover:text-white text-sm rounded-lg transition-colors">{t('Voltar', 'Back')}</button>
              <button onClick={send} disabled={sending || (!!risk && !optIn && !riskOk)} className="flex-1 py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm font-semibold rounded-lg transition-colors">
                {sending ? t('Enviando…', 'Sending…') : t('Enviar', 'Send')}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
