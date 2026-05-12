import { get, patch, post, apiBaseURL } from './http'

export type ApiResponse<T> = {
  code: number
  message: string
  data: T
  meta?: unknown
}

export type FilmEngineStage = {
  id: string
  title: string
  owner: string
  status: 'done' | 'pending' | string
  evidence: string
  goal?: string
  artifacts?: string[] | null
  ui_surface?: string
  metrics?: Record<string, unknown> | null
}

export type FilmEngineRenderRequest = {
  shot_id: string
  provider: string
  model: string
  prompt: string
  references: string[]
  output_path: string
  parameters: Record<string, unknown>
}

export type FilmEngineQAReport = {
  shot_id: string
  passed: boolean
  score: number
  metrics?: Record<string, number>
  issues: Array<{
    code: string
    message: string
    severity: string
    metric: string
    score?: number
    threshold?: number
  }>
}

export type FilmEngineRetryRequest = {
  shot_id: string
  prompt: string
  parameters: Record<string, unknown>
  reason_codes: string[]
}

export type FilmEngineShotQAResult = {
  shot_id: string
  task_id: string
  evaluator: string
  status: string
  metrics: Record<string, number>
  details: Record<string, unknown>
  reason?: string
}

export type FilmEngineRetryTaskResult = {
  task_id: string
  shot_id: string
  chapter_id: string
  ratio: string
  reason_codes: string[]
  retry_prompt: string
}

export type FilmEngineStockAsset = {
  id: string
  file_id?: string | null
  media_type: 'image' | 'video' | string
  title: string
  provider: string
  source_url: string
  thumbnail_url: string
  license_page_url: string
  width?: number | null
  height?: number | null
  duration?: number | null
  description?: string
  tags?: string[]
}

export type FilmEngineStockAssetCollectResult = {
  query: string
  provider: string
  persisted: boolean
  created_file_count: number
  item_count: number
  items: FilmEngineStockAsset[]
  sources: Array<{
    name: string
    api: string
    license_note?: string
  }>
}

export type FilmEnginePlanSummary = {
  project: { id: string; title: string }
  chapter: { id: string; title: string }
  workflow: string[]
  metadata: FilmEngineMetadata
  render_requests: FilmEngineRenderRequest[]
  qa: {
    passed: boolean
    reports: FilmEngineQAReport[]
  }
  retry_requests: FilmEngineRetryRequest[]
  post_production: {
    enabled: boolean
    output_path?: string | null
  }
}

export type FilmEngineConfig = {
  enabled: boolean
  runtime_provider: string
  runtime_model: string
  reference_mode: 'first' | 'last' | 'key' | 'first_last' | 'first_last_key' | 'text_only'
  lens: string
  output_dir: string
  qa_threshold: number
  auto_retry: boolean
  retry_limit: number
}

export type FilmEngineConfigUpdate = Partial<FilmEngineConfig>

export type FilmEngineNextAction = {
  key?: string
  label?: string
  hint?: string
}

export type FilmEngineMetadata = Record<string, unknown> & {
  mode?: string
  scope?: string
  shot_count?: number
  plannable_shot_count?: number
  ready_shot_count?: number
  generated_video_count?: number
  linked_character_count?: number
  linked_scene_count?: number
  config?: FilmEngineConfig
  next_action?: FilmEngineNextAction
}

export type FilmEngineStageIndex = {
  project: { id: string; title: string }
  chapter: { id: string; title: string }
  all_stages_done: boolean
  summary: FilmEnginePlanSummary
  stages: FilmEngineStage[]
  workflow_stages: FilmEngineStage[]
}

export type FilmEngineSeriesChapter = {
  id: string
  index: number
  title: string
  shot_count: number
  plannable_shot_count: number
  ready_shot_count: number
  generated_video_count: number
  retry_count: number
  qa_report_count: number
  qa_passed: boolean
  post_production_enabled: boolean
  stage_done_count: number
  stage_total: number
  workflow_done_count: number
  workflow_total: number
  all_stages_done: boolean
  next_action?: FilmEngineNextAction
}

export type FilmEngineSeriesIndex = {
  project: { id: string; title: string }
  config: FilmEngineConfig
  episode_count: number
  all_chapters_done: boolean
  totals: {
    shot_count: number
    plannable_shot_count: number
    ready_shot_count: number
    generated_video_count: number
    retry_count: number
    qa_report_count: number
  }
  next_action?: FilmEngineNextAction
  chapters: FilmEngineSeriesChapter[]
}

function buildQuery(params: Record<string, string | undefined | null>): string {
  const search = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value) search.set(key, value)
  })
  const text = search.toString()
  return text ? `?${text}` : ''
}

export function getFilmEngineApiBaseURL(): string {
  return apiBaseURL
}

export async function getFilmEngineStageIndex(params: {
  projectId?: string
  chapterId?: string
} = {}): Promise<FilmEngineStageIndex> {
  const response = await get<ApiResponse<FilmEngineStageIndex>>(
    `/v1/film/engine/stage-index${buildQuery({
      project_id: params.projectId,
      chapter_id: params.chapterId,
    })}`,
  )
  return response.data
}

export async function getFilmEngineConfig(projectId: string): Promise<FilmEngineConfig> {
  const response = await get<ApiResponse<FilmEngineConfig>>(
    `/v1/film/engine/config${buildQuery({ project_id: projectId })}`,
  )
  return response.data
}

export async function getFilmEngineSeriesIndex(projectId: string): Promise<FilmEngineSeriesIndex> {
  const response = await get<ApiResponse<FilmEngineSeriesIndex>>(
    `/v1/film/engine/series-index${buildQuery({ project_id: projectId })}`,
  )
  return response.data
}

export async function updateFilmEngineConfig(projectId: string, data: FilmEngineConfigUpdate): Promise<FilmEngineConfig> {
  const response = await patch<ApiResponse<FilmEngineConfig>>(
    `/v1/film/engine/config${buildQuery({ project_id: projectId })}`,
    data,
  )
  return response.data
}

/** Run Film Visual QA for an existing generated shot video. */
export async function evaluateFilmEngineShotQA(shotId: string): Promise<FilmEngineShotQAResult> {
  const response = await post<ApiResponse<FilmEngineShotQAResult>>('/v1/film/engine/qa/evaluate-shot', {
    shot_id: shotId,
  })
  return response.data
}

/** Create a real video_generation retry task from the current Film Engine retry request. */
export async function createFilmEngineRetryTask(params: {
  projectId: string
  shotId: string
  chapterId?: string
  ratio?: string
}): Promise<FilmEngineRetryTaskResult> {
  const response = await post<ApiResponse<FilmEngineRetryTaskResult>>('/v1/film/engine/retry-task', {
    project_id: params.projectId,
    shot_id: params.shotId,
    chapter_id: params.chapterId,
    ratio: params.ratio,
  })
  return response.data
}

/** Collect free stock image/video references for Film Engine bootstrap assets. */
export async function collectFilmEngineStockAssets(params: {
  projectId?: string
  chapterId?: string
  query?: string
  imageCount?: number
  videoCount?: number
  persist?: boolean
}): Promise<FilmEngineStockAssetCollectResult> {
  const response = await post<ApiResponse<FilmEngineStockAssetCollectResult>>('/v1/film/engine/stock-assets/collect', {
    project_id: params.projectId,
    chapter_id: params.chapterId,
    query: params.query,
    image_count: params.imageCount ?? 4,
    video_count: params.videoCount ?? 2,
    persist: params.persist ?? true,
  })
  return response.data
}
