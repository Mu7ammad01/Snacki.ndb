import { NextResponse, type NextRequest } from "next/server";

import { relay, staffFetch } from "@/lib/server/staff";
import { isSameOrigin, publicOrigin } from "@/lib/staff";

const MAX_BODY = 512;

/** État d'une carte pour la caisse : le numéro passe dans le corps, jamais dans l'URL. */
export async function POST(request: NextRequest) {
  if (!isSameOrigin(request.headers.get("origin"), publicOrigin())) {
    return NextResponse.json({ detail: "Origine refusée" }, { status: 403 });
  }
  const body = await request.text();
  if (body.length > MAX_BODY) return NextResponse.json({ detail: "Requête trop grande" }, { status: 413 });
  try {
    return await relay(
      await staffFetch("/v1/caisse/loyalty", { method: "POST", body, headers: { "Content-Type": "application/json" } }),
    );
  } catch {
    return NextResponse.json({ detail: "Service momentanément indisponible" }, { status: 503 });
  }
}
