import { NextResponse, type NextRequest } from "next/server";

import { clientIp } from "@/lib/forwarded";
import { apiFetch } from "@/lib/server/api";

const MAX_BODY = 4096; // une commande de 10 lignes fait moins de 1 Ko

/** Relais vers POST /v1/orders : le serveur web transmet, l'API valide et calcule. */
export async function POST(request: NextRequest) {
  if (!request.headers.get("content-type")?.startsWith("application/json"))
    return NextResponse.json({ detail: "JSON attendu" }, { status: 415 });
  const body = await request.text();
  if (body.length > MAX_BODY) return NextResponse.json({ detail: "Requête trop grande" }, { status: 413 });

  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const ip = clientIp(request.headers.get("x-forwarded-for"));
  if (ip) headers["X-Forwarded-For"] = ip;

  try {
    const r = await apiFetch("/v1/orders", { method: "POST", body, headers });
    const out = NextResponse.json(await r.json(), { status: r.status });
    const retry = r.headers.get("retry-after");
    if (retry) out.headers.set("Retry-After", retry);
    out.headers.set("Cache-Control", "no-store");
    return out;
  } catch {
    return NextResponse.json({ detail: "Service momentanément indisponible" }, { status: 503 });
  }
}
