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
  provider: '数据来源',
  selected: '已选方案',
  alternatives: '备选方案',
  max_price: '价格上限',
  max_distance_km: '距离上限(km)',
  room_type: '房型',
  arrival_before: '到达时限',
  route: '航线',
  preference: '偏好',
  city: '城市',
  nights: '晚数',
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
export const HIDDEN_RESULT_KEYS = new Set(['form_id', 'provider', 'alternatives'])

export function taskFieldLabel(key: string): string {
  return FIELD_LABELS[key] ?? key
}

export function taskFieldValue(value: unknown): string {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'object') {
    const obj = value as Record<string, unknown>
    if ('flight_no' in obj) {
      return `${obj.flight_no} ${obj.departure_time ?? ''} → ${obj.arrival_time ?? ''}`.trim()
    }
    if ('name' in obj && 'price_per_night' in obj) {
      return `${obj.name} ${obj.price_per_night}元/晚`
    }
    return JSON.stringify(obj)
  }
  const str = String(value)
  return VALUE_LABELS[str] ?? str
}
