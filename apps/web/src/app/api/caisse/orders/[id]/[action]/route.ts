import { NextResponse, type NextRequest } from "next/server";

import { isCaisseAction } from "@/lib/caisse";
import { relay, staffFetch } from "@/lib/server/staff";
import { isSameOrigin, publicOrigin } from "@/lib/staff";

const MAX_BODY = 1024;

/** Action sur une commande. Liste blanche des actions ; rôle et état sont vérifiés par l'API. */
export async function POST(request: NextRequest, ctx: { params: Promise<{ id: string; action: string }> }) {
  if (!isSameOrigin(request.headers.get("origin"), publicOrigin())) {
    return NextResponse.json({ detail: "Origine refusée" }, { status: 403 });
  }
  const { id, action } = await ctx.params;
  if (!/^[1-9][0-9]{0,8}$/.test(id) || !isCaisseAction(action))
    return NextResponse.json({ detail: "Action inconnue" }, { status: 404 });
  const body = await request.text();
  if (body.length > MAX_BODY) return NextResponse.json({ detail: "Requête trop grande" }, { status: 413 });
  if (body && !request.headers.get("content-type")?.startsWith("application/json"))
    return NextResponse.json({ detail: "JSON attendu" }, { status: 415 });
  try {
    return await relay(
      await staffFetch(`/v1/caisse/orders/${id}/${action}`, {
        method: "POST",
        ...(body ? { body, headers: { "Content-Type": "application/json" } } : {}),
      }),
    );
  } catch {
    return NextResponse.json({ detail: "Service momentanément indisponible" }, { status: 503 });
  }
}
