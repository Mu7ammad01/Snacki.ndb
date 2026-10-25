import { NextResponse, type NextRequest } from "next/server";

import { byteLength } from "@/lib/validate";

import { relay, staffFetch } from "@/lib/server/staff";
import { isSameOrigin, publicOrigin } from "@/lib/staff";

const MAX_BODY = 1024;

/** J16 : ajouter un fournisseur. L'API vérifie la session et le rôle (gérante ou admin) à chaque appel. */
export async function POST(request: NextRequest) {
  if (!isSameOrigin(request.headers.get("origin"), publicOrigin())) {
    return NextResponse.json({ detail: "Origine refusée" }, { status: 403 });
  }
  if (!request.headers.get("content-type")?.startsWith("application/json"))
    return NextResponse.json({ detail: "JSON attendu" }, { status: 415 });
  const body = await request.text();
  if (byteLength(body) > MAX_BODY) return NextResponse.json({ detail: "Requête trop grande" }, { status: 413 });
  try {
    return await relay(
      await staffFetch("/v1/achats/fournisseurs", { method: "POST", body, headers: { "Content-Type": "application/json" } }),
    );
  } catch {
    return NextResponse.json({ detail: "Service momentanément indisponible" }, { status: 503 });
  }
}
