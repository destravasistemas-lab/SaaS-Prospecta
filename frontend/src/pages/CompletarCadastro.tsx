import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import api from '../services/api'

export default function CompletarCadastro() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const email = searchParams.get('email') || ''

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')

    if (password !== confirmPassword) {
      setError('Senhas não conferem')
      return
    }
    if (password.length < 6) {
      setError('Senha deve ter no mínimo 6 caracteres')
      return
    }

    setLoading(true)
    try {
      const { data } = await api.post('/auth/complete-signup', {
        email,
        password,
      })
      localStorage.setItem('access_token', data.access_token)
      localStorage.setItem('refresh_token', data.refresh_token)
      localStorage.setItem('user_id', data.user_id)
      localStorage.setItem('tenant_id', data.tenant_id)
      navigate('/app')
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Erro ao completar cadastro')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-[#0a0a0f] flex items-center justify-center px-4 py-8">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <div className="w-14 h-14 bg-indigo-600 rounded-xl flex items-center justify-center mx-auto mb-4">
            <span className="text-2xl font-bold text-white">AM</span>
          </div>
          <h1 className="text-2xl font-bold text-[#e2e2e8]">Bem-vindo ao adStudioAI</h1>
          <p className="text-[#555] text-sm mt-1">Seu pagamento foi confirmado! Agora defina sua senha.</p>
        </div>
        <form onSubmit={handleSubmit} className="bg-[#111118] rounded-2xl border border-white/[0.06] p-8 space-y-5">
          {error && (
            <div className="bg-red-900/20 border border-red-500/20 text-red-400 text-sm rounded-lg px-4 py-3 text-center">{error}</div>
          )}
          <div>
            <label className="block text-sm font-medium text-[#666] mb-2">Email</label>
            <input
              type="email"
              value={email}
              disabled
              className="w-full px-4 py-2.5 bg-[#0a0a0f] border border-white/[0.08] text-[#555] rounded-lg cursor-not-allowed"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-[#666] mb-2">Senha</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Mínimo 6 caracteres"
              className="w-full px-4 py-2.5 bg-[#0a0a0f] border border-white/[0.08] text-[#e2e2e8] rounded-lg focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500 focus:outline-none placeholder-[#333]"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-[#666] mb-2">Confirmar senha</label>
            <input
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              placeholder="Repita a senha"
              className="w-full px-4 py-2.5 bg-[#0a0a0f] border border-white/[0.08] text-[#e2e2e8] rounded-lg focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500 focus:outline-none placeholder-[#333]"
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:bg-indigo-600/50 text-white font-semibold rounded-lg transition-colors"
          >
            {loading ? 'Salvando...' : 'Criar Conta e Acessar'}
          </button>
        </form>
      </div>
    </div>
  )
}
