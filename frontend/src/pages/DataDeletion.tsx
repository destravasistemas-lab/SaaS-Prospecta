import { useEffect, useState, type FormEvent } from 'react'
import { useSearchParams } from 'react-router-dom'
import { BRANDING } from '../config/branding'
import LegalLayout, { LegalSection } from '../components/LegalLayout'
import api from '../services/api'
import { useI18n } from '../i18n'

interface DeletionStatus {
  confirmation_code: string
  status: string
  requested_at: string | null
  completed_at: string | null
  message: string
}

export default function DataDeletion() {
  const { t, locale } = useI18n()
  const [params] = useSearchParams()
  const [code, setCode] = useState(params.get('code') || '')
  const [status, setStatus] = useState<DeletionStatus | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function lookup(c: string) {
    if (!c.trim()) return
    setLoading(true)
    setError('')
    setStatus(null)
    try {
      const { data } = await api.get<DeletionStatus>('/privacy/data-deletion-status', { params: { id: c.trim() } })
      setStatus(data)
    } catch (err: any) {
      setError(err.response?.data?.detail || t('Não foi possível consultar o status.', 'Could not look up the status.'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    const c = params.get('code')
    if (c) lookup(c)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    lookup(code)
  }

  const fmt = (iso: string | null) => (iso ? new Date(iso).toLocaleString(locale) : '—')

  return (
    <LegalLayout title={t('Exclusão de Dados', 'Data Deletion')}>
      <LegalSection title={t('Como excluir seus dados', 'How to delete your data')}>
        <ol className="list-decimal list-inside space-y-2">
          <li>
            <strong className="text-[#cbd5e1]">{t('Pelo Facebook ou Instagram', 'From Facebook or Instagram')}:</strong>{' '}
            {t('acesse Configurações → Apps e sites (ou Segurança → Apps e sites no Instagram), selecione', 'go to Settings → Apps and websites (or Security → Apps and websites on Instagram), select')}{' '}
            {BRANDING.name} {t('e clique em Remover. A Meta nos envia o pedido e excluímos automaticamente seus tokens, identificadores e dados associados. Você recebe um código de confirmação para acompanhar aqui.', 'and click Remove. Meta sends us the request and we automatically delete your tokens, identifiers and associated data. You get a confirmation code to track it here.')}
          </li>
          <li>
            <strong className="text-[#cbd5e1]">{t('Pelo app', 'In the app')}:</strong>{' '}
            {t('em Conexões Meta, clique em Desconectar em cada integração. O acesso é revogado na Meta e o token é apagado.', 'in Meta Connections, click Disconnect on each integration. Access is revoked at Meta and the token is deleted.')}
          </li>
          <li>
            <strong className="text-[#cbd5e1]">{t('Por e-mail', 'By email')}:</strong>{' '}
            {t('envie um pedido para', 'send a request to')}{' '}
            <a href={`mailto:${BRANDING.supportEmail}`} className="text-sky-400 underline">{BRANDING.supportEmail}</a>{' '}
            {t('a partir do e-mail da conta. Concluímos em até 30 dias.', 'from your account email. We complete it within 30 days.')}
          </li>
        </ol>
      </LegalSection>

      <LegalSection title={t('Consultar status do pedido', 'Check request status')}>
        <form onSubmit={onSubmit} className="flex flex-col sm:flex-row gap-2">
          <input
            value={code}
            onChange={(e) => setCode(e.target.value)}
            placeholder={t('Código de confirmação', 'Confirmation code')}
            className="flex-1 bg-white/[0.03] border border-white/10 rounded-lg px-3 py-2 text-sm text-white placeholder-[#475569] focus:outline-none focus:border-sky-500/50"
          />
          <button
            type="submit"
            disabled={loading || !code.trim()}
            className="px-4 py-2 rounded-lg bg-sky-500 hover:bg-sky-400 text-white text-sm font-medium disabled:opacity-50"
          >
            {loading ? t('Consultando…', 'Checking…') : t('Consultar', 'Check')}
          </button>
        </form>
        {error && <p className="text-red-400">{error}</p>}
        {status && (
          <div className="rounded-lg border border-white/10 bg-white/[0.02] p-4 space-y-1">
            <p><span className="text-[#64748b]">{t('Código', 'Code')}:</span> <span className="font-mono text-white">{status.confirmation_code}</span></p>
            <p>
              <span className="text-[#64748b]">Status:</span>{' '}
              <span className={status.status === 'completed' ? 'text-emerald-400' : 'text-amber-400'}>
                {status.status === 'completed' ? t('Concluído', 'Completed') : t('Recebido', 'Received')}
              </span>
            </p>
            <p><span className="text-[#64748b]">{t('Solicitado em', 'Requested at')}:</span> {fmt(status.requested_at)}</p>
            <p><span className="text-[#64748b]">{t('Concluído em', 'Completed at')}:</span> {fmt(status.completed_at)}</p>
            <p className="text-[#cbd5e1] pt-1">{status.message}</p>
          </div>
        )}
      </LegalSection>
    </LegalLayout>
  )
}
