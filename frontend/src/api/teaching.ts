import { http } from './client'

export type CategoryValue = 'concept' | 'error' | 'experiment' | 'sql' | 'web' | 'assignment'
export type TeachingModeValue = 'guided' | 'study'
export type HintAction = 'open' | 'continue' | 'rephrase' | 'understood'

export interface CategoryMeta {
  value: CategoryValue
  label: string
  description: string
}

export interface CategoryOption {
  category: CategoryValue
  label: string
  confidence: number
}

export interface Citation {
  index: number
  chunk_id: string
  doc_name: string
  location: string
  heading: string | null
  snippet: string
  score: number
}

export interface HintBlock {
  kind: 'explain' | 'steps' | 'code' | 'example' | 'evidence' | 'limit' | 'note' | 'feedback'
  title: string
  content: string
  citations: number[]
  meta: Record<string, string>
}

export interface CheckQuestion {
  question: string
  purpose: string
}

export interface TeachingResponse {
  question: string
  mode: TeachingModeValue
  category: CategoryValue
  category_label: string
  category_source: 'auto' | 'user'
  category_confidence: number
  category_options: CategoryOption[]
  requested_level: number
  level: number
  level_name: string
  level_intent: string
  clamped: boolean
  clamp_reason: 'max_one_level_per_step' | 'guided_requires_attempt' | null
  blocks: HintBlock[]
  citations: Citation[]
  check_question: CheckQuestion
  allowed_actions: string[]
  next_level: number | null
  insufficient_evidence: boolean
  example_generated: boolean
  safety: Record<string, string>
}

export interface SubmissionFeedback {
  verdict: 'on_track' | 'partial' | 'off_track'
  summary: string
  blocks: { kind: 'affirm' | 'question' | 'warning'; text: string }[]
  next_question: string
  safety: Record<string, string>
}

export interface HintPayload {
  question: string
  mode: TeachingModeValue
  category: CategoryValue | null
  current_level: number
  target_level: number
  variant: number
  action: HintAction
}

export interface FeedbackPayload {
  question: string
  mode: TeachingModeValue
  category: CategoryValue | null
  current_level: number
  target_level: number
  submission: { kind: 'code' | 'thinking'; text: string }
}

export async function fetchCategories(): Promise<CategoryMeta[]> {
  const { data } = await http.get<CategoryMeta[]>('/api/teaching/categories')
  return data
}

export async function fetchDemoCase(): Promise<{ question: string }> {
  const { data } = await http.get<{ question: string }>('/api/teaching/demo-case')
  return data
}

export async function requestHint(payload: HintPayload): Promise<TeachingResponse> {
  const { data } = await http.post<TeachingResponse>('/api/teaching/hint', payload)
  return data
}

export async function requestFeedback(payload: FeedbackPayload): Promise<SubmissionFeedback> {
  const { data } = await http.post<SubmissionFeedback>('/api/teaching/feedback', payload)
  return data
}
