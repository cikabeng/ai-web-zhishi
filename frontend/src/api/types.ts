/** 与后端 app/models/schemas.py 对应的类型定义。 */

export interface KnowledgeBaseStatus {
  status: 'not_initialized' | 'ready' | 'degraded'
  documents: number
  chunks: number
}

export interface HealthResponse {
  status: 'ok'
  name: string
  version: string
  env: string
  demo_mode: boolean
  llm_configured: boolean
  llm_model: string | null
  embed_provider: 'api' | 'hash'
  embed_model: string | null
  embed_dim: number | null
  knowledge_base: KnowledgeBaseStatus
  server_time: string
}
