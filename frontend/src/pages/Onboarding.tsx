import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../services/api'
import { BRANDING } from '../config/branding'
import { useI18n, LanguageToggle } from '../i18n'

export default function Onboarding() {
  const { t } = useI18n()
  const options = [
    {
      id: 'autonomo',
      name: t('Autônomo', 'Business'),
      description: t('Para gerenciar o próprio negócio', 'To manage your own business'),
      features: [
        t('Conecte seu Instagram, WhatsApp e Ads', 'Connect your Instagram, WhatsApp and Ads'),
        t('Captação e atendimento de leads', 'Lead capture and customer service'),
        t('Automação por palavra-chave e DM', 'Keyword and DM automation'),
        t('Dashboard e métricas do seu negócio', 'Dashboard and business metrics'),
      ],
      icon: '🚀',
      featured: false,
    },
    {
      id: 'agencia',
      name: t('Agência', 'Agency'),
      description: t('Para gerenciar várias empresas-clientes', 'To manage multiple client businesses'),
      features: [
        t('Tudo do Autônomo, para cada cliente', 'Everything in Business, for each client'),
        t('Crie e gerencie contas de clientes', 'Create and manage client accounts'),
        t('Troque entre empresas num clique', 'Switch between businesses in one click'),
        t('Visão consolidada da agência', 'Consolidated agency view'),
      ],
      icon: '🏢',
      featured: true,
    },
  ]
  const navigate = useNavigate()
  const [loading, setLoading] = useState('')
  const [error, setError] = useState('')

  async function handleSelect(plan: string) {
    if (loading) return
    setLoading(plan)
    setError('')
    try {
      await api.post('/auth/onboarding/plan', { plan_type: plan })
      navigate('/app')
    } catch {
      setError(t('Erro ao selecionar. Tente novamente.', 'Selection failed. Please try again.'))
      setLoading('')
    }
  }

  return (
    <div className="min-h-screen bg-[#0a0a0f] flex flex-col">
      <div className="px-4 py-6">
        <div className="max-w-4xl mx-auto">
          <div className="flex items-center justify-between">
          <button
            onClick={() => navigate('/')}
            className="text-base font-semibold text-white hover:text-indigo-400 transition-colors"
          >
            {BRANDING.namePrefix}<span className="text-sky-400">{BRANDING.nameHighlight}</span>
          </button>
          <LanguageToggle compact />
          </div>
        </div>
      </div>

      <div className="flex-1 px-4 pb-16 flex items-center">
        <div className="max-w-4xl mx-auto w-full">
          <div className="text-center mb-8">
            <h2 className="text-3xl font-bold text-white mb-2">{t('Que tipo de conta?', 'What type of account?')}</h2>
            <p className="text-[#555] max-w-lg mx-auto">
              {t('Escolha como vai usar a plataforma. Você conecta Instagram, WhatsApp e Ads depois, na página', "Choose how you'll use the platform. You'll connect Instagram, WhatsApp and Ads next, on the")}{' '}
              <span className="text-[#888]">{t('Conexões Meta', 'Meta Connections')}</span>{t('.', ' page.')}
            </p>
          </div>

          {error && (
            <div className="max-w-md mx-auto mb-6 bg-red-900/20 border border-red-500/20 text-red-400 text-sm rounded-lg px-4 py-3 text-center">{error}</div>
          )}

          <div className="grid md:grid-cols-2 gap-6">
            {options.map((opt) => (
              <div
                key={opt.id}
                className={`rounded-xl border p-6 flex flex-col transition-all cursor-pointer hover:scale-[1.02] ${
                  opt.featured
                    ? 'bg-[#1a1850] border-indigo-500/40 shadow-xl shadow-indigo-900/20'
                    : 'bg-[#111118] border-white/[0.06] hover:border-indigo-500/30'
                }`}
                onClick={() => handleSelect(opt.id)}
              >
                {opt.featured && (
                  <span className="text-indigo-400 text-[10px] font-semibold bg-indigo-500/15 rounded-full px-3 py-1 w-fit mb-3">{t('Mais popular', 'Most popular')}</span>
                )}
                <div className="flex items-center gap-3 mb-3">
                  <span className="text-2xl">{opt.icon}</span>
                  <h4 className="text-xl font-bold text-white">{opt.name}</h4>
                </div>
                <p className={`text-sm mb-6 ${opt.featured ? 'text-indigo-300/60' : 'text-[#555]'}`}>{opt.description}</p>
                <ul className="space-y-3 mb-8 flex-1">
                  {opt.features.map((f) => (
                    <li key={f} className={`flex items-center gap-2 text-sm ${opt.featured ? 'text-indigo-200/70' : 'text-[#666]'}`}>
                      <span className="text-indigo-400">✓</span>
                      {f}
                    </li>
                  ))}
                </ul>
                <button
                  disabled={!!loading}
                  className={`w-full py-3 font-semibold rounded-xl transition-colors text-sm ${
                    opt.featured
                      ? 'bg-indigo-600 hover:bg-indigo-500 text-white'
                      : 'bg-indigo-600/10 hover:bg-indigo-600/20 text-indigo-400'
                  } disabled:opacity-50`}
                >
                  {loading === opt.id ? t('Entrando...', 'Loading...') : `${t('Continuar como', 'Continue as')} ${opt.name}`}
                </button>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
