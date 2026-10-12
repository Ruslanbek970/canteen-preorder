import { useAuthStore } from '@/features/auth/store';

export const API_BASE = '/api/v1';

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
    public readonly details: Record<string, unknown> = {},
  ) {
    super(message);
  }
}

interface ErrorBody {
  error?: { code: string; message: string; details?: Record<string, unknown> };
}

type Method = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';

let refreshing: Promise<boolean> | null = null;

/** Exchanges the refresh token for a new pair. Concurrent callers share one request. */
async function refreshTokens(): Promise<boolean> {
  const { refreshToken, setTokens, clear } = useAuthStore.getState();
  if (!refreshToken) return false;
  refreshing ??= (async () => {
    try {
      const resp = await fetch(`${API_BASE}/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });
      if (!resp.ok) {
        clear();
        return false;
      }
      const data = (await resp.json()) as { access_token: string; refresh_token: string };
      setTokens(data.access_token, data.refresh_token);
      return true;
    } catch {
      return false;
    } finally {
      refreshing = null;
    }
  })();
  return refreshing;
}

async function toError(resp: Response): Promise<ApiError> {
  const body = (await resp.json().catch(() => null)) as ErrorBody | null;
  return new ApiError(
    resp.status,
    body?.error?.code ?? 'http_error',
    body?.error?.message ?? resp.statusText,
    body?.error?.details ?? {},
  );
}

export async function apiRequest<T>(
  method: Method,
  path: string,
  body?: unknown,
  retry = true,
): Promise<T> {
  const token = useAuthStore.getState().accessToken;
  const headers: Record<string, string> = { Accept: 'application/json' };
  if (body !== undefined && !(body instanceof FormData))
    headers['Content-Type'] = 'application/json';
  if (token) headers.Authorization = `Bearer ${token}`;
  const resp = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : body instanceof FormData ? body : JSON.stringify(body),
  });
  if (resp.status === 401 && retry && token && (await refreshTokens())) {
    return apiRequest<T>(method, path, body, false);
  }
  if (!resp.ok) throw await toError(resp);
  if (resp.status === 204) return undefined as T;
  const type = resp.headers.get('content-type') ?? '';
  return (type.includes('application/json') ? await resp.json() : await resp.text()) as T;
}

export const apiGet = <T>(path: string) => apiRequest<T>('GET', path);
export const apiPost = <T>(path: string, body?: unknown) => apiRequest<T>('POST', path, body ?? {});
export const apiPut = <T>(path: string, body?: unknown) => apiRequest<T>('PUT', path, body ?? {});
export const apiPatch = <T>(path: string, body?: unknown) =>
  apiRequest<T>('PATCH', path, body ?? {});
export const apiDelete = <T>(path: string) => apiRequest<T>('DELETE', path);

/** Builds a query string, skipping empty values. */
export function qs(params: Record<string, string | number | boolean | null | undefined>): string {
  const search = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== '') search.set(k, String(v));
  }
  const s = search.toString();
  return s ? `?${s}` : '';
}
