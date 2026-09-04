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
  start_time?: string
  end_time?: string
  conflict_reason: string | null
  equipment_pref?: string | null
  browse_mode?: boolean
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
  skipped_days?: Array<{ day_date: string; day_label?: string; reason: string }>
  total_hours?: number
}

export interface PlanConfirmItem {
  label: string
  value: string
}

export interface WorkpackagePlanConfirmMeta {
  status: 'pending' | 'confirmed' | 'superseded'
  title: string
  items: PlanConfirmItem[]
  project_options?: string[]
  selected_project?: string | null
  date_start?: string | null
  date_end?: string | null
  fill_dates?: Array<{
    day_date: string
    day_label?: string
    period?: string
    person_days?: number
    hours?: number
  }>
  hours_per_day?: number
  hours_confirmed?: boolean
  all_days_eight_hours?: boolean | null
  hours_question?: string
  hour_presets?: Array<{ label: string; value: number }>
  requires_project?: boolean
}

export interface LeavePlanConfirmMeta {
  status: 'pending' | 'confirmed' | 'superseded'
  title: string
  items: PlanConfirmItem[]
  leave_type?: string
  date_start?: string | null
  date_end?: string | null
  start_period?: string
  end_period?: string
  reason?: string | null
  attachment_name?: string | null
  requires_reason?: boolean
}

export interface PlanConfirmMeta {
  status: 'pending' | 'confirmed' | 'superseded'
  title: string
  items: PlanConfirmItem[]
  confirm_label?: string
}

export interface MeetingTimeOption {
  label: string
  date_hint: string
  start_hint: string
  end_hint: string
  selected?: boolean
}

export interface MeetingRoomOption {
  room: string
  label: string
  floor: string
  capacity: number
  equipment: string
}

export interface MeetingPlanConfirmMeta extends PlanConfirmMeta {
  plan_mode?: 'gn_only' | 'room_only' | 'combined'
  needs_gn_meeting?: boolean
  needs_room_booking?: boolean
  time_options?: MeetingTimeOption[]
  time_hint?: string
  room_options?: MeetingRoomOption[]
  selected_room?: string | null
  room_flexible?: boolean
  subject?: string
  attendees?: string
  room_hint?: string
  attendees_hint?: string
}

export interface GnMeetingResultMeta {
  meeting_no: string
  meeting_link: string
  meeting_password: string
  subject?: string
}

export interface RoomBookingResultMeta {
  room_name: string
  subject: string
  start_time: string
  end_time: string
  time_label: string
  attendees: string
}

export interface RelatedTaskMeta {
  task_id: string
  task_title: string
  progress: string
  progress_percent: number
  steps_desc: string
  meeting_kind?: 'gn' | 'room'
}

export interface InfoCollectPlanConfirmMeta {
  status: 'pending' | 'confirmed' | 'superseded'
  title: string
  items: PlanConfirmItem[]
  structured?: Record<string, unknown>
  field_errors?: Record<string, string>
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

export type TaskCategory = 'travel' | 'meeting' | 'gn_meeting' | 'workpackage' | 'leave' | 'email' | 'info_collect' | 'other'
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

export type WorkflowNodeStatus = 'pending' | 'running' | 'submitted' | 'completed'

export interface WorkflowPlanNode {
  id: string
  label: string
  status: WorkflowNodeStatus
  task_id?: string | null
}

export interface WorkflowPlan {
  nodes: WorkflowPlanNode[]
  active_node_id: string | null
}

export interface WorkflowNextNode {
  node_id: string | null
  label: string | null
  missing_slots: string[]
}
