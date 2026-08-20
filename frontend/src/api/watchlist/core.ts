import { api } from '../client'
import type { GroupMembersBatchResult, WatchlistGroup, WatchlistItem } from './types'

export const watchlistCoreApi = {
  list: (groupId?: string) => {
    const q = groupId ? `?group_id=${encodeURIComponent(groupId)}` : ''
    return api<WatchlistItem[]>(`/api/v1/watchlist${q}`)
  },
  add: (symbol: string, name = '') =>
    api<WatchlistItem>('/api/v1/watchlist', {
      method: 'POST',
      body: JSON.stringify({ symbol, name }),
    }),
  remove: (vtSymbol: string) =>
    api<{ ok: boolean }>(`/api/v1/watchlist/${encodeURIComponent(vtSymbol)}`, {
      method: 'DELETE',
    }),
  groups: () => api<WatchlistGroup[]>('/api/v1/watchlist/groups'),
  createGroup: (name: string) =>
    api<WatchlistGroup>('/api/v1/watchlist/groups', {
      method: 'POST',
      body: JSON.stringify({ name }),
    }),
  deleteGroup: (id: string) =>
    api<{ ok: boolean }>(`/api/v1/watchlist/groups/${encodeURIComponent(id)}`, {
      method: 'DELETE',
    }),
  renameGroup: (id: string, name: string) =>
    api<WatchlistGroup>(`/api/v1/watchlist/groups/${encodeURIComponent(id)}`, {
      method: 'PATCH',
      body: JSON.stringify({ name }),
    }),
  reorderGroups: (groupIds: string[]) =>
    api<WatchlistGroup[]>('/api/v1/watchlist/groups/reorder', {
      method: 'PUT',
      body: JSON.stringify({ group_ids: groupIds }),
    }),
  addToGroup: (groupId: string, symbol: string) =>
    api<{ ok: boolean }>(`/api/v1/watchlist/groups/${encodeURIComponent(groupId)}/members`, {
      method: 'POST',
      body: JSON.stringify({ symbol }),
    }),
  removeFromGroup: (groupId: string, vtSymbol: string) =>
    api<{ ok: boolean }>(
      `/api/v1/watchlist/groups/${encodeURIComponent(groupId)}/members/${encodeURIComponent(vtSymbol)}`,
      { method: 'DELETE' },
    ),
  batchGroupMembers: (groupId: string, symbols: string[], action: 'add' | 'remove') =>
    api<GroupMembersBatchResult>(
      `/api/v1/watchlist/groups/${encodeURIComponent(groupId)}/members/batch`,
      {
        method: 'POST',
        body: JSON.stringify({ symbols, action }),
      },
    ),
}
