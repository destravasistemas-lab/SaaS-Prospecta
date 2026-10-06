import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import api from '../services/api'
import { BRANDING } from '../config/branding'
import { useI18n, type Lang } from '../i18n'

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
      setError(err.response?.data?.detail || t('Erro ao salvar.', 'Failed to save.'))
    } finally {
      setSaving(false)
    }
  }

  const input = 'w-full px-4 py-2 bg-[#0a0a0f] border border-white/[0.08] text-[#e2e2e8] rounded-lg focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500 focus:outline-none placeholder-[#333]'

  return (
    <div>
      <h2 className="text-2xl font-bold text-[#e2e2e8] mb-6">{t('Configurações', 'Settings')}</h2>
      <div className="max-w-lg space-y-6">
        <form onSubmit={saveBrand} className="bg-[#111118] rounded-xl border border-white/[0.06] p-6 space-y-4">
          <h3 className="text-sm font-semibold text-[#e2e2e8]">{t('Empresa', 'Business')}</h3>
          <div>
            <label className="block text-sm font-medium text-[#666] mb-1">{t('Nome da marca', 'Brand name')}</label>
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

        <div className="bg-[#111118] rounded-xl border border-white/[0.06] p-6 space-y-3">
          <h3 className="text-sm font-semibold text-[#e2e2e8]">{t('Idioma da interface', 'Interface language')}</h3>
          <select value={lang} onChange={(e) => setLang(e.target.value as Lang)} className={input}>
            <option value="pt">Português (Brasil)</option>
            <option value="en">English (US)</option>
          </select>
        </div>

        <div className="bg-[#111118] rounded-xl border border-white/[0.06] p-6 space-y-3">
          <h3 className="text-sm font-semibold text-[#e2e2e8]">{t('Privacidade e dados', 'Privacy & data')}</h3>
          <p className="text-xs text-[#666]">
            {t(
              'Para revogar o acesso às suas contas da Meta, use Desconectar em Conexões Meta. Para excluir todos os dados da sua conta, siga as instruções da página de Exclusão de Dados.',
              'To revoke access to your Meta accounts, use Disconnect on Meta Connections. To delete all data in your account, follow the instructions on the Data Deletion page.',
            )}
          </p>
          <div className="flex flex-wrap gap-x-4 gap-y-2 text-xs">
            <Link to="/app/conexao" className="text-sky-400 hover:text-sky-300">{t('Conexões Meta', 'Meta Connections')}</Link>
            <Link to="/data-deletion" className="text-sky-400 hover:text-sky-300">{t('Exclusão de Dados', 'Data Deletion')}</Link>
            <Link to="/privacy" className="text-sky-400 hover:text-sky-300">{t('Política de Privacidade', 'Privacy Policy')}</Link>
            <Link to="/terms" className="text-sky-400 hover:text-sky-300">{t('Termos de Serviço', 'Terms of Service')}</Link>
            <a href={`mailto:${BRANDING.supportEmail}`} className="text-sky-400 hover:text-sky-300">{BRANDING.supportEmail}</a>
          </div>
        </div>

        <div className="pt-2">
          <p className="text-xs text-[#444]">{t('Versão', 'Version')}: 1.0.0</p>
        </div>
      </div>
    </div>
  )
}
