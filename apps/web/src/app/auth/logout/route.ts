import { NextResponse, type NextRequest } from "next/server";

import { staffFetch } from "@/lib/server/staff";
import { SESSION_COOKIE, isSameOrigin, publicOrigin } from "@/lib/staff";

/** Déconnexion (formulaire POST de ce site uniquement) : l'API révoque toutes les sessions du compte. */
export async function POST(request: NextRequest) {
  const origin = publicOrigin();
  if (!isSameOrigin(request.headers.get("origin"), origin)) {
    return NextResponse.json({ detail: "Origine refusée" }, { status: 403 });
  }
  try {
    await staffFetch("/v1/auth/logout", { method: "POST" });
  } catch {
    // Le cookie est supprimé quoi qu'il arrive.
  }
  const out = NextResponse.redirect(new URL("/connexion?deconnecte=1", origin), 303);
  out.cookies.delete(SESSION_COOKIE);
  // Le navigateur efface aussi son cache et le stockage de ce site (ASVS V14.3.1).
  out.headers.set("Clear-Site-Data", '"cache", "storage"');
  return out;
}
