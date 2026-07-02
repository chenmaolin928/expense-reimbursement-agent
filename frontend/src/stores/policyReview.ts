import { defineStore } from 'pinia'
import { ref, computed, reactive } from 'vue'
import { policyApi, type PolicyVersionDetail, type PolicyDomain, type RuleReview } from '../api/policy'

export const usePolicyReviewStore = defineStore('policyReview', () => {
  const versionDetail = ref<PolicyVersionDetail | null>(null)
  const originalText = ref('')
  const selectedRuleKey = ref<string | null>(null) // "domainId_ruleId"
  const reviews = reactive<Record<string, RuleReview>>({})
  const ruleUpdates = reactive<Record<string, Record<string, any>>>({})
  const dirty = ref(false)
  const loading = ref(false)
  const saving = ref(false)
  const policyId = ref(0)
  const versionId = ref(0)

  // Derive domains from versionDetail
  const domains = computed<PolicyDomain[]>(() => {
    return versionDetail.value?.ai_draft?.policy_doc?.domains ?? []
  })

  const selectedRule = computed(() => {
    if (!selectedRuleKey.value) return null
    const [dId, rId] = selectedRuleKey.value.split('_', 2)
    for (const d of domains.value) {
      if (d.id === dId) {
        for (const r of d.rules) {
          if (r.id === rId) return { domain: d, rule: r }
        }
      }
    }
    return null
  })

  const totalRuleCount = computed(() =>
    domains.value.reduce((s, d) => s + d.rules.length, 0)
  )

  const reviewedCount = computed(() =>
    Object.values(reviews).filter(r => r.status !== 'pending_review').length
  )

  const progress = computed(() =>
    totalRuleCount.value > 0
      ? Math.round((reviewedCount.value / totalRuleCount.value) * 100)
      : 0
  )

  // Find which rule (if any) a text offset belongs to
  function findRuleByOffset(offset: number): { domainId: string; ruleId: string } | null {
    for (const d of domains.value) {
      for (const r of d.rules) {
        if (!r.raw_text) continue
        const pos = originalText.value.indexOf(r.raw_text)
        if (pos >= 0 && offset >= pos && offset <= pos + r.raw_text.length) {
          return { domainId: d.id, ruleId: r.id }
        }
      }
    }
    return null
  }

  // Get highlight range for a rule's raw_text
  function getHighlightRange(domainId: string, ruleId: string): { start: number; end: number } | null {
    for (const d of domains.value) {
      if (d.id !== domainId) continue
      for (const r of d.rules) {
        if (r.id !== ruleId || !r.raw_text) continue
        const pos = originalText.value.indexOf(r.raw_text)
        if (pos >= 0) return { start: pos, end: pos + r.raw_text.length }
      }
    }
    return null
  }

  function selectRule(domainId: string, ruleId: string) {
    selectedRuleKey.value = `${domainId}_${ruleId}`
  }

  function clearSelection() {
    selectedRuleKey.value = null
  }

  function getReview(domainId: string, ruleId: string): RuleReview {
    const key = `${domainId}_${ruleId}`
    return reviews[key] || {
      rule_id: ruleId,
      domain_id: domainId,
      status: 'pending_review' as const,
      notes: '',
    }
  }

  function setReviewStatus(domainId: string, ruleId: string, status: string, notes?: string) {
    const key = `${domainId}_${ruleId}`
    const existing = reviews[key]
    reviews[key] = {
      rule_id: ruleId,
      domain_id: domainId,
      status: status as any,
      notes: notes ?? existing?.notes ?? '',
      updated_at: new Date().toISOString(),
    }
    dirty.value = true
  }

  function updateRuleField(domainId: string, ruleId: string, field: string, value: any) {
    const d = domains.value.find(d => d.id === domainId)
    if (!d) return
    const r = d.rules.find(r => r.id === ruleId)
    if (!r) return
    ;(r as any)[field] = value
    const key = `${domainId}_${ruleId}`
    ruleUpdates[key] = {
      ...(ruleUpdates[key] || { domain_id: domainId, rule_id: ruleId }),
      [field]: value,
    }
    dirty.value = true
  }

  // Bulk-update scope sub-fields
  function updateRuleScope(domainId: string, ruleId: string, scopeField: string, value: string | null) {
    const d = domains.value.find(d => d.id === domainId)
    if (!d) return
    const r = d.rules.find(r => r.id === ruleId)
    if (!r) return
    if (!r.scope) r.scope = { role: null, region: null, amount_range: null }
    ;(r.scope as any)[scopeField] = value
    const key = `${domainId}_${ruleId}`
    const existingScope = ruleUpdates[key]?.scope || {}
    ruleUpdates[key] = {
      ...(ruleUpdates[key] || { domain_id: domainId, rule_id: ruleId }),
      scope: {
        ...existingScope,
        [scopeField]: value,
      },
    }
    dirty.value = true
  }

  async function loadReviewSession(pid: number, vid: number) {
    loading.value = true
    policyId.value = pid
    versionId.value = vid
    try {
      const [detail, textResp] = await Promise.all([
        policyApi.getVersion(pid, vid),
        policyApi.getOriginalText(pid, vid),
      ])
      versionDetail.value = detail
      originalText.value = textResp.text

      // Initialize reviews from stored data or defaults
      const storedReviews = detail.ai_draft?.reviews ?? {}
      for (const key of Object.keys(reviews)) delete reviews[key]
      for (const key of Object.keys(ruleUpdates)) delete ruleUpdates[key]
      // Initialize all rules
      for (const d of (detail.ai_draft?.policy_doc?.domains ?? [])) {
        for (const r of d.rules) {
          const key = `${d.id}_${r.id}`
          if (storedReviews[key]) {
            reviews[key] = { ...storedReviews[key] }
          } else {
            reviews[key] = {
              rule_id: r.id,
              domain_id: d.id,
              status: 'pending_review',
              notes: '',
            }
          }
        }
      }
      dirty.value = false
    } finally {
      loading.value = false
    }
  }

  async function saveAll() {
    saving.value = true
    try {
      const revs: Record<string, any> = {}
      for (const [k, v] of Object.entries(reviews)) {
        revs[k] = { ...v }
      }
      await policyApi.batchUpdateReview(policyId.value, versionId.value, {
        reviews: revs,
        rule_updates: Object.values(ruleUpdates),
      })
      for (const key of Object.keys(ruleUpdates)) delete ruleUpdates[key]
      dirty.value = false
    } finally {
      saving.value = false
    }
  }

  async function splitRule(domainId: string, sourceRuleId: string, splits: any[]) {
    const resp = await policyApi.splitRule(policyId.value, versionId.value, {
      domain_id: domainId,
      source_rule_id: sourceRuleId,
      splits,
    })
    // Reload to get fresh data
    await loadReviewSession(policyId.value, versionId.value)
    return resp
  }

  async function mergeRules(domainId: string, sourceRuleIds: string[], target: any) {
    const resp = await policyApi.mergeRules(policyId.value, versionId.value, {
      domain_id: domainId,
      source_rule_ids: sourceRuleIds,
      ...target,
    })
    await loadReviewSession(policyId.value, versionId.value)
    return resp
  }

  async function deleteRule(domainId: string, ruleId: string) {
    await policyApi.deleteRule(policyId.value, versionId.value, domainId, ruleId)
    // Remove from local state
    const key = `${domainId}_${ruleId}`
    delete reviews[key]
    delete ruleUpdates[key]
    if (selectedRuleKey.value === key) clearSelection()
    // Reload domains
    await loadReviewSession(policyId.value, versionId.value)
  }

  return {
    versionDetail,
    originalText,
    selectedRuleKey,
    reviews,
    dirty,
    loading,
    saving,
    policyId,
    versionId,
    domains,
    selectedRule,
    totalRuleCount,
    reviewedCount,
    progress,
    findRuleByOffset,
    getHighlightRange,
    selectRule,
    clearSelection,
    getReview,
    setReviewStatus,
    updateRuleField,
    updateRuleScope,
    loadReviewSession,
    saveAll,
    splitRule,
    mergeRules,
    deleteRule,
  }
})
