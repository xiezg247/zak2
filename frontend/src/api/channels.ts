import { api } from './client'

export type Channel = {
  id: string
  channel_type: string
  name: string
  webhook_url: string
  enabled: boolean
  created_at: string
  updated_at: string
}

export type ChannelTestResult = {
  ok: boolean
  message: string
}

export const channelApi = {
  list: () => api<{ items: Channel[] }>('/api/v1/channels'),
  create: (body: { name: string; webhook_url: string; enabled?: boolean }) =>
    api<Channel>('/api/v1/channels', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  update: (id: string, body: { name?: string; webhook_url?: string; enabled?: boolean }) =>
    api<Channel>(`/api/v1/channels/${encodeURIComponent(id)}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),
  remove: (id: string) =>
    api<{ ok: boolean }>(`/api/v1/channels/${encodeURIComponent(id)}`, {
      method: 'DELETE',
    }),
  test: (id: string) =>
    api<ChannelTestResult>(`/api/v1/channels/${encodeURIComponent(id)}/test`, {
      method: 'POST',
    }),
}
