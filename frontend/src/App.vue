<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'
import { RouterView } from 'vue-router'
import { subscribeOaTaskUpdates } from '@/utils/oaDemo'
import { useChatStore } from '@/stores/useChatStore'

const chat = useChatStore()
let unsubscribeOaSync: (() => void) | null = null

onMounted(() => {
  unsubscribeOaSync = subscribeOaTaskUpdates((payload) => {
    void chat.handleOaTaskUpdate(payload)
  })
})

onUnmounted(() => {
  unsubscribeOaSync?.()
  unsubscribeOaSync = null
})
</script>

<template>
  <RouterView />
</template>
