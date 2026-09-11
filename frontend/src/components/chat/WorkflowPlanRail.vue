<script setup lang="ts">
import { computed, ref } from 'vue'
import type { Message, WorkflowPlan, WorkflowPlanNode } from '@/types'
import { buildWorkflowProgressSummary } from '@/utils/workflowProgressSummary'
import { nodeStatusLabel } from '@/utils/workflowPlan'

const props = defineProps<{
  plan: WorkflowPlan
  expanded: boolean
  messages: Message[]
}>()

const emit = defineEmits<{
  toggle: []
  focusNode: [node: WorkflowPlanNode]
}>()

const completedCount = computed(
  () => props.plan.nodes.filter((node) => node.status === 'completed').length,
)

const copied = ref(false)

const hasStartedNodes = computed(
  () => props.plan.nodes.some((node) => node.status !== 'pending'),
)

async function copyProgressSummary() {
  if (!hasStartedNodes.value) return
  const text = buildWorkflowProgressSummary(props.plan, props.messages)
  try {
    await navigator.clipboard.writeText(text)
    copied.value = true
    window.setTimeout(() => {
      copied.value = false
    }, 2000)
  } catch {
    window.alert('复制失败，请稍后重试')
  }
}

function nodeDisplayLabel(node: WorkflowPlanNode): string {
  if (node.id === 'gn_meeting') return '国能会'
  return node.label
}

function bookingVisualStatus(node: WorkflowPlanNode): string {
  if (node.status === 'cancelled') return 'cancelled'
  if (node.id !== 'booking') return node.status
  const progress = node.booking_progress
  if (!progress) return node.status
  if (
    progress.outbound === 'completed'
    && progress.needs_return
    && progress.return !== 'completed'
  ) {
    return 'partial'
  }
  if (
    progress.outbound === 'completed'
    && (!progress.needs_return || progress.return === 'completed')
  ) {
    return 'completed'
  }
  return node.status
}

function nodeClass(node: WorkflowPlanNode) {
  const visual = bookingVisualStatus(node)
  return [
    'plan-node',
    visual,
    { active: props.plan.active_node_id === node.id && node.status === 'running' },
  ]
}

function handleNodeClick(node: WorkflowPlanNode) {
  emit('focusNode', node)
}
</script>

<template>
  <div class="workflow-rail-wrap" :class="{ 'is-collapsed': !expanded }">
    <aside class="workflow-rail" :class="{ collapsed: !expanded }">
      <template v-if="expanded">
        <header class="rail-head">
          <strong class="rail-title">办理节点</strong>
          <span class="rail-progress">{{ completedCount }}/{{ plan.nodes.length }}</span>
        </header>

        <div class="rail-track">
          <div
            v-for="(node, index) in plan.nodes"
            :key="node.id"
            class="rail-item"
          >
            <div class="rail-line" :class="{ last: index === plan.nodes.length - 1 }" />
            <button
              type="button"
              class="node-button"
              :class="nodeClass(node)"
              :title="`${nodeStatusLabel(node.status)} · 点击查看相关对话`"
              @click="handleNodeClick(node)"
            >
              <span class="node-label">{{ nodeDisplayLabel(node) }}</span>
            </button>
          </div>
        </div>

        <div class="rail-copy-wrap">
          <button
            type="button"
            class="btn-copy-progress"
            :class="{ copied }"
            :disabled="!hasStartedNodes"
            :title="hasStartedNodes ? '复制已开始节点的状态与关键信息' : '暂无已开始节点'"
            @click="copyProgressSummary"
          >
            {{ copied ? '已复制' : '复制' }}
          </button>
        </div>

        <footer class="rail-legend">
          <span><i class="dot running" />进行中</span>
          <span><i class="dot submitted" />审批中</span>
          <span><i class="dot completed" />已完成</span>
          <span><i class="dot cancelled" />已取消</span>
        </footer>

        <button
          type="button"
          class="rail-collapse-btn"
          title="收起办理节点"
          @click="emit('toggle')"
        >
          <span class="chevron" aria-hidden="true">▲</span>
          <span>收起</span>
        </button>
      </template>

      <button
        v-else
        type="button"
        class="rail-collapsed-chip"
        title="展开办理节点"
        @click="emit('toggle')"
      >
        <span class="chip-label">办理节点</span>
        <span class="chip-progress">{{ completedCount }}/{{ plan.nodes.length }}</span>
        <span class="chip-chevron" aria-hidden="true">▲</span>
      </button>
    </aside>
  </div>
</template>

<style scoped>
.workflow-rail-wrap {
  position: absolute;
  top: 64px;
  right: 16px;
  bottom: auto;
  z-index: 20;
  pointer-events: none;
  transition:
    top 0.28s ease,
    bottom 0.28s ease,
    right 0.28s ease;
}

.workflow-rail-wrap.is-collapsed {
  top: auto;
  bottom: 132px;
  right: 16px;
}

.workflow-rail {
  pointer-events: auto;
  width: 88px;
  border: 1px solid var(--border);
  border-radius: 12px;
  background: color-mix(in srgb, var(--surface) 92%, #fff);
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.12);
  overflow: hidden;
  transition:
    width 0.28s ease,
    border-radius 0.28s ease,
    box-shadow 0.28s ease;
}

.workflow-rail.collapsed {
  width: auto;
  border-radius: 999px;
  box-shadow: 0 6px 20px rgba(15, 23, 42, 0.14);
}

.rail-head {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 12px 10px 0;
  font-size: 12px;
  text-align: center;
}

.rail-title {
  display: block;
  width: 100%;
  color: var(--text);
  font-size: 12px;
  letter-spacing: 0.02em;
  white-space: nowrap;
}

.btn-copy-progress {
  width: 100%;
  padding: 5px 8px;
  border: 1px solid var(--primary);
  border-radius: 6px;
  background: #fff;
  color: var(--primary);
  font-size: 10px;
  line-height: 1.2;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}

.btn-copy-progress:hover:not(:disabled) {
  background: color-mix(in srgb, var(--primary) 8%, #fff);
}

.btn-copy-progress:disabled {
  opacity: 0.45;
  cursor: not-allowed;
  border-color: #cbd5e1;
  color: #94a3b8;
}

.btn-copy-progress.copied {
  border-color: #22c55e;
  color: #15803d;
  background: #f0fdf4;
}

.rail-copy-wrap {
  margin: 12px 10px 0;
  padding-top: 10px;
  border-top: 1px solid var(--border);
}

.rail-progress {
  color: var(--text-secondary);
  font-size: 11px;
}

.rail-track {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 14px;
  padding: 12px 10px 0;
}

.rail-item {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.rail-line {
  position: absolute;
  top: 34px;
  width: 2px;
  height: calc(100% + 14px);
  background: #dbe1ea;
}

.rail-line.last {
  display: none;
}

.node-button {
  position: relative;
  z-index: 1;
  width: 52px;
  height: 52px;
  border-radius: 999px;
  border: 2px solid #cbd5e1;
  background: var(--surface);
  color: var(--text);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  transition: border-color 0.2s, background 0.2s, transform 0.15s;
}

.node-button:hover {
  transform: translateY(-1px);
}

.node-label {
  font-size: 12px;
  font-weight: 600;
  line-height: 1.1;
  letter-spacing: 0.02em;
}

.plan-node.pending {
  border-color: #cbd5e1;
  color: #94a3b8;
  background: #f8fafc;
}

.plan-node.running,
.plan-node.active {
  border-color: var(--primary);
  color: var(--primary);
  background: var(--surface);
  box-shadow: 0 0 0 4px color-mix(in srgb, var(--primary) 12%, transparent);
}

.plan-node.submitted,
.plan-node.partial {
  border-color: #f59e0b;
  background: #fef3c7;
  color: #b45309;
}

.plan-node.completed {
  border-color: #22c55e;
  background: #dcfce7;
  color: #15803d;
}

.plan-node.cancelled {
  border-color: #94a3b8;
  background: #e2e8f0;
  color: #64748b;
  opacity: 0.72;
}

.dot.cancelled {
  border-color: #94a3b8;
  background: #e2e8f0;
}

.rail-legend {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin: 10px 10px 0;
  padding: 0;
  font-size: 10px;
  color: var(--text-secondary);
}

.rail-legend span {
  display: flex;
  align-items: center;
  gap: 6px;
}

.dot {
  width: 10px;
  height: 10px;
  border-radius: 999px;
  border: 2px solid #cbd5e1;
  background: var(--surface);
  flex-shrink: 0;
}

.dot.submitted {
  border-color: #f59e0b;
  background: #fef3c7;
}

.dot.completed {
  border-color: #22c55e;
  background: #dcfce7;
}

.rail-collapse-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  width: 100%;
  margin-top: 10px;
  padding: 8px 6px 10px;
  border: none;
  border-top: 1px solid var(--border);
  background: color-mix(in srgb, var(--surface) 88%, #f1f5f9);
  color: var(--text-secondary);
  font-size: 11px;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}

.rail-collapse-btn:hover {
  background: #f8fafc;
  color: var(--primary);
}

.rail-collapse-btn .chevron {
  font-size: 10px;
  line-height: 1;
}

.rail-collapsed-chip {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  border: none;
  background: transparent;
  color: var(--text);
  cursor: pointer;
  white-space: nowrap;
  transition: background 0.15s;
}

.rail-collapsed-chip:hover {
  background: color-mix(in srgb, var(--primary) 6%, transparent);
}

.chip-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--text);
}

.chip-progress {
  font-size: 12px;
  color: var(--text-secondary);
}

.chip-chevron {
  font-size: 10px;
  line-height: 1;
  color: var(--primary);
}
</style>
