import { useState, useEffect } from 'react'
import { Users, Plus, Trash2, X, Eye, EyeOff, Shield, User as UserIcon, Building2 } from 'lucide-react'
import api from '../services/api'

interface Member {
  id: string
  username: string
  full_name: string | null
  role: string
  is_active: boolean
  allowed_modules: string[] | null
}

interface ClientLite {
  id: string
  brand_name: string
}

// Módulos que o admin pode liberar por usuário (bate com AVAILABLE_MODULES do backend)
const MODULES: { key: string; label: string }[] = [
  { key: 'whatsapp', label: 'WhatsApp' },
  { key: 'instagram', label: 'Instagram' },
  { key: 'ads', label: 'Meta Ads' },
  { key: 'ia', label: 'IA de atendimento' },
]

export default function Equipe() {
  const myId = localStorage.getItem('user_id') || ''
  const [members, setMembers] = useState<Member[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const [showCreate, setShowCreate] = useState(false)
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [fullName, setFullName] = useState('')
  const [role, setRole] = useState('agent')
  const [showPwd, setShowPwd] = useState(false)
  const [creating, setCreating] = useState(false)
  const [createError, setCreateError] = useState('')

  // Módulos na criação (para agente): null = todos; senão lista escolhida
  const [createModules, setCreateModules] = useState<Set<string>>(new Set())
  const [createAllModules, setCreateAllModules] = useState(true)
  const [createClientIds, setCreateClientIds] = useState<Set<string>>(new Set())

  // Editar módulos de um membro existente
  const [modulesMember, setModulesMember] = useState<Member | null>(null)
  const [moduleDraft, setModuleDraft] = useState<Set<string>>(new Set())
  const [moduleAll, setModuleAll] = useState(true)
  const [savingModules, setSavingModules] = useState(false)

  // Módulos que a conta tem liberado (o resto a agência/super admin bloqueou)
  const [accountBlocked, setAccountBlocked] = useState<string[]>([])

  // Atribuição de empresas (agência)
  const [isAgency, setIsAgency] = useState(false)
  const [clients, setClients] = useState<ClientLite[]>([])
  const [assignMember, setAssignMember] = useState<Member | null>(null)
  const [assignedIds, setAssignedIds] = useState<Set<string>>(new Set())
  const [savingAssign, setSavingAssign] = useState(false)

  // Módulos oferecíveis = catálogo menos os bloqueados na conta
  const availableModules = MODULES.filter((m) => !accountBlocked.includes(m.key))

  useEffect(() => { load() }, [])

  async function load() {
    setLoading(true)
    try {
      const { data } = await api.get('/auth/users')
      setMembers(data)
      try {
        const me = (await api.get('/auth/me')).data
        setAccountBlocked(me.blocked_modules || [])
        if (me.plan_type === 'agencia') {
          setIsAgency(true)
          const list = (await api.get('/auth/clients')).data
          setClients(list.map((c: any) => ({ id: c.id, brand_name: c.brand_name })))
        }
      } catch { /* não é agência ou sem permissão */ }
    } catch {
      setError('Erro ao carregar a equipe.')
    } finally {
      setLoading(false)
    }
  }

  async function openAssign(m: Member) {
    setAssignMember(m)
    setAssignedIds(new Set())
    try {
      const { data } = await api.get(`/auth/clients/assignments/${m.id}`)
      setAssignedIds(new Set(data.client_ids))
    } catch { /* começa vazio */ }
  }

  function toggleAssign(id: string) {
    setAssignedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  async function saveAssignments() {
    if (!assignMember) return
    setSavingAssign(true)
    try {
      await api.put(`/auth/clients/assignments/${assignMember.id}`, {
        client_ids: [...assignedIds],
      })
      setAssignMember(null)
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Erro ao salvar atribuições.')
    } finally {
      setSavingAssign(false)
    }
  }

  function openCreate() {
    setUsername(''); setPassword(''); setFullName(''); setRole('agent')
    setCreateModules(new Set()); setCreateAllModules(true); setCreateClientIds(new Set())
    setCreateError(''); setShowCreate(true)
  }

  function toggleCreateModule(key: string) {
    setCreateModules((prev) => {
      const next = new Set(prev)
      next.has(key) ? next.delete(key) : next.add(key)
      return next
    })
  }
  function toggleCreateClient(id: string) {
    setCreateClientIds((prev) => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  async function handleCreate(e: React.SyntheticEvent) {
    e.preventDefault()
    setCreateError('')
    if (!username.trim() || password.length < 6) {
      setCreateError('Preencha usuário e uma senha de no mínimo 6 caracteres.')
      return
    }
    setCreating(true)
    try {
      await api.post('/auth/users', {
        username: username.trim(),
        password,
        full_name: fullName.trim() || null,
        role,
        // Só manda módulos para agente e quando NÃO for "todos"
        allowed_modules: role === 'agent' && !createAllModules ? [...createModules] : null,
        client_ids: isAgency && role === 'agent' ? [...createClientIds] : [],
      })
      setShowCreate(false)
      await load()
    } catch (err: any) {
      setCreateError(err.response?.data?.detail || 'Erro ao criar membro.')
    } finally {
      setCreating(false)
    }
  }

  // ---- Editar módulos de um membro existente ----
  function openModules(m: Member) {
    setModulesMember(m)
    setModuleAll(m.allowed_modules === null)
    setModuleDraft(new Set(m.allowed_modules || []))
  }
  function toggleModuleDraft(key: string) {
    setModuleDraft((prev) => {
      const next = new Set(prev)
      next.has(key) ? next.delete(key) : next.add(key)
      return next
    })
  }
  async function saveMemberModules() {
    if (!modulesMember) return
    setSavingModules(true)
    try {
      await api.put(`/auth/users/${modulesMember.id}/modules`, {
        allowed_modules: moduleAll ? null : [...moduleDraft],
      })
      setModulesMember(null)
      await load()
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Erro ao salvar módulos.')
    } finally {
      setSavingModules(false)
    }
  }

  async function handleDelete(id: string) {
    if (!confirm('Remover este membro da equipe?')) return
    try {
      await api.delete(`/auth/users/${id}`)
      await load()
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Erro ao remover.')
    }
  }

  const active = members.filter((m) => m.is_active)

  return (
    <div className="max-w-3xl mx-auto">
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold text-[#e2e2e8] flex items-center gap-2">
            <Users size={20} className="text-indigo-400" />
            Equipe
          </h1>
          <p className="text-[#555] text-sm mt-0.5">Gerencie os usuários que acessam esta conta.</p>
        </div>
        <button
          onClick={openCreate}
          className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-semibold rounded-lg transition-colors"
        >
          <Plus size={15} />
          Novo Membro
        </button>
      </div>

      {error && <div className="mb-5 bg-red-900/20 border border-red-500/20 text-red-400 text-sm rounded-lg px-4 py-3">{error}</div>}

      {loading ? (
        <p className="text-center text-[#555] text-sm py-10">Carregando…</p>
      ) : (
        <div className="space-y-2">
          {active.map((m) => (
            <div key={m.id} className="bg-[#111118] rounded-xl border border-white/[0.06] p-4 flex items-center gap-3">
              <div className="w-9 h-9 rounded-full bg-white/[0.06] flex items-center justify-center text-xs font-bold text-[#8a8a9e] shrink-0">
                {(m.full_name || m.username).charAt(0).toUpperCase()}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <p className="text-sm font-semibold text-[#e2e2e8]">{m.full_name || m.username}</p>
                  <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded border flex items-center gap-1 ${
                    m.role === 'admin'
                      ? 'text-amber-400 bg-amber-900/20 border-amber-500/20'
                      : 'text-blue-400 bg-blue-900/20 border-blue-500/20'
                  }`}>
                    {m.role === 'admin' ? <Shield size={9} /> : <UserIcon size={9} />}
                    {m.role === 'admin' ? 'Admin' : 'Agente'}
                  </span>
                  {m.id === myId && <span className="text-[10px] text-[#555]">(você)</span>}
                </div>
                <p className="text-[11px] text-[#555] mt-0.5">@{m.username}</p>
                {m.role !== 'admin' && (
                  <p className="text-[10px] text-[#555] mt-1">
                    Módulos: {m.allowed_modules === null
                      ? 'todos da conta'
                      : (m.allowed_modules.length
                          ? m.allowed_modules.map((k) => MODULES.find((x) => x.key === k)?.label || k).join(', ')
                          : 'nenhum')}
                  </p>
                )}
              </div>
              <div className="flex gap-2 shrink-0">
                {m.role !== 'admin' && (
                  <button
                    onClick={() => openModules(m)}
                    className="flex items-center gap-1.5 px-3 py-1.5 bg-white/[0.04] border border-white/[0.1] text-[#c0c0d0] rounded-lg text-xs font-semibold hover:bg-white/[0.08] transition-colors"
                  >
                    <Shield size={12} />
                    Módulos
                  </button>
                )}
                {isAgency && m.role !== 'admin' && (
                  <button
                    onClick={() => openAssign(m)}
                    className="flex items-center gap-1.5 px-3 py-1.5 bg-indigo-600/15 border border-indigo-500/30 text-indigo-300 rounded-lg text-xs font-semibold hover:bg-indigo-600/25 transition-colors"
                  >
                    <Building2 size={12} />
                    Empresas
                  </button>
                )}
                {m.id !== myId && (
                  <button
                    onClick={() => handleDelete(m.id)}
                    className="p-1.5 bg-red-900/20 text-red-400 rounded-lg hover:bg-red-900/40 transition-colors"
                  >
                    <Trash2 size={13} />
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm px-4">
          <div className="bg-[#111118] border border-white/[0.08] rounded-2xl p-6 w-full max-w-md">
            <div className="flex items-center justify-between mb-5">
              <h3 className="text-base font-semibold text-white">Novo Membro</h3>
              <button onClick={() => setShowCreate(false)} className="text-[#444] hover:text-[#888]"><X size={18} /></button>
            </div>

            <form onSubmit={handleCreate} className="space-y-4">
              {createError && <div className="bg-red-900/20 border border-red-500/20 text-red-400 text-xs rounded-lg px-4 py-3">{createError}</div>}

              <div>
                <label className="block text-xs font-medium text-[#666] mb-1.5">Usuário / login *</label>
                <input value={username} onChange={(e) => setUsername(e.target.value)} placeholder="ex: maria@empresa.com" className="w-full px-4 py-2.5 bg-[#0a0a0f] border border-white/[0.08] text-[#e2e2e8] text-sm rounded-lg focus:border-indigo-500 focus:outline-none placeholder-[#333]" />
              </div>

              <div>
                <label className="block text-xs font-medium text-[#666] mb-1.5">Senha *</label>
                <div className="relative">
                  <input type={showPwd ? 'text' : 'password'} value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Mínimo 6 caracteres" className="w-full px-4 py-2.5 pr-10 bg-[#0a0a0f] border border-white/[0.08] text-[#e2e2e8] text-sm rounded-lg focus:border-indigo-500 focus:outline-none placeholder-[#333]" />
                  <button type="button" onClick={() => setShowPwd(!showPwd)} className="absolute right-3 top-1/2 -translate-y-1/2 text-[#444] hover:text-[#888]">
                    {showPwd ? <EyeOff size={14} /> : <Eye size={14} />}
                  </button>
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-[#666] mb-1.5">Nome completo (opcional)</label>
                <input value={fullName} onChange={(e) => setFullName(e.target.value)} placeholder="Ex: Maria Silva" className="w-full px-4 py-2.5 bg-[#0a0a0f] border border-white/[0.08] text-[#e2e2e8] text-sm rounded-lg focus:border-indigo-500 focus:outline-none placeholder-[#333]" />
              </div>

              <div>
                <label className="block text-xs font-medium text-[#666] mb-1.5">Função</label>
                <div className="grid grid-cols-2 gap-2">
                  {[
                    { id: 'agent', label: 'Agente', desc: 'Atende conversas' },
                    { id: 'admin', label: 'Admin', desc: 'Acesso total' },
                  ].map((r) => (
                    <button
                      type="button"
                      key={r.id}
                      onClick={() => setRole(r.id)}
                      className={`px-3 py-2 rounded-lg border text-left transition-colors ${
                        role === r.id ? 'bg-indigo-600/15 border-indigo-500/40' : 'bg-[#0a0a0f] border-white/[0.08] hover:border-white/[0.16]'
                      }`}
                    >
                      <p className={`text-sm font-medium ${role === r.id ? 'text-indigo-300' : 'text-[#c0c0d0]'}`}>{r.label}</p>
                      <p className="text-[10px] text-[#555]">{r.desc}</p>
                    </button>
                  ))}
                </div>
              </div>

              {role === 'agent' && (
                <div>
                  <label className="block text-xs font-medium text-[#666] mb-1.5">Módulos que este agente acessa</label>
                  <label className="flex items-center gap-2 px-3 py-2 rounded-lg border border-white/[0.08] bg-[#0a0a0f] cursor-pointer mb-1.5">
                    <input type="checkbox" checked={createAllModules} onChange={() => setCreateAllModules(!createAllModules)} className="accent-indigo-600" />
                    <span className="text-sm text-[#c0c0d0]">Todos os módulos da conta</span>
                  </label>
                  {!createAllModules && (
                    <div className="grid grid-cols-2 gap-1.5">
                      {availableModules.map((m) => {
                        const on = createModules.has(m.key)
                        return (
                          <label key={m.key} className={`flex items-center gap-2 px-3 py-2 rounded-lg border cursor-pointer transition-colors ${on ? 'bg-indigo-600/10 border-indigo-500/40' : 'bg-[#0a0a0f] border-white/[0.06] hover:border-white/[0.14]'}`}>
                            <input type="checkbox" checked={on} onChange={() => toggleCreateModule(m.key)} className="accent-indigo-600" />
                            <span className={`text-xs ${on ? 'text-[#e2e2e8]' : 'text-[#8a8a9e]'}`}>{m.label}</span>
                          </label>
                        )
                      })}
                    </div>
                  )}
                </div>
              )}

              {isAgency && role === 'agent' && clients.length > 0 && (
                <div>
                  <label className="block text-xs font-medium text-[#666] mb-1.5">Empresas que este membro vê (opcional)</label>
                  <div className="grid grid-cols-2 gap-1.5 max-h-32 overflow-y-auto">
                    {clients.map((c) => {
                      const on = createClientIds.has(c.id)
                      return (
                        <label key={c.id} className={`flex items-center gap-2 px-3 py-2 rounded-lg border cursor-pointer transition-colors ${on ? 'bg-indigo-600/10 border-indigo-500/40' : 'bg-[#0a0a0f] border-white/[0.06] hover:border-white/[0.14]'}`}>
                          <input type="checkbox" checked={on} onChange={() => toggleCreateClient(c.id)} className="accent-indigo-600" />
                          <span className={`text-xs truncate ${on ? 'text-[#e2e2e8]' : 'text-[#8a8a9e]'}`}>{c.brand_name}</span>
                        </label>
                      )
                    })}
                  </div>
                </div>
              )}

              <div className="flex gap-3 pt-1">
                <button type="button" onClick={() => setShowCreate(false)} className="flex-1 py-2.5 border border-white/[0.08] text-[#666] hover:text-white text-sm font-medium rounded-lg transition-colors">Cancelar</button>
                <button type="submit" disabled={creating} className="flex-1 py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm font-semibold rounded-lg transition-colors">
                  {creating ? 'Criando…' : 'Criar Membro'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: atribuir empresas ao membro */}
      {assignMember && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm px-4">
          <div className="bg-[#111118] border border-white/[0.08] rounded-2xl p-6 w-full max-w-md max-h-[85vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-1">
              <h3 className="text-base font-semibold text-white">Empresas de {assignMember.full_name || assignMember.username}</h3>
              <button onClick={() => setAssignMember(null)} className="text-[#444] hover:text-[#888]"><X size={18} /></button>
            </div>
            <p className="text-xs text-[#555] mb-4">
              Este membro só vai ver e acessar as empresas marcadas abaixo.
            </p>

            {clients.length === 0 ? (
              <p className="text-[#5a5a6e] text-sm text-center py-6">Nenhuma empresa cadastrada ainda.</p>
            ) : (
              <div className="space-y-1.5 mb-5">
                {clients.map((c) => {
                  const checked = assignedIds.has(c.id)
                  return (
                    <label
                      key={c.id}
                      className={`flex items-center gap-3 px-3 py-2.5 rounded-lg border cursor-pointer transition-colors ${
                        checked
                          ? 'bg-indigo-600/10 border-indigo-500/40'
                          : 'bg-[#0a0a0f] border-white/[0.06] hover:border-white/[0.14]'
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() => toggleAssign(c.id)}
                        className="accent-indigo-600"
                      />
                      <div className="w-7 h-7 rounded-lg bg-white/[0.05] flex items-center justify-center text-[10px] font-bold text-[#8a8a9e]">
                        {c.brand_name.charAt(0).toUpperCase()}
                      </div>
                      <span className={`text-sm ${checked ? 'text-[#e2e2e8]' : 'text-[#8a8a9e]'}`}>{c.brand_name}</span>
                    </label>
                  )
                })}
              </div>
            )}

            <div className="flex gap-3">
              <button onClick={() => setAssignMember(null)} className="flex-1 py-2.5 border border-white/[0.08] text-[#666] hover:text-white text-sm font-medium rounded-lg transition-colors">
                Cancelar
              </button>
              <button
                onClick={saveAssignments}
                disabled={savingAssign}
                className="flex-1 py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm font-semibold rounded-lg transition-colors"
              >
                {savingAssign ? 'Salvando…' : `Salvar (${assignedIds.size})`}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal: módulos que o membro pode acessar */}
      {modulesMember && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm px-4">
          <div className="bg-[#111118] border border-white/[0.08] rounded-2xl p-6 w-full max-w-md">
            <div className="flex items-center justify-between mb-1">
              <h3 className="text-base font-semibold text-white">Módulos de {modulesMember.full_name || modulesMember.username}</h3>
              <button onClick={() => setModulesMember(null)} className="text-[#444] hover:text-[#888]"><X size={18} /></button>
            </div>
            <p className="text-xs text-[#555] mb-4">Escolha o que este agente pode acessar. (Módulos bloqueados pela agência não aparecem.)</p>

            <label className="flex items-center gap-2 px-3 py-2.5 rounded-lg border border-white/[0.08] bg-[#0a0a0f] cursor-pointer mb-2">
              <input type="checkbox" checked={moduleAll} onChange={() => setModuleAll(!moduleAll)} className="accent-indigo-600" />
              <span className="text-sm text-[#c0c0d0]">Todos os módulos da conta</span>
            </label>

            {!moduleAll && (
              <div className="space-y-1.5 mb-5">
                {availableModules.map((m) => {
                  const on = moduleDraft.has(m.key)
                  return (
                    <label key={m.key} className={`flex items-center gap-3 px-3 py-2.5 rounded-lg border cursor-pointer transition-colors ${on ? 'bg-indigo-600/10 border-indigo-500/40' : 'bg-[#0a0a0f] border-white/[0.06] hover:border-white/[0.14]'}`}>
                      <input type="checkbox" checked={on} onChange={() => toggleModuleDraft(m.key)} className="accent-indigo-600" />
                      <span className={`text-sm ${on ? 'text-[#e2e2e8]' : 'text-[#8a8a9e]'}`}>{m.label}</span>
                    </label>
                  )
                })}
              </div>
            )}

            <div className="flex gap-3 mt-4">
              <button onClick={() => setModulesMember(null)} className="flex-1 py-2.5 border border-white/[0.08] text-[#666] hover:text-white text-sm font-medium rounded-lg transition-colors">Cancelar</button>
              <button onClick={saveMemberModules} disabled={savingModules} className="flex-1 py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm font-semibold rounded-lg transition-colors">
                {savingModules ? 'Salvando…' : 'Salvar'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
