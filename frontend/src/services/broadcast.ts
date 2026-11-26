import api from './api'
import { tr } from '../i18n'

export interface BroadcastJob {
  id: string
  status: 'queued' | 'running' | 'done' | 'failed' | 'canceled'
  template_name: string
  total: number
  sent: number
  failed: number
  skipped: number
  error: string | null
  error_code: number | null
}

const FINISHED = ['done', 'failed', 'canceled']
const POLL_MS = 1500

/**
 * Cria o disparo e acompanha a fila até terminar. Se já houver um disparo do
 * mesmo template em andamento (clique duplo, outra aba), acompanha aquele.
 * O envio continua no servidor mesmo se a tela for fechada.
 */
export async function runBroadcast(
  body: { template_name: string; language: string; variables: string[]; lead_ids?: string[]; include_without_opt_in?: boolean },
  onProgress: (job: BroadcastJob) => void,
  keepWatching: () => boolean = () => true,
): Promise<BroadcastJob> {
  let job: BroadcastJob
  try {
    job = (await api.post<BroadcastJob>('/whatsapp/broadcast', body)).data
  } catch (err: any) {
    const detail = err?.response?.data?.detail
    if (detail?.code !== 'broadcast_running') throw err
    job = detail.job
  }
  onProgress(job)
  while (!FINISHED.includes(job.status) && keepWatching()) {
    await new Promise((resolve) => setTimeout(resolve, POLL_MS))
    job = (await api.get<BroadcastJob>(`/whatsapp/broadcast/jobs/${job.id}`)).data
    onProgress(job)
  }
  return job
}

export async function cancelBroadcast(jobId: string): Promise<BroadcastJob> {
  return (await api.post<BroadcastJob>(`/whatsapp/broadcast/jobs/${jobId}/cancel`)).data
}

export function isFinished(job: BroadcastJob | null): boolean {
  return !!job && FINISHED.includes(job.status)
}

export function broadcastText(job: BroadcastJob): string {
  const skipped = job.skipped
    ? ' ' + tr(`${job.skipped} pulados (campo vazio ou opt-out).`, `${job.skipped} skipped (empty field or opt-out).`)
    : ''
  if (!isFinished(job)) {
    return tr(
      `Enviando… ${job.sent + job.failed + (job.skipped || 0)} de ${job.total}. Pode fechar esta janela: o envio continua.`,
      `Sending… ${job.sent + job.failed + (job.skipped || 0)} of ${job.total}. You can close this window: sending continues.`,
    )
  }
  if (job.status === 'canceled') {
    return tr(
      `Disparo parado: ${job.sent} enviados antes de parar (de ${job.total}).`,
      `Broadcast stopped: ${job.sent} sent before stopping (of ${job.total}).`,
    ) + skipped
  }
  const summary = tr(
    `Disparo concluído: ${job.sent} enviados · ${job.failed} falharam (de ${job.total}).`,
    `Broadcast finished: ${job.sent} sent · ${job.failed} failed (of ${job.total}).`,
  ) + skipped
  return job.error ? `${summary} ${tr('Motivo das falhas', 'Failure reason')}: ${job.error}` : summary
}
