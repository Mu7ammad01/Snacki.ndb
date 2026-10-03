import { NextResponse, type NextRequest } from "next/server";

import { clientIp } from "@/lib/forwarded";
import { apiFetch } from "@/lib/server/api";
import {
  FLOW_COOKIE,
  SESSION_COOKIE,
  SESSION_HOURS,
  callbackParams,
  cookieOptions,
  publicOrigin,
} from "@/lib/staff";

/**
 * Retour de Google. Le web transmet le code, le state et le jeton de parcours à l'API, qui
 * vérifie tout. Succès : cookie de session HttpOnly de 8 h, puis l'espace staff.
 * Échec, quel qu'il soit : même message, sans détail.
 */
export async function GET(request: NextRequest) {
  const origin = publicOrigin();
  const refused = () => {
    const out = NextResponse.redirect(new URL("/connexion?erreur=refusee", origin), 303);
    out.cookies.delete(FLOW_COOKIE);
    return out;
  };

  const params = callbackParams(request.nextUrl.searchParams);
  const flow = request.cookies.get(FLOW_COOKIE)?.value;
  if (!params || !flow) return refused();

  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const ip = clientIp(request.headers.get("x-forwarded-for"));
  if (ip) headers["X-Forwarded-For"] = ip;
  try {
    const r = await apiFetch("/v1/auth/callback", {
      method: "POST",
      headers,
      body: JSON.stringify({ ...params, flow }),
    });
    if (!r.ok) return refused();
    const { session } = (await r.json()) as { session: string };
    const out = NextResponse.redirect(new URL("/staff", origin), 303);
    out.cookies.delete(FLOW_COOKIE);
    out.cookies.set(SESSION_COOKIE, session, cookieOptions(SESSION_HOURS * 3600));
    out.headers.set("Cache-Control", "no-store");
    return out;
  } catch {
    return refused();
  }
}
