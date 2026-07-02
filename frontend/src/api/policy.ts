import api from './index'

export interface PolicyListItem {
  id: number
  name: string
  description: string
  policy_type: string
  status: string
  current_version_number: number | null
  created_at: string | null
  updated_at: string | null
}

export interface PolicyDetail {
  id: number
  name: string
  description: string
  policy_type: string
  status: string
  enterprise: string
  current_version_id: number | null
  created_at: string | null
  updated_at: string | null
}

export interface PolicyVersionItem {
  id: number
  version_number: number
  status: string
  pdf_filename: string | null
  kb_id: number | null
  published_at: string | null
  created_at: string | null
}

export interface PolicyVersionDetail {
  id: number
  version_number: number
  status: string
  pdf_filename: string | null
  kb_id: number | null
  ai_draft: any
  policy_json: any
  published_at: string | null
  created_at: string | null
}

export interface DraftExpenseType {
  code: string
  name: string
  reimbursement_ratio: number
  max_amount: number | null
  need_invoice: boolean
  need_attachment: boolean
  need_guest: boolean
  approval_over: number
  enabled: boolean
  confidence: number
  source_text: string
  ai_reasoning: string
}

export interface PolicyDraft {
  enterprise: string
  description: string
  expense_types: DraftExpenseType[]
  warnings: string[]
  metadata: Record<string, any>
}

export interface PolicyUploadResponse {
  policy_id: number
  version_id: number
  version_number: number
  status: string
  pdf_filename: string
  kb_id: number | null
  message: string
}

export interface NormalizeResponse {
  policy_json: any
  warnings: string[]
}

export interface PublishResponse {
  success: boolean
  message: string
  policy_id: number
  version_id: number
}

export const policyApi = {
  async uploadPdf(file: File, name?: string, enterprise?: string): Promise<PolicyUploadResponse> {
    const form = new FormData()
    form.append('file', file)
    if (name) form.append('name', name)
    if (enterprise) form.append('enterprise', enterprise)
    const res = await api.post('/policy/upload', form)
    return res.data
  },

  async list(): Promise<PolicyListItem[]> {
    const res = await api.get('/policy/list')
    return res.data
  },

  async get(policyId: number): Promise<PolicyDetail> {
    const res = await api.get(`/policy/${policyId}`)
    return res.data
  },

  async listVersions(policyId: number): Promise<PolicyVersionItem[]> {
    const res = await api.get(`/policy/${policyId}/versions`)
    return res.data
  },

  async getVersion(policyId: number, versionId: number): Promise<PolicyVersionDetail> {
    const res = await api.get(`/policy/${policyId}/versions/${versionId}`)
    return res.data
  },

  async reparse(policyId: number, versionId: number): Promise<PolicyDraft> {
    const res = await api.post(`/policy/${policyId}/versions/${versionId}/parse`)
    return res.data
  },

  async updateDraft(policyId: number, versionId: number, draft: PolicyDraft): Promise<any> {
    const res = await api.put(`/policy/${policyId}/versions/${versionId}/draft`, { draft })
    return res.data
  },

  async normalize(policyId: number, versionId: number): Promise<NormalizeResponse> {
    const res = await api.post(`/policy/${policyId}/versions/${versionId}/normalize`)
    return res.data
  },

  async publish(policyId: number, versionId: number): Promise<PublishResponse> {
    const res = await api.post(`/policy/${policyId}/versions/${versionId}/publish`)
    return res.data
  },

  async archive(policyId: number, versionId: number): Promise<any> {
    const res = await api.post(`/policy/${policyId}/versions/${versionId}/archive`)
    return res.data
  },

  async parseText(text: string): Promise<any> {
    const res = await api.post('/policy/parse', { text })
    return res.data
  },

  async getCurrent(): Promise<any> {
    const res = await api.get('/policy/current')
    return res.data
  },
}
