import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import api from '../services/api'
import { BRANDING } from '../config/branding'
import { useI18n } from '../i18n'

export default function ResetPassword() {
  const { t } = useI18n()
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token') || ''

  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [done, setDone] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (password.length < 6) { setError(t('Mínimo 6 caracteres.', 'Minimum 6 characters.')); return }
    if (password !== confirm) { setError(t('As senhas não conferem.', 'Passwords do not match.')); return }
    if (!token) { setError(t('Token inválido.', 'Invalid token.')); return }
    setLoading(true)
    setError('')
    try {
      await api.post('/auth/reset-password', { token, password })
      setDone(true)
    } catch (err: any) {
      setError(err.response?.data?.detail || t('Erro ao redefinir senha.', 'Failed to reset password.'))
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
          <h2 className="text-xl font-semibold text-white mb-2">{t('Senha redefinida', 'Password reset')}</h2>
          <p className="text-sm text-white/40 mb-6">{t('Sua senha foi alterada com sucesso.', 'Your password was changed successfully.')}</p>
          <Link to="/login" className="text-sm text-indigo-400 hover:text-indigo-300 no-underline">
            {t('Fazer login →', 'Sign in →')}
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-[#030712] flex items-center justify-center px-5">
      <div className="w-full max-w-sm">
        <div className="mb-8">
          <Link to="/" className="inline-flex items-center gap-2 no-underline mb-8">
            <div className="w-6 h-6 bg-gradient-to-br from-[#0284c7] via-[#0ea5e9] to-[#38bdf8] rounded-md flex items-center justify-center font-bold text-xs text-white shadow-sm shadow-sky-500/30">
              P
            </div>
            <span className="text-sm font-semibold text-white">
              {BRANDING.name}
              <span className="ml-1 text-[10px] text-sky-400 font-normal">by {BRANDING.company}</span>
            </span>
          </Link>
          <h1 className="text-xl font-semibold text-white mb-1">{t('Redefinir senha', 'Reset password')}</h1>
          <p className="text-sm text-[#94a3b8]">{t('Escolha uma nova senha para sua conta.', 'Choose a new password for your account.')}</p>
        </div>

        <form onSubmit={handleSubmit}>
          {error && (
            <div className="bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2.5 mb-3.5">
              <span className="text-xs text-red-400">{error}</span>
            </div>
          )}
          <div className="mb-3">
            <label className="block text-xs font-medium text-[#94a3b8] mb-1.5">{t('Nova senha', 'New password')}</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder={t('Mínimo 6 caracteres', 'Minimum 6 characters')}
              className="w-full px-3.5 py-2.5 bg-[#070e22] border border-white/[0.1] text-white text-sm rounded-lg outline-none transition-all placeholder-[#475569] focus:border-sky-400 focus:shadow-[0_0_0_3px_rgba(56,189,248,0.15)]"
            />
          </div>
          <div className="mb-4">
            <label className="block text-xs font-medium text-[#94a3b8] mb-1.5">{t('Confirmar senha', 'Confirm password')}</label>
            <input
              type="password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              placeholder={t('Repita a senha', 'Repeat the password')}
              className="w-full px-3.5 py-2.5 bg-[#070e22] border border-white/[0.1] text-white text-sm rounded-lg outline-none transition-all placeholder-[#475569] focus:border-sky-400 focus:shadow-[0_0_0_3px_rgba(56,189,248,0.15)]"
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 bg-gradient-to-r from-[#0284c7] via-[#0ea5e9] to-[#38bdf8] text-white text-sm font-semibold rounded-lg hover:brightness-110 transition-all disabled:opacity-50 shadow-lg shadow-[#0284c7]/25"
          >
            {loading ? t('Redefinindo...', 'Resetting...') : t('Redefinir senha', 'Reset password')}
          </button>
        </form>
      </div>
    </div>
  )
}
