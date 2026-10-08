import { NextResponse, type NextRequest } from "next/server";

import { byteLength } from "@/lib/validate";

import { clientIp } from "@/lib/forwarded";
import { apiFetch } from "@/lib/server/api";
import { isSameOrigin, publicOrigin } from "@/lib/staff";

/** Le client suit sa carte (QR). Numéro dans le corps ; adresse réelle transmise pour la
 * limite de débit de l'API (T28 : essais de numéros au hasard). */
export async function POST(request: NextRequest) {
  if (!isSameOrigin(request.headers.get("origin"), publicOrigin())) {
    return NextResponse.json({ detail: "Origine refusée" }, { status: 403 });
  }
  const body = await request.text();
  if (byteLength(body) > 256) return NextResponse.json({ detail: "Requête trop grande" }, { status: 413 });
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const ip = clientIp(request.headers.get("x-forwarded-for"));
  if (ip) headers["X-Forwarded-For"] = ip;
  try {
    const r = await apiFetch("/v1/loyalty/status", { method: "POST", body, headers });
    const out = NextResponse.json(await r.json().catch(() => ({})), { status: r.status });
    out.headers.set("Cache-Control", "no-store");
    return out;
  } catch {
    return NextResponse.json({ detail: "Service momentanément indisponible" }, { status: 503 });
  }
}
