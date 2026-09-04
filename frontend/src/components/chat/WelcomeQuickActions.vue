<script setup lang="ts">
import { WELCOME_QUICK_ACTIONS } from '@/constants/welcomeQuickActions'

defineProps<{
  message: string
  disabled?: boolean
}>()

const emit = defineEmits<{
  select: [prompt: string]
}>()
</script>

<template>
  <div class="welcome-panel">
    <div class="welcome-head">
      <span class="welcome-avatar" aria-hidden="true">助</span>
      <p class="welcome-text">{{ message }}</p>
    </div>

    <div class="quick-grid">
      <button
        v-for="action in WELCOME_QUICK_ACTIONS"
        :key="action.id"
        type="button"
        class="quick-chip"
        :disabled="disabled"
        @click="emit('select', action.prompt)"
      >
        <span class="chip-icon" aria-hidden="true">{{ action.icon }}</span>
        <span class="chip-label">{{ action.label }}</span>
      </button>
    </div>

    <p class="welcome-hint">也可不选，直接在下方输入框说出您的需求</p>
  </div>
</template>

<style scoped>
.welcome-panel {
  width: 100%;
  max-width: 560px;
  padding: 16px 18px;
  border-radius: 14px;
  border: 1px solid var(--border);
  background: linear-gradient(145deg, #ffffff 0%, #fafbfd 100%);
  box-shadow: 0 4px 20px rgba(15, 23, 42, 0.04);
}

.welcome-head {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  margin-bottom: 14px;
}

.welcome-avatar {
  flex-shrink: 0;
  width: 32px;
  height: 32px;
  border-radius: 10px;
  background: linear-gradient(135deg, #c41e3a 0%, #e85d75 100%);
  color: #fff;
  font-size: 13px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
}

.welcome-text {
  margin: 4px 0 0;
  font-size: 14px;
  line-height: 1.55;
  color: var(--text-primary);
}

.quick-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
}

.quick-chip {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  min-height: 56px;
  padding: 8px 4px;
  border: 1px solid #e8ecf1;
  border-radius: 10px;
  background: #fff;
  cursor: pointer;
  transition: border-color 0.15s, box-shadow 0.15s, transform 0.12s;
}

.quick-chip:hover:not(:disabled) {
  border-color: #f5c6c6;
  box-shadow: 0 2px 8px rgba(196, 30, 58, 0.08);
  transform: translateY(-1px);
}

.quick-chip:active:not(:disabled) {
  transform: translateY(0);
}

.quick-chip:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.chip-icon {
  font-size: 16px;
  line-height: 1;
}

.chip-label {
  font-size: 11px;
  color: var(--text-secondary);
  font-weight: 500;
  white-space: nowrap;
  text-align: center;
  line-height: 1.2;
}

.welcome-hint {
  margin: 12px 0 0;
  font-size: 11px;
  color: var(--text-muted);
  text-align: center;
}

@media (max-width: 560px) {
  .quick-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
