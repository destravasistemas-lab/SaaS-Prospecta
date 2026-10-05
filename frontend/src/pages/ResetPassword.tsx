import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import api from '../services/api'

export default function ResetPassword() {
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token') || ''

  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [done, setDone] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (password.length < 6) { setError('Mínimo 6 caracteres.'); return }
    if (password !== confirm) { setError('Senhas não conferem.'); return }
    if (!token) { setError('Token inválido.'); return }
    setLoading(true)
    setError('')
    try {
      await api.post('/auth/reset-password', { token, password })
      setDone(true)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Erro ao redefinir senha.')
    } finally {
      setLoading(false)
    }
  }

  if (done) {
    return (
      <div className="min-h-screen bg-[#0c0c10] flex items-center justify-center px-5">
        <div className="text-center max-w-sm">
          <div className="w-14 h-14 bg-green-500/10 rounded-full flex items-center justify-center mx-auto mb-4">
            <svg className="w-7 h-7 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
              <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
            </svg>
          </div>
          <h2 className="text-xl font-semibold text-white mb-2">Senha redefinida</h2>
          <p className="text-sm text-white/40 mb-6">Sua senha foi alterada com sucesso.</p>
          <Link to="/login" className="text-sm text-indigo-400 hover:text-indigo-300 no-underline">
            Fazer login →
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-[#0c0c10] flex items-center justify-center px-5">
      <div className="w-full max-w-sm">
        <div className="mb-8">
          <Link to="/" className="inline-flex items-center gap-2 no-underline mb-8">
            <div className="w-6 h-6 bg-indigo-600 rounded-md flex items-center justify-center">
              <svg viewBox="0 0 24 24" className="w-3.5 h-3.5 fill-white"><path d="M13 3L4 14h8l-1 7 9-11h-8z" /></svg>
            </div>
            <span className="text-sm font-semibold text-white">adStudio<span className="text-white/40">AI</span></span>
          </Link>
          <h1 className="text-xl font-semibold text-white mb-1">Redefinir senha</h1>
          <p className="text-sm text-white/30">Escolha uma nova senha para sua conta.</p>
        </div>

        <form onSubmit={handleSubmit}>
          {error && (
            <div className="bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2.5 mb-3.5">
              <span className="text-xs text-red-400">{error}</span>
            </div>
          )}
          <div className="mb-3">
            <label className="block text-xs font-medium text-white/40 mb-1.5">Nova senha</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Mínimo 6 caracteres"
              className="w-full px-3.5 py-2.5 bg-white/[0.04] border border-white/[0.1] text-white text-sm rounded-lg outline-none transition-all placeholder-white/20 focus:border-indigo-500/60"
            />
          </div>
          <div className="mb-4">
            <label className="block text-xs font-medium text-white/40 mb-1.5">Confirmar senha</label>
            <input
              type="password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              placeholder="Repita a senha"
              className="w-full px-3.5 py-2.5 bg-white/[0.04] border border-white/[0.1] text-white text-sm rounded-lg outline-none transition-all placeholder-white/20 focus:border-indigo-500/60"
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 bg-indigo-600 text-white text-sm font-semibold rounded-lg hover:bg-indigo-700 transition-all disabled:opacity-50"
          >
            {loading ? 'Redefinindo...' : 'Redefinir senha'}
          </button>
        </form>
      </div>
    </div>
  )
}
