import type { ApiResponse } from '@/types'
import api from './api'

export interface TicketCreatePayload {
  session_id?: string | null
  title: string
  description: string
}

export interface TicketPublic {
  id: string
  session_id: string | null
  title: string
  description: string
  status: string
  created_at: string
}

export interface TicketStatusPublic {
  id: string
  status: string
  title: string
  created_at: string
}

export async function createTicket(
  payload: TicketCreatePayload,
): Promise<ApiResponse<TicketPublic>> {
  const { data } = await api.post('/tickets', payload)
  return data
}

export async function fetchTicket(ticketId: string): Promise<ApiResponse<TicketStatusPublic>> {
  const { data } = await api.get(`/tickets/${ticketId}`)
  return data
}
