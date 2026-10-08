import type { NextConfig } from "next";

// En-têtes de sécurité sur toutes les réponses (la CSP, qui change à chaque requête, est posée
// par src/proxy.ts).
const securityHeaders = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "no-referrer" },
  { key: "Cross-Origin-Opener-Policy", value: "same-origin" },
  { key: "Strict-Transport-Security", value: "max-age=31536000; includeSubDomains" },
  // Scan ZAP de J13 : aucune ressource d'un autre site n'est chargée, et aucun autre site ne
  // peut intégrer les nôtres.
  { key: "Cross-Origin-Embedder-Policy", value: "require-corp" },
  { key: "Cross-Origin-Resource-Policy", value: "same-origin" },
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
      // Le navigateur doit toujours vérifier la dernière version du service worker (J11).
      { source: "/sw.js", headers: [{ key: "Cache-Control", value: "no-cache" }] },
      // Caméra autorisée sur la seule page de la caisse (lecture du QR des cartes, J8 bis).
      { source: "/((?!caisse$).*)", headers: [{ key: "Permissions-Policy", value: NO_DEVICES }] },
      { source: "/caisse", headers: [{ key: "Permissions-Policy", value: "camera=(self), microphone=(), geolocation=(), payment=()" }] },
    ];
  },
};

export default nextConfig;
