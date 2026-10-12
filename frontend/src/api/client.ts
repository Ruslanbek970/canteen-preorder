export const API_BASE = '/api/v1';

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
  ) {
    super(message);
  }
}

export async function apiGet<T>(path: string): Promise<T> {
  const resp = await fetch(`${API_BASE}${path}`, { headers: { Accept: 'application/json' } });
  if (!resp.ok) {
    const body = (await resp.json().catch(() => null)) as {
      error?: { code: string; message: string };
    } | null;
    throw new ApiError(
      resp.status,
      body?.error?.code ?? 'http_error',
      body?.error?.message ?? resp.statusText,
    );
  }
  return (await resp.json()) as T;
}
