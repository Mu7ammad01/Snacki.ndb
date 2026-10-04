import type { NextConfig } from "next";

// En-têtes de sécurité sur toutes les réponses (la CSP, qui change à chaque requête, est posée
// par src/proxy.ts).
const securityHeaders = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "no-referrer" },
  { key: "Cross-Origin-Opener-Policy", value: "same-origin" },
  { key: "Strict-Transport-Security", value: "max-age=31536000; includeSubDomains" },
];

const NO_DEVICES = "camera=(), microphone=(), geolocation=(), payment=()";

const nextConfig: NextConfig = {
  poweredByHeader: false, // ne pas annoncer la technologie utilisée
  reactStrictMode: true,
  output: "standalone", // image Docker minimale à J5
  agentRules: false, // pas de fichiers AGENTS.md / CLAUDE.md générés par « next dev »
  async headers() {
    return [
      { source: "/:path*", headers: securityHeaders },
      // Caméra autorisée sur la seule page de la caisse (lecture du QR des cartes, J8 bis).
      { source: "/((?!caisse$).*)", headers: [{ key: "Permissions-Policy", value: NO_DEVICES }] },
      { source: "/caisse", headers: [{ key: "Permissions-Policy", value: "camera=(self), microphone=(), geolocation=(), payment=()" }] },
    ];
  },
};

export default nextConfig;
