import { createContext, useContext } from 'react'

export interface Me {
  id: string
  tenant_id: string
  username: string
  full_name: string | null
  role: string
  plan_type: string | null
  brand_name: string | null
  blocked_modules: string[]
  modules: string[]
  is_super_admin: boolean
  calling_enabled: boolean
  billing?: Billing
}

export interface Billing {
  status: 'unmanaged' | 'courtesy' | 'trial' | 'active' | 'past_due' | 'canceled' | 'blocked'
  allowed: boolean
  enforced: boolean
  until: string | null
  days_left: number | null
  plan: string | null
}

export const MeContext = createContext<Me | null>(null)

/** Usuário logado, carregado uma vez pelo Layout. Null enquanto carrega. */
export function useMe(): Me | null {
  return useContext(MeContext)
}

/** Módulo liberado para este usuário (whatsapp, instagram, ads, ia). */
export function hasModule(me: Me | null, module: string): boolean {
  if (!me) return true
  return Array.isArray(me.modules) ? me.modules.includes(module) : !(me.blocked_modules ?? []).includes(module)
}
