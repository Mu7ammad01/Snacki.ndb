import { NextResponse, type NextRequest } from "next/server";

import { canonicalRedirect } from "@/lib/canonical";
import { buildCsp, newNonce } from "@/lib/csp";

/** Chaque page reçoit un nonce neuf et la CSP qui l'autorise (menace T06). */
export function proxy(request: NextRequest) {
  // Ancienne adresse Cloud Run ou www : redirection permanente vers l'adresse publique (ADR 0012).
  const to = canonicalRedirect(
    request.headers.get("host"),
    request.nextUrl.pathname + request.nextUrl.search,
    process.env.SNACKI_PUBLIC_URL,
  );
  if (to) return NextResponse.redirect(to, 308);
  const nonce = newNonce();
  const csp = buildCsp(nonce, process.env.NODE_ENV === "development");
  const headers = new Headers(request.headers);
  headers.set("x-nonce", nonce);
  headers.set("Content-Security-Policy", csp);
  const response = NextResponse.next({ request: { headers } });
  response.headers.set("Content-Security-Policy", csp);
  return response;
}

export const config = {
  matcher: [
    {
      source: "/((?!api|_next/static|_next/image|img|fonts|icons|manifest.webmanifest).*)",
      missing: [
        { type: "header", key: "next-router-prefetch" },
        { type: "header", key: "purpose", value: "prefetch" },
      ],
    },
  ],
};
