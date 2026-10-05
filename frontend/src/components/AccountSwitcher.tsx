import { useState, useEffect, useRef } from 'react'
import { ChevronsUpDown, Building2, Check, Briefcase } from 'lucide-react'
import axios from 'axios'
import { API_BASE } from '../services/api'

interface ClientLite {
  id: string
  brand_name: string
}

// Keys used to preserve the agency's own session while impersonating a client.
const AG = {
  token: 'agency_access_token',
  refresh: 'agency_refresh_token',
  tenant: 'agency_tenant_id',
  user: 'agency_user_id',
  name: 'agency_name',
}

function authHeader(token: string) {
  return { headers: { Authorization: `Bearer ${token}` } }
}

export default function AccountSwitcher() {
  const [open, setOpen] = useState(false)
  const [isAgency, setIsAgency] = useState(false)
  const [agencyName, setAgencyName] = useState('')
  const [clients, setClients] = useState<ClientLite[]>([])
  const [switching, setSwitching] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  const impersonating = localStorage.getItem('impersonating') === 'true'
  const activeName = impersonating
    ? localStorage.getItem('impersonating_name') || 'Cliente'
    : agencyName
  const activeTenant = localStorage.getItem('tenant_id') || ''

  useEffect(() => {
    load()
    function onClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onClick)
    return () => document.removeEventListener('mousedown', onClick)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // The agency token is the original one saved when impersonation started;
  // if not impersonating, the active token IS the agency token.
  function agencyToken(): string {
    return localStorage.getItem(AG.token) || localStorage.getItem('access_token') || ''
  }

  async function load() {
    const token = agencyToken()
    if (!token) return
    try {
      const me = (await axios.get(`${API_BASE}/api/v1/auth/me`, authHeader(token))).data
      if (me.plan_type !== 'agencia') {
        setIsAgency(false)
        return
      }
      setIsAgency(true)
      setAgencyName(me.brand_name || 'Minha agência')
      const list = (await axios.get(`${API_BASE}/api/v1/auth/clients`, authHeader(token))).data
      setClients(list.map((c: any) => ({ id: c.id, brand_name: c.brand_name })))
    } catch {
      setIsAgency(false)
    }
  }

  async function switchToClient(client: ClientLite) {
    if (switching) return
    setSwitching(true)
    try {
      const token = agencyToken()
      // Preserve the agency's own session (idempotent — only meaningful the first time).
      localStorage.setItem(AG.token, token)
      localStorage.setItem(AG.refresh, localStorage.getItem(AG.refresh) || localStorage.getItem('refresh_token') || '')
      localStorage.setItem(AG.tenant, localStorage.getItem(AG.tenant) || localStorage.getItem('tenant_id') || '')
      localStorage.setItem(AG.user, localStorage.getItem(AG.user) || localStorage.getItem('user_id') || '')
      localStorage.setItem(AG.name, agencyName)

      const { data } = await axios.post(
        `${API_BASE}/api/v1/auth/clients/${client.id}/impersonate`, {}, authHeader(token),
      )
      localStorage.setItem('access_token', data.access_token)
      localStorage.setItem('refresh_token', data.refresh_token)
      localStorage.setItem('user_id', data.user_id)
      localStorage.setItem('tenant_id', data.tenant_id)
      localStorage.setItem('impersonating', 'true')
      localStorage.setItem('impersonating_name', data.client_brand_name)
      // Full reload so every screen refetches with the new tenant.
      window.location.href = '/app'
    } catch {
      setSwitching(false)
      alert('Erro ao acessar a conta do cliente.')
    }
  }

  function switchToAgency() {
    const t = localStorage.getItem(AG.token)
    const r = localStorage.getItem(AG.refresh)
    const ten = localStorage.getItem(AG.tenant)
    const u = localStorage.getItem(AG.user)
    if (t && r && ten && u) {
      localStorage.setItem('access_token', t)
      localStorage.setItem('refresh_token', r)
      localStorage.setItem('tenant_id', ten)
      localStorage.setItem('user_id', u)
    }
    ;[AG.token, AG.refresh, AG.tenant, AG.user, AG.name].forEach((k) => localStorage.removeItem(k))
    localStorage.removeItem('impersonating')
    localStorage.removeItem('impersonating_name')
    window.location.href = '/app'
  }

  if (!isAgency) return null

  return (
    <div ref={ref} className="relative px-3 pt-2 pb-1">
      <button
        onClick={() => setOpen((o) => !o)}
        disabled={switching}
        className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg bg-white/[0.04] border border-white/[0.07] hover:border-white/[0.14] transition-colors text-left disabled:opacity-50"
      >
        <div className="w-6 h-6 rounded-md bg-indigo-500/15 flex items-center justify-center shrink-0">
          {impersonating
            ? <Building2 size={13} className="text-indigo-300" />
            : <Briefcase size={13} className="text-indigo-300" />}
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-[10px] text-[#5a5a6e] leading-none mb-0.5">
            {impersonating ? 'Cliente' : 'Agência'}
          </p>
          <p className="text-xs font-medium text-[#e2e2e8] truncate leading-tight">{activeName}</p>
        </div>
        <ChevronsUpDown size={13} className="text-[#5a5a6e] shrink-0" />
      </button>

      {open && (
        <div className="absolute left-3 right-3 mt-1 z-50 bg-[#111118] border border-white/[0.1] rounded-lg shadow-xl shadow-black/40 py-1.5 max-h-80 overflow-y-auto">
          {/* Agency itself */}
          <button
            onClick={() => { setOpen(false); if (impersonating) switchToAgency() }}
            className="w-full flex items-center gap-2.5 px-3 py-2 hover:bg-white/[0.04] transition-colors text-left"
          >
            <div className="w-6 h-6 rounded-md bg-indigo-500/15 flex items-center justify-center shrink-0">
              <Briefcase size={13} className="text-indigo-300" />
            </div>
            <span className="flex-1 text-xs font-medium text-[#e2e2e8] truncate">{agencyName}</span>
            <span className="text-[9px] text-[#5a5a6e] uppercase tracking-wide">Agência</span>
            {!impersonating && <Check size={13} className="text-indigo-400 shrink-0" />}
          </button>

          {clients.length > 0 && <div className="h-px bg-white/[0.06] my-1 mx-2" />}

          {clients.map((client) => {
            const active = impersonating && client.id === activeTenant
            return (
              <button
                key={client.id}
                onClick={() => { setOpen(false); if (!active) switchToClient(client) }}
                className="w-full flex items-center gap-2.5 px-3 py-2 hover:bg-white/[0.04] transition-colors text-left"
              >
                <div className="w-6 h-6 rounded-md bg-white/[0.05] flex items-center justify-center shrink-0 text-[10px] font-bold text-[#8a8a9e]">
                  {client.brand_name.charAt(0).toUpperCase()}
                </div>
                <span className="flex-1 text-xs text-[#c0c0d0] truncate">{client.brand_name}</span>
                {active && <Check size={13} className="text-indigo-400 shrink-0" />}
              </button>
            )
          })}

          {clients.length === 0 && (
            <p className="px-3 py-2 text-[11px] text-[#5a5a6e]">Nenhum cliente ainda.</p>
          )}
        </div>
      )}
    </div>
  )
}
