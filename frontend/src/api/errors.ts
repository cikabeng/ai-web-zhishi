import { http } from './client'
import type { Citation } from './teaching'

export interface OcrLine {
  text: string
  confidence: number | null
}

export interface OcrResult {
  provider: string
  text: string
  lines: OcrLine[]
  mean_confidence: number | null
  low_confidence: boolean
  warnings: string[]
}

export interface ParsedFrame {
  file: string | null
  line: number | null
  function: string | null
  code: string | null
}

export interface ParsedError {
  exception_type: string | null
  message: string | null
  file: string | null
  line: number | null
  line_estimated: boolean
  frames: ParsedFrame[]
  code_snippet: string | null
  language: 'python' | 'javascript' | 'sql' | 'unknown'
  missing: string[]
}

export interface TeachingEntry {
  question: string
  path: string
  level: number
}

export interface GeneralKnowledge {
  label: string
  pattern: string
  summary: string
  causes: string[]
  steps: string[]
}

export interface ErrorAnalysis {
  source: 'image' | 'text'
  recognized_text: string
  edited: boolean
  ocr: OcrResult | null
  parsed: ParsedError
  category: string
  category_label: string
  explanation: string
  causes: string[]
  steps: string[]
  general_knowledge: GeneralKnowledge | null
  evidence_coverage: 'full' | 'partial' | 'none'
  citations: Citation[]
  retrieval: {
    query: string
    hit_count: number
    sufficient: boolean
    retriever: string
  }
  teaching_entry: TeachingEntry
  warnings: string[]
  safety: Record<string, string>
}

export interface OcrCapability {
  provider: string
  available: boolean
  kind: 'local' | 'remote' | 'none'
  note: string
}

export interface Capabilities {
  active: string
  providers: OcrCapability[]
  max_image_mb: number
  formats: string[]
  manual_text_fallback: boolean
}

export async function fetchCapabilities(): Promise<Capabilities> {
  const { data } = await http.get<Capabilities>('/api/errors/capabilities')
  return data
}

/** 演示用：后端实时绘制的报错截图。 */
export async function fetchSampleImage(): Promise<Blob> {
  const { data } = await http.get('/api/errors/sample-image', { responseType: 'blob' })
  return data as Blob
}

export async function analyzeImage(file: File): Promise<ErrorAnalysis> {
  const form = new FormData()
  form.append('file', file)
  const { data } = await http.post<ErrorAnalysis>('/api/errors/analyze-image', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000,
  })
  return data
}

export async function analyzeText(text: string, edited = false): Promise<ErrorAnalysis> {
  const { data } = await http.post<ErrorAnalysis>('/api/errors/analyze-text', { text, edited }, { timeout: 60000 })
  return data
}
