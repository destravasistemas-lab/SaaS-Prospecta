import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import api, { apiError } from '../services/api'
import { BRANDING } from '../config/branding'
import { useI18n, type Lang } from '../i18n'
import HelpLink from '../components/HelpLink'

export default function Configuracoes() {
  const { t, lang, setLang } = useI18n()
  const tenantId = localStorage.getItem('tenant_id') || ''
  const [brandName, setBrandName] = useState('')
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    api.get('/auth/me').then(({ data }) => setBrandName(data?.brand_name || '')).catch(() => {})
  }, [])

  async function saveBrand(e: React.FormEvent) {
    e.preventDefault()
    if (!brandName.trim() || !tenantId) return
    setSaving(true)
    setMessage('')
    setError('')
    try {
      await api.put(`/accounts/${tenantId}`, { brand_name: brandName.trim() })
      setMessage(t('Salvo!', 'Saved!'))
    } catch (err: any) {
      setError(apiError(err, t('Erro ao salvar.', 'Failed to save.')))
    } finally {
      setSaving(false)
    }
  }

  const input = 'w-full px-4 py-2 bg-field border border-white/[0.08] text-ink rounded-lg focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500 focus:outline-none placeholder-ink-5'

  return (
    <div>
      <h2 className="text-2xl font-bold text-ink mb-6">{t('Configurações', 'Settings')}</h2>
      <HelpLink section="privacidade" className="mb-4 block" />
      <div className="max-w-lg space-y-6">
        <form onSubmit={saveBrand} className="bg-card rounded-xl border border-white/[0.06] p-6 space-y-4">
          <h3 className="text-sm font-semibold text-ink">{t('Empresa', 'Business')}</h3>
          <div>
            <label className="block text-sm font-medium text-ink-4 mb-1">{t('Nome da marca', 'Brand name')}</label>
            <input value={brandName} onChange={(e) => setBrandName(e.target.value)} placeholder={t('Minha Marca', 'My Brand')} className={input} />
          </div>
          {message && <p className="text-xs text-emerald-400">{message}</p>}
          {error && <p className="text-xs text-red-400">{error}</p>}
          <button
            type="submit"
            disabled={saving || !brandName.trim()}
            className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm font-semibold rounded-lg"
          >
            {saving ? t('Salvando…', 'Saving…') : t('Salvar', 'Save')}
          </button>
        </form>

        <div className="bg-card rounded-xl border border-white/[0.06] p-6 space-y-3">
          <h3 className="text-sm font-semibold text-ink">{t('Idioma da interface', 'Interface language')}</h3>
          <select value={lang} onChange={(e) => setLang(e.target.value as Lang)} className={input}>
            <option value="pt">Português (Brasil)</option>
            <option value="en">English (US)</option>
          </select>
        </div>

        <div className="bg-card rounded-xl border border-white/[0.06] p-6 space-y-3">
          <h3 className="text-sm font-semibold text-ink">{t('Privacidade e dados', 'Privacy & data')}</h3>
          <p className="text-xs text-ink-4">
            {t(
              'Para revogar o acesso às suas contas da Meta, use Desconectar em Conexões Meta. Para excluir todos os dados da sua conta, siga as instruções da página de Exclusão de Dados.',
              'To revoke access to your Meta accounts, use Disconnect on Meta Connections. To delete all data in your account, follow the instructions on the Data Deletion page.',
            )}
          </p>
          <div className="flex flex-wrap gap-x-4 gap-y-2 text-xs">
            <Link to="/app/conexao" className="text-violet-400 hover:text-violet-300">{t('Conexões Meta', 'Meta Connections')}</Link>
            <Link to="/data-deletion" className="text-violet-400 hover:text-violet-300">{t('Exclusão de Dados', 'Data Deletion')}</Link>
            <Link to="/privacy" className="text-violet-400 hover:text-violet-300">{t('Política de Privacidade', 'Privacy Policy')}</Link>
            <Link to="/terms" className="text-violet-400 hover:text-violet-300">{t('Termos de Serviço', 'Terms of Service')}</Link>
            <a href={`mailto:${BRANDING.supportEmail}`} className="text-violet-400 hover:text-violet-300">{BRANDING.supportEmail}</a>
          </div>
        </div>

        <div className="pt-2">
          <p className="text-xs text-ink-5">{t('Versão', 'Version')}: 1.0.0</p>
        </div>
      </div>
    </div>
  )
}
