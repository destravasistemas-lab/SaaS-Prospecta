import axios from 'axios'
import { getLang } from '../i18n'

// Em produção com o backend em host separado (ex.: Fly), defina VITE_API_URL no
// build (ex.: https://api.seudominio.com). Em dev / docker-compose, deixe vazio:
// os caminhos ficam relativos e o nginx faz o proxy de /api e /ws (comportamento atual).
const RAW_API = (import.meta.env as any).VITE_API_URL as string | undefined
export const API_BASE = (RAW_API || '').replace(/\/$/, '')

// Base do WebSocket derivada do backend (ou da origem atual, no modo relativo).
export const WS_BASE = (API_BASE || (typeof location !== 'undefined' ? location.origin : ''))
  .replace(/^http/, 'ws')

const api = axios.create({
  baseURL: `${API_BASE}/api/v1`,
  headers: {
    'Content-Type': 'application/json',
  },
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  config.headers['X-Lang'] = getLang()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401 && !error.config._retry) {
      const refreshToken = localStorage.getItem('refresh_token')
      if (refreshToken) {
        error.config._retry = true
        try {
          const { data } = await axios.post(`${API_BASE}/api/v1/auth/refresh`, { refresh_token: refreshToken })
          localStorage.setItem('access_token', data.access_token)
          localStorage.setItem('refresh_token', data.refresh_token)
          error.config.headers.Authorization = `Bearer ${data.access_token}`
          return api(error.config)
        } catch {
          localStorage.removeItem('access_token')
          localStorage.removeItem('refresh_token')
          window.location.href = '/login'
        }
      }
    }
    return Promise.reject(error)
  }
)

/** Texto do erro da API: aceita detail em texto, {message} ou a lista de validação do FastAPI. */
export function apiError(err: any, fallback: string): string {
  const detail = err?.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (detail && typeof detail.message === 'string') return detail.message
  if (Array.isArray(detail) && detail.length) {
    const msgs = detail.map((d: any) => d?.msg).filter(Boolean)
    if (msgs.length) return msgs.join('; ')
  }
  return fallback
}

export default api
