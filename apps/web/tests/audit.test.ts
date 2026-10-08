import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { byteLength } from "@/lib/validate";

/**
 * Audit J13 : règles vérifiées sur TOUTES les routes du serveur web, présentes et futures.
 * Une nouvelle route qui oublierait une protection fait échouer la CI.
 */
function routes(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return routes(path);
    return name === "route.ts" ? [path] : [];
  });
}

const ALL = routes("src/app").map((file) => ({ file, code: readFileSync(file, "utf8") }));
const WRITES = /export async function (POST|PUT|PATCH|DELETE)\b/;

describe("routes du serveur web", () => {
  it("en trouve au moins une dizaine (le test parcourt bien l'arborescence)", () => {
    expect(ALL.length).toBeGreaterThanOrEqual(10);
  });

  it("toute action du staff qui modifie vérifie l'origine (CSRF, T08)", () => {
    for (const { file, code } of ALL.filter((r) => WRITES.test(r.code) && r.code.includes("staffFetch"))) {
      expect(code, file).toContain("isSameOrigin(");
    }
  });

  it("toute route publique qui modifie exige du JSON (pas de formulaire d'un autre site)", () => {
    for (const { file, code } of ALL.filter((r) => WRITES.test(r.code) && !r.code.includes("staffFetch"))) {
      const guarded = code.includes("application/json") || code.includes("isSameOrigin(");
      expect(guarded, file).toBe(true);
    }
  });

  it("aucune route ne renvoie une réponse mise en cache par erreur", () => {
    for (const { file, code } of ALL.filter((r) => r.code.includes("NextResponse.json(await r.json()"))) {
      expect(code, file).toContain("no-store");
    }
  });

  it("aucune route ne lit un secret ou une URL d'API depuis la requête", () => {
    for (const { file, code } of ALL) {
      expect(code, file).not.toMatch(/searchParams\.get\(["'](url|redirect|next|api)["']\)/);
    }
  });

  it("la taille des requêtes se mesure en octets (audit J13, A3)", () => {
    expect(byteLength("abc")).toBe(3);
    expect(byteLength("عربي")).toBe(8);
    for (const { file, code } of ALL) {
      expect(code, file).not.toMatch(/body\.length\s*>/);
    }
  });
});
