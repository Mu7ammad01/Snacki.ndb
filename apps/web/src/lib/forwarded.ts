/**
 * Adresse du client, transmise à l'API pour sa limite de débit (T04).
 *
 * Le dernier élément de X-Forwarded-For est celui ajouté par le proxy le plus proche
 * (Codespaces, puis l'équilibreur de Google à J5) : c'est le seul fiable. Les éléments
 * précédents peuvent être inventés par le client. À vérifier sur Cloud Run à J5.
 */
const IP = /^[0-9a-fA-F:.]{2,45}$/;

export function clientIp(forwardedFor: string | null): string | null {
  if (!forwardedFor) return null;
  const last = forwardedFor.split(",").map((s) => s.trim()).filter(Boolean).pop();
  return last && IP.test(last) ? last : null;
}
