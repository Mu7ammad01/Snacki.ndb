import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

import {
  FLOW_COOKIE,
  SESSION_COOKIE,
  callbackParams,
  cookieOptions,
  isGoogleAuthUrl,
  isSameOrigin,
  publicOrigin,
  sectionsFor,
} from "@/lib/staff";

const SITE = "https://snacki-web-prod-57h4g6dvma-uc.a.run.app";

describe("T07 · cookies de session", () => {
  it("HttpOnly, Secure, SameSite=Lax, tout le site, préfixe __Host-", () => {
    expect(cookieOptions(3600)).toEqual({ httpOnly: true, secure: true, sameSite: "lax", path: "/", maxAge: 3600 });
    expect(SESSION_COOKIE.startsWith("__Host-")).toBe(true);
    expect(FLOW_COOKIE.startsWith("__Host-")).toBe(true);
  });

  it("aucun jeton du staff n'est rangé dans le navigateur par du JavaScript", () => {
    const team = readFileSync("src/components/TeamAdmin.tsx", "utf8");
    expect(team).not.toMatch(/localStorage|sessionStorage|document\.cookie/);
  });
});

describe("T08 · CSRF : vérification de l'origine", () => {
  it("accepte seulement ce site", () => {
    expect(isSameOrigin(SITE, SITE)).toBe(true);
    expect(isSameOrigin(`${SITE}/`, SITE)).toBe(true);
  });

  it.each([
    null,
    "",
    "null",
    "https://evil.example",
    "http://snacki-web-prod-57h4g6dvma-uc.a.run.app",
    "https://snacki-web-prod-57h4g6dvma-uc.a.run.app.evil.example",
    "https://snacki-web-staging-57h4g6dvma-uc.a.run.app",
  ])("refuse %s", (origin) => {
    expect(isSameOrigin(origin, SITE)).toBe(false);
  });

  it("l'adresse publique vient de la configuration, pas de l'en-tête Host", () => {
    expect(publicOrigin(`${SITE}/chemin`)).toBe(SITE);
  });
});

describe("T10 · parcours OAuth", () => {
  it("ne redirige que vers la page d'autorisation de Google", () => {
    expect(isGoogleAuthUrl("https://accounts.google.com/o/oauth2/v2/auth?client_id=x")).toBe(true);
    for (const bad of [
      "https://accounts.google.com.evil.example/o/oauth2/v2/auth?x",
      "http://accounts.google.com/o/oauth2/v2/auth?x",
      "https://evil.example/?https://accounts.google.com/o/oauth2/v2/auth?",
      "javascript:alert(1)",
      42,
    ]) expect(isGoogleAuthUrl(bad)).toBe(false);
  });

  it("valide le code et le state avant tout appel", () => {
    const ok = new URLSearchParams({ code: "4/0AbCdEfGhIjK", state: "A".repeat(32) });
    expect(callbackParams(ok)).toEqual({ code: "4/0AbCdEfGhIjK", state: "A".repeat(32) });
    expect(callbackParams(new URLSearchParams({ error: "access_denied" }))).toBeNull();
    expect(callbackParams(new URLSearchParams({ code: "court", state: "A".repeat(32) }))).toBeNull();
    expect(callbackParams(new URLSearchParams({ code: "4/0AbCdEfGhIjK", state: "<script>" }))).toBeNull();
  });
});

describe("T09 · ce que chaque rôle voit", () => {
  it("le caissier ne voit ni le pilotage ni l'équipe ; la gérante pas l'équipe", () => {
    expect(sectionsFor("caissier")).toEqual({ caisse: true, pilotage: false, equipe: false });
    expect(sectionsFor("gerante")).toEqual({ caisse: true, pilotage: true, equipe: false });
    expect(sectionsFor("admin")).toEqual({ caisse: true, pilotage: true, equipe: true });
  });
});
