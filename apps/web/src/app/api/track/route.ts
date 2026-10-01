import { NextResponse, type NextRequest } from "next/server";

import { clientIp } from "@/lib/forwarded";
import { apiFetch } from "@/lib/server/api";
import { isToken } from "@/lib/token";

const NOT_FOUND = { detail: "Commande introuvable ou lien expiré" };

/** Relais vers GET /v1/orders/track. Le jeton arrive et repart dans un en-tête (T03). */
export async function GET(request: NextRequest) {
  const token = request.headers.get("x-tracking-token");
  if (!isToken(token)) return NextResponse.json(NOT_FOUND, { status: 404 });

  const headers: Record<string, string> = { "X-Tracking-Token": token };
  const ip = clientIp(request.headers.get("x-forwarded-for"));
  if (ip) headers["X-Forwarded-For"] = ip;

  try {
    const r = await apiFetch("/v1/orders/track", { headers });
    const out = NextResponse.json(await r.json(), { status: r.status });
    out.headers.set("Cache-Control", "no-store");
    return out;
  } catch {
    return NextResponse.json({ detail: "Service momentanément indisponible" }, { status: 503 });
  }
}
