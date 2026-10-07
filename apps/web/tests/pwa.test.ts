import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

/** J11 : le service worker ne met en cache que des fichiers publics, jamais une page ou l'API. */
const sw = readFileSync("public/sw.js", "utf8");
const STATIC = new RegExp(sw.match(/const STATIC = \/(.+)\/;/)![1]);

describe("service worker", () => {
  it("met en cache les fichiers publics versionnés", () => {
    for (const p of ["/_next/static/chunks/a1.js", "/img/salade.jpg", "/icons/icon-192.png", "/fonts/x.woff2"]) {
      expect(STATIC.test(p), p).toBe(true);
    }
  });

  it("ne met jamais en cache les pages, l'API ni la caisse", () => {
    for (const p of ["/", "/caisse", "/pilotage", "/suivi", "/api/caisse/orders", "/api/orders", "/carte", "/staff"]) {
      expect(STATIC.test(p), p).toBe(false);
    }
  });

  it("ignore les requêtes qui modifient et les autres sites", () => {
    expect(sw).toContain('if (request.method !== "GET") return;');
    expect(sw).toContain("if (url.origin !== self.location.origin) return;");
  });
});
