import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../services/api';
import { useI18n, LanguageToggle } from '../i18n';

interface Plan {
  id: string;
  name: string;
  value: number;
  description: string;
  features: string[];
  interval_days: number;
}

const PLAN_EN: Record<string, { name: string; description: string; features: string[] }> = {
  free: { name: 'Free', description: 'Perfect to get started', features: ['Up to 5 campaigns', 'Basic chat', 'Dashboard'] },
  starter: { name: 'Starter', description: 'For small businesses', features: ['Up to 50 campaigns', 'Email support', 'Basic automations'] },
  pro: {
    name: 'Professional',
    description: 'For agencies and growing businesses',
    features: ['Unlimited campaigns', 'Priority support', 'Advanced automations', 'APIs', 'Manage up to 10 clients', 'Access client accounts'],
  },
  premium: {
    name: 'Premium',
    description: 'For large operations',
    features: ['Everything unlimited', '24/7 support', 'Advanced analytics', 'Dedicated manager', 'Unlimited clients'],
  },
}

interface Subscription {
  id: string;
  plan: string;
  status: string;
  is_active: boolean;
}

export default function Pricing() {
  const [plans, setPlans] = useState<Plan[]>([]);
  const [currentSubscription, setCurrentSubscription] = useState<Subscription | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedPlan, setSelectedPlan] = useState<string | null>(null);
  const navigate = useNavigate();
  const { t, lang } = useI18n();
  const localized = (plan: Plan): Plan =>
    lang === 'en' && PLAN_EN[plan.id] ? { ...plan, ...PLAN_EN[plan.id] } : plan;

  useEffect(() => {
    fetchPlans();
    fetchCurrentSubscription();
  }, []);

  const fetchPlans = async () => {
    try {
      const response = await api.get('/payments/plans');
      setPlans(response.data);
    } catch (error) {
      console.error('Error fetching plans:', error);
    }
  };

  const fetchCurrentSubscription = async () => {
    const token = localStorage.getItem('access_token');
    if (!token) {
      setLoading(false);
      return;
    }
    try {
      const response = await api.get('/payments/current');
      setCurrentSubscription(response.data);
    } catch (error) {
      console.error('Error fetching subscription:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSubscribe = async (planId: string) => {
    const token = localStorage.getItem('access_token');
    if (!token) {
      navigate('/login');
      return;
    }
    setSelectedPlan(planId);
    try {
      const response = await api.post('/payments/subscribe', {
        plan: planId,
      });

      if (response.data.payment_link) {
        window.location.href = response.data.payment_link;
      } else {
        const p = plans.find(p => p.id === planId);
        alert(t('Bem-vindo ao plano ', 'Welcome to the ') + (p ? localized(p).name : '') + t('!', ' plan!'));
        fetchCurrentSubscription();
      }
    } catch (error) {
      console.error('Error subscribing:', error);
      alert(t('Erro ao criar assinatura. Tente novamente.', 'Failed to create subscription. Please try again.'));
    } finally {
      setSelectedPlan(null);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-[#0a0a0f]">
        <div className="text-[#555]">{t('Carregando planos...', 'Loading plans...')}</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#0a0a0f] py-12 px-4">
      <div className="max-w-7xl mx-auto">
        <div className="flex justify-between items-center mb-6">
          <button onClick={() => navigate(-1)} className="text-sm text-[#64748b] hover:text-white">← {t('Voltar', 'Back')}</button>
          <LanguageToggle compact />
        </div>
        <div className="text-center mb-12">
          <h1 className="text-4xl font-bold text-white mb-4">{t('Planos e Preços', 'Plans & Pricing')}</h1>
          <p className="text-[#555]">
            {t('Escolha o plano perfeito para suas necessidades', 'Choose the right plan for your needs')}
          </p>
        </div>

        {currentSubscription && (
          <div className="mb-8 p-4 bg-green-900/20 border border-green-500/20 rounded-lg text-center">
            <p className="text-green-400">
              ✓ {t('Você está no plano', "You're on the")}{' '}
              <strong>{(() => { const p = plans.find(p => p.id === currentSubscription.plan); return p ? localized(p).name : '' })()}</strong>
              {t('', ' plan')}
            </p>
          </div>
        )}

        <div className="grid md:grid-cols-4 gap-6 mb-12">
          {plans.map(localized).map((plan) => (
            <div
              key={plan.id}
              className={`relative rounded-xl border overflow-hidden transition-all duration-300 ${
                currentSubscription?.plan === plan.id
                  ? 'border-indigo-500 shadow-xl shadow-indigo-900/20'
                  : 'border-white/[0.06] hover:border-white/[0.12]'
              }`}
            >
              <div className="bg-[#111118] p-6 h-full flex flex-col">
                {plan.id === 'premium' && (
                  <div className="absolute top-0 right-0 bg-indigo-600 text-white px-3 py-1 text-xs font-bold rounded-bl-lg">
                    {t('MAIS POPULAR', 'MOST POPULAR')}
                  </div>
                )}

                {currentSubscription?.plan === plan.id && (
                  <div className="absolute top-0 left-0 bg-green-500 text-white px-3 py-1 text-xs font-bold rounded-br-lg">
                    {t('ATUAL', 'CURRENT')}
                  </div>
                )}

                <h3 className="text-2xl font-bold text-white mb-2">{plan.name}</h3>
                <p className="text-[#555] text-sm mb-4">{plan.description}</p>

                <div className="mb-6">
                  <div className="text-4xl font-bold text-white">
                    R$ {plan.value === 0 ? '0' : plan.value.toFixed(0)}
                  </div>
                  <p className="text-[#444] text-sm">
                    {plan.value > 0 ? t('/mês', '/month') : t('Para sempre', 'Forever')}
                  </p>
                </div>

                <div className="mb-8 flex-grow">
                  <ul className="space-y-3">
                    {plan.features.map((feature, idx) => (
                      <li key={idx} className="flex items-start">
                        <span className="text-green-400 mr-3">✓</span>
                        <span className="text-[#666] text-sm">{feature}</span>
                      </li>
                    ))}
                  </ul>
                </div>

                <button
                  onClick={() => handleSubscribe(plan.id)}
                  disabled={
                    selectedPlan !== null ||
                    (currentSubscription?.plan === plan.id &&
                      currentSubscription?.is_active)
                  }
                  className={`w-full py-3 rounded-lg font-semibold transition-all duration-200 ${
                    currentSubscription?.plan === plan.id &&
                    currentSubscription?.is_active
                      ? 'bg-white/[0.04] text-[#555] cursor-not-allowed'
                      : selectedPlan === plan.id
                      ? 'bg-white/[0.04] text-[#666] cursor-wait'
                      : plan.id === 'premium'
                      ? 'bg-indigo-600 text-white hover:bg-indigo-500'
                      : 'bg-indigo-600/10 text-indigo-400 hover:bg-indigo-600/20'
                  }`}
                >
                  {selectedPlan === plan.id
                    ? t('Processando...', 'Processing...')
                    : currentSubscription?.plan === plan.id &&
                      currentSubscription?.is_active
                    ? t('Plano Atual', 'Current Plan')
                    : t('Escolher', 'Choose')}
                </button>
              </div>
            </div>
          ))}
        </div>

        <div className="bg-[#111118] rounded-xl border border-white/[0.06] p-8 max-w-2xl mx-auto">
          <h2 className="text-2xl font-bold text-white mb-6">{t('Perguntas Frequentes', 'FAQ')}</h2>
          <div className="space-y-4">
            <div>
              <h3 className="text-[#e2e2e8] font-semibold mb-2">
                {t('Posso mudar de plano a qualquer momento?', 'Can I change plans at any time?')}
              </h3>
              <p className="text-[#555]">
                {t('Sim! Você pode fazer upgrade ou downgrade a qualquer momento. A mudança será refletida no próximo ciclo de cobrança.', 'Yes! You can upgrade or downgrade at any time. The change applies to the next billing cycle.')}
              </p>
            </div>
            <div>
              <h3 className="text-[#e2e2e8] font-semibold mb-2">
                {t('Há período de teste?', 'Is there a free trial?')}
              </h3>
              <p className="text-[#555]">
                {t('Sim, todos os planos pagos têm 7 dias de teste gratuito, sem cartão de crédito.', 'Yes, all paid plans include a 7-day free trial, no credit card required.')}
              </p>
            </div>
            <div>
              <h3 className="text-[#e2e2e8] font-semibold mb-2">
                {t('O que acontece se eu cancelar?', 'What happens if I cancel?')}
              </h3>
              <p className="text-[#555]">
                {t('Você pode cancelar a qualquer momento. O acesso permanece até o fim do período pago.', 'You can cancel at any time. Access remains until the end of the paid period.')}
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
