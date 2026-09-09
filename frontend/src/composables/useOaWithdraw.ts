import { ref, type Ref } from 'vue'
import { withdrawOaApplication } from '@/services/taskService'
import { buildOaNotifyPayload, notifyAssistantOaUpdate } from '@/utils/oaDemo'

export function useOaWithdraw(taskId: Ref<string>, onReload: () => Promise<void>) {
  const withdrawing = ref(false)

  async function handleWithdraw(): Promise<boolean> {
    if (withdrawing.value) return false
    if (!window.confirm('确认撤回 OA 审批？原申请将作废，修改后可重新提交。')) {
      return false
    }

    withdrawing.value = true
    try {
      const res = await withdrawOaApplication(taskId.value)
      if (res.code !== 200 || !res.data) {
        window.alert(res.message || '撤回失败，请稍后重试')
        return false
      }
      notifyAssistantOaUpdate(buildOaNotifyPayload(res.data, taskId.value, 'submitted'))
      await onReload()
      return true
    } catch {
      window.alert('撤回失败，请返回助手重试')
      return false
    } finally {
      withdrawing.value = false
    }
  }

  return { withdrawing, handleWithdraw }
}
