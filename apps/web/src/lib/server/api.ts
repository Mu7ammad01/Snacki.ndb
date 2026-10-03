import "server-only";

import { createIdTokenProvider } from "@/lib/gcp-auth";

/**
 * Appels du serveur web vers l'API Python. Le navigateur ne parle jamais directement à l'API
 * (ADR 0001). Sur Cloud Run, l'API est privée : seul le compte de service du serveur web peut
 * l'appeler, en joignant son jeton d'identité Google (SNACKI_API_AUTH=gcp, ADR 0007).
 */
function apiUrl(): string {
  const url = process.env.SNACKI_API_URL;
  if (url) return url.replace(/\/+$/, "");
  if (process.env.NODE_ENV === "production") throw new Error("SNACKI_API_URL manquant");
  return "http://localhost:8000";
}

const idToken = createIdTokenProvider();

export async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const base = apiUrl();
  const headers: Record<string, string> = {
    Accept: "application/json",
    ...((init.headers as Record<string, string> | undefined) ?? {}),
  };
  // L'audience du jeton est l'adresse de l'API : un jeton volé ne vaut que pour ce service.
  if (process.env.SNACKI_API_AUTH === "gcp") headers.Authorization = `Bearer ${await idToken(base)}`;
  return fetch(base + path, {
    ...init,
    cache: "no-store",
    signal: AbortSignal.timeout(8000),
    headers,
  });
}
