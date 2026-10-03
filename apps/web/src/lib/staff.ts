/**
 * Connexion du staff côté web (J6, ADR 0008) : règles pures, testées sans serveur.
 *
 * Le web ne décide de rien : il range deux jetons signés par l'API dans des cookies que le
 * JavaScript de la page ne peut pas lire (HttpOnly), et refuse les requêtes venues d'un autre site.
 */

export type Role = "caissier" | "gerante" | "admin";
export type StaffMe = { id: number; email: string; display_name: string | null; role: Role };
export type StaffMember = StaffMe & { active: boolean; last_login_at: string | null };

// Préfixe __Host- : le navigateur n'accepte le cookie que s'il est Secure, posé par ce site
// exactement (pas de Domain) et valable pour tout le site (Path=/). Un sous-domaine ne peut pas
// l'écraser.
export const SESSION_COOKIE = "__Host-snacki_session";
export const FLOW_COOKIE = "__Host-snacki_oauth";
export const SESSION_HOURS = 8;
export const FLOW_MINUTES = 10;

export type CookieOptions = {
  httpOnly: true;
  secure: true;
  sameSite: "lax";
  path: "/";
  maxAge: number;
};

/**
 * Lax plutôt que Strict : au retour de Google (navigation venue d'un autre site), le cookie de
 * parcours doit être envoyé, et la session posée doit l'être sur la page suivante. Les requêtes
 * qui modifient quelque chose sont en plus protégées par la vérification d'origine (T08).
 */
export function cookieOptions(maxAgeSeconds: number): CookieOptions {
  return { httpOnly: true, secure: true, sameSite: "lax", path: "/", maxAge: maxAgeSeconds };
}

export const ROLE_LABEL: Record<Role, string> = {
  caissier: "Caissier",
  gerante: "Gérante",
  admin: "Administrateur",
};

/** Adresse publique du site (jamais déduite de l'en-tête Host, qui peut être forgé). */
export function publicOrigin(env: string | undefined = process.env.SNACKI_PUBLIC_URL): string {
  if (env) return new URL(env).origin;
  if (process.env.NODE_ENV === "production") throw new Error("SNACKI_PUBLIC_URL manquant");
  return "http://localhost:3000";
}

/**
 * Protection CSRF (T08) : une requête qui modifie quelque chose doit venir de ce site.
 * Le navigateur pose Origin lui-même ; une page malveillante ne peut pas le falsifier.
 */
export function isSameOrigin(origin: string | null, expected: string): boolean {
  if (!origin) return false;
  try {
    return new URL(origin).origin === expected;
  } catch {
    return false;
  }
}

/** On ne redirige que vers la page d'autorisation de Google (pas de redirection ouverte). */
export function isGoogleAuthUrl(url: unknown): url is string {
  return typeof url === "string" && url.startsWith("https://accounts.google.com/o/oauth2/v2/auth?");
}

const CODE = /^[\x21-\x7e]{10,512}$/;
const STATE = /^[A-Za-z0-9_-]{16,64}$/;

/** Paramètres de retour de Google, validés avant tout appel à l'API. */
export function callbackParams(search: URLSearchParams): { code: string; state: string } | null {
  const code = search.get("code");
  const state = search.get("state");
  if (!code || !state || !CODE.test(code) || !STATE.test(state)) return null;
  return { code, state };
}

/** Ce que chaque rôle voit sur l'espace staff (le contrôle réel est fait par l'API). */
export function sectionsFor(role: Role): { caisse: boolean; pilotage: boolean; equipe: boolean } {
  return { caisse: true, pilotage: role !== "caissier", equipe: role === "admin" };
}
