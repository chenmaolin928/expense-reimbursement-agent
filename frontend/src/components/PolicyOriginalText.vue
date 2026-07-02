<template>
  <div class="text-panel">
    <div class="text-panel-header">
      <h3>📄 原文</h3>
      <span class="char-count">{{ text.length }} 字符</span>
    </div>
    <div class="text-content" ref="textContainer" @click="handleTextClick">
      <template v-if="text">
        <span v-for="(seg, i) in segments" :key="i"
              :class="['text-segment', { highlight: seg.highlight }]"
              :data-start="seg.start"
              :data-end="seg.end"
              @click="onSegmentClick(seg)">
          {{ seg.content }}
        </span>
      </template>
      <div v-else class="empty-state">暂无原文内容</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'

const props = defineProps<{
  text: string
  highlightRange: { start: number; end: number } | null
}>()

const emit = defineEmits<{
  textClick: [start: number, end: number]
}>()

const textContainer = ref<HTMLElement | null>(null)

interface TextSegment {
  content: string
  start: number
  end: number
  highlight: boolean
}

const segments = computed<TextSegment[]>(() => {
  if (!props.text || !props.highlightRange) {
    return props.text ? [{ content: props.text, start: 0, end: props.text.length, highlight: false }] : []
  }
  const { start, end } = props.highlightRange
  const clampedStart = Math.max(0, start)
  const clampedEnd = Math.min(props.text.length, end)
  const result: TextSegment[] = []

  if (clampedStart > 0) {
    result.push({ content: props.text.slice(0, clampedStart), start: 0, end: clampedStart, highlight: false })
  }
  result.push({ content: props.text.slice(clampedStart, clampedEnd), start: clampedStart, end: clampedEnd, highlight: true })
  if (clampedEnd < props.text.length) {
    result.push({ content: props.text.slice(clampedEnd), start: clampedEnd, end: props.text.length, highlight: false })
  }
  return result
})

watch(() => props.highlightRange, () => {
  if (props.highlightRange && textContainer.value) {
    const mark = textContainer.value.querySelector('.highlight')
    if (mark) {
      mark.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }
  }
})

function onSegmentClick(seg: TextSegment) {
  if (seg.highlight) {
    emit('textClick', seg.start, seg.end)
  }
}

function handleTextClick(event: MouseEvent) {
  const target = event.target as HTMLElement
  const start = target.dataset.start
  const end = target.dataset.end
  if (start && end) {
    emit('textClick', parseInt(start), parseInt(end))
  }
}
</script>

<style scoped>
.text-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #14141a;
  border: 1px solid #2a2a35;
  border-radius: 8px;
  overflow: hidden;
}

.text-panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid #2a2a35;
  flex-shrink: 0;
}

.text-panel-header h3 {
  margin: 0;
  font-size: 14px;
  color: #e0e0e0;
}

.char-count {
  font-size: 12px;
  color: #888;
}

.text-content {
  padding: 16px;
  overflow-y: auto;
  flex: 1;
  font-size: 13px;
  line-height: 1.7;
  color: #c0c0c0;
  white-space: pre-wrap;
  word-wrap: break-word;
  cursor: pointer;
}

.text-segment {
  transition: background-color 0.2s;
  border-radius: 2px;
}

.text-segment.highlight {
  background: rgba(99, 102, 241, 0.25);
  color: #e8e8ff;
  outline: 1px solid rgba(99, 102, 241, 0.4);
}

.text-segment:not(.highlight):hover {
  background: rgba(255, 255, 255, 0.03);
}

.empty-state {
  color: #666;
  text-align: center;
  padding: 40px;
}
</style>
