import { onMounted, onUnmounted } from 'vue'
import { subscribeOaTaskUpdates, type OaDemoPayload } from '@/utils/oaDemo'

export function useOaTaskSync(onUpdate: (payload: OaDemoPayload) => void) {
  let unsubscribe: (() => void) | null = null

  onMounted(() => {
    unsubscribe = subscribeOaTaskUpdates(onUpdate)
  })

  onUnmounted(() => {
    unsubscribe?.()
    unsubscribe = null
  })
}
