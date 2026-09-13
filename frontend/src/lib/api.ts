export class ApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.status = status
  }
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const hasJsonBody = Boolean(options.body) && !(options.body instanceof FormData)
  const response = await fetch(`/api${path}`, {
    ...options,
    credentials: 'include',
    headers: {
      ...(hasJsonBody ? { 'Content-Type': 'application/json' } : {}),
      ...options.headers,
    },
  })

  if (response.status === 204) {
    return undefined as T
  }

  const isJson = response.headers.get('content-type')?.includes('application/json')
  const data = isJson ? await response.json() : await response.text()
  if (!response.ok) {
    const detail = typeof data === 'object' && data?.detail ? data.detail : data
    const message = Array.isArray(detail)
      ? detail.map((item) => item.msg).join(', ')
      : String(detail || 'Something went wrong')
    if (response.status === 401) {
      window.dispatchEvent(new Event('ai-analytic-platform:unauthorized'))
    }
    throw new ApiError(message, response.status)
  }
  return data as T
}

export function queryString(values: Record<string, string | boolean | undefined>): string {
  const params = new URLSearchParams()
  Object.entries(values).forEach(([key, value]) => {
    if (value !== undefined && value !== '') params.set(key, String(value))
  })
  const query = params.toString()
  return query ? `?${query}` : ''
}
