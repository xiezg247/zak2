import { api, getToken, pageQuery, type Page } from './client'

export type Session = {
  id: string
  title: string
  scene: string
  created_at: string
  updated_at: string
}

export type ChatMessage = {
  id: number
  session_id: string
  role: string
  content: string
  created_at: string
}

export type LlmStatus = {
  configured: boolean
  model: string
  api_base: string
}

export type ConfirmProposal = {
  proposal_id: string
  tool: string
  summary: string
  args: Record<string, unknown>
  status: 'pending' | 'confirmed' | 'rejected' | 'error'
  detail?: string
}

export type StreamHandlers = {
  onDelta: (text: string) => void
  onTool?: (event: { type: 'tool_started' | 'tool_finished'; name: string; ok?: boolean }) => void
  onConfirmRequired?: (proposal: ConfirmProposal) => void
  onDone: (msg: ChatMessage) => void
  onError: (err: string) => void
}

export type TeamScoreBlock = {
  score?: number
  summary?: string
  highlights?: string[]
  risks?: string[]
}

export type TeamHandlers = {
  onEvent: (ev: {
    type: string
    agent?: string
    kind?: string
    label?: string
    score?: number
    summary?: string
    content?: string
    weighted?: number
    detail?: string
    vt_symbol?: string
    name?: string
    highlights?: string[]
    risks?: string[]
  }) => void
  onReportSaved?: (ev: { report_id: number; title: string; vt_symbol: string }) => void
  onDone: (msg?: ChatMessage) => void
  onError: (err: string) => void
}

export const aiApi = {
  status: () => api<LlmStatus>('/api/v1/ai/status'),
  sessionsPage: (page = 1, pageSize = 20) =>
    api<Page<Session>>(`/api/v1/ai/sessions/page?${pageQuery(page, pageSize)}`),
  createSession: (title = '', scene = 'general') =>
    api<Session>('/api/v1/ai/sessions', {
      method: 'POST',
      body: JSON.stringify({ title, scene }),
    }),
  deleteSession: (id: string) =>
    api<{ ok: boolean }>(`/api/v1/ai/sessions/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  messages: (id: string) =>
    api<ChatMessage[]>(`/api/v1/ai/sessions/${encodeURIComponent(id)}/messages`),
  chat: (id: string, content: string, includeContext = true, useTools = true) =>
    api<ChatMessage>(`/api/v1/ai/sessions/${encodeURIComponent(id)}/chat`, {
      method: 'POST',
      body: JSON.stringify({ content, include_context: includeContext, use_tools: useTools }),
    }),
  confirmProposal: (proposalId: string) =>
    api<{ ok: boolean; summary: string; result: Record<string, unknown> }>(
      `/api/v1/ai/proposals/${encodeURIComponent(proposalId)}/confirm`,
      { method: 'POST' },
    ),
  rejectProposal: (proposalId: string) =>
    api<{ ok: boolean; status: string }>(
      `/api/v1/ai/proposals/${encodeURIComponent(proposalId)}/reject`,
      { method: 'POST' },
    ),
  streamTeam: async (
    vtSymbol: string,
    handlers: TeamHandlers,
    sessionId?: string,
    mode: 'fast' | 'deep' = 'fast',
  ) => {
    const resp = await fetch('/api/v1/ai/team/stream', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${getToken()}`,
      },
      body: JSON.stringify({
        vt_symbol: vtSymbol,
        session_id: sessionId || null,
        mode,
      }),
    })
    if (!resp.ok || !resp.body) {
      handlers.onError(`HTTP ${resp.status}`)
      return
    }
    const reader = resp.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const parts = buffer.split('\n\n')
      buffer = parts.pop() || ''
      for (const part of parts) {
        const line = part.trim()
        if (!line.startsWith('data: ')) continue
        try {
          const data = JSON.parse(line.slice(6)) as {
            type: string
            agent?: string
            kind?: string
            label?: string
            score?: number
            summary?: string
            content?: string
            weighted?: number
            detail?: string
            vt_symbol?: string
            name?: string
            message?: ChatMessage
            highlights?: string[]
            risks?: string[]
            report_id?: number
            title?: string
          }
          if (data.type === 'error') {
            handlers.onError(data.detail || '团队分析错误')
            continue
          }
          if (data.type === 'done') {
            handlers.onDone(data.message)
            continue
          }
          if (data.type === 'report_saved' && data.report_id != null) {
            handlers.onReportSaved?.({
              report_id: data.report_id,
              title: data.title || '',
              vt_symbol: data.vt_symbol || vtSymbol,
            })
            continue
          }
          if (data.type === 'team') handlers.onEvent(data)
        } catch {
          /* ignore */
        }
      }
    }
  },
  streamChat: async (
    id: string,
    content: string,
    handlers: StreamHandlers,
    includeContext = true,
    useTools = true,
  ) => {
    const resp = await fetch(`/api/v1/ai/sessions/${encodeURIComponent(id)}/chat/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${getToken()}`,
      },
      body: JSON.stringify({ content, include_context: includeContext, use_tools: useTools }),
    })
    if (!resp.ok || !resp.body) {
      handlers.onError(`HTTP ${resp.status}`)
      return
    }
    const reader = resp.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const parts = buffer.split('\n\n')
      buffer = parts.pop() || ''
      for (const part of parts) {
        const line = part.trim()
        if (!line.startsWith('data: ')) continue
        try {
          const data = JSON.parse(line.slice(6)) as {
            type: string
            content?: string
            detail?: string
            name?: string
            ok?: boolean
            message?: ChatMessage
            proposal_id?: string
            tool?: string
            summary?: string
            args?: Record<string, unknown>
          }
          if (data.type === 'delta' && data.content) handlers.onDelta(data.content)
          if ((data.type === 'tool_started' || data.type === 'tool_finished') && data.name) {
            handlers.onTool?.({
              type: data.type,
              name: data.name,
              ok: data.ok,
            })
          }
          if (data.type === 'confirm_required' && data.proposal_id && data.tool) {
            handlers.onConfirmRequired?.({
              proposal_id: data.proposal_id,
              tool: data.tool,
              summary: data.summary || data.tool,
              args: data.args || {},
              status: 'pending',
            })
          }
          if (data.type === 'done' && data.message) handlers.onDone(data.message)
          if (data.type === 'error') handlers.onError(data.detail || '流式错误')
        } catch {
          /* ignore */
        }
      }
    }
  },
}
