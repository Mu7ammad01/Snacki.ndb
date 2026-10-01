/**
 * Jeton de suivi (T03). Il vit dans le fragment de l'URL (…/suivi#jeton) : le navigateur
 * n'envoie jamais le fragment au serveur, il n'apparaît donc dans aucun journal.
 * Le script de la page le lit, puis l'envoie à l'API dans l'en-tête X-Tracking-Token.
 */
const TOKEN = /^[A-Za-z0-9_-]{16,64}$/;

export function tokenFromHash(hash: string): string | null {
  const value = hash.startsWith("#") ? hash.slice(1) : hash;
  return TOKEN.test(value) ? value : null;
}

export const isToken = (value: string | null): value is string => !!value && TOKEN.test(value);

export const trackingPath = (token: string) => `/suivi#${token}`;
