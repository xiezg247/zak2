import { computed, ref, type Ref } from 'vue'
import { screenerApi, type RecipeWeightItem, type RecipeWeights } from '../../../api/screener'

const WEIGHT_EDITABLE = new Set(['intraday_multi', 'post_close_multi', 'ultra_short_unified'])

export function useScreenerWeights(
  selectedRecipe: Ref<string>,
  statusText: Ref<string>,
) {
  const weightOpen = ref(true)
  const weightItems = ref<RecipeWeightItem[]>([])
  const weightDraft = ref<Record<string, number>>({})
  const weightBusy = ref(false)
  const weightErr = ref('')

  const isWeightEditable = computed(() => WEIGHT_EDITABLE.has(selectedRecipe.value))

  function applyWeights(w: RecipeWeights) {
    weightItems.value = w.items
    weightDraft.value = { ...w.weights }
  }

  function clearWeights() {
    weightItems.value = []
    weightDraft.value = {}
    weightErr.value = ''
  }

  async function loadRecipeWeights() {
    if (!isWeightEditable.value) {
      clearWeights()
      return
    }
    weightBusy.value = true
    weightErr.value = ''
    try {
      const w = await screenerApi.recipeWeights(selectedRecipe.value)
      applyWeights(w)
    } catch (e) {
      weightItems.value = []
      weightDraft.value = {}
      weightErr.value = e instanceof Error ? e.message : '权重加载失败'
    } finally {
      weightBusy.value = false
    }
  }

  async function saveRecipeWeights() {
    if (!isWeightEditable.value) return
    if (weightItems.value.length === 0) {
      weightErr.value = '权重尚未加载，无法保存'
      return
    }
    const payload: Record<string, number> = {}
    for (const item of weightItems.value) {
      const v = weightDraft.value[item.key]
      if (typeof v === 'number' && Number.isFinite(v)) {
        payload[item.key] = v
      }
    }
    if (Object.keys(payload).length === 0) {
      weightErr.value = '没有可保存的权重，请先加载或填写'
      return
    }
    weightBusy.value = true
    weightErr.value = ''
    try {
      const out = await screenerApi.putRecipeWeights(selectedRecipe.value, payload)
      applyWeights(out)
      statusText.value = '权重已保存'
    } catch (e) {
      weightErr.value = e instanceof Error ? e.message : '保存失败'
    } finally {
      weightBusy.value = false
    }
  }

  async function resetRecipeWeights() {
    if (!isWeightEditable.value) return
    weightBusy.value = true
    weightErr.value = ''
    try {
      const out = await screenerApi.putRecipeWeights(selectedRecipe.value, {})
      applyWeights(out)
      statusText.value = '已恢复默认权重'
    } catch (e) {
      weightErr.value = e instanceof Error ? e.message : '恢复失败'
    } finally {
      weightBusy.value = false
    }
  }

  return {
    weightOpen,
    weightItems,
    weightDraft,
    weightBusy,
    weightErr,
    isWeightEditable,
    clearWeights,
    loadRecipeWeights,
    saveRecipeWeights,
    resetRecipeWeights,
  }
}
