export type FormType = 'email' | 'meeting' | 'travel' | 'workpackage' | 'leave' | 'info_collect'
export type FormStatus = 'preview' | 'confirmed' | 'submitted' | 'receipt'

export interface FormData {
  form_id: string
  form_type: FormType
  status: FormStatus
  title: string
  fields: Record<string, string>
}

export interface FormReceipt {
  receipt_id: string
  status: string
  summary: string
  submitted_at: string
}

const travelFields: Record<string, string> = {
  destination: '鄂尔多斯',
  departure_date: '2026-03-26',
  return_date: '2026-03-28',
  project: '神东能源数据治理平台',
  transport: '飞机 · 经济舱',
  description: '现场培训',
}

export const mockForms: Record<string, FormData> = {
  form_001: {
    form_id: 'form_001',
    form_type: 'travel',
    status: 'preview',
    title: '差旅申请表单',
    fields: { ...travelFields },
  },
}

export const formFieldLabels: Record<string, Record<string, string>> = {
  travel: {
    destination: '目的地',
    departure_date: '出发日期',
    return_date: '返回日期',
    project: '关联项目',
    transport: '交通方式',
    description: '出差说明',
  },
  workpackage: {
    project: '项目名称',
    hours: '工时',
    content: '工作内容',
    period: '填报周期',
  },
  leave: {
    leave_type: '请假类型',
    date_start: '开始日期',
    date_end: '结束日期',
    start_period: '开始时段',
    end_period: '结束时段',
    reason: '请假事由',
    days: '请假天数',
    attachment_name: '附件',
  },
  meeting: {
    subject: '会议主题',
    start_time: '开始时间',
    end_time: '结束时间',
    room: '会议室',
    attendees: '参会人员',
  },
  email: {
    to: '收件人',
    cc: '抄送',
    subject: '主题',
    body: '正文',
  },
  info_collect: {
    topic: '收集主题',
    target: '收集对象',
    fields: '需收集字段',
    deadline: '截止时间',
    description: '说明',
  },
}

export function mockGetForm(formId: string): FormData | null {
  return mockForms[formId] ? { ...mockForms[formId], fields: { ...mockForms[formId].fields } } : null
}

export function mockConfirmForm(formId: string): FormData | null {
  const form = mockForms[formId]
  if (!form) return null
  form.status = 'confirmed'
  return mockGetForm(formId)
}

export function mockSubmitForm(formId: string, fields: Record<string, string>): FormReceipt {
  const form = mockForms[formId]
  if (form) {
    form.fields = { ...fields }
    form.status = 'submitted'
  }
  return {
    receipt_id: 'RC20260325001',
    status: 'submitted',
    summary: '差旅申请已进入审批流程',
    submitted_at: new Date().toISOString(),
  }
}

export function mockPreviewForm(formType: FormType): FormData {
  const id = `form_${Date.now()}`
  const templates: Record<FormType, FormData> = {
    travel: {
      form_id: id,
      form_type: 'travel',
      status: 'preview',
      title: '差旅申请表单',
      fields: { ...travelFields },
    },
    workpackage: {
      form_id: id,
      form_type: 'workpackage',
      status: 'preview',
      title: '工包填报',
      fields: {
        project: '神东能源数据治理平台',
        hours: '40',
        content: '数据治理方案编写',
        period: '2026-W12',
      },
    },
    leave: {
      form_id: id,
      form_type: 'leave',
      status: 'preview',
      title: '请假申请',
      fields: {
        leave_type: '病假',
        date_start: '2026-09-05',
        date_end: '2026-09-05',
        start_period: '全天',
        end_period: '全天',
        reason: '身体不适需休息',
        days: '1',
        attachment_name: '',
      },
    },
    meeting: {
      form_id: id,
      form_type: 'meeting',
      status: 'preview',
      title: '会议预约',
      fields: {
        subject: '项目进度评审会',
        start_time: '2026-03-26 14:00',
        end_time: '2026-03-26 16:00',
        room: '总部 A301',
        attendees: '张明、李经理、王芳',
      },
    },
    email: {
      form_id: id,
      form_type: 'email',
      status: 'preview',
      title: '邮件撰写',
      fields: {
        to: 'limanager@ceic.com',
        cc: '',
        subject: '神东项目出差安排确认',
        body: '赵士廷经理，您好！\n\n烦请知悉，我计划于下周三前往神东项目现场…\n\n此致\n敬礼',
      },
    },
    info_collect: {
      form_id: id,
      form_type: 'info_collect',
      status: 'preview',
      title: '信息收集',
      fields: {
        topic: '神东项目团队信息收集',
        target: '神东项目团队',
        fields: '姓名、工号、联系电话、邮箱',
        deadline: '2026-09-10',
        description: '请各成员如实填写联系方式，便于项目协调',
      },
    },
  }
  const form = templates[formType]
  mockForms[id] = form
  return mockGetForm(id)!
}
