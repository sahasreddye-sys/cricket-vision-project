// Thin client for the PitchVision REST API. All requests go to /api on the same origin.
const TOKEN_KEY = 'pv-token'

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

export const getToken = () => {
  try { return localStorage.getItem(TOKEN_KEY) } catch { return null }
}
export const setToken = (t: string | null) => {
  try { t ? localStorage.setItem(TOKEN_KEY, t) : localStorage.removeItem(TOKEN_KEY) } catch { /* private mode */ }
}

function detail(body: any, status: number): string {
  const d = body?.detail
  if (typeof d === 'string') return d
  if (Array.isArray(d) && d.length) {
    // FastAPI validation errors: name the field and say what is wrong.
    return d.map((e: any) => {
      const field = (e.loc ?? []).filter((x: any) => x !== 'body' && x !== 'query').join(' ').replace(/_/g, ' ')
      return field ? `${field}: ${e.msg}` : e.msg
    }).join('. ')
  }
  if (status === 0) return 'Cannot reach the PitchVision server. Check that the backend is running.'
  return `Request failed (${status}).`
}

async function request<T>(method: string, path: string, body?: unknown, form?: FormData): Promise<T> {
  const headers: Record<string, string> = {}
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  let res: Response
  try {
    res = await fetch(`/api${path}`, { method, headers, body: form ?? (body !== undefined ? JSON.stringify(body) : undefined) })
  } catch {
    throw new ApiError(0, detail(null, 0))
  }
  if (res.status === 204) return undefined as T
  let data: any = null
  try { data = await res.json() } catch { /* empty or non-JSON body */ }
  if (!res.ok) {
    if (res.status === 401 && token) {
      setToken(null)
      window.dispatchEvent(new Event('pv-signed-out'))
    }
    throw new ApiError(res.status, detail(data, res.status))
  }
  return data as T
}

export const api = {
  get: <T = any>(path: string) => request<T>('GET', path),
  post: <T = any>(path: string, body?: unknown) => request<T>('POST', path, body ?? {}),
  put: <T = any>(path: string, body: unknown) => request<T>('PUT', path, body),
  patch: <T = any>(path: string, body: unknown) => request<T>('PATCH', path, body),
  del: <T = any>(path: string) => request<T>('DELETE', path),
  upload: <T = any>(path: string, form: FormData) => request<T>('POST', path, undefined, form),
}

export const qs = (params: Record<string, string | number | null | undefined>) => {
  const p = Object.entries(params).filter(([, v]) => v !== null && v !== undefined && v !== '')
  return p.length ? '?' + p.map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`).join('&') : ''
}
