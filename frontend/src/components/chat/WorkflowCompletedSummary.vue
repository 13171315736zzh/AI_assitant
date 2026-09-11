<script setup lang="ts">
import type { WorkflowCompletedNode } from '@/types'

defineProps<{
  node: WorkflowCompletedNode
}>()
</script>

<template>
  <section class="completed-summary">
    <h5 class="summary-title">{{ node.node_label }} · 已确认信息</h5>
    <dl v-if="node.items.length" class="info-list">
      <div v-for="(item, i) in node.items" :key="`${item.label}-${i}`" class="info-row">
        <dt>{{ item.label }}</dt>
        <dd>{{ item.value }}</dd>
      </div>
    </dl>
    <p v-else class="summary-empty">信息已确认，可前往 OA 继续办理。</p>
  </section>
</template>

<style scoped>
.completed-summary {
  padding: 12px;
  background: color-mix(in srgb, var(--text) 4%, var(--surface));
  border: 1px solid color-mix(in srgb, var(--border) 80%, transparent);
  border-radius: var(--radius-sm);
}

.summary-title {
  margin: 0 0 10px;
  font-size: 13px;
  font-weight: 600;
}

.info-list {
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.info-row {
  display: grid;
  grid-template-columns: 88px 1fr;
  gap: 8px;
  padding: 8px 10px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  font-size: 13px;
}

.info-row dt {
  color: var(--text-secondary);
}

.info-row dd {
  margin: 0;
  color: var(--text);
  word-break: break-word;
}

.summary-empty {
  margin: 0;
  font-size: 12px;
  color: var(--text-muted);
}

@media (max-width: 520px) {
  .info-row {
    grid-template-columns: 1fr;
  }
}
</style>
