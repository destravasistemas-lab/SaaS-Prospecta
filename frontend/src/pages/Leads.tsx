import { useEffect, useState } from 'react'
import {
  Users, Search, Flame, Thermometer, Snowflake,
  MessageCircle, RefreshCw, Trash2, ChevronDown, X, Send,
  TrendingUp, GitMerge,
} from 'lucide-react'
import api from '../services/api'

interface Lead {
  id: string
  name: string | null
  instagram_handle: string
  ig_user_id: string | null
  email: string | null
  phone: string | null
  origin_ad_id: string | null
  source: string
  status: string
  score: number | null
  score_label: string | null
  score_notes: string | null
  last_scored_at: string | null
  captured_at: string
}

const statusConfig: Record<string, { label: string; color: string; dot: string }> = {
  new:       { label: 'Novo',         color: 'bg-blue-900/30 text-blue-300 border-blue-500/20',    dot: 'bg-blue-400' },
  contacted: { label: 'Contactado',   color: 'bg-purple-900/30 text-purple-300 border-purple-500/20', dot: 'bg-purple-400' },
  qualified: { label: 'Qualificado',  color: 'bg-yellow-900/30 text-yellow-300 border-yellow-500/20', dot: 'bg-yellow-400' },
  converted: { label: 'Convertido',   color: 'bg-green-900/30 text-green-300 border-green-500/20',  dot: 'bg-green-400' },
  lost:      { label: 'Perdido',      color: 'bg-red-900/30 text-red-300 border-red-500/20',       dot: 'bg-red-400' },
}

const sourceLabel: Record<string, string> = {
  instagram_comment: 'Comentário',
  instagram_dm: 'DM',
  instagram_form: 'Formulário',
  manual: 'Manual',
}

function ScoreBadge({ label, score }: { label: string | null; score: number | null }) {
  if (!label || score === null) {
    return <span className="text-[#444] text-xs">—</span>
  }
  if (label === 'hot' || label === 'converted') {
    return (
      <span className="inline-flex items-center gap-1 text-xs font-semibold px-2 py-0.5 rounded-full bg-orange-900/30 text-orange-300 border border-orange-500/20">
        <Flame size={10} />
        {score}
      </span>
    )
  }
  if (label === 'warm') {
    return (
      <span className="inline-flex items-center gap-1 text-xs font-semibold px-2 py-0.5 rounded-full bg-amber-900/30 text-amber-300 border border-amber-500/20">
        <Thermometer size={10} />
        {score}
      </span>
    )
  }
  return (
    <span className="inline-flex items-center gap-1 text-xs font-semibold px-2 py-0.5 rounded-full bg-sky-900/30 text-sky-300 border border-sky-500/20">
      <Snowflake size={10} />
      {score}
    </span>
  )
}

function StatusPill({ status }: { status: string }) {
  const cfg = statusConfig[status] ?? { label: status, color: 'bg-white/[0.06] text-[#888] border-white/[0.06]', dot: 'bg-gray-400' }
  return (
    <span className={`inline-flex items-center gap-1.5 text-[11px] font-medium px-2 py-0.5 rounded-full border ${cfg.color}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${cfg.dot}`} />
      {cfg.label}
    </span>
  )
}

export default function Leads() {
  const [leads, setLeads] = useState<Lead[]>([])
  const [loading, setLoading] = useState(true)
  const [scoring, setScoring] = useState(false)
  const [search, setSearch] = useState('')
  const [filterStatus, setFilterStatus] = useState('')
  const [filterScore, setFilterScore] = useState('')

  // DM modal
  const [dmLead, setDmLead] = useState<Lead | null>(null)
  const [dmMessage, setDmMessage] = useState('')
  const [dmSending, setDmSending] = useState(false)
  const [dmError, setDmError] = useState('')
  const [dmSuccess, setDmSuccess] = useState(false)

  // Status dropdown
  const [editingStatus, setEditingStatus] = useState<string | null>(null)

  // Merge modal — lead sobrevivente + busca do lead a absorver
  const [mergeSurvivor, setMergeSurvivor] = useState<Lead | null>(null)
  const [mergeSearch, setMergeSearch] = useState('')
  const [merging, setMerging] = useState(false)
  const [mergeError, setMergeError] = useState('')

  useEffect(() => { loadLeads() }, [filterStatus, filterScore])

  async function loadLeads() {
    setLoading(true)
    try {
      const params: Record<string, string> = {}
      if (filterStatus) params.status = filterStatus
      if (filterScore) params.score_label = filterScore
      const { data } = await api.get('/leads', { params })
      setLeads(data)
    } catch {
      /* ignore */
    } finally {
      setLoading(false)
    }
  }

  async function handleScoreAll() {
    setScoring(true)
    try {
      await api.post('/leads/score-all')
      await loadLeads()
    } finally {
      setScoring(false)
    }
  }

  async function handleStatusChange(leadId: string, newStatus: string) {
    setEditingStatus(null)
    try {
      await api.put(`/leads/${leadId}`, { status: newStatus })
      setLeads((prev) => prev.map((l) => l.id === leadId ? { ...l, status: newStatus } : l))
    } catch { /* ignore */ }
  }

  async function handleDelete(leadId: string) {
    if (!confirm('Remover este lead?')) return
    try {
      await api.delete(`/leads/${leadId}`)
      setLeads((prev) => prev.filter((l) => l.id !== leadId))
    } catch { /* ignore */ }
  }

  async function handleMerge(absorbedId: string) {
    if (!mergeSurvivor) return
    setMerging(true)
    setMergeError('')
    try {
      await api.post(`/leads/${mergeSurvivor.id}/merge`, { absorbed_lead_id: absorbedId })
      setMergeSurvivor(null)
      setMergeSearch('')
      await loadLeads()
    } catch (err: any) {
      setMergeError(err.response?.data?.detail || 'Erro ao mesclar leads.')
    } finally {
      setMerging(false)
    }
  }

  async function handleSendDM(e: React.SyntheticEvent) {
    e.preventDefault()
    if (!dmLead || !dmMessage.trim()) return
    setDmSending(true)
    setDmError('')
    try {
      await api.post('/instagram/dm/send', {
        recipient_ig_user_id: dmLead.ig_user_id,
        message: dmMessage.trim(),
        lead_id: dmLead.id,
      })
      setDmSuccess(true)
      setLeads((prev) => prev.map((l) =>
        l.id === dmLead.id && l.status === 'new' ? { ...l, status: 'contacted' } : l
      ))
      setTimeout(() => { setDmLead(null); setDmSuccess(false); setDmMessage('') }, 1500)
    } catch (err: any) {
      setDmError(err.response?.data?.detail || 'Erro ao enviar DM.')
    } finally {
      setDmSending(false)
    }
  }

  const filtered = leads.filter((l) => {
    if (!search) return true
    const s = search.toLowerCase()
    return (
      (l.name || '').toLowerCase().includes(s) ||
      l.instagram_handle.toLowerCase().includes(s) ||
      (l.email || '').toLowerCase().includes(s)
    )
  })

  const hotCount   = leads.filter((l) => l.score_label === 'hot').length
  const warmCount  = leads.filter((l) => l.score_label === 'warm').length
  const coldCount  = leads.filter((l) => l.score_label === 'cold').length
  const noScore    = leads.filter((l) => !l.score_label).length

  return (
    <div className="max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold text-[#e2e2e8] flex items-center gap-2">
            <Users size={20} className="text-indigo-400" />
            Leads
          </h1>
          <p className="text-[#555] text-sm mt-0.5">
            {leads.length} leads captados
          </p>
        </div>
        <button
          onClick={handleScoreAll}
          disabled={scoring || leads.length === 0}
          className="flex items-center gap-2 px-3.5 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm font-medium rounded-lg transition-colors"
        >
          <RefreshCw size={14} className={scoring ? 'animate-spin' : ''} />
          {scoring ? 'Analisando...' : 'Analisar Leads'}
        </button>
      </div>

      {/* Score summary cards */}
      {leads.length > 0 && (
        <div className="grid grid-cols-4 gap-3 mb-5">
          <button
            onClick={() => setFilterScore(filterScore === 'hot' ? '' : 'hot')}
            className={`flex items-center gap-2.5 p-3 rounded-xl border transition-all text-left ${
              filterScore === 'hot'
                ? 'bg-orange-900/30 border-orange-500/30'
                : 'bg-[#111118] border-white/[0.06] hover:border-orange-500/20'
            }`}
          >
            <div className="w-8 h-8 rounded-lg bg-orange-900/30 flex items-center justify-center">
              <Flame size={15} className="text-orange-400" />
            </div>
            <div>
              <p className="text-lg font-semibold text-[#e2e2e8] leading-none">{hotCount}</p>
              <p className="text-[11px] text-[#555] mt-0.5">Quentes</p>
            </div>
          </button>

          <button
            onClick={() => setFilterScore(filterScore === 'warm' ? '' : 'warm')}
            className={`flex items-center gap-2.5 p-3 rounded-xl border transition-all text-left ${
              filterScore === 'warm'
                ? 'bg-amber-900/30 border-amber-500/30'
                : 'bg-[#111118] border-white/[0.06] hover:border-amber-500/20'
            }`}
          >
            <div className="w-8 h-8 rounded-lg bg-amber-900/30 flex items-center justify-center">
              <Thermometer size={15} className="text-amber-400" />
            </div>
            <div>
              <p className="text-lg font-semibold text-[#e2e2e8] leading-none">{warmCount}</p>
              <p className="text-[11px] text-[#555] mt-0.5">Mornos</p>
            </div>
          </button>

          <button
            onClick={() => setFilterScore(filterScore === 'cold' ? '' : 'cold')}
            className={`flex items-center gap-2.5 p-3 rounded-xl border transition-all text-left ${
              filterScore === 'cold'
                ? 'bg-sky-900/30 border-sky-500/30'
                : 'bg-[#111118] border-white/[0.06] hover:border-sky-500/20'
            }`}
          >
            <div className="w-8 h-8 rounded-lg bg-sky-900/30 flex items-center justify-center">
              <Snowflake size={15} className="text-sky-400" />
            </div>
            <div>
              <p className="text-lg font-semibold text-[#e2e2e8] leading-none">{coldCount}</p>
              <p className="text-[11px] text-[#555] mt-0.5">Frios</p>
            </div>
          </button>

          <div className="flex items-center gap-2.5 p-3 rounded-xl border bg-[#111118] border-white/[0.06]">
            <div className="w-8 h-8 rounded-lg bg-white/[0.04] flex items-center justify-center">
              <TrendingUp size={15} className="text-[#555]" />
            </div>
            <div>
              <p className="text-lg font-semibold text-[#e2e2e8] leading-none">
                {leads.length > 0
                  ? Math.round(leads.filter((l) => l.score !== null).reduce((acc, l) => acc + (l.score ?? 0), 0) / Math.max(leads.filter((l) => l.score !== null).length, 1))
                  : 0}
              </p>
              <p className="text-[11px] text-[#555] mt-0.5">Score médio</p>
            </div>
          </div>
        </div>
      )}

      {/* Search + filters */}
      <div className="flex gap-3 mb-4">
        <div className="flex-1 relative">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#444]" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Buscar por nome, @handle ou email..."
            className="w-full pl-9 pr-4 py-2.5 bg-[#111118] border border-white/[0.06] text-[#e2e2e8] text-sm rounded-lg focus:outline-none focus:border-indigo-500/50 placeholder-[#333]"
          />
        </div>

        <select
          value={filterStatus}
          onChange={(e) => setFilterStatus(e.target.value)}
          className="px-3 py-2.5 bg-[#111118] border border-white/[0.06] text-[#888] text-sm rounded-lg focus:outline-none focus:border-indigo-500/50 appearance-none cursor-pointer"
        >
          <option value="">Todos os status</option>
          <option value="new">Novos</option>
          <option value="contacted">Contactados</option>
          <option value="qualified">Qualificados</option>
          <option value="converted">Convertidos</option>
          <option value="lost">Perdidos</option>
        </select>
      </div>

      {/* Active filters */}
      {(filterScore || filterStatus) && (
        <div className="flex items-center gap-2 mb-4">
          <span className="text-[11px] text-[#444]">Filtros ativos:</span>
          {filterScore && (
            <button
              onClick={() => setFilterScore('')}
              className="inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-full bg-indigo-900/30 text-indigo-300 border border-indigo-500/20 hover:border-indigo-500/50"
            >
              Score: {filterScore}
              <X size={10} />
            </button>
          )}
          {filterStatus && (
            <button
              onClick={() => setFilterStatus('')}
              className="inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-full bg-indigo-900/30 text-indigo-300 border border-indigo-500/20 hover:border-indigo-500/50"
            >
              Status: {statusConfig[filterStatus]?.label ?? filterStatus}
              <X size={10} />
            </button>
          )}
        </div>
      )}

      {/* Table */}
      {loading ? (
        <div className="bg-[#111118] rounded-xl border border-white/[0.06] overflow-hidden">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="flex items-center gap-4 px-5 py-3.5 border-b border-white/[0.04] animate-pulse">
              <div className="w-8 h-8 rounded-full bg-white/[0.04]" />
              <div className="flex-1 space-y-1.5">
                <div className="h-3 bg-white/[0.04] rounded w-32" />
                <div className="h-2.5 bg-white/[0.03] rounded w-24" />
              </div>
              <div className="h-5 w-16 bg-white/[0.04] rounded-full" />
              <div className="h-5 w-12 bg-white/[0.04] rounded-full" />
              <div className="h-5 w-20 bg-white/[0.04] rounded-full" />
            </div>
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <div className="bg-[#111118] rounded-xl border border-white/[0.06] p-16 text-center">
          <div className="w-14 h-14 rounded-2xl bg-indigo-500/10 flex items-center justify-center mx-auto mb-4">
            <Users size={24} className="text-indigo-400" />
          </div>
          <h3 className="text-base font-semibold text-[#e2e2e8] mb-1.5">
            {leads.length === 0 ? 'Nenhum lead captado' : 'Nenhum resultado'}
          </h3>
          <p className="text-[#444] text-sm max-w-sm mx-auto">
            {leads.length === 0
              ? 'Conecte sua conta Meta e configure a automação para captar leads pelo Instagram.'
              : 'Tente ajustar os filtros ou a busca.'}
          </p>
        </div>
      ) : (
        <div className="bg-[#111118] rounded-xl border border-white/[0.06] overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-white/[0.05]">
                <th className="text-left px-5 py-3 text-[11px] font-medium uppercase tracking-wider text-[#444]">Lead</th>
                <th className="text-left px-4 py-3 text-[11px] font-medium uppercase tracking-wider text-[#444]">Origem</th>
                <th className="text-left px-4 py-3 text-[11px] font-medium uppercase tracking-wider text-[#444]">Score</th>
                <th className="text-left px-4 py-3 text-[11px] font-medium uppercase tracking-wider text-[#444]">Status</th>
                <th className="text-left px-4 py-3 text-[11px] font-medium uppercase tracking-wider text-[#444]">Data</th>
                <th className="text-right px-5 py-3 text-[11px] font-medium uppercase tracking-wider text-[#444]">Ações</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((lead) => (
                <tr key={lead.id} className="border-b border-white/[0.03] hover:bg-white/[0.015] transition-colors group">
                  {/* Lead info */}
                  <td className="px-5 py-3.5">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-full bg-indigo-500/10 flex items-center justify-center text-xs font-semibold text-indigo-400 shrink-0">
                        {(lead.name || lead.instagram_handle).charAt(0).toUpperCase()}
                      </div>
                      <div>
                        <p className="text-[#d0d0e0] font-medium text-[13px] leading-tight">
                          {lead.name || <span className="text-[#444] italic">sem nome</span>}
                        </p>
                        <p className="text-[#555] text-[11px] mt-0.5">@{lead.instagram_handle}</p>
                        {lead.email && <p className="text-[#444] text-[10px]">{lead.email}</p>}
                      </div>
                    </div>
                  </td>

                  {/* Source */}
                  <td className="px-4 py-3.5">
                    <div className="flex items-center gap-1.5 flex-wrap">
                      <span className="text-xs text-[#555]">
                        {sourceLabel[lead.source] ?? lead.source}
                      </span>
                      {lead.origin_ad_id && (
                        <span
                          title={`Veio do anúncio ${lead.origin_ad_id}`}
                          className="text-[10px] px-1.5 py-0.5 rounded bg-violet-900/30 text-violet-300 border border-violet-500/20"
                        >
                          📣 Anúncio
                        </span>
                      )}
                    </div>
                  </td>

                  {/* Score */}
                  <td className="px-4 py-3.5">
                    <div>
                      <ScoreBadge label={lead.score_label} score={lead.score} />
                      {lead.score_notes && (
                        <p className="text-[10px] text-[#3a3a4a] mt-0.5 max-w-[120px] truncate" title={lead.score_notes}>
                          {lead.score_notes}
                        </p>
                      )}
                    </div>
                  </td>

                  {/* Status with dropdown */}
                  <td className="px-4 py-3.5 relative">
                    <button
                      onClick={() => setEditingStatus(editingStatus === lead.id ? null : lead.id)}
                      className="flex items-center gap-1 group/status"
                    >
                      <StatusPill status={lead.status} />
                      <ChevronDown size={10} className="text-[#333] group-hover/status:text-[#555] transition-colors" />
                    </button>
                    {editingStatus === lead.id && (
                      <div className="absolute z-20 left-4 top-full mt-1 bg-[#1a1a24] border border-white/[0.1] rounded-xl shadow-xl py-1 min-w-[140px]">
                        {Object.entries(statusConfig).map(([key, cfg]) => (
                          <button
                            key={key}
                            onClick={() => handleStatusChange(lead.id, key)}
                            className={`w-full text-left px-3 py-2 text-xs flex items-center gap-2 hover:bg-white/[0.04] transition-colors ${
                              lead.status === key ? 'text-indigo-300' : 'text-[#888]'
                            }`}
                          >
                            <span className={`w-1.5 h-1.5 rounded-full ${cfg.dot}`} />
                            {cfg.label}
                          </button>
                        ))}
                      </div>
                    )}
                  </td>

                  {/* Date */}
                  <td className="px-4 py-3.5">
                    <span className="text-[#444] text-xs">
                      {new Date(lead.captured_at).toLocaleDateString('pt-BR', { day: '2-digit', month: 'short' })}
                    </span>
                  </td>

                  {/* Actions */}
                  <td className="px-5 py-3.5">
                    <div className="flex items-center justify-end gap-1.5 opacity-0 group-hover:opacity-100 transition-opacity">
                      <button
                        onClick={() => {
                          setDmLead(lead)
                          setDmMessage('')
                          setDmError('')
                          setDmSuccess(false)
                        }}
                        disabled={!lead.ig_user_id}
                        title={lead.ig_user_id ? 'Enviar DM' : 'ID do Instagram não disponível'}
                        className="p-1.5 rounded-lg bg-indigo-600/20 text-indigo-400 hover:bg-indigo-600/40 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                      >
                        <MessageCircle size={13} />
                      </button>
                      <button
                        onClick={() => {
                          setMergeSurvivor(lead)
                          setMergeSearch('')
                          setMergeError('')
                        }}
                        title="Mesclar com outro lead (mesma pessoa em outro canal)"
                        className="p-1.5 rounded-lg bg-white/[0.04] text-[#8a8a9e] hover:bg-indigo-600/30 hover:text-indigo-300 transition-colors"
                      >
                        <GitMerge size={13} />
                      </button>
                      <button
                        onClick={() => handleDelete(lead.id)}
                        className="p-1.5 rounded-lg bg-red-900/20 text-red-400 hover:bg-red-900/40 transition-colors"
                      >
                        <Trash2 size={13} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          <div className="px-5 py-3 border-t border-white/[0.04] flex items-center justify-between">
            <p className="text-[11px] text-[#444]">
              {filtered.length} de {leads.length} leads
              {noScore > 0 && ` · ${noScore} sem score (clique em "Analisar Leads")`}
            </p>
          </div>
        </div>
      )}

      {/* DM Modal */}
      {dmLead && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm px-4">
          <div className="bg-[#111118] border border-white/[0.08] rounded-2xl p-7 w-full max-w-md">
            <div className="flex items-center justify-between mb-5">
              <div>
                <h3 className="text-base font-semibold text-white flex items-center gap-2">
                  <MessageCircle size={16} className="text-indigo-400" />
                  Enviar DM
                </h3>
                <p className="text-xs text-[#555] mt-0.5">Para @{dmLead.instagram_handle}</p>
              </div>
              <button onClick={() => setDmLead(null)} className="text-[#444] hover:text-[#888] transition-colors">
                <X size={18} />
              </button>
            </div>

            {dmSuccess ? (
              <div className="text-center py-6">
                <div className="w-12 h-12 rounded-full bg-green-900/30 flex items-center justify-center mx-auto mb-3">
                  <Send size={20} className="text-green-400" />
                </div>
                <p className="text-green-400 font-medium">DM enviada com sucesso!</p>
              </div>
            ) : (
              <form onSubmit={handleSendDM} className="space-y-4">
                {dmError && (
                  <div className="bg-red-900/20 border border-red-500/20 text-red-400 text-xs rounded-lg px-4 py-3">
                    {dmError}
                  </div>
                )}
                <div>
                  <label className="block text-xs font-medium text-[#666] mb-1.5">Mensagem</label>
                  <textarea
                    value={dmMessage}
                    onChange={(e) => setDmMessage(e.target.value)}
                    placeholder="Escreva sua mensagem..."
                    rows={4}
                    className="w-full px-4 py-3 bg-[#0a0a0f] border border-white/[0.08] text-[#e2e2e8] text-sm rounded-lg focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500 focus:outline-none placeholder-[#333] resize-none"
                  />
                </div>
                <div className="flex gap-3">
                  <button
                    type="button"
                    onClick={() => setDmLead(null)}
                    className="flex-1 py-2.5 border border-white/[0.08] text-[#666] hover:text-white text-sm font-medium rounded-lg transition-colors"
                  >
                    Cancelar
                  </button>
                  <button
                    type="submit"
                    disabled={dmSending || !dmMessage.trim()}
                    className="flex-1 py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm font-semibold rounded-lg transition-colors flex items-center justify-center gap-2"
                  >
                    <Send size={14} />
                    {dmSending ? 'Enviando...' : 'Enviar'}
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}

      {/* Merge modal */}
      {mergeSurvivor && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm px-4">
          <div className="bg-[#111118] border border-white/[0.08] rounded-2xl p-7 w-full max-w-lg">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-base font-semibold text-white flex items-center gap-2">
                  <GitMerge size={16} className="text-indigo-400" />
                  Mesclar leads
                </h3>
                <p className="text-xs text-[#555] mt-0.5">
                  Escolha o lead que é a mesma pessoa. Ele será fundido em{' '}
                  <span className="text-[#c0c0d0] font-medium">
                    {mergeSurvivor.name || mergeSurvivor.instagram_handle}
                  </span>{' '}
                  e removido.
                </p>
              </div>
              <button onClick={() => setMergeSurvivor(null)} className="text-[#444] hover:text-[#888] transition-colors">
                <X size={18} />
              </button>
            </div>

            <div className="bg-indigo-900/15 border border-indigo-500/20 rounded-lg px-3 py-2 mb-3">
              <p className="text-[11px] text-indigo-300/90">
                Manter (sobrevivente): <strong>{mergeSurvivor.name || mergeSurvivor.instagram_handle}</strong>
                {mergeSurvivor.phone && ` · ${mergeSurvivor.phone}`}
                {' · '}{sourceLabel[mergeSurvivor.source] ?? mergeSurvivor.source}
              </p>
            </div>

            {mergeError && (
              <div className="bg-red-900/20 border border-red-500/20 text-red-400 text-xs rounded-lg px-4 py-2.5 mb-3">
                {mergeError}
              </div>
            )}

            <div className="relative mb-2">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#444]" />
              <input
                autoFocus
                value={mergeSearch}
                onChange={(e) => setMergeSearch(e.target.value)}
                placeholder="Buscar o lead a mesclar (nome, @handle, telefone)…"
                className="w-full pl-9 pr-4 py-2.5 bg-[#0a0a0f] border border-white/[0.08] text-[#e2e2e8] text-sm rounded-lg focus:outline-none focus:border-indigo-500/50 placeholder-[#333]"
              />
            </div>

            <div className="max-h-64 overflow-y-auto border border-white/[0.06] rounded-lg divide-y divide-white/[0.04]">
              {leads
                .filter((l) => l.id !== mergeSurvivor.id)
                .filter((l) => {
                  if (!mergeSearch.trim()) return true
                  const s = mergeSearch.toLowerCase()
                  return (
                    (l.name || '').toLowerCase().includes(s) ||
                    l.instagram_handle.toLowerCase().includes(s) ||
                    (l.phone || '').toLowerCase().includes(s)
                  )
                })
                .slice(0, 30)
                .map((l) => (
                  <button
                    key={l.id}
                    onClick={() => handleMerge(l.id)}
                    disabled={merging}
                    className="w-full flex items-center gap-3 px-3 py-2.5 text-left hover:bg-white/[0.03] disabled:opacity-50 transition-colors"
                  >
                    <div className="w-8 h-8 rounded-full bg-white/[0.06] flex items-center justify-center text-xs font-semibold text-[#8a8a9e] shrink-0">
                      {(l.name || l.instagram_handle).charAt(0).toUpperCase()}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-[13px] text-[#d0d0e0] font-medium truncate">
                        {l.name || l.instagram_handle}
                      </p>
                      <p className="text-[11px] text-[#555] truncate">
                        {l.phone ? l.phone : `@${l.instagram_handle}`}
                        {' · '}{sourceLabel[l.source] ?? l.source}
                      </p>
                    </div>
                    <GitMerge size={13} className="text-[#444] shrink-0" />
                  </button>
                ))}
              {leads.filter((l) => l.id !== mergeSurvivor.id).length === 0 && (
                <p className="text-center text-[#555] text-xs py-6">Não há outro lead para mesclar.</p>
              )}
            </div>

            {merging && <p className="text-[11px] text-[#555] mt-3 text-center">Mesclando…</p>}
          </div>
        </div>
      )}

      {/* Close dropdown on outside click */}
      {editingStatus && (
        <div className="fixed inset-0 z-10" onClick={() => setEditingStatus(null)} />
      )}
    </div>
  )
}
