/** 任务步骤 params / result 字段中文标签 */
const FIELD_LABELS: Record<string, string> = {
  destination: '目的地',
  departure_date: '出发日期',
  return_date: '返回日期',
  project: '关联项目',
  transport: '交通方式',
  description: '出差说明',
  cabin: '舱位等级',
  hotel: '酒店',
  check_in: '入住日期',
  check_out: '离店日期',
  receipt_id: '工单编号',
  form_id: '表单编号',
  order_id: '订单编号',
  flight_no: '航班号',
  status: '状态',
}

/** 枚举值中文展示 */
const VALUE_LABELS: Record<string, string> = {
  economy: '经济舱',
  business: '商务舱',
  first: '头等舱',
  pending: '待处理',
  running: '进行中',
  completed: '已完成',
  failed: '失败',
  cancelled: '已取消',
}

/** result 区不重复展示的字段（已有专门入口） */
export const HIDDEN_RESULT_KEYS = new Set(['form_id'])

export function taskFieldLabel(key: string): string {
  return FIELD_LABELS[key] ?? key
}

export function taskFieldValue(value: unknown): string {
  if (value === null || value === undefined) return '—'
  const str = String(value)
  return VALUE_LABELS[str] ?? str
}
