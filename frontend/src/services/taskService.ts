import type { ApiResponse, PaginatedData, Task, TaskSummary } from '@/types'
import { mockCancelTask, mockConfirmTask, mockGetTask, mockListTasks } from '@/mocks/tasks'
import { buildTaskSummary } from '@/utils/taskCatalog'
import api, { isMockMode } from './api'

export async function listTasks(params?: {
  status?: 'running' | 'completed' | 'cancelled'
  category?: TaskSummary['category']
  page?: number
  page_size?: number
}): Promise<ApiResponse<PaginatedData<TaskSummary>>> {
  const page = params?.page ?? 1
  const pageSize = params?.page_size ?? 20
  const status = params?.status
  const category = params?.category

  if (isMockMode('tasks')) {
    await delay(200)
    let items = mockListTasks().map(buildTaskSummary)
    if (status === 'cancelled') {
      items = items.filter((t) => t.status === 'cancelled')
    } else if (status === 'running') {
      items = items.filter((t) => t.status === 'running')
    } else if (status === 'completed') {
      items = items.filter((t) => t.status === 'completed')
    } else {
      items = items.filter((t) => t.status !== 'cancelled')
    }
    if (category) {
      items = items.filter((t) => t.category === category)
    }
    items.sort((a, b) => b.created_at.localeCompare(a.created_at))
    const total = items.length
    const start = (page - 1) * pageSize
    return {
      code: 200,
      message: 'success',
      data: {
        items: items.slice(start, start + pageSize),
        total,
        page,
        page_size: pageSize,
      },
    }
  }

  const { data } = await api.get<ApiResponse<PaginatedData<TaskSummary>>>('/tasks', {
    params: { status, category, page, page_size: pageSize },
  })
  return data
}

export async function fetchTask(taskId: string): Promise<ApiResponse<Task>> {
  if (isMockMode('tasks')) {
    await delay(200)
    const task = mockGetTask(taskId)
    if (!task) return { code: 404, message: '任务不存在', data: null as unknown as Task }
    return { code: 200, message: 'success', data: task }
  }
  const { data } = await api.get<ApiResponse<Task>>(`/tasks/${taskId}`)
  return data
}

export type OaTaskActionResult = {
  task: Task
  session_id: string
  receipt_id?: string | null
  assistant_message?: import('@/types').Message | null
}

export async function cancelTask(taskId: string): Promise<ApiResponse<OaTaskActionResult>> {
  if (isMockMode('tasks')) {
    const task = mockCancelTask(taskId)
    if (!task) {
      return { code: 404, message: '任务不存在', data: null as unknown as OaTaskActionResult }
    }
    return {
      code: 200,
      message: 'success',
      data: { task, session_id: task.session_id, receipt_id: null, assistant_message: null },
    }
  }
  const { data } = await api.post(`/tasks/${taskId}/cancel`)
  return data
}

export async function withdrawOaApplication(
  taskId: string,
): Promise<ApiResponse<OaTaskActionResult>> {
  if (isMockMode('tasks')) {
    await delay(300)
    const task = mockGetTask(taskId)
    if (!task) {
      return { code: 404, message: '任务不存在', data: null as unknown as OaTaskActionResult }
    }
    return {
      code: 200,
      message: 'success',
      data: {
        task: { ...task, status: 'running' },
        session_id: task.session_id,
        receipt_id: null,
        assistant_message: null,
      },
    }
  }
  const { data } = await api.post(`/tasks/${taskId}/withdraw-oa`)
  return data
}

export async function confirmTask(
  taskId: string,
  stepId: number,
): Promise<ApiResponse<{ id: string; status: string; current_step: number }>> {
  if (isMockMode('tasks')) {
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

export async function submitOaApplication(
  taskId: string,
): Promise<
  ApiResponse<{
    task: Task
    session_id: string
    receipt_id?: string | null
    assistant_message?: import('@/types').Message | null
  }>
> {
  if (isMockMode('tasks')) {
    await delay(300)
    const task = mockGetTask(taskId)
    if (!task) {
      return {
        code: 404,
        message: '任务不存在',
        data: null as unknown as { task: Task; session_id: string },
      }
    }
    return {
      code: 200,
      message: 'success',
      data: {
        task: { ...task, status: 'running' },
        session_id: task.session_id,
        receipt_id: `RC${Date.now()}`,
      },
    }
  }
  const { data } = await api.post(`/tasks/${taskId}/oa-submit`)
  return data
}

export async function approveOaApplication(
  taskId: string,
): Promise<
  ApiResponse<{
    task: Task
    session_id: string
    receipt_id?: string | null
    assistant_message?: import('@/types').Message | null
  }>
> {
  if (isMockMode('tasks')) {
    await delay(400)
    const task = mockGetTask(taskId)
    if (!task) {
      return {
        code: 404,
        message: '任务不存在',
        data: null as unknown as { task: Task; session_id: string },
      }
    }
    const completedSteps = task.steps.map((step) => ({ ...step, status: 'completed' as const }))
    return {
      code: 200,
      message: 'success',
      data: {
        task: {
          ...task,
          status: 'completed',
          current_step: task.total_steps,
          steps: completedSteps,
        },
        session_id: task.session_id,
        receipt_id: `RC${Date.now()}`,
      },
    }
  }
  const { data } = await api.post(`/tasks/${taskId}/oa-approve`)
  return data
}

export async function createGnMeeting(
  taskId: string,
): Promise<
  ApiResponse<{
    task: Task
    session_id: string
    receipt_id?: string | null
    assistant_message?: import('@/types').Message | null
  }>
> {
  if (isMockMode('tasks')) {
    await delay(400)
    const task = mockGetTask(taskId)
    if (!task) {
      return {
        code: 404,
        message: '任务不存在',
        data: null as unknown as { task: Task; session_id: string },
      }
    }
    const completedSteps = task.steps.map((step) => ({ ...step, status: 'completed' as const }))
    return {
      code: 200,
      message: 'success',
      data: {
        task: {
          ...task,
          status: 'completed',
          current_step: task.total_steps,
          steps: completedSteps,
        },
        session_id: task.session_id,
        receipt_id: `GN${Date.now()}`,
      },
    }
  }
  const { data } = await api.post(`/tasks/${taskId}/gn-meeting-create`)
  return data
}

export async function createTransportBooking(
  taskId: string,
): Promise<
  ApiResponse<{
    task: Task
    session_id: string
    receipt_id?: string | null
    assistant_message?: import('@/types').Message | null
  }>
> {
  if (isMockMode('tasks')) {
    await delay(400)
    const task = mockGetTask(taskId)
    if (!task) {
      return {
        code: 404,
        message: '任务不存在',
        data: null as unknown as { task: Task; session_id: string },
      }
    }
    const completedSteps = task.steps.map((step) => ({ ...step, status: 'completed' as const }))
    return {
      code: 200,
      message: 'success',
      data: {
        task: {
          ...task,
          status: 'completed',
          current_step: task.total_steps,
          steps: completedSteps,
        },
        session_id: task.session_id,
        receipt_id: `TR${Date.now()}`,
      },
    }
  }
  const { data } = await api.post(`/tasks/${taskId}/transport-booking-create`)
  return data
}

export async function createHotelBooking(
  taskId: string,
): Promise<
  ApiResponse<{
    task: Task
    session_id: string
    receipt_id?: string | null
    assistant_message?: import('@/types').Message | null
  }>
> {
  if (isMockMode('tasks')) {
    await delay(400)
    const task = mockGetTask(taskId)
    if (!task) {
      return {
        code: 404,
        message: '任务不存在',
        data: null as unknown as { task: Task; session_id: string },
      }
    }
    const completedSteps = task.steps.map((step) => ({ ...step, status: 'completed' as const }))
    return {
      code: 200,
      message: 'success',
      data: {
        task: {
          ...task,
          status: 'completed',
          current_step: task.total_steps,
          steps: completedSteps,
        },
        session_id: task.session_id,
        receipt_id: `HT${Date.now()}`,
      },
    }
  }
  const { data } = await api.post(`/tasks/${taskId}/hotel-booking-create`)
  return data
}

export async function submitEmailSent(
  taskId: string,
  payload: {
    recipient?: string
    subject?: string
    message_id?: string
    body?: string
    sent_at?: string
  },
): Promise<
  ApiResponse<{
    task: Task
    session_id: string
    assistant_message?: import('@/types').Message | null
  }>
> {
  if (isMockMode('tasks')) {
    await delay(300)
    const task = mockGetTask(taskId)
    if (!task) {
      return {
        code: 404,
        message: '任务不存在',
        data: null as unknown as { task: Task; session_id: string },
      }
    }
    const completedSteps = task.steps.map((step) => ({ ...step, status: 'completed' as const }))
    return {
      code: 200,
      message: 'success',
      data: {
        task: {
          ...task,
          status: 'completed',
          current_step: task.total_steps,
          steps: completedSteps,
        },
        session_id: task.session_id,
      },
    }
  }
  const { data } = await api.post(`/tasks/${taskId}/email-sent`, payload)
  return data
}

function delay(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}
