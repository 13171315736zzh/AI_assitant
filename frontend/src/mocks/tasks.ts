import type { Task } from '@/types'

export const mockTasks: Record<string, Task> = {
  task_001: {
    id: 'task_001',
    session_id: 'sess_001',
    goal: '下周三去神东项目出差，安排差旅申请和机票',
    status: 'running',
    current_step: 2,
    total_steps: 4,
    replan_count: 0,
    steps: [
      {
        step_id: 1,
        action: '差旅申请创建',
        tool: 'travel_apply',
        status: 'completed',
        depends_on: [],
        params: { destination: '鄂尔多斯' },
        result: { receipt_id: 'TA20260325001', form_id: 'form_001' },
      },
      {
        step_id: 2,
        action: '机票预订',
        tool: 'flight_book',
        status: 'running',
        depends_on: [1],
        params: { cabin: 'economy' },
        result: null,
      },
      {
        step_id: 3,
        action: '酒店预订',
        tool: 'hotel_book',
        status: 'pending',
        depends_on: [1],
        params: {},
        result: null,
      },
      {
        step_id: 4,
        action: '用户确认',
        tool: 'user_confirm',
        status: 'pending',
        depends_on: [2, 3],
        params: {},
        result: null,
      },
    ],
    created_at: '2026-03-20T09:15:05+08:00',
  },
}

export function mockGetTask(taskId: string): Task | null {
  return mockTasks[taskId] ?? null
}

export function mockCancelTask(taskId: string): Task | null {
  const task = mockTasks[taskId]
  if (!task) return null
  task.status = 'cancelled'
  return task
}

export function mockConfirmTask(taskId: string, stepId: number): Task | null {
  const task = mockTasks[taskId]
  if (!task) return null
  task.current_step = stepId
  task.status = 'running'
  const step = task.steps.find((s) => s.step_id === stepId)
  if (step) step.status = 'running'
  return task
}
