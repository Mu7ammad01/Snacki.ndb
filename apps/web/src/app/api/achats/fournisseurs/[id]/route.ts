import { NextResponse, type NextRequest } from "next/server";

import { byteLength } from "@/lib/validate";

import { relay, staffFetch } from "@/lib/server/staff";
import { isSameOrigin, publicOrigin } from "@/lib/staff";

const MAX_BODY = 1024;

/** J16 : modifier ou désactiver un fournisseur. L'API vérifie la session et le rôle (gérante ou admin) à chaque appel. */
export async function PATCH(request: NextRequest, ctx: { params: Promise<{ id: string }> }) {
  if (!isSameOrigin(request.headers.get("origin"), publicOrigin())) {
    return NextResponse.json({ detail: "Origine refusée" }, { status: 403 });
  }
  const { id } = await ctx.params;
  if (!/^[1-9][0-9]{0,8}$/.test(id)) return NextResponse.json({ detail: "Fournisseur introuvable" }, { status: 404 });
  if (!request.headers.get("content-type")?.startsWith("application/json"))
    return NextResponse.json({ detail: "JSON attendu" }, { status: 415 });
  const body = await request.text();
  if (byteLength(body) > MAX_BODY) return NextResponse.json({ detail: "Requête trop grande" }, { status: 413 });
  try {
    return await relay(
      await staffFetch(`/v1/achats/fournisseurs/${id}`, { method: "PATCH", body, headers: { "Content-Type": "application/json" } }),
    );
  } catch {
    return NextResponse.json({ detail: "Service momentanément indisponible" }, { status: 503 });
  }
}
