/**
 * Adresse unique du site (J8 ter, ADR 0012).
 *
 * En production, le site répond sur snackindb.com, mais aussi sur son ancienne adresse Cloud Run
 * (…run.app), imprimée dans les QR des premières cartes de fidélité, et sur www. Ces deux adresses
 * renvoient vers l'adresse publique : une seule origine pour les cookies, la protection CSRF et la
 * connexion Google. Le fragment (#FID-…) est conservé par le navigateur lors de la redirection.
 *
 * La destination est toujours l'adresse publique configurée (SNACKI_PUBLIC_URL), jamais une
 * valeur tirée de la requête : pas de redirection ouverte.
 */
export function canonicalRedirect(
  host: string | null,
  pathAndQuery: string,
  publicUrl: string | undefined,
): string | null {
  if (!host || !publicUrl) return null;
  let target: URL;
  try {
    target = new URL(publicUrl);
  } catch {
    return null;
  }
  const h = host.toLowerCase().replace(/:\d+$/, "");
  if (h === target.hostname) return null;
  const alias = h.endsWith(".run.app") || h === `www.${target.hostname}`;
  if (!alias || !pathAndQuery.startsWith("/") || pathAndQuery.startsWith("//")) return null;
  return target.origin + pathAndQuery;
}
