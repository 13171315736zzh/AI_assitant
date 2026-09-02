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
        status: 'completed',
        depends_on: [1],
        params: { cabin: 'economy' },
        result: { selected: { flight_no: 'CA1234' } },
      },
      {
        step_id: 3,
        action: '酒店预订',
        tool: 'hotel_book',
        status: 'running',
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
  task_002: {
    id: 'task_002',
    session_id: 'sess_002',
    goal: '预约明天下午项目进度评审会',
    status: 'running',
    current_step: 2,
    total_steps: 3,
    replan_count: 0,
    steps: [
      {
        step_id: 1,
        action: '会议室确认',
        tool: 'room_book',
        status: 'completed',
        depends_on: [],
        params: { room: 'A301' },
        result: { room: 'A301', status: 'confirmed' },
      },
      {
        step_id: 2,
        action: '会议预约',
        tool: 'meeting_book',
        status: 'completed',
        depends_on: [1],
        params: { subject: '项目进度评审会' },
        result: { form_id: 'form_meeting_001' },
      },
      {
        step_id: 3,
        action: '用户确认',
        tool: 'user_confirm',
        status: 'pending',
        depends_on: [2],
        params: {},
        result: null,
      },
    ],
    created_at: '2026-03-18T14:20:00+08:00',
  },
  task_003: {
    id: 'task_003',
    session_id: 'sess_003',
    goal: '填报本周神东能源数据治理平台工包',
    status: 'completed',
    current_step: 2,
    total_steps: 2,
    replan_count: 0,
    steps: [
      {
        step_id: 1,
        action: '工包填报',
        tool: 'workpackage_fill',
        status: 'completed',
        depends_on: [],
        params: { project: '神东能源数据治理平台' },
        result: { form_id: 'form_wp_001', total_person_days: 3 },
      },
      {
        step_id: 2,
        action: '用户确认',
        tool: 'user_confirm',
        status: 'completed',
        depends_on: [1],
        params: {},
        result: null,
      },
    ],
    created_at: '2026-03-15T10:00:00+08:00',
  },
  task_004: {
    id: 'task_004',
    session_id: 'sess_004',
    goal: '给李经理发邮件通知鄂尔多斯出差安排',
    status: 'completed',
    current_step: 2,
    total_steps: 2,
    replan_count: 0,
    steps: [
      {
        step_id: 1,
        action: '邮件通知项目经理',
        tool: 'email_notify',
        status: 'completed',
        depends_on: [],
        params: { recipient: '李经理' },
        result: { form_id: 'form_email_001' },
      },
      {
        step_id: 2,
        action: '用户确认',
        tool: 'user_confirm',
        status: 'completed',
        depends_on: [1],
        params: {},
        result: null,
      },
    ],
    created_at: '2026-03-10T16:30:00+08:00',
  },
}

export function mockGetTask(taskId: string): Task | null {
  const task = mockTasks[taskId]
  return task ? { ...task, steps: task.steps.map((s) => ({ ...s })) } : null
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

export function mockListTasks(): Task[] {
  return Object.values(mockTasks).map((task) => ({
    ...task,
    steps: task.steps.map((s) => ({ ...s })),
  }))
}
