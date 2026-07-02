import api from './index'

export interface KbInfo {
  id: number
  name: string
  description: string
  created_by: number
  is_active: boolean
  created_at: string
  document_count: number
}

export interface KbDocument {
  id: number
  kb_id: number
  filename: string
  chunk_count: number
  created_at: string
  chunks_preview: ChunkPreview[]
}

export interface ChunkPreview {
  index: number
  text: string
  char_count: number
}

export interface KbSearchResult {
  chunk_id: string
  document_id: number
  filename: string
  kb_name: string
  snippet: string
  score: number
  distance: number | null
}

export const kbApi = {
  async getBase(kbId: number): Promise<KbInfo> {
    // reuse list and filter
    const all = await this.listBases()
    const found = all.find(b => b.id === kbId)
    if (!found) throw new Error(`KB ${kbId} not found`)
    return found
  },

  async listBases(): Promise<KbInfo[]> {
    const res = await api.get('/knowledge/bases')
    return res.data
  },

  async listDocuments(kbId: number): Promise<KbDocument[]> {
    const res = await api.get(`/knowledge/bases/${kbId}/documents`)
    return res.data
  },

  async getChunks(docId: number): Promise<{ document_id: number; filename: string; kb_name: string; total_chunks: number; chunks: ChunkPreview[] }> {
    const res = await api.get(`/knowledge/documents/${docId}/chunks`)
    return res.data
  },

  async search(q: string, kbId?: number, topK?: number): Promise<KbSearchResult[]> {
    const params: any = { q }
    if (kbId != null) params.kb_id = kbId
    if (topK != null) params.top_k = topK
    const res = await api.get('/knowledge/search', { params })
    return res.data
  },
}
