// Тонкая обёртка над fetch для запросов к /api.
// Все запросы идут через Vite-proxy (dev) или nginx (prod) на бэкенд.

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
    this.name = 'ApiError'
  }
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  // Для FormData не выставляем Content-Type — браузер сам проставит multipart boundary.
  const isForm = init?.body instanceof FormData
  const response = await fetch(`/api${path}`, {
    credentials: 'include',
    ...init,
    headers: {
      ...(isForm ? {} : { 'Content-Type': 'application/json' }),
      ...init?.headers,
    },
  })
  if (!response.ok) {
    const text = await response.text().catch(() => '')
    throw new ApiError(response.status, text || response.statusText)
  }
  if (response.status === 204) {
    return undefined as T
  }
  return (await response.json()) as T
}
