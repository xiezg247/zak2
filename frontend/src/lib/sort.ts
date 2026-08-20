export type SortDir = 'asc' | 'desc'

/** 可空数值排序：缺失值一律垫底 */
export function cmpNullable(
  a: number | null | undefined,
  b: number | null | undefined,
  dir: SortDir,
): number {
  const aMissing = a == null || Number.isNaN(a)
  const bMissing = b == null || Number.isNaN(b)
  if (aMissing && bMissing) return 0
  if (aMissing) return 1
  if (bMissing) return -1
  const d = (a as number) - (b as number)
  return dir === 'asc' ? d : -d
}
