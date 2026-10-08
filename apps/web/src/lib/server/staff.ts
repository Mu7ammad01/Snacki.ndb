import "server-only";

import { cookies, headers as requestHeaders } from "next/headers";
import { NextResponse } from "next/server";

import { clientIp } from "@/lib/forwarded";
import { apiFetch } from "@/lib/server/api";
import { SESSION_COOKIE, type StaffMe } from "@/lib/staff";

const SESSION = /^[A-Za-z0-9_.-]{20,2048}$/;

/** Jeton de session lu dans le cookie HttpOnly (jamais accessible au JavaScript de la page). */
export async function sessionToken(): Promise<string | null> {
  const value = (await cookies()).get(SESSION_COOKIE)?.value;
  return value && SESSION.test(value) ? value : null;
}

/** Appel à l'API au nom du membre connecté : la session voyage dans un en-tête, serveur à serveur. */
export async function staffFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const token = await sessionToken();
  if (!token) return new Response(JSON.stringify({ detail: "Session absente" }), { status: 401 });
  // Audit J13 (A1) : l'adresse du client accompagne la session, pour que chaque appareil ait sa
  // propre limite de débit dans l'API (assistant, fidélité, résumé).
  const ip = clientIp((await requestHeaders()).get("x-forwarded-for"));
  return apiFetch(path, {
    ...init,
    headers: {
      ...((init.headers as Record<string, string> | undefined) ?? {}),
      "X-Staff-Session": token,
      ...(ip ? { "X-Forwarded-For": ip } : {}),
    },
  });
}

/** Membre connecté, ou null si la session est absente, expirée ou révoquée. */
export async function currentStaff(): Promise<StaffMe | null> {
  try {
    const r = await staffFetch("/v1/staff/me");
    return r.ok ? ((await r.json()) as StaffMe) : null;
  } catch {
    return null;
  }
}

/** Renvoie au navigateur la réponse de l'API (statut et JSON), jamais mise en cache. */
export async function relay(r: Response): Promise<NextResponse> {
  const out = NextResponse.json(await r.json().catch(() => ({})), { status: r.status });
  out.headers.set("Cache-Control", "no-store");
  return out;
}
