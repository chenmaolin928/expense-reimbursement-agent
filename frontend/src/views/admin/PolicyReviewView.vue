<template>
  <div class="review-view">
    <PolicyReviewToolbar
      :policy-name="store.versionDetail?.ai_draft?.policy_doc?.title || store.versionDetail?.pdf_filename || ''"
      :version-number="store.versionDetail?.version_number || 0"
      :sub-status="store.versionDetail?.status || ''"
      :dirty="store.dirty"
      :saving="store.saving"
      :progress="store.progress"
      :reviewed-count="store.reviewedCount"
      :total-count="store.totalRuleCount"
      @save-all="handleSaveAll"
      @normalize="handleNormalize"
      @exit="handleExit"
    />

    <div v-if="store.loading" class="loading-state">
      <p>加载审核数据...</p>
    </div>

    <div v-else class="review-layout">
      <!-- Left: Original Text -->
      <PolicyOriginalText
        :text="store.originalText"
        :highlight-range="highlightRange"
        @text-click="handleTextClick"
      />

      <!-- Center: Rule List -->
      <PolicyRuleList
        :domains="store.domains"
        :selected-rule-key="store.selectedRuleKey"
        @select-rule="handleSelectRule"
        @split-rule="handleSplitRule"
        @merge-rules="handleMergeRules"
        @delete-rule="handleDeleteRule"
      />

      <!-- Right: Edit Panel -->
      <PolicyRuleEditPanel
        :rule="store.selectedRule?.rule || null"
        :domain-id="store.selectedRule?.domain.id || null"
        :review="store.selectedRuleKey ? (store.getReview(store.selectedRule?.domain.id || '', store.selectedRule?.rule.id || '')) : null"
        @save="handleSaveAll"
        @close="store.clearSelection()"
        @delete="handleDeleteSelectedRule"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { usePolicyReviewStore } from '../../stores/policyReview'
import PolicyOriginalText from '../../components/PolicyOriginalText.vue'
import PolicyRuleList from '../../components/PolicyRuleList.vue'
import PolicyRuleEditPanel from '../../components/PolicyRuleEditPanel.vue'
import PolicyReviewToolbar from '../../components/PolicyReviewToolbar.vue'
import { policyApi } from '../../api/policy'

const route = useRoute()
const router = useRouter()
const store = usePolicyReviewStore()

const policyId = computed(() => parseInt(route.params.policyId as string))
const versionId = computed(() => parseInt(route.params.versionId as string))

// Compute highlight range from selected rule
const highlightRange = computed(() => {
  if (!store.selectedRuleKey) return null
  const [dId, rId] = store.selectedRuleKey.split('_', 2)
  return store.getHighlightRange(dId, rId)
})

// Beforeunload guard for unsaved changes
function beforeUnload(e: BeforeUnloadEvent) {
  if (store.dirty) {
    e.preventDefault()
    e.returnValue = ''
  }
}

onMounted(async () => {
  try {
    await store.loadReviewSession(policyId.value, versionId.value)
    window.addEventListener('beforeunload', beforeUnload)
  } catch (e) {
    console.error('Failed to load review session', e)
  }
})

onBeforeUnmount(() => {
  window.removeEventListener('beforeunload', beforeUnload)
})

function handleSelectRule(domainId: string, ruleId: string) {
  store.selectRule(domainId, ruleId)
}

function handleTextClick(start: number, _end: number) {
  const match = store.findRuleByOffset(start)
  if (match) {
    store.selectRule(match.domainId, match.ruleId)
  }
}

async function handleSaveAll() {
  await store.saveAll()
}

async function handleNormalize() {
  if (store.dirty) {
    alert('请先保存修改')
    return
  }
  if (confirm('确定要将此草稿规范化为 Policy JSON？')) {
    try {
      await policyApi.normalize(store.policyId, store.versionId)
      // Navigate back to PolicyView
      router.push('/admin/policy')
    } catch (e) {
      alert('规范化失败: ' + (e as any).message)
    }
  }
}

function handleExit() {
  if (store.dirty && !confirm('有未保存的修改，确定退出？')) return
  router.push('/admin/policy')
}

async function handleSplitRule(domainId: string, ruleId: string, splits: any[]) {
  await store.splitRule(domainId, ruleId, splits)
}

async function handleMergeRules(selectedKeys: string[]) {
  // Group by domain
  const byDomain: Record<string, string[]> = {}
  for (const k of selectedKeys) {
    const [dId, rId] = k.split('_', 2)
    if (!byDomain[dId]) byDomain[dId] = []
    byDomain[dId].push(rId)
  }

  for (const [domainId, ruleIds] of Object.entries(byDomain)) {
    // Find a domain to get scope info
    const domain = store.domains.find(d => d.id === domainId)
    if (!domain) continue
    const target = {
      domain_id: domainId,
      source_rule_ids: ruleIds,
      target_type: 'other',
      target_title: `合并规则 (${ruleIds.join(',')})`,
      target_condition: '',
      target_value: null,
      target_unit: '',
    }
    await store.mergeRules(domainId, ruleIds, target)
  }
}

async function handleDeleteRule(domainId: string, ruleId: string) {
  await store.deleteRule(domainId, ruleId)
}

async function handleDeleteSelectedRule() {
  if (!store.selectedRule?.domain.id || !store.selectedRule?.rule.id) return
  await store.deleteRule(store.selectedRule.domain.id, store.selectedRule.rule.id)
}
</script>

<style scoped>
.review-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  gap: 12px;
  padding: 16px;
}

.loading-state {
  display: flex;
  align-items: center;
  justify-content: center;
  flex: 1;
  color: #888;
  font-size: 14px;
}

.review-layout {
  display: grid;
  grid-template-columns: 1fr 1.5fr 1.2fr;
  gap: 16px;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

@media (max-width: 1200px) {
  .review-layout {
    grid-template-columns: 1fr 1.2fr;
  }
}
</style>
