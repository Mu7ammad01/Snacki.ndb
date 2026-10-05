import { describe, expect, it } from "vitest";

import { canonicalRedirect } from "@/lib/canonical";

const PUBLIC = "https://snackindb.com";
const RUN = "snacki-web-prod-57h4g6dvma-uc.a.run.app";

describe("ADR 0012 · une seule adresse publique", () => {
  it("l'ancienne adresse Cloud Run renvoie vers le domaine, chemin et paramètres compris", () => {
    expect(canonicalRedirect(RUN, "/carte", PUBLIC)).toBe("https://snackindb.com/carte");
    expect(canonicalRedirect(RUN, "/suivi?n=SNK-1", PUBLIC)).toBe("https://snackindb.com/suivi?n=SNK-1");
    expect(canonicalRedirect("www.snackindb.com", "/", PUBLIC)).toBe("https://snackindb.com/");
  });

  it("pas de redirection sur le domaine lui-même, ni en staging (adresse run.app)", () => {
    expect(canonicalRedirect("snackindb.com", "/", PUBLIC)).toBeNull();
    expect(canonicalRedirect("SNACKINDB.COM:443", "/", PUBLIC)).toBeNull();
    const staging = "snacki-web-staging-57h4g6dvma-uc.a.run.app";
    expect(canonicalRedirect(staging, "/", `https://${staging}`)).toBeNull();
    expect(canonicalRedirect(RUN, "/", undefined)).toBeNull();
  });

  it("aucune redirection ouverte : hôte inconnu ou chemin vers un autre site", () => {
    expect(canonicalRedirect("evil.example", "/", PUBLIC)).toBeNull();
    expect(canonicalRedirect("snackindb.com.evil.example", "/", PUBLIC)).toBeNull();
    expect(canonicalRedirect(RUN, "//evil.example/x", PUBLIC)).toBeNull();
    expect(canonicalRedirect(RUN, "https://evil.example", PUBLIC)).toBeNull();
  });
});
