import type { PlanEvent, PlanPayload, Poi, SessionInfo, Trip, TripSummary } from './types'

const API = '/api/v1'

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers || {})
  if (options.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  const res = await fetch(API + path, {
    ...options,
    headers,
    credentials: 'include',
  })
  if (!res.ok) {
    let message = `请求失败（${res.status}）`
    try {
      const data = await res.json()
      if (typeof data.detail === 'string') message = data.detail
      else if (Array.isArray(data.detail)) message = data.detail.map((x: any) => x.msg).join('；')
      else if (data.message) message = data.message
    } catch {
      // ignore
    }
    throw new Error(message)
  }
  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

export const api = {
  session: () => request<SessionInfo>('/session'),
  createPlan: (payload: PlanPayload) =>
    request<{ runId: string }>('/plan-runs', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  getTrip: (tripId: string) => request<Trip>(`/trips/${tripId}`),
  getRun: (runId: string) =>
    request<{ runId: string; status: string; stage: string; progress: number; tripId?: string | null; error?: string | null }>(
      `/plan-runs/${runId}`,
    ),
  listTrips: () => request<TripSummary[]>('/trips'),
  deleteTrip: (tripId: string) => request<{ ok: boolean }>(`/trips/${tripId}`, { method: 'DELETE' }),
  searchPoi: (city: string, keyword: string, type: string) =>
    request<{ items: Poi[] }>(
      `/poi/search?city=${encodeURIComponent(city)}&keyword=${encodeURIComponent(keyword)}&type=${type}`,
    ),
  addItem: (
    tripId: string,
    dayIndex: number,
    poi: Poi,
    afterItemId?: string,
  ) =>
    request<Trip>(`/trips/${tripId}/items`, {
      method: 'POST',
      body: JSON.stringify({ dayIndex, poi, afterItemId }),
    }),
  updateItem: (tripId: string, itemId: string, payload: Record<string, unknown>) =>
    request<Trip>(`/trips/${tripId}/items/${itemId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),
  deleteItem: (tripId: string, itemId: string) =>
    request<Trip>(`/trips/${tripId}/items/${itemId}`, { method: 'DELETE' }),
  reorderDay: (tripId: string, dayIndex: number, itemIds: string[]) =>
    request<Trip>(`/trips/${tripId}/days/${dayIndex}/order`, {
      method: 'PUT',
      body: JSON.stringify({ itemIds }),
    }),
  createExport: (tripId: string, format: 'pdf' | 'png') =>
    request<{ exportId: string; status: string; format: string; downloadUrl?: string | null; error?: string | null }>(
      `/trips/${tripId}/exports`,
      {
        method: 'POST',
        body: JSON.stringify({ format }),
      },
    ),
  getExport: (exportId: string) =>
    request<{ exportId: string; status: string; format: string; downloadUrl?: string | null; error?: string | null }>(
      `/exports/${exportId}`,
    ),
  downloadExport: (exportId: string) => `${API}/exports/${exportId}/download`,
}

export async function streamPlanRun(
  runId: string,
  onEvent: (event: PlanEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch(`${API}/plan-runs/${runId}/events`, {
    credentials: 'include',
    signal,
    headers: { Accept: 'text/event-stream' },
  })
  if (!res.ok || !res.body) {
    throw new Error(`无法连接规划进度（${res.status}）`)
  }
  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    let boundary = buffer.indexOf('\n\n')
    while (boundary >= 0) {
      const frame = buffer.slice(0, boundary)
      buffer = buffer.slice(boundary + 2)
      const dataLines = frame
        .split('\n')
        .filter((line) => line.startsWith('data:'))
        .map((line) => line.slice(5).trim())
      if (dataLines.length) {
        try {
          onEvent(JSON.parse(dataLines.join('\n')) as PlanEvent)
        } catch {
          // ignore malformed frame
        }
      }
      boundary = buffer.indexOf('\n\n')
    }
  }
}
