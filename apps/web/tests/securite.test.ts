import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { buildCsp, newNonce } from "@/lib/csp";
import { clientIp } from "@/lib/forwarded";
import { isToken, tokenFromHash, trackingPath } from "@/lib/token";

function sources(dir: string): string[] {
  return readdirSync(dir).flatMap((f) => {
    const p = join(dir, f);
    return statSync(p).isDirectory() ? sources(p) : /\.(ts|tsx)$/.test(p) ? [p] : [];
  });
}

describe("T06 · XSS", () => {
  it("aucun HTML brut injecté dans la page : React n'insère que du texte", () => {
    for (const file of sources("src")) {
      const code = readFileSync(file, "utf8");
      expect(code, file).not.toMatch(/dangerouslySetInnerHTML|\.innerHTML\s*=|outerHTML|insertAdjacentHTML|document\.write|\beval\(/);
    }
  });

  it("la CSP n'autorise que les scripts portant le nonce", () => {
    const csp = buildCsp("abc123", false);
    const script = csp.split("; ").find((d) => d.startsWith("script-src"))!;
    expect(script).toBe("script-src 'self' 'nonce-abc123' 'strict-dynamic'");
    expect(csp).not.toContain("unsafe-inline");
    expect(csp).not.toContain("unsafe-eval");
    expect(csp).toContain("frame-ancestors 'none'");
    expect(csp).toContain("object-src 'none'");
  });

  it("unsafe-eval n'existe qu'en développement", () => {
    expect(buildCsp("n", true)).toContain("'unsafe-eval'");
  });

  it("le nonce change à chaque requête et fait 128 bits", () => {
    const a = newNonce(), b = newNonce();
    expect(a).not.toBe(b);
    expect(Buffer.from(a, "base64")).toHaveLength(16);
  });
});

describe("T03 · jeton dans le fragment", () => {
  const token = "faux-jeton-de-test-0001"; // gitleaks:allow (faux jeton de test)

  it("le lien de suivi met le jeton après #", () => {
    expect(trackingPath(token)).toBe(`/suivi#${token}`);
    expect(tokenFromHash(`#${token}`)).toBe(token);
  });

  it.each(["", "#", "#court", "#<script>alert(1)</script>", "#a b c d e f g h i j", `#${"a".repeat(65)}`])(
    "un fragment invalide est ignoré : %s",
    (hash) => expect(tokenFromHash(hash)).toBeNull(),
  );

  it("isToken refuse l'absence de jeton", () => {
    expect(isToken(null)).toBe(false);
    expect(isToken(token)).toBe(true);
  });
});

describe("T04 · adresse du client transmise à l'API", () => {
  it("garde l'adresse ajoutée par le dernier proxy, pas celles inventées par le client", () => {
    expect(clientIp("6.6.6.6, 41.188.10.20")).toBe("41.188.10.20");
    expect(clientIp("41.188.10.20")).toBe("41.188.10.20");
    expect(clientIp("2001:db8::1")).toBe("2001:db8::1");
  });

  it.each([null, "", "pas une ip", "1.2.3.4, <script>"])("valeur inutilisable : %s", (v) => {
    expect(clientIp(v)).toBeNull();
  });
});
