<script setup lang="ts">
import { computed } from 'vue'
import type { WorkflowPlan, WorkflowPlanNode } from '@/types'
import { nodeStatusLabel } from '@/utils/workflowPlan'

const props = defineProps<{
  plan: WorkflowPlan
  expanded: boolean
}>()

const emit = defineEmits<{
  toggle: []
  focusNode: [node: WorkflowPlanNode]
}>()

const completedCount = computed(
  () => props.plan.nodes.filter((node) => node.status === 'completed').length,
)

function nodeDisplayLabel(node: WorkflowPlanNode): string {
  if (node.id === 'gn_meeting') return '国能会'
  return node.label
}

function nodeClass(node: WorkflowPlanNode) {
  return [
    'plan-node',
    node.status,
    { active: props.plan.active_node_id === node.id && node.status === 'running' },
  ]
}

function handleNodeClick(node: WorkflowPlanNode) {
  emit('focusNode', node)
}
</script>

<template>
  <div class="workflow-rail-wrap">
    <aside class="workflow-rail" :class="{ collapsed: !expanded }">
      <template v-if="expanded">
        <header class="rail-head">
          <strong>办理节点</strong>
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
              :title="`${nodeStatusLabel(node.status)} · ${node.status === 'completed' ? '点击查看相关对话' : '点击开始办理或查看进度'}`"
              @click="handleNodeClick(node)"
            >
              <span class="node-label">{{ nodeDisplayLabel(node) }}</span>
            </button>
          </div>
        </div>

        <footer class="rail-legend">
          <span><i class="dot running" />进行中</span>
          <span><i class="dot submitted" />审批中</span>
          <span><i class="dot completed" />已完成</span>
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
        class="rail-expand-btn"
        title="展开办理节点"
        @click="emit('toggle')"
      >
        <strong>办理节点</strong>
        <span class="rail-progress">{{ completedCount }}/{{ plan.nodes.length }}</span>
        <span class="chevron" aria-hidden="true">▼</span>
      </button>
    </aside>
  </div>
</template>

<style scoped>
.workflow-rail-wrap {
  position: absolute;
  top: 72px;
  right: 12px;
  z-index: 20;
  pointer-events: none;
}

.workflow-rail {
  pointer-events: auto;
  width: 88px;
  border: 1px solid var(--border);
  border-radius: 12px;
  background: color-mix(in srgb, var(--surface) 92%, #fff);
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.12);
  overflow: hidden;
}

.workflow-rail.collapsed {
  width: 72px;
  box-shadow: 0 4px 16px rgba(15, 23, 42, 0.1);
}

.rail-head {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 12px 10px 0;
  font-size: 12px;
}

.rail-head strong {
  color: var(--text);
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

.plan-node.submitted {
  border-color: #f59e0b;
  background: #fef3c7;
  color: #b45309;
}

.plan-node.completed {
  border-color: #22c55e;
  background: #dcfce7;
  color: #15803d;
}

.rail-legend {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin: 14px 10px 0;
  padding: 10px 0 0;
  border-top: 1px solid var(--border);
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

.rail-expand-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  width: 100%;
  padding: 12px 8px;
  border: none;
  background: transparent;
  color: var(--text);
  cursor: pointer;
  transition: background 0.15s;
}

.rail-expand-btn:hover {
  background: color-mix(in srgb, var(--primary) 6%, transparent);
}

.rail-expand-btn strong {
  font-size: 12px;
  font-weight: 600;
}

.rail-expand-btn .rail-progress {
  font-size: 11px;
}

.rail-expand-btn .chevron {
  margin-top: 2px;
  font-size: 10px;
  line-height: 1;
  color: var(--text-secondary);
}
</style>
