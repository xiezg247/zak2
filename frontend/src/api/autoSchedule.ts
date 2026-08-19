import { api } from './client'

export type AutoSchedule = {
  id: number
  name: string
  recipe_id: string
  days_of_week: string
  times: string[]
  enabled: boolean
  last_run_at: string | null
  last_message: string | null
  last_success: boolean | null
  created_at: string
  updated_at: string
}

export type AutoScheduleBody = {
  name: string
  recipe_id: string
  days_of_week: string
  times: string[]
}

export const autoScheduleApi = {
  list: () => api<{ items: AutoSchedule[] }>('/api/v1/auto-schedules'),
  create: (body: AutoScheduleBody) =>
    api<AutoSchedule>('/api/v1/auto-schedules', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  update: (id: number, body: Partial<AutoScheduleBody>) =>
    api<AutoSchedule>(`/api/v1/auto-schedules/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),
  setEnabled: (id: number, enabled: boolean) =>
    api<AutoSchedule>(`/api/v1/auto-schedules/${id}/enabled`, {
      method: 'PATCH',
      body: JSON.stringify({ enabled }),
    }),
  remove: (id: number) =>
    api<{ ok: boolean }>(`/api/v1/auto-schedules/${id}`, {
      method: 'DELETE',
    }),
}
