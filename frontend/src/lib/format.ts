export function fmtDateTime(raw?: string | null): string {
  if (!raw) return ''
  // 已是空格分隔或纯文本时间，原样返回
  if (!raw.includes('T')) return raw
  // ISO 8601：去毫秒与时区后缀，如 2026-06-25T12:10:11.123Z → 2026-06-25 12:10:11
  return raw.replace('T', ' ').slice(0, 19)
}
