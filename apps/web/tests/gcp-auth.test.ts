import { describe, expect, it, vi } from "vitest";

import { createIdTokenProvider } from "@/lib/gcp-auth";

const FAKE_JWT = "eyJhbGciOiJSUzI1NiJ9.eyJhdWQiOiJ4In0.c2lnbmF0dXJl"; // gitleaks:allow (faux jeton de test)
const API = "https://snacki-api-staging-123.us-central1.run.app";

function metadata(body = FAKE_JWT, status = 200) {
  return vi.fn(async (_url: string, _init: RequestInit) => new Response(body, { status }));
}

describe("API privée · jeton d'identité du serveur web (T01, T09)", () => {
  it("demande le jeton au serveur de métadonnées, pour l'adresse de l'API", async () => {
    const fetcher = metadata();
    const token = await createIdTokenProvider(fetcher)(API);
    expect(token).toBe(FAKE_JWT);
    const [url, init] = fetcher.mock.calls[0];
    expect(url).toMatch(/^http:\/\/metadata\.google\.internal\/computeMetadata\/v1\//);
    expect(new URL(url).searchParams.get("audience")).toBe(API);
    expect((init.headers as Record<string, string>)["Metadata-Flavor"]).toBe("Google");
  });

  it("garde le jeton 50 minutes, puis en redemande un", async () => {
    const fetcher = metadata();
    let t = 0;
    const idToken = createIdTokenProvider(fetcher, () => t);
    await idToken(API);
    t = 49 * 60_000;
    await idToken(API);
    expect(fetcher).toHaveBeenCalledTimes(1);
    t = 51 * 60_000;
    await idToken(API);
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it("refuse une réponse en erreur ou qui n'est pas un jeton", async () => {
    await expect(createIdTokenProvider(metadata("", 404))(API)).rejects.toThrow("HTTP 404");
    await expect(createIdTokenProvider(metadata("<html>"))(API)).rejects.toThrow("mal formé");
  });
});
