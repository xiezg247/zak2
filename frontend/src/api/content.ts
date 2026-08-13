import { api } from './client'

export type PlaybookSection = {
  section_id: string
  title: string
  body_md: string
  collapsed: boolean
  sort_order: number
  updated_at: string
}

export type DisciplineCheck = {
  check_id: string
  label: string
  checked: boolean
}

export type NoteSymbol = {
  symbol: string
  exchange: string
  vt_symbol: string
  memo_preview: string
  entry_count: number
  updated_at: string
}

export type NoteMemo = {
  symbol: string
  exchange: string
  vt_symbol: string
  body: string
  updated_at: string
}

export type NoteEntry = {
  id: number
  symbol: string
  exchange: string
  vt_symbol: string
  body: string
  created_at: string
}

export type TeamReportListItem = {
  id: number
  title: string
  summary: string
  mode: string
  created_at: string
  vt_symbol: string
}

export type TeamReport = {
  id: number
  symbol: string
  exchange: string
  vt_symbol: string
  title: string
  body: string
  summary: string
  mode: string
  context_json: string
  created_at: string
}

export type BilibiliUserHit = {
  mid: string
  name: string
  avatar: string
  sign: string
}

export type FeedSub = {
  id: string
  source_type: string
  source_id: string
  display_name: string
  avatar_url: string
  enabled: boolean
  sort_order: number
  sync_error?: string | null
}

export type FeedItem = {
  id: string
  subscription_id: string
  source_type: string
  item_type: string
  title: string
  summary: string
  url: string
  author_name: string
  published_at: string
  is_read: boolean
}

export type Plan = {
  id: string
  trade_date: string
  emotion_expected: string
  max_position_pct: number
  notes: string
  status: string
  symbols: {
    vt_symbol: string
    allowed_modes: string
    entry_conditions: string
    symbol?: string
    exchange?: string
  }[]
}

export const contentApi = {
  sections: () => api<PlaybookSection[]>('/api/v1/playbook/sections'),
  updateSection: (id: string, body: Partial<PlaybookSection>) =>
    api<PlaybookSection>(`/api/v1/playbook/sections/${encodeURIComponent(id)}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),
  discipline: (tradeDate?: string) => {
    const q = tradeDate ? `?trade_date=${encodeURIComponent(tradeDate)}` : ''
    return api<DisciplineCheck[]>(`/api/v1/playbook/discipline${q}`)
  },
  setDiscipline: (checkId: string, checked: boolean, tradeDate?: string) => {
    const q = tradeDate ? `?trade_date=${encodeURIComponent(tradeDate)}` : ''
    return api<DisciplineCheck>(`/api/v1/playbook/discipline/${encodeURIComponent(checkId)}${q}`, {
      method: 'PUT',
      body: JSON.stringify({ checked }),
    })
  },
  plans: () => api<Plan[]>('/api/v1/playbook/plans'),
  patchPlan: (id: string, body: { notes?: string; max_position_pct?: number; symbols?: string[] }) =>
    api<Plan>(`/api/v1/playbook/plans/${encodeURIComponent(id)}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),
  activatePlan: (id: string) =>
    api<Plan>(`/api/v1/playbook/plans/${encodeURIComponent(id)}/activate`, { method: 'POST' }),
  abandonPlan: (id: string) =>
    api<Plan>(`/api/v1/playbook/plans/${encodeURIComponent(id)}/abandon`, { method: 'POST' }),
  noteSymbols: () => api<NoteSymbol[]>('/api/v1/notes/symbols'),
  memo: (vt: string) => api<NoteMemo>(`/api/v1/notes/${encodeURIComponent(vt)}/memo`),
  saveMemo: (vt: string, body: string) =>
    api<NoteMemo>(`/api/v1/notes/${encodeURIComponent(vt)}/memo`, {
      method: 'PUT',
      body: JSON.stringify({ body }),
    }),
  entries: (vt: string) => api<NoteEntry[]>(`/api/v1/notes/${encodeURIComponent(vt)}/entries`),
  addEntry: (vt: string, body: string) =>
    api<NoteEntry>(`/api/v1/notes/${encodeURIComponent(vt)}/entries`, {
      method: 'POST',
      body: JSON.stringify({ body }),
    }),
  deleteEntry: (id: number) =>
    api<{ ok: boolean }>(`/api/v1/notes/entries/${id}`, { method: 'DELETE' }),
  teamReports: (vt: string) =>
    api<TeamReportListItem[]>(`/api/v1/notes/${encodeURIComponent(vt)}/reports`),
  teamReport: (id: number) => api<TeamReport>(`/api/v1/notes/reports/${id}`),
  feedSubs: () => api<FeedSub[]>('/api/v1/feed/subscriptions'),
  searchBilibiliUps: (q: string, limit = 8) =>
    api<{ results: BilibiliUserHit[] }>(
      `/api/v1/feed/bilibili/search?q=${encodeURIComponent(q)}&limit=${limit}`,
    ),
  addFeedSub: (body: { mid: string; sync_now?: boolean }) =>
    api<FeedSub>(`/api/v1/feed/subscriptions`, { method: 'POST', body: JSON.stringify(body) }),
  removeFeedSub: (id: string) =>
    api<{ ok: boolean }>(`/api/v1/feed/subscriptions/${encodeURIComponent(id)}`, {
      method: 'DELETE',
    }),
  setFeedEnabled: (id: string, enabled: boolean) =>
    api<FeedSub>(`/api/v1/feed/subscriptions/${encodeURIComponent(id)}?enabled=${enabled}`, {
      method: 'PATCH',
    }),
  feedItems: (subscriptionId?: string) => {
    const q = subscriptionId ? `?subscription_id=${encodeURIComponent(subscriptionId)}` : ''
    return api<FeedItem[]>(`/api/v1/feed/items${q}`)
  },
  markRead: (id: string) =>
    api<{ ok: boolean }>(`/api/v1/feed/items/${encodeURIComponent(id)}/read`, { method: 'POST' }),
}
