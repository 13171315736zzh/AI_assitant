export interface WelcomeQuickAction {
  id: string
  label: string
  icon: string
  prompt: string
}

export const DEFAULT_WELCOME_TEXT = '您好，我是国能办公助手，有什么可以帮您？'

export const WELCOME_QUICK_ACTIONS: WelcomeQuickAction[] = [
  { id: 'travel', label: '差旅申请', icon: '✈️', prompt: '我想申请出差，请帮我安排行程' },
  { id: 'ticket', label: '车票预订', icon: '🎫', prompt: '帮我预订出差车票' },
  { id: 'hotel', label: '酒店预订', icon: '🏨', prompt: '帮我预订出差酒店' },
  { id: 'workpackage', label: '工时填报', icon: '📊', prompt: '我要填报本周工包工时' },
  { id: 'email', label: '邮件撰写', icon: '✉️', prompt: '帮我起草一封工作邮件' },
  { id: 'meeting', label: '会议室预约', icon: '📅', prompt: '帮我预约会议室' },
]
