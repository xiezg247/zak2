import { onMounted, onUnmounted, ref } from 'vue'
import { getToken } from '../api/client'

const POLL_FAST_MS = 15_000
const POLL_SLOW_MS = 60_000

export type QuoteNotifyHandlers = {
  onQuotesUpdated?: (seq: number) => void
}

/**
 * 订阅服务端行情 notify（Redis → WS）。
 * 返回 connected；建议：connected 时用 60s 轮询兜底，否则 15s。
 */
export function useQuoteNotify(handlers: QuoteNotifyHandlers = {}) {
  const connected = ref(false)
  let socket: WebSocket | null = null
  let reconnectTimer: number | null = null
  let closed = false

  function wsUrl(): string | null {
    const token = getToken()
    if (!token) return null
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    return `${proto}//${window.location.host}/api/v1/ws/quotes?token=${encodeURIComponent(token)}`
  }

  function clearReconnect() {
    if (reconnectTimer != null) {
      window.clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
  }

  function connect() {
    if (closed) return
    const url = wsUrl()
    if (!url) {
      connected.value = false
      return
    }
    try {
      socket = new WebSocket(url)
    } catch {
      connected.value = false
      scheduleReconnect()
      return
    }
    socket.onopen = () => {
      connected.value = true
    }
    socket.onclose = () => {
      connected.value = false
      socket = null
      scheduleReconnect()
    }
    socket.onerror = () => {
      connected.value = false
    }
    socket.onmessage = (ev) => {
      try {
        const data = JSON.parse(String(ev.data || '')) as { type?: string; seq?: number }
        if (data.type === 'quotes_updated' && typeof data.seq === 'number') {
          handlers.onQuotesUpdated?.(data.seq)
        }
        if (data.type === 'ping' && socket?.readyState === WebSocket.OPEN) {
          socket.send('ping')
        }
      } catch {
        /* ignore */
      }
    }
  }

  function scheduleReconnect() {
    if (closed) return
    clearReconnect()
    reconnectTimer = window.setTimeout(() => connect(), 3000)
  }

  function disconnect() {
    closed = true
    clearReconnect()
    if (socket) {
      socket.onclose = null
      socket.close()
      socket = null
    }
    connected.value = false
  }

  onMounted(() => {
    closed = false
    connect()
  })
  onUnmounted(() => disconnect())

  return { connected, pollIntervalMs: () => (connected.value ? POLL_SLOW_MS : POLL_FAST_MS) }
}

export { POLL_FAST_MS, POLL_SLOW_MS }
