import { NextResponse, type NextRequest } from "next/server";

import { clientIp } from "@/lib/forwarded";
import { apiFetch } from "@/lib/server/api";
import { FLOW_COOKIE, FLOW_MINUTES, cookieOptions, isGoogleAuthUrl, publicOrigin } from "@/lib/staff";

/**
 * « Se connecter avec Google » (un lien, pas un formulaire : la CSP limite les formulaires à ce
 * site). L'API prépare state, nonce et PKCE ; le web garde le jeton de parcours dans un cookie
 * HttpOnly de 10 minutes et envoie le navigateur chez Google.
 */
export async function GET(request: NextRequest) {
  const origin = publicOrigin();
  const headers: Record<string, string> = {};
  const ip = clientIp(request.headers.get("x-forwarded-for"));
  if (ip) headers["X-Forwarded-For"] = ip;
  try {
    const r = await apiFetch("/v1/auth/start", { method: "POST", headers });
    const body = (await r.json()) as { authorization_url?: unknown; flow?: unknown };
    if (!r.ok || !isGoogleAuthUrl(body.authorization_url) || typeof body.flow !== "string") {
      return NextResponse.redirect(new URL("/connexion?erreur=indisponible", origin), 303);
    }
    const out = NextResponse.redirect(body.authorization_url, 302);
    out.cookies.set(FLOW_COOKIE, body.flow, cookieOptions(FLOW_MINUTES * 60));
    out.headers.set("Cache-Control", "no-store");
    return out;
  } catch {
    return NextResponse.redirect(new URL("/connexion?erreur=indisponible", origin), 303);
  }
}
