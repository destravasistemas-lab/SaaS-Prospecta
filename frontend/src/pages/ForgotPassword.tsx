import { useState } from 'react'
import { Link } from 'react-router-dom'
import api from '../services/api'

export default function ForgotPassword() {
  const [email, setEmail] = useState('')
  const [sent, setSent] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!email.trim()) { setError('Informe seu email.'); return }
    setLoading(true)
    setError('')
    try {
      await api.post('/auth/forgot-password', { email: email.trim() })
      setSent(true)
    } catch {
      setError('Erro ao enviar email. Tente novamente.')
    } finally {
      setLoading(false)
    }
  }

  if (sent) {
    return (
      <div className="min-h-screen bg-[#0c0c10] flex items-center justify-center px-5">
        <div className="text-center max-w-sm">
          <div className="w-14 h-14 bg-indigo-500/10 rounded-full flex items-center justify-center mx-auto mb-4">
            <svg className="w-7 h-7 text-indigo-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
              <path strokeLinecap="round" strokeLinejoin="round" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
            </svg>
          </div>
          <h2 className="text-xl font-semibold text-white mb-2">Email enviado</h2>
          <p className="text-sm text-white/40 mb-6">
            Se o email existir, você receberá um link de redefinição de senha.
          </p>
          <Link to="/login" className="text-sm text-indigo-400 hover:text-indigo-300 no-underline">
            Voltar ao login →
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
          <h1 className="text-xl font-semibold text-white mb-1">Esqueceu sua senha?</h1>
          <p className="text-sm text-white/30">Digite seu email e enviaremos um link para redefinir.</p>
        </div>

        <form onSubmit={handleSubmit}>
          {error && (
            <div className="bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2.5 mb-3.5">
              <span className="text-xs text-red-400">{error}</span>
            </div>
          )}
          <div className="mb-4">
            <label className="block text-xs font-medium text-white/40 mb-1.5">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="seu@email.com"
              className="w-full px-3.5 py-2.5 bg-white/[0.04] border border-white/[0.1] text-white text-sm rounded-lg outline-none transition-all placeholder-white/20 focus:border-indigo-500/60"
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 bg-indigo-600 text-white text-sm font-semibold rounded-lg hover:bg-indigo-700 transition-all disabled:opacity-50"
          >
            {loading ? 'Enviando...' : 'Enviar link'}
          </button>
        </form>

        <div className="text-center mt-4">
          <Link to="/login" className="text-xs text-indigo-400/70 hover:text-indigo-400 no-underline">
            ← Voltar ao login
          </Link>
        </div>
      </div>
    </div>
  )
}
