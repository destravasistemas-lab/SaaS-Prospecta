import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../services/api';

interface Plan {
  id: string;
  name: string;
  value: number;
  description: string;
  features: string[];
  interval_days: number;
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
        alert('Bem-vindo ao plano ' + plans.find(p => p.id === planId)?.name + '!');
        fetchCurrentSubscription();
      }
    } catch (error) {
      console.error('Error subscribing:', error);
      alert('Erro ao criar assinatura. Tente novamente.');
    } finally {
      setSelectedPlan(null);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-[#0a0a0f]">
        <div className="text-[#555]">Carregando planos...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#0a0a0f] py-12 px-4">
      <div className="max-w-7xl mx-auto">
        <div className="text-center mb-12">
          <h1 className="text-4xl font-bold text-white mb-4">Planos e Preços</h1>
          <p className="text-[#555]">
            Escolha o plano perfeito para suas necessidades
          </p>
        </div>

        {currentSubscription && (
          <div className="mb-8 p-4 bg-green-900/20 border border-green-500/20 rounded-lg text-center">
            <p className="text-green-400">
              ✓ Você está no plano{' '}
              <strong>{plans.find(p => p.id === currentSubscription.plan)?.name}</strong>
            </p>
          </div>
        )}

        <div className="grid md:grid-cols-4 gap-6 mb-12">
          {plans.map((plan) => (
            <div
              key={plan.id}
              className={`rounded-xl border overflow-hidden transition-all duration-300 ${
                currentSubscription?.plan === plan.id
                  ? 'border-indigo-500 shadow-xl shadow-indigo-900/20'
                  : 'border-white/[0.06] hover:border-white/[0.12]'
              }`}
            >
              <div className="bg-[#111118] p-6 h-full flex flex-col">
                {plan.id === 'premium' && (
                  <div className="absolute top-0 right-0 bg-indigo-600 text-white px-3 py-1 text-xs font-bold rounded-bl-lg">
                    MAIS POPULAR
                  </div>
                )}

                {currentSubscription?.plan === plan.id && (
                  <div className="absolute top-0 left-0 bg-green-500 text-white px-3 py-1 text-xs font-bold rounded-br-lg">
                    ATUAL
                  </div>
                )}

                <h3 className="text-2xl font-bold text-white mb-2">{plan.name}</h3>
                <p className="text-[#555] text-sm mb-4">{plan.description}</p>

                <div className="mb-6">
                  <div className="text-4xl font-bold text-white">
                    R$ {plan.value === 0 ? '0' : plan.value.toFixed(0)}
                  </div>
                  <p className="text-[#444] text-sm">
                    {plan.value > 0 ? '/mês' : 'Para sempre'}
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
                    ? 'Processando...'
                    : currentSubscription?.plan === plan.id &&
                      currentSubscription?.is_active
                    ? 'Plano Atual'
                    : 'Escolher'}
                </button>
              </div>
            </div>
          ))}
        </div>

        <div className="bg-[#111118] rounded-xl border border-white/[0.06] p-8 max-w-2xl mx-auto">
          <h2 className="text-2xl font-bold text-white mb-6">Perguntas Frequentes</h2>
          <div className="space-y-4">
            <div>
              <h3 className="text-[#e2e2e8] font-semibold mb-2">
                Posso mudar de plano a qualquer momento?
              </h3>
              <p className="text-[#555]">
                Sim! Você pode fazer upgrade ou downgrade de plano a qualquer momento. A mudança
                será refletida no próximo ciclo de cobrança.
              </p>
            </div>
            <div>
              <h3 className="text-[#e2e2e8] font-semibold mb-2">
                Há período de trial?
              </h3>
              <p className="text-[#555]">
                Sim, todos os planos pagos têm 7 dias de teste gratuito. Sem necessidade de cartão
                de crédito.
              </p>
            </div>
            <div>
              <h3 className="text-[#e2e2e8] font-semibold mb-2">
                O que acontece se eu cancelar?
              </h3>
              <p className="text-[#555]">
                Você pode cancelar a qualquer momento. O acesso permanecerá até o final do período
                pago.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
