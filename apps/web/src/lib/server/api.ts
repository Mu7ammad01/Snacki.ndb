import "server-only";

/**
 * Appels du serveur web vers l'API Python. Le navigateur ne parle jamais directement à l'API
 * (ADR 0001) : à J5, l'API ne sera joignable que par le compte de service du serveur web.
 */
function apiUrl(): string {
  const url = process.env.SNACKI_API_URL;
  if (url) return url.replace(/\/+$/, "");
  if (process.env.NODE_ENV === "production") throw new Error("SNACKI_API_URL manquant");
  return "http://localhost:8000";
}

export async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  return fetch(apiUrl() + path, {
    ...init,
    cache: "no-store",
    signal: AbortSignal.timeout(8000),
    headers: { Accept: "application/json", ...(init.headers ?? {}) },
  });
}
