import { NextResponse, type NextRequest } from "next/server";

import { byteLength } from "@/lib/validate";

import { relay, staffFetch } from "@/lib/server/staff";
import { isSameOrigin, publicOrigin } from "@/lib/staff";

const MAX_BODY = 4096;
const unavailable = () => NextResponse.json({ detail: "Service momentanément indisponible" }, { status: 503 });

/** Commandes du jour (tout le staff). */
export async function GET() {
  try {
    return await relay(await staffFetch("/v1/caisse/orders"));
  } catch {
    return unavailable();
  }
}

/** Vente au comptoir : seuls les produits et quantités sont transmis, l'API fixe les prix. */
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
      await staffFetch("/v1/caisse/orders", { method: "POST", body, headers: { "Content-Type": "application/json" } }),
    );
  } catch {
    return unavailable();
  }
}
