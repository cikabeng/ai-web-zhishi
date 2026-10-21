import { http } from './client'

export interface LibraryDocument {
  id: string
  name: string
  ext: string
  size: number
  sha256: string
  status: 'parsing' | 'indexed' | 'failed'
  error: string | null
  pages: number
  chunks: number
  chars: number
  created_at: string
}

export interface LibraryStats {
  documents: number
  indexed: number
  failed: number
  chunks: number
  chars: number
  status: 'ready' | 'not_initialized'
}

export interface PreviewChunk {
  text: string
  page: number
  heading: string
  ordinal: number
}

export async function fetchDocuments(): Promise<{ documents: LibraryDocument[]; stats: LibraryStats }> {
  const { data } = await http.get('/api/library/documents')
  return data
}

export async function uploadDocument(file: File): Promise<{ document: LibraryDocument; duplicate: boolean }> {
  const form = new FormData()
  form.append('file', file)
  const { data } = await http.post('/api/library/documents', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000,
  })
  return data
}

export async function deleteDocument(id: string): Promise<void> {
  await http.delete(`/api/library/documents/${id}`)
}

export async function reindexDocument(id: string): Promise<LibraryDocument> {
  const { data } = await http.post(`/api/library/documents/${id}/reindex`)
  return data.document
}

export async function previewChunks(id: string, limit = 5): Promise<PreviewChunk[]> {
  const { data } = await http.get(`/api/library/documents/${id}/chunks`, { params: { limit } })
  return data.chunks
}
