export interface ApiResponse<T> {
  code: number
  message: string
  data: T
}

export interface PaginatedData<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

export type UserRole = 'admin' | 'employee'

export interface User {
  id: number
  username: string
  display_name: string
  role: UserRole
  employee_id: string
}

export interface LoginData {
  access_token: string
  token_type: string
  user: User
}

export type SessionStatus = 'active' | 'ended'
export type EndedReason = 'completed' | 'manual' | null

export interface Session {
  id: string
  user_id: number
  title: string
  status: SessionStatus
  ended_reason: EndedReason
  message_count: number
  created_at: string
  updated_at: string
}

export type MessageRole = 'user' | 'assistant' | 'system'
export type MessageType = 'text' | 'form' | 'task' | 'reject' | 'pending'

export interface Message {
  id: string
  session_id: string
  role: MessageRole
  content: string
  message_type: MessageType
  metadata: Record<string, unknown> | null
  created_at: string
}

export interface SendMessageData {
  user_message: Message
  assistant_message: Message
}

export interface MessageSource {
  filename: string
  clause: string
  document_id?: string
}

export interface TaskStep {
  step_id: number
  action: string
  tool: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  depends_on: number[]
  params: Record<string, unknown>
  result: Record<string, unknown> | null
}

export interface Task {
  id: string
  session_id: string
  goal: string
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'
  current_step: number
  total_steps: number
  replan_count: number
  steps: TaskStep[]
  created_at: string
}
