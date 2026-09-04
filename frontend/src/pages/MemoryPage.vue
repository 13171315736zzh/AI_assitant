<script setup lang="ts">
import { useRouter } from 'vue-router'
import ChatTopbar from '@/components/chat/ChatTopbar.vue'
import MemoryPanel from '@/components/memory/MemoryPanel.vue'

const router = useRouter()
</script>

<template>
  <div class="app-shell memory-page">
    <section class="main">
      <ChatTopbar />

      <div class="page-main">
        <header class="page-header">
          <div>
            <h1>长期记忆</h1>
            <p class="subtitle">
              查看并编辑系统为您保存的个人信息与偏好。对话中自动提取的内容会汇总在此，您也可以手动修改；助手在办理差旅、工时等业务时会参考这些记忆。
            </p>
          </div>
          <button type="button" class="btn-back" @click="router.push({ name: 'chat' })">
            返回对话
          </button>
        </header>

        <MemoryPanel />
      </div>
    </section>
  </div>
</template>

<style scoped>
.memory-page .main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  min-height: 100vh;
}

.page-main {
  flex: 1;
  overflow-y: auto;
  padding: 24px 32px 40px;
  max-width: 960px;
}

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 24px;
}

.page-header h1 {
  font-size: 24px;
  margin: 0 0 8px;
}

.subtitle {
  margin: 0;
  font-size: 14px;
  line-height: 1.6;
  color: var(--text-secondary);
  max-width: 640px;
}

.btn-back {
  flex-shrink: 0;
  height: 36px;
  padding: 0 16px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--surface);
  color: var(--text-secondary);
  font-size: 13px;
  cursor: pointer;
  white-space: nowrap;
}

.btn-back:hover {
  border-color: var(--primary);
  color: var(--primary);
}
</style>
