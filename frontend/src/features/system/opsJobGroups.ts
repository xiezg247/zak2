import type { SchedulerJob } from '../../api/ops'

/** Pure helpers for OpsView job filter/group. No vitest in frontend — verify via npm run build / smoke. */

export type JobKind = 'runnable' | 'process' | 'planned'
export type JobFilter = 'all' | JobKind

export const KIND_ORDER: JobKind[] = ['runnable', 'process', 'planned']
export const KIND_TITLE: Record<JobKind, string> = {
  runnable: '可跑',
  process: '独立进程',
  planned: '未实现',
}

export function filterJobs(jobs: SchedulerJob[], filter: JobFilter): SchedulerJob[] {
  if (filter === 'all') return jobs
  return jobs.filter((j) => j.job_kind === filter)
}

export type JobGroup = { kind: JobKind; title: string; items: SchedulerJob[] }

export function groupJobs(jobs: SchedulerJob[]): JobGroup[] {
  return KIND_ORDER.map((kind) => ({
    kind,
    title: KIND_TITLE[kind],
    items: jobs.filter((j) => j.job_kind === kind),
  })).filter((g) => g.items.length > 0)
}
