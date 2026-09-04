<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()

onMounted(() => {
  router.replace({ name: 'user-memory' })
})
</script>

<template>
  <div class="redirect-hint">正在跳转到长期记忆…</div>
</template>

<style scoped>
.redirect-hint {
  font-size: 14px;
  color: var(--text-muted);
}
</style>
