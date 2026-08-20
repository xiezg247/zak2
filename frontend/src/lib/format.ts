export function fmtDateTime(raw?: string | null): string {
  if (!raw) return ''
  // 已是空格分隔或纯文本时间，原样返回
  if (!raw.includes('T')) return raw
  // ISO 8601：去毫秒与时区后缀，如 2026-06-25T12:10:11.123Z → 2026-06-25 12:10:11
  return raw.replace('T', ' ').slice(0, 19)
}

const EMPTY = '—'

function isMissing(v: number | null | undefined): boolean {
  return v == null || Number.isNaN(v)
}

/** 通用两位小数；null/NaN → — */
export function formatNum2(v: number | null | undefined): string {
  if (isMissing(v)) return EMPTY
  return (v as number).toFixed(2)
}

/** 现价：无数据或 ≤0 → —（避免行情缺省假 0） */
export function formatPrice(v: number | null | undefined): string {
  if (isMissing(v) || (v as number) <= 0) return EMPTY
  return (v as number).toFixed(2)
}

/** 成交额（元）→ x.xx亿 */
export function formatAmountYi(v: number | null | undefined): string {
  if (isMissing(v)) return EMPTY
  return `${((v as number) / 1e8).toFixed(2)}亿`
}
