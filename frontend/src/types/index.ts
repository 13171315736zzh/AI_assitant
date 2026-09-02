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
  excerpt?: string
}

export interface FlightOption {
  flight_no: string
  airline: string
  origin: string
  destination: string
  departure_time: string
  arrival_time: string
  cabin: string
  price: number
}

export interface HotelOption {
  name: string
  address: string
  distance_km: number
  price_per_night: number
  room_type: string
  check_in: string
  check_out: string
}

export interface BookingSelectionMeta {
  status: 'pending' | 'confirmed'
  needs_flight: boolean
  needs_hotel: boolean
  destination: string
  flights: FlightOption[]
  hotels: HotelOption[]
}

export interface RoomOption {
  room: string
  floor: string
  capacity: number
  equipment: string
  available: boolean
}

export interface RoomSelectionMeta {
  status: 'pending' | 'confirmed'
  subject: string
  requested_room: string
  time_label: string
  conflict_reason: string | null
  options: RoomOption[]
}

export interface TimesheetConflict {
  day_label: string
  day_date: string
  period: string
  existing_project: string
  person_days: number
  hours?: number
}

export interface TimesheetEntry {
  day_label: string
  day_date: string
  period: string
  project: string
  person_days: number
  hours: number
  selected?: boolean
}

export interface WorkpackageConfirmMeta {
  status: 'pending' | 'confirmed'
  project: string
  period_label: string
  requested_days: number
  fillable_days: number
  total_budget_days: number | null
  hours_per_day: number
  conflicts: TimesheetConflict[]
  entries: TimesheetEntry[]
}

export interface PlanConfirmItem {
  label: string
  value: string
}

export interface WorkpackagePlanConfirmMeta {
  status: 'pending' | 'confirmed'
  title: string
  items: PlanConfirmItem[]
  project_options?: string[]
  selected_project?: string | null
  date_start?: string | null
  date_end?: string | null
  hours_per_day?: number
  requires_project?: boolean
}

export interface PlanConfirmMeta {
  status: 'pending' | 'confirmed'
  title: string
  items: PlanConfirmItem[]
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

export type TaskCategory = 'travel' | 'meeting' | 'workpackage' | 'email' | 'other'
export type TaskDisplayStatus = 'running' | 'completed' | 'cancelled' | 'failed'

export interface TaskSummary {
  id: string
  session_id: string
  goal: string
  status: TaskDisplayStatus
  raw_status: string
  category: TaskCategory
  category_label: string
  tags: string[]
  completed_steps: number
  total_steps: number
  progress_percent: number
  current_step: number
  replan_count: number
  created_at: string
}
