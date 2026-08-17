import { api, pageQuery, type Page } from './client'

export type User = {
  id: string
  username: string
  display_name: string
}

export type TokenResponse = {
  access_token: string
  token_type: string
  user: User
}

export type Preset = {
  name: string
  source: string
  rule_kind: string
  description: string
  implemented: boolean
}

export type HardFilterPrefs = {
  exclude_st: boolean
  exclude_suspended: boolean
  min_amount_wan: number
  min_total_mv_yi: number
  exclude_new_listing: boolean
  min_listing_days: number
  exclude_limit_board: boolean
  exclude_one_word: boolean
  allowed_industries: string
  allowed_market_boards: string
}

export type HardFilterTemplate = {
  id: string
  name: string
  prefs: HardFilterPrefs
}

export type BuiltinRecipe = {
  recipe_id: string
  name: string
  trigger_kind: string
  top_n: number
  implemented: boolean
}

export type PatternMeta = {
  pattern_id: string
  name: string
  description: string
}

export type Scheme = {
  id: string
  name: string
  config: Record<string, unknown>
  created_at: string
  updated_at: string
}

export type Job = {
  id: string
  kind: string
  status: string
  progress: number
  error: string | null
  result_ref: string | null
  created_at: string
  updated_at: string
}

export type RunSummary = {
  id: string
  condition: string
  source: string
  row_count: number
  total_scanned: number
  created_at: string
}

export type RunDetail = RunSummary & {
  config: Record<string, unknown>
  result: {
    rows?: Record<string, unknown>[]
    industry_dist?: { industry: string; count: number; ratio: number }[]
    diff?: { added: string[]; removed: string[]; kept: string[] }
    [key: string]: unknown
  }
}

export type RecipeWeightItem = {
  key: string
  label: string
  weight: number
  default_weight: number
}

export type RecipeWeights = {
  recipe_id: string
  items: RecipeWeightItem[]
  weights: Record<string, number>
}

export const authApi = {
  login: (username: string, password: string) =>
    api<TokenResponse>('/api/v1/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    }),
  me: () => api<User>('/api/v1/auth/me'),
}

export const screenerApi = {
  presets: () => api<Preset[]>('/api/v1/screener/presets'),
  industries: () => api<{ items: string[] }>('/api/v1/screener/industries'),
  hardFilterTemplates: () => api<HardFilterTemplate[]>('/api/v1/screener/hard-filter-templates'),
  builtinRecipes: () => api<BuiltinRecipe[]>('/api/v1/screener/builtin-recipes'),
  patterns: () => api<PatternMeta[]>('/api/v1/screener/patterns'),
  dataStatus: () =>
    api<{
      redis: { available: boolean; quote_count: number; updated_at: string | null }
      tushare_configured: boolean
    }>('/api/v1/screener/data-status'),
  schemes: () => api<Scheme[]>('/api/v1/screener/schemes'),
  createScheme: (name: string, config: Record<string, unknown>) =>
    api<Scheme>('/api/v1/screener/schemes', {
      method: 'POST',
      body: JSON.stringify({ name, config }),
    }),
  deleteScheme: (id: string) =>
    api<{ ok: boolean }>(`/api/v1/screener/schemes/${encodeURIComponent(id)}`, {
      method: 'DELETE',
    }),
  runCondition: (body: Record<string, unknown>) =>
    api<{ job_id: string }>('/api/v1/screener/runs/condition', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  runRecipe: (body: Record<string, unknown>) =>
    api<{ job_id: string }>('/api/v1/screener/runs/recipe', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  runPattern: (body: Record<string, unknown>) =>
    api<{ job_id: string }>('/api/v1/screener/runs/pattern', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  runReferencePeer: (body: Record<string, unknown>) =>
    api<{ job_id: string }>('/api/v1/screener/runs/reference-peer', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  runsPage: (page = 1, pageSize = 20) =>
    api<Page<RunSummary>>(`/api/v1/screener/runs/page?${pageQuery(page, pageSize)}`),
  run: (id: string) => api<RunDetail>(`/api/v1/screener/runs/${id}`),
  exportCsvUrl: (id: string) => `/api/v1/screener/runs/${id}/export.csv`,
  recipeWeights: (recipeId: string) =>
    api<RecipeWeights>(`/api/v1/screener/recipes/${encodeURIComponent(recipeId)}/weights`),
  putRecipeWeights: (recipeId: string, weights: Record<string, number>) =>
    api<RecipeWeights>(`/api/v1/screener/recipes/${encodeURIComponent(recipeId)}/weights`, {
      method: 'PUT',
      body: JSON.stringify({ weights }),
    }),
}

export const jobsApi = {
  get: (id: string) => api<Job>(`/api/v1/jobs/${id}`),
}
