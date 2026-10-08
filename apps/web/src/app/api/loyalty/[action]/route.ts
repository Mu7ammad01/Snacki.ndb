import { NextResponse, type NextRequest } from "next/server";

import { byteLength } from "@/lib/validate";

import { relay, staffFetch } from "@/lib/server/staff";
import { isSameOrigin, publicOrigin } from "@/lib/staff";

const MAX_BODY = 512;
// Liste blanche : seules ces actions de la gérante sont relayées (l'API vérifie le rôle).
const ACTIONS = new Set(["block", "transfer", "search"]);

export async function POST(request: NextRequest, ctx: { params: Promise<{ action: string }> }) {
  if (!isSameOrigin(request.headers.get("origin"), publicOrigin())) {
    return NextResponse.json({ detail: "Origine refusée" }, { status: 403 });
  }
  const { action } = await ctx.params;
  if (!ACTIONS.has(action)) return NextResponse.json({ detail: "Action inconnue" }, { status: 404 });
  const body = await request.text();
  if (byteLength(body) > MAX_BODY) return NextResponse.json({ detail: "Requête trop grande" }, { status: 413 });
  try {
    return await relay(
      await staffFetch(`/v1/loyalty/${action}`, { method: "POST", body, headers: { "Content-Type": "application/json" } }),
    );
  } catch {
    return NextResponse.json({ detail: "Service momentanément indisponible" }, { status: 503 });
  }
}
