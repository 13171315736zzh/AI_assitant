export interface WelcomeQuickAction {
  id: string
  label: string
  icon: string
  prompt: string
}

export const DEFAULT_WELCOME_TEXT = '您好，我是国能办公助手，有什么可以帮您？'

export const WELCOME_QUICK_ACTIONS: WelcomeQuickAction[] = [
  // 第一行
  { id: 'travel', label: '差旅申请', icon: '✈️', prompt: '我想申请出差，请帮我安排行程' },
  { id: 'ticket', label: '车票预定', icon: '🎫', prompt: '帮我预订出差车票' },
  { id: 'hotel', label: '酒店预定', icon: '🏨', prompt: '帮我预订出差酒店' },
  { id: 'meeting', label: '会议室预定', icon: '📅', prompt: '帮我预约会议室' },
  // 第二行
  { id: 'workpackage', label: '工时填报', icon: '📊', prompt: '我要填报本周工包工时' },
  { id: 'email', label: '邮件撰写', icon: '✉️', prompt: '帮我起草一封工作邮件' },
  { id: 'info_collect', label: '信息收集', icon: '📝', prompt: '帮我完善个人信息，写入长期记忆' },
  { id: 'leave', label: '请假申请', icon: '🏖️', prompt: '我要申请请假，请帮我办理' },
]
