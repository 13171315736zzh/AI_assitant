import type { ApiResponse } from '@/types'
import type { FormData, FormReceipt, FormType } from '@/mocks/forms'
import { mockConfirmForm, mockGetForm, mockPreviewForm, mockSubmitForm } from '@/mocks/forms'
import api, { isMockMode } from './api'

export async function fetchForm(formId: string): Promise<ApiResponse<FormData>> {
  if (isMockMode('forms')) {
    await delay(150)
    const form = mockGetForm(formId)
    if (!form) return { code: 404, message: '表单不存在', data: null as unknown as FormData }
    return { code: 200, message: 'success', data: form }
  }
  const { data } = await api.get<ApiResponse<FormData>>(`/forms/${formId}`)
  return data
}

export async function previewForm(
  formType: FormType,
  sessionId: string,
  taskId?: string,
): Promise<ApiResponse<FormData>> {
  if (isMockMode('forms')) {
    await delay(200)
    const form = mockPreviewForm(formType)
    void sessionId
    void taskId
    return { code: 200, message: 'success', data: form }
  }
  const { data } = await api.post<ApiResponse<FormData>>(`/forms/${formType}/preview`, {
    session_id: sessionId,
    task_id: taskId,
  })
  return data
}

export async function confirmForm(formId: string): Promise<ApiResponse<{ form_id: string; status: string }>> {
  if (isMockMode('forms')) {
    const form = mockConfirmForm(formId)
    if (!form) return { code: 404, message: '表单不存在', data: null as unknown as { form_id: string; status: string } }
    return { code: 200, message: 'success', data: { form_id: form.form_id, status: form.status } }
  }
  const { data } = await api.post(`/forms/${formId}/confirm`)
  return data
}

export async function submitForm(
  formId: string,
  fields: Record<string, string>,
): Promise<ApiResponse<{ form_id: string; status: string; receipt_id: string; message: string }>> {
  if (isMockMode('forms')) {
    await delay(300)
    const receipt = mockSubmitForm(formId, fields)
    return {
      code: 200,
      message: 'success',
      data: {
        form_id: formId,
        status: 'submitted',
        receipt_id: receipt.receipt_id,
        message: receipt.summary,
      },
    }
  }
  const { data } = await api.post(`/forms/${formId}/submit`, { fields })
  return data
}

export async function fetchReceipt(formId: string): Promise<ApiResponse<FormReceipt>> {
  if (isMockMode('forms')) {
    return {
      code: 200,
      message: 'success',
      data: {
        receipt_id: 'RC20260325001',
        status: 'submitted',
        summary: '差旅申请已进入审批流程',
        submitted_at: '2026-03-20T10:00:00+08:00',
      },
    }
  }
  const { data } = await api.get<ApiResponse<FormReceipt>>(`/forms/${formId}/receipt`)
  return data
}

function delay(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

export type { FormData, FormReceipt, FormType }
