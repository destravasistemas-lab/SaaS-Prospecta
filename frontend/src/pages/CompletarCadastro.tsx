import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import api from '../services/api'
import { BRANDING } from '../config/branding'

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
    <div className="min-h-screen bg-[#030712] flex items-center justify-center px-4 py-8">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <div className="w-14 h-14 bg-gradient-to-br from-[#0284c7] via-[#0ea5e9] to-[#38bdf8] rounded-xl flex items-center justify-center mx-auto mb-4 shadow-lg shadow-[#0ea5e9]/30">
            <span className="text-2xl font-bold text-white">P</span>
          </div>
          <h1 className="text-2xl font-bold text-white">Bem-vindo ao {BRANDING.name}</h1>
          <p className="text-xs text-sky-400 font-medium mb-1">{BRANDING.developedBy}</p>
          <p className="text-[#94a3b8] text-sm mt-1">Seu pagamento foi confirmado! Agora defina sua senha.</p>
        </div>
        <form onSubmit={handleSubmit} className="bg-[#070e22] rounded-2xl border border-[#38bdf8]/15 p-8 space-y-5 shadow-xl shadow-sky-950/30">
          {error && (
            <div className="bg-red-900/20 border border-red-500/20 text-red-400 text-sm rounded-lg px-4 py-3 text-center">{error}</div>
          )}
          <div>
            <label className="block text-sm font-medium text-[#94a3b8] mb-2">Email</label>
            <input
              type="email"
              value={email}
              disabled
              className="w-full px-4 py-2.5 bg-[#030712] border border-white/[0.08] text-[#94a3b8] rounded-lg opacity-60 cursor-not-allowed"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-[#94a3b8] mb-2">Senha</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Mínimo 6 caracteres"
              className="w-full px-4 py-2.5 bg-[#030712] border border-white/[0.08] text-[#f8fafc] rounded-lg focus:ring-1 focus:ring-sky-400 focus:border-sky-400 focus:outline-none placeholder-[#475569]"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-[#94a3b8] mb-2">Confirmar senha</label>
            <input
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              placeholder="Repita a senha"
              className="w-full px-4 py-2.5 bg-[#030712] border border-white/[0.08] text-[#f8fafc] rounded-lg focus:ring-1 focus:ring-sky-400 focus:border-sky-400 focus:outline-none placeholder-[#475569]"
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 bg-gradient-to-r from-[#0284c7] via-[#0ea5e9] to-[#38bdf8] hover:brightness-110 disabled:opacity-50 text-white font-semibold rounded-lg transition-all shadow-lg shadow-[#0284c7]/25"
          >
            {loading ? 'Salvando...' : 'Criar Conta e Acessar'}
          </button>
        </form>
      </div>
    </div>
  )
}
