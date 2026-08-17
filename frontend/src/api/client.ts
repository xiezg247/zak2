const TOKEN_KEY = 'zak_access_token'

export type ApiError = { detail?: string }

export type Page<T> = {
  items: T[]
  total: number
  page: number
  page_size: number
  pages: number
}

export function pageQuery(page: number, pageSize: number, extra?: Record<string, string>): string {
  const params = new URLSearchParams()
  params.set('page', String(page))
  params.set('page_size', String(pageSize))
  if (extra) {
    for (const [key, value] of Object.entries(extra)) {
      if (value != null && value !== '') params.set(key, value)
    }
  }
  return params.toString()
}

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string | null) {
  if (token) localStorage.setItem(TOKEN_KEY, token)
  else localStorage.removeItem(TOKEN_KEY)
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers || {})
  if (!headers.has('Content-Type') && options.body) {
    headers.set('Content-Type', 'application/json')
  }
  const token = getToken()
  if (token) headers.set('Authorization', `Bearer ${token}`)

  const resp = await fetch(path, { ...options, headers })
  if (!resp.ok) {
    let detail = resp.statusText
    try {
      const data = (await resp.json()) as ApiError
      detail = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail)
    } catch {
      /* ignore */
    }
    throw new Error(detail || `HTTP ${resp.status}`)
  }
  if (resp.status === 204) return undefined as T
  const ct = resp.headers.get('content-type') || ''
  if (ct.includes('application/json')) {
    const body = (await resp.json()) as { code: number; message: string; data: T }
    if (body.code !== 0) throw new Error(body.message || '请求失败')
    return body.data
  }
  return (await resp.text()) as T
}
