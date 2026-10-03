/**
 * Jeton d'identité Google du serveur web, pour appeler l'API privée sur Cloud Run (J5, ADR 0007).
 *
 * Sur Cloud Run, chaque conteneur peut demander au serveur de métadonnées (joignable uniquement
 * depuis l'intérieur de Google) un jeton signé qui prouve « je suis le compte de service
 * snacki-web-… ». L'API refuse toute requête sans ce jeton (IAM Cloud Run) : aucune clé, aucun
 * mot de passe à stocker.
 *
 * Le jeton vit 1 h : on le garde 50 min en mémoire pour ne pas le redemander à chaque requête.
 * Il ne quitte jamais le serveur (ce module n'est importé que par lib/server/api.ts).
 */
const METADATA =
  "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/identity";
const TTL_MS = 50 * 60 * 1000;
const JWT = /^[\w-]+\.[\w-]+\.[\w-]+$/;

type Fetcher = (url: string, init: RequestInit) => Promise<Response>;

export function createIdTokenProvider(fetcher: Fetcher = fetch, now: () => number = Date.now) {
  const cache = new Map<string, { token: string; expires: number }>();
  return async function idToken(audience: string): Promise<string> {
    const hit = cache.get(audience);
    if (hit && hit.expires > now()) return hit.token;
    const r = await fetcher(`${METADATA}?audience=${encodeURIComponent(audience)}`, {
      headers: { "Metadata-Flavor": "Google" },
      cache: "no-store",
      signal: AbortSignal.timeout(2000),
    });
    if (!r.ok) throw new Error(`Jeton d'identité indisponible (HTTP ${r.status})`);
    const token = (await r.text()).trim();
    if (!JWT.test(token)) throw new Error("Jeton d'identité mal formé");
    cache.set(audience, { token, expires: now() + TTL_MS });
    return token;
  };
}
