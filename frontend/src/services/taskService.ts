import type { ApiResponse, Task } from '@/types'
import { mockCancelTask, mockConfirmTask, mockGetTask } from '@/mocks/tasks'
import api, { isMockMode } from './api'

export async function fetchTask(taskId: string): Promise<ApiResponse<Task>> {
  if (isMockMode()) {
    await delay(200)
    const task = mockGetTask(taskId)
    if (!task) return { code: 404, message: '任务不存在', data: null as unknown as Task }
    return { code: 200, message: 'success', data: task }
  }
  const { data } = await api.get<ApiResponse<Task>>(`/tasks/${taskId}`)
  return data
}

export async function cancelTask(taskId: string): Promise<ApiResponse<{ id: string; status: string }>> {
  if (isMockMode()) {
    const task = mockCancelTask(taskId)
    if (!task) return { code: 404, message: '任务不存在', data: null as unknown as { id: string; status: string } }
    return { code: 200, message: 'success', data: { id: task.id, status: task.status } }
  }
  const { data } = await api.post(`/tasks/${taskId}/cancel`)
  return data
}

export async function confirmTask(
  taskId: string,
  stepId: number,
): Promise<ApiResponse<{ id: string; status: string; current_step: number }>> {
  if (isMockMode()) {
    const task = mockConfirmTask(taskId, stepId)
    if (!task) return { code: 404, message: '任务不存在', data: null as unknown as { id: string; status: string; current_step: number } }
    return {
      code: 200,
      message: 'success',
      data: { id: task.id, status: task.status, current_step: task.current_step },
    }
  }
  const { data } = await api.post(`/tasks/${taskId}/confirm`, { step_id: stepId })
  return data
}

function delay(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}
