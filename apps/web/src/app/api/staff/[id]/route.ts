import { NextResponse, type NextRequest } from "next/server";

import { relay, staffFetch } from "@/lib/server/staff";
import { isSameOrigin, publicOrigin } from "@/lib/staff";

const MAX_BODY = 1024;

/** Changer le rôle d'un membre ou le désactiver (admin seulement, vérifié par l'API). */
export async function PATCH(request: NextRequest, ctx: { params: Promise<{ id: string }> }) {
  if (!isSameOrigin(request.headers.get("origin"), publicOrigin())) {
    return NextResponse.json({ detail: "Origine refusée" }, { status: 403 });
  }
  const { id } = await ctx.params;
  if (!/^[1-9][0-9]{0,8}$/.test(id)) return NextResponse.json({ detail: "Membre introuvable" }, { status: 404 });
  if (!request.headers.get("content-type")?.startsWith("application/json"))
    return NextResponse.json({ detail: "JSON attendu" }, { status: 415 });
  const body = await request.text();
  if (body.length > MAX_BODY) return NextResponse.json({ detail: "Requête trop grande" }, { status: 413 });
  try {
    return await relay(
      await staffFetch(`/v1/staff/${id}`, { method: "PATCH", body, headers: { "Content-Type": "application/json" } }),
    );
  } catch {
    return NextResponse.json({ detail: "Service momentanément indisponible" }, { status: 503 });
  }
}
