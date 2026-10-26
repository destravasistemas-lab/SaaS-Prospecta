import { useCallback, useEffect, useState } from 'react'
import { Eye, EyeOff, Reply, Send, Trash2, X } from 'lucide-react'
import api, { apiError } from '../services/api'
import { useI18n } from '../i18n'

interface IgReply {
  id: string
  text: string
  username: string | null
  timestamp: string | null
  hidden: boolean
}

interface IgComment extends IgReply {
  like_count: number
  replies: IgReply[]
}

/** Moderação dos comentários de um post: comentar, responder, ocultar/reexibir e excluir. */
export default function IgCommentsModal({ mediaId, caption, onClose }: { mediaId: string; caption: string | null; onClose: () => void }) {
  const { t, locale } = useI18n()
  const [comments, setComments] = useState<IgComment[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [busyId, setBusyId] = useState<string | null>(null)
  const [newComment, setNewComment] = useState('')
  const [replyTo, setReplyTo] = useState<string | null>(null)
  const [replyText, setReplyText] = useState('')

  const load = useCallback(async () => {
    setError('')
    try {
      const { data } = await api.get<IgComment[]>(`/instagram/media/${mediaId}/comments`)
      setComments(data)
    } catch (err: any) {
      setError(apiError(err, t('Não foi possível carregar os comentários.', 'Could not load the comments.')))
    } finally {
      setLoading(false)
    }
  }, [mediaId])

  useEffect(() => { load() }, [load])

  async function run(id: string, action: () => Promise<unknown>, fallback: string): Promise<boolean> {
    setBusyId(id)
    setError('')
    try {
      await action()
      await load()
      return true
    } catch (err: any) {
      setError(apiError(err, fallback))
      return false
    } finally {
      setBusyId(null)
    }
  }

  function postComment(e: React.FormEvent) {
    e.preventDefault()
    if (!newComment.trim()) return
    run('new', () => api.post(`/instagram/media/${mediaId}/comments`, { message: newComment.trim() }),
      t('Erro ao publicar o comentário.', 'Failed to post the comment.'))
      .then((ok) => ok && setNewComment(''))
  }

  function sendReply(e: React.FormEvent, commentId: string) {
    e.preventDefault()
    if (!replyText.trim()) return
    run(commentId, () => api.post(`/instagram/comments/${commentId}/replies`, { message: replyText.trim() }),
      t('Erro ao responder.', 'Failed to reply.'))
      .then((ok) => { if (ok) { setReplyTo(null); setReplyText('') } })
  }

  const toggleHidden = (c: IgReply) =>
    run(c.id, () => api.post(`/instagram/comments/${c.id}/visibility`, { hide: !c.hidden }),
      t('Erro ao atualizar o comentário.', 'Failed to update the comment.'))

  const remove = (c: IgReply) => {
    if (!confirm(t('Excluir este comentário do Instagram?', 'Delete this comment from Instagram?'))) return
    run(c.id, () => api.delete(`/instagram/comments/${c.id}`), t('Erro ao excluir o comentário.', 'Failed to delete the comment.'))
  }

  const fmt = (iso: string | null) => (iso ? new Date(iso).toLocaleString(locale) : '')

  function Row({ c, isReply }: { c: IgReply; isReply?: boolean }) {
    const busy = busyId === c.id
    return (
      <div className={`flex items-start gap-3 ${isReply ? 'ml-8 mt-2' : ''} ${c.hidden ? 'opacity-50' : ''}`}>
        <div className="flex-1 min-w-0">
          <p className="text-[13px] text-[#e2e2e8] break-words">
            <span className="font-semibold text-violet-300">@{c.username || '—'}</span> {c.text}
          </p>
          <p className="text-[10px] text-[#555] mt-0.5">
            {fmt(c.timestamp)}
            {c.hidden && <span className="ml-2 text-amber-400">{t('Oculto', 'Hidden')}</span>}
          </p>
        </div>
        <div className="flex items-center gap-1 shrink-0">
          {!isReply && (
            <button onClick={() => { setReplyTo(replyTo === c.id ? null : c.id); setReplyText('') }} disabled={busy}
              title={t('Responder', 'Reply')} className="p-1.5 rounded-md text-[#8a8a9e] hover:text-white hover:bg-white/[0.06] disabled:opacity-40">
              <Reply size={14} />
            </button>
          )}
          <button onClick={() => toggleHidden(c)} disabled={busy}
            title={c.hidden ? t('Reexibir', 'Unhide') : t('Ocultar', 'Hide')}
            className="p-1.5 rounded-md text-[#8a8a9e] hover:text-amber-300 hover:bg-white/[0.06] disabled:opacity-40">
            {c.hidden ? <Eye size={14} /> : <EyeOff size={14} />}
          </button>
          <button onClick={() => remove(c)} disabled={busy}
            title={t('Excluir', 'Delete')} className="p-1.5 rounded-md text-[#8a8a9e] hover:text-red-400 hover:bg-white/[0.06] disabled:opacity-40">
            <Trash2 size={14} />
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm px-4 py-8">
      <div className="bg-[#170e2c] border border-white/[0.08] rounded-2xl w-full max-w-lg max-h-full flex flex-col">
        <div className="flex items-start justify-between gap-3 p-5 border-b border-white/[0.06]">
          <div className="min-w-0">
            <h3 className="text-white font-semibold text-base">{t('Comentários do post', 'Post comments')}</h3>
            <p className="text-[#666] text-xs truncate">{caption || t('Sem legenda', 'No caption')}</p>
          </div>
          <button onClick={onClose} className="text-[#555] hover:text-white"><X size={18} /></button>
        </div>

        <div className="flex-1 overflow-y-auto p-5 space-y-4">
          {error && <p className="text-red-400 text-xs">{error}</p>}
          {loading ? (
            <p className="text-[#555] text-sm">{t('Carregando…', 'Loading…')}</p>
          ) : comments.length === 0 ? (
            <p className="text-[#555] text-sm">{t('Nenhum comentário ainda.', 'No comments yet.')}</p>
          ) : (
            comments.map((c) => (
              <div key={c.id} className="pb-3 border-b border-white/[0.04] last:border-0">
                <Row c={c} />
                {c.replies.map((r) => <Row key={r.id} c={r} isReply />)}
                {replyTo === c.id && (
                  <form onSubmit={(e) => sendReply(e, c.id)} className="ml-8 mt-2 flex gap-2">
                    <input value={replyText} onChange={(e) => setReplyText(e.target.value)} autoFocus
                      placeholder={t(`Responder @${c.username || ''}`, `Reply to @${c.username || ''}`)}
                      className="flex-1 px-3 py-1.5 bg-[#0f0820] border border-white/[0.08] text-[#e2e2e8] text-xs rounded-lg focus:border-indigo-500 focus:outline-none" />
                    <button type="submit" disabled={busyId === c.id || !replyText.trim()}
                      className="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-xs font-semibold rounded-lg">
                      {t('Responder', 'Reply')}
                    </button>
                  </form>
                )}
              </div>
            ))
          )}
        </div>

        <form onSubmit={postComment} className="p-4 border-t border-white/[0.06] flex gap-2">
          <input value={newComment} onChange={(e) => setNewComment(e.target.value)}
            placeholder={t('Escreva um comentário no post…', 'Write a comment on the post…')}
            className="flex-1 px-3 py-2 bg-[#0f0820] border border-white/[0.08] text-[#e2e2e8] text-sm rounded-lg focus:border-indigo-500 focus:outline-none" />
          <button type="submit" disabled={busyId === 'new' || !newComment.trim()}
            className="flex items-center gap-1.5 px-3 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm font-semibold rounded-lg">
            <Send size={14} /> {t('Comentar', 'Comment')}
          </button>
        </form>
      </div>
    </div>
  )
}
