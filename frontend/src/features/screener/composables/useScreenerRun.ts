import { ref, type ComputedRef, type Ref } from 'vue'
import { getToken } from '../../../api/client'
import { jobsApi, screenerApi, type RunDetail, type RunSummary } from '../../../api/screener'
import { watchlistApi } from '../../../api/watchlist'

export type ScreenerTab = 'condition' | 'recipe' | 'pattern' | 'peer'

export type ScreenerRunForm = {
  tab: Ref<ScreenerTab>
  selectedPreset: Ref<string>
  selectedRecipe: Ref<string>
  selectedPattern: Ref<string>
  peerSymbol: Ref<string>
  leaderVariant: Ref<'mainline' | 'all_market'>
  hardTemplate: Ref<string>
  topN: Ref<number>
  maxScan: Ref<number>
  minChange: Ref<number | null>
  maxChange: Ref<number | null>
  minTurnover: Ref<number | null>
  maxTurnover: Ref<number | null>
  selectedIndustries: Ref<string[]>
  isCustom: ComputedRef<boolean>
  isRadarLeader: ComputedRef<boolean>
}

export function emptyToNull(v: number | null): number | null {
  if (v === null || Number.isNaN(v as number)) return null
  return v
}

export function useScreenerRun(form: ScreenerRunForm) {
  const current = ref<RunDetail | null>(null)
  const history = ref<RunSummary[]>([])
  const historyPage = ref(1)
  const historyPages = ref(0)
  const historyTotal = ref(0)
  const historyBusy = ref(false)
  const historyErr = ref('')
  const runBusy = ref(false)
  const running = ref(false)
  const statusText = ref('')
  const error = ref('')
  const batchBusy = ref(false)

  function hardFilterOverride(): { allowed_industries: string } | undefined {
    const picked = form.selectedIndustries.value.filter((s) => s.trim())
    if (!picked.length) return undefined
    return { allowed_industries: picked.join(',') }
  }

  function mergeHardFilter(body: Record<string, unknown>) {
    const hf = hardFilterOverride()
    if (hf) body.hard_filter = hf
    return body
  }

  function buildConditionBody() {
    const body: Record<string, unknown> = {
      preset: form.selectedPreset.value,
      top_n: form.topN.value,
      hard_filter_template: form.hardTemplate.value,
    }
    if (form.isCustom.value) {
      body.min_change_pct = emptyToNull(form.minChange.value)
      body.max_change_pct = emptyToNull(form.maxChange.value)
      body.min_turnover_rate = emptyToNull(form.minTurnover.value)
      body.max_turnover_rate = emptyToNull(form.maxTurnover.value)
    }
    return mergeHardFilter(body)
  }

  async function loadHistory() {
    historyBusy.value = true
    historyErr.value = ''
    try {
      const p = await screenerApi.runsPage(historyPage.value, 20)
      history.value = p.items
      historyTotal.value = p.total
      historyPages.value = p.pages
    } catch (e) {
      historyErr.value = e instanceof Error ? e.message : '加载历史失败'
    } finally {
      historyBusy.value = false
    }
  }

  async function goHistoryPage(p: number) {
    historyPage.value = p
    await loadHistory()
  }

  async function pollJob(jobId: string) {
    for (let i = 0; i < 120; i++) {
      const job = await jobsApi.get(jobId)
      statusText.value = `${job.status} · ${Math.round(job.progress * 100)}%`
      if (job.status === 'success' && job.result_ref) {
        current.value = await screenerApi.run(job.result_ref)
        await loadHistory()
        return
      }
      if (job.status === 'failed') {
        throw new Error(job.error || '任务失败')
      }
      await new Promise((r) => setTimeout(r, 500))
    }
    throw new Error('任务超时')
  }

  async function runScreen() {
    error.value = ''
    running.value = true
    statusText.value = '提交中…'
    try {
      if (form.tab.value === 'condition') {
        const { job_id } = await screenerApi.runCondition(buildConditionBody())
        await pollJob(job_id)
      } else if (form.tab.value === 'pattern') {
        const { job_id } = await screenerApi.runPattern(
          mergeHardFilter({
            pattern_id: form.selectedPattern.value,
            top_n: Math.min(form.topN.value, 100),
            max_scan: form.maxScan.value,
            hard_filter_template: form.hardTemplate.value,
          }),
        )
        await pollJob(job_id)
      } else if (form.tab.value === 'peer') {
        const vt = form.peerSymbol.value.trim()
        if (!vt) throw new Error('请填写标杆代码')
        const { job_id } = await screenerApi.runReferencePeer(
          mergeHardFilter({
            vt_symbol: vt,
            top_n: Math.min(form.topN.value, 100),
            hard_filter_template: form.hardTemplate.value,
          }),
        )
        await pollJob(job_id)
      } else {
        const body: Record<string, unknown> = {
          recipe_id: form.selectedRecipe.value,
          top_n: form.topN.value,
          hard_filter_template: form.hardTemplate.value,
        }
        if (form.isRadarLeader.value) body.variant = form.leaderVariant.value
        const { job_id } = await screenerApi.runRecipe(mergeHardFilter(body))
        await pollJob(job_id)
      }
      statusText.value = '完成'
    } catch (e) {
      error.value = e instanceof Error ? e.message : '运行失败'
      statusText.value = '失败'
    } finally {
      running.value = false
    }
  }

  async function openRun(id: string) {
    runBusy.value = true
    error.value = ''
    try {
      current.value = await screenerApi.run(id)
    } catch (e) {
      error.value = e instanceof Error ? e.message : '打开运行记录失败'
    } finally {
      runBusy.value = false
    }
  }

  function rowVt(row: Record<string, unknown>): string {
    return String(row.vt_symbol || row.symbol || '').trim()
  }

  async function addToWatchlist(row: Record<string, unknown>) {
    const vt = rowVt(row)
    if (!vt) return
    try {
      await watchlistApi.add(vt, String(row.name || ''))
      statusText.value = `已加入自选 ${vt}`
    } catch (e) {
      error.value = e instanceof Error ? e.message : '加入自选失败'
    }
  }

  async function addSelectedToWatchlist(queue: Record<string, unknown>[]) {
    if (!queue.length || batchBusy.value) return
    batchBusy.value = true
    error.value = ''
    let ok = 0
    let skip = 0
    let fail = 0
    try {
      for (const row of queue) {
        const vt = rowVt(row)
        const name = String(row.name || '')
        try {
          await watchlistApi.add(vt, name)
          ok++
        } catch (e) {
          const msg = e instanceof Error ? e.message : ''
          if (msg.includes('已在自选中')) skip++
          else fail++
        }
      }
      statusText.value = `已加入 ${ok} · 已在自选 ${skip} · 失败 ${fail}`
      if (fail > 0) error.value = '部分加入失败，见上方汇总'
    } finally {
      batchBusy.value = false
    }
  }

  function exportCsv() {
    if (!current.value) return
    const url = screenerApi.exportCsvUrl(current.value.id)
    const a = document.createElement('a')
    a.download = `screener_${current.value.id}.csv`
    void fetch(url, { headers: { Authorization: `Bearer ${getToken()}` } })
      .then((r) => r.blob())
      .then((blob) => {
        a.href = URL.createObjectURL(blob)
        a.click()
        URL.revokeObjectURL(a.href)
      })
  }

  return {
    current,
    history,
    historyPage,
    historyPages,
    historyTotal,
    historyBusy,
    historyErr,
    runBusy,
    running,
    statusText,
    error,
    batchBusy,
    hardFilterOverride,
    loadHistory,
    goHistoryPage,
    pollJob,
    runScreen,
    openRun,
    exportCsv,
    addToWatchlist,
    addSelectedToWatchlist,
  }
}
