import { ref } from 'vue'

export type AnalysisTabKey =
  | 'quote'
  | 'fundamental'
  | 'signal'
  | 'radar'
  | 'ai'
  | 'notes'

const isOpen = ref(false)
const vtSymbol = ref('')
const name = ref('')
const activeTab = ref<AnalysisTabKey>('quote')
const loadedTabs = ref<Set<AnalysisTabKey>>(new Set())

export function useStockAnalysis() {
  function open(vt: string, label = '') {
    vtSymbol.value = vt.trim()
    name.value = label
    activeTab.value = 'quote'
    loadedTabs.value = new Set()
    isOpen.value = true
  }
  function close() {
    isOpen.value = false
    vtSymbol.value = ''
    name.value = ''
  }
  function markLoaded(tab: AnalysisTabKey) {
    loadedTabs.value = new Set([...loadedTabs.value, tab])
  }
  function invalidate(tab: AnalysisTabKey) {
    if (!loadedTabs.value.has(tab)) return
    const next = new Set(loadedTabs.value)
    next.delete(tab)
    loadedTabs.value = next
  }
  function isLoaded(tab: AnalysisTabKey): boolean {
    return loadedTabs.value.has(tab)
  }
  return { isOpen, vtSymbol, name, activeTab, open, close, markLoaded, invalidate, isLoaded }
}
