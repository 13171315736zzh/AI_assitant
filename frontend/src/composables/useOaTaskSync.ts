import { onMounted, onUnmounted } from 'vue'
import { OA_TASK_EVENT, type OaDemoPayload } from '@/utils/oaDemo'

export function useOaTaskSync(onUpdate: (payload: OaDemoPayload) => void) {
  function handleMessage(event: MessageEvent) {
    if (event.origin !== window.location.origin) return
    const data = event.data as { type?: string } & Partial<OaDemoPayload>
    if (data?.type !== OA_TASK_EVENT || !data.sessionId || !data.taskId || !data.action) {
      return
    }
    onUpdate({
      sessionId: data.sessionId,
      taskId: data.taskId,
      action: data.action,
    })
  }

  onMounted(() => {
    window.addEventListener('message', handleMessage)
  })

  onUnmounted(() => {
    window.removeEventListener('message', handleMessage)
  })
}
