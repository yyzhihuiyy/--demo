export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string, public details: unknown = {}) {
    super(message)
  }
}

const TOKEN_KEY = 'live-training-token'
export const tokenStorage = {
  get: () => sessionStorage.getItem(TOKEN_KEY),
  set: (token: string) => sessionStorage.setItem(TOKEN_KEY, token),
  clear: () => sessionStorage.removeItem(TOKEN_KEY),
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers)
  if (options.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json')
  const token = tokenStorage.get()
  if (token) headers.set('Authorization', `Bearer ${token}`)
  let response: Response
  try {
    response = await fetch(`/api${path}`, { ...options, headers })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    throw new ApiError(0, 'NETWORK_ERROR', '无法连接服务，请确认服务已启动后重试')
  }
  const body = await response.json().catch(() => null)
  if (!response.ok) {
    if (response.status === 401) {
      tokenStorage.clear()
      window.dispatchEvent(new Event('auth-expired'))
    }
    throw new ApiError(response.status, body?.error?.code ?? 'HTTP_ERROR',
      body?.error?.message ?? `请求失败（${response.status}）`, body?.error?.details)
  }
  if (!body || !('data' in body)) throw new ApiError(502, 'INVALID_RESPONSE', '服务返回格式不正确')
  return body.data as T
}

export function mutation<T>(path: string, body?: unknown, method = 'POST', idempotencyKey?: string): Promise<T> {
  return api<T>(path, {
    method,
    body: body === undefined ? undefined : JSON.stringify(body),
    headers: idempotencyKey ? { 'Idempotency-Key': idempotencyKey } : {},
  })
}

export const requestKey = () => crypto.randomUUID()
export const errorMessage = (error: unknown) => error instanceof Error ? error.message : '操作失败，请重试'
