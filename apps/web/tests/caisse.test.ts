import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

import { actionsFor, cardFrom, columnOf, isCaisseAction, newArrivals, parseFee, telLink } from "@/lib/caisse";
import type { CaisseOrder } from "@/lib/types";

const order = (over: Partial<CaisseOrder> = {}): CaisseOrder => ({
  id: 1, number: "SNK-1003-001", status: "recue", fulfilment: "emporter", total_mru: 320, delivery_fee_mru: 0,
  grand_total_mru: 320, currency: "MRU", lines: [], created_at: "2026-10-03T12:00:00Z", ready_at: null,
  closed_reason: null, source: "app", customer_name: "Aïcha", phone: "22123456", landmark: null, note: null,
  pay_pref: null, accepted_at: null, customer_called_at: null, paid_method: null, paid_at: null, ...over,
});
const kinds = (o: CaisseOrder, role: "caissier" | "gerante" | "admin") => actionsFor(o, role).map((a) => a.kind);

describe("caisse · boutons selon l'état et le rôle", () => {
  it("le caissier accepte mais ne refuse pas ; la gérante peut refuser", () => {
    expect(kinds(order(), "caissier")).toEqual(["accept"]);
    expect(kinds(order(), "gerante")).toEqual(["accept", "refuse"]);
    expect(kinds(order(), "admin")).toEqual(["accept", "refuse"]);
  });

  it("annuler une commande en cours : gérante ou admin seulement", () => {
    const o = order({ status: "en_preparation" });
    expect(kinds(o, "caissier")).not.toContain("cancel");
    expect(kinds(o, "gerante")).toContain("cancel");
  });

  it("livraison : « Remise » bloquée tant que le client n'est pas appelé", () => {
    const o = order({ status: "prete", fulfilment: "livraison" });
    const adv = actionsFor(o, "caissier").find((a) => a.kind === "advance");
    expect(adv).toMatchObject({ to: "livree", blocked: expect.any(String) });
    expect(kinds(o, "caissier")).toContain("called");
    const called = actionsFor({ ...o, customer_called_at: "2026-10-03T12:20:00Z" }, "caissier");
    expect(called.find((a) => a.kind === "advance")).not.toHaveProperty("blocked");
  });

  it("encaissement proposé une seule fois, jamais sur une commande refusée", () => {
    expect(kinds(order({ status: "acceptee" }), "caissier")).toContain("pay");
    expect(kinds(order({ status: "acceptee", paid_at: "x" }), "caissier")).not.toContain("pay");
    expect(kinds(order({ status: "refusee" }), "gerante")).toEqual([]);
  });

  it("colonnes : à accepter, en cours, terminées", () => {
    expect(columnOf("recue")).toBe("todo");
    expect(columnOf("prete")).toBe("doing");
    expect(["livree", "refusee", "annulee"].map((s) => columnOf(s as CaisseOrder["status"]))).toEqual(["done", "done", "done"]);
  });

  it("son et notification seulement pour les nouvelles commandes reçues", () => {
    const list = [order({ id: 1 }), order({ id: 2 }), order({ id: 3, status: "acceptee" })];
    expect(newArrivals(new Set([1]), list)).toEqual([2]);
  });
});

describe("caisse · saisies", () => {
  it.each([["50", 50], [" 0 ", 0], ["2000", 2000], ["2001", null], ["-5", null], ["5.5", null], ["", null]])(
    "frais %j → %j", (raw, value) => expect(parseFee(raw)).toBe(value),
  );

  it("lien d'appel seulement pour un numéro mauritanien valide", () => {
    expect(telLink("22123456")).toBe("tel:+22222123456");
    expect(telLink("javascript:alert(1)")).toBeNull();
    expect(telLink(null)).toBeNull();
  });
});

describe("caisse · relais web", () => {
  it("liste blanche des actions relayées vers l'API", () => {
    for (const a of ["accept", "status", "called", "pay", "refuse", "cancel", "loyalty", "reward"]) expect(isCaisseAction(a)).toBe(true);
    for (const a of ["../staff", "delete", "", "accept/../../staff"]) expect(isCaisseAction(a)).toBe(false);
  });

  it("le relais vérifie l'origine et l'identifiant avant d'appeler l'API", () => {
    const src = readFileSync("src/app/api/caisse/orders/[id]/[action]/route.ts", "utf8");
    expect(src).toMatch(/isSameOrigin/);
    expect(src).toMatch(/isCaisseAction/);
    expect(src).toMatch(/\^\[1-9\]\[0-9\]\{0,8\}\$/);
  });

  it("la caisse ne range aucun jeton dans le navigateur", () => {
    const board = readFileSync("src/components/CaisseBoard.tsx", "utf8");
    expect(board).not.toMatch(/localStorage|sessionStorage|document\.cookie/);
  });
});

describe("caisse · fidélité", () => {
  it("tampon après l'encaissement, cadeau avant, une seule carte par commande", () => {
    expect(kinds(order({ status: "acceptee" }), "caissier")).toContain("reward");
    expect(kinds(order({ status: "acceptee" }), "caissier")).not.toContain("stamp");
    expect(kinds(order({ status: "acceptee", paid_at: "x" }), "caissier")).toContain("stamp");
    expect(kinds(order({ status: "acceptee", paid_at: "x", loyalty_card_id: 3 }), "caissier")).not.toContain("stamp");
    expect(kinds(order({ status: "acceptee", discount_mru: 100 }), "caissier")).not.toContain("reward");
    expect(kinds(order({ status: "annulee", paid_at: "x" }), "gerante")).toEqual([]);
  });

  it("numéro lu dans le QR ou saisi, mis en forme", () => {
    expect(cardFrom("https://snacki.test/carte#FID-7KQ2-M9XA")).toBe("FID-7KQ2-M9XA");
    expect(cardFrom("fid 7kq2 m9xa")).toBe("FID-7KQ2-M9XA");
    expect(cardFrom("7KQ2M9XA")).toBe("FID-7KQ2-M9XA");
    for (const bad of ["", "FID-123", "javascript:alert(1)", "<img src=x>"]) expect(cardFrom(bad)).toBeNull();
  });

  it("caméra permise sur la seule page de la caisse", () => {
    const cfg = readFileSync("next.config.ts", "utf8");
    expect(cfg).toMatch(/source: "\/caisse", headers: \[\{ key: "Permissions-Policy", value: "camera=\(self\)/);
    expect(cfg).toMatch(/NO_DEVICES = "camera=\(\)/);
  });

  it("aucune image de la caméra n'est envoyée : lecture du QR dans le téléphone", () => {
    const scanner = readFileSync("src/components/QrScanner.tsx", "utf8");
    expect(scanner).not.toMatch(/fetch\(|XMLHttpRequest|toDataURL/);
  });
});
