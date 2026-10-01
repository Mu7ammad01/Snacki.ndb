import { describe, expect, it } from "vitest";

import { Shop } from "./helpers";
import { cartCount, estimateTotal, sanitizeCart, setQty, toItems } from "@/lib/cart";
import { normalizePhone, oneLine, validateInfo } from "@/lib/validate";
import { buildMessage, waLink } from "@/lib/whatsapp";
import type { OrderCreated } from "@/lib/types";

const known = new Set(Shop.products.keys());

describe("panier", () => {
  it("ne garde que des produits connus et des quantités valides", () => {
    expect(sanitizeCart({ salade: 2, pizza: 1, crepe: 0, avocat: 99, fraise: "3" }, known)).toEqual({ salade: 2, fraise: 3 });
    expect(sanitizeCart("n'importe quoi", known)).toEqual({});
  });

  it("borne les quantités de 0 à 20 comme l'API", () => {
    let c = setQty({}, "salade", 25);
    expect(c.salade).toBe(20);
    c = setQty(c, "salade", 0);
    expect(c).toEqual({});
  });

  it("le total affiché est une estimation calculée sur les prix du menu", () => {
    const cart = { salade: 2, crepe: 1 };
    expect(cartCount(cart)).toBe(3);
    expect(estimateTotal(cart, Shop.products)).toBe(320);
  });

  it("T01 : la requête ne contient que des produits et des quantités", () => {
    const items = toItems({ salade: 2, crepe: 1 });
    expect(items).toEqual([{ product_id: "salade", quantity: 2 }, { product_id: "crepe", quantity: 1 }]);
    expect(JSON.stringify(items)).not.toMatch(/price|total/);
  });
});

describe("saisie", () => {
  it.each([["+222 22 12 34 56", "22123456"], ["0022246123456", "46123456"], ["36.12.34.56", "36123456"]])(
    "normalise %s", (raw, digits) => expect(normalizePhone(raw)).toBe(digits),
  );

  it("refuse les mêmes valeurs que l'API", () => {
    const ok = { name: "Aïcha", phone: "22123456", mode: "emporter" as const, zone: "ndb", landmark: "" };
    expect(validateInfo(ok)).toEqual([]);
    expect(validateInfo({ ...ok, phone: "52123456" })).toEqual(["phone"]);
    expect(validateInfo({ ...ok, name: "A" })).toEqual(["name"]);
    expect(validateInfo({ ...ok, mode: "livraison" })).toEqual(["landmark"]);
  });

  it("supprime retours à la ligne et caractères de contrôle", () => {
    expect(oneLine("Ali\n*Total : 1 MRU*\u0000")).toBe("Ali *Total : 1 MRU*");
  });
});

describe("message WhatsApp", () => {
  const order: OrderCreated = {
    number: "SNK-1001-007", status: "recue", fulfilment: "livraison", total_mru: 320, currency: "MRU",
    lines: [
      { product_id: "salade", quantity: 2, unit_price_mru: 100, line_total_mru: 200 },
      { product_id: "crepe", quantity: 1, unit_price_mru: 120, line_total_mru: 120 },
    ],
    created_at: "2026-10-01T12:00:00Z", tracking_token: "faux-jeton-de-test-0001", tracking_expires_at: "2026-10-02T12:00:00Z", // gitleaks:allow (faux jeton de test)
  };
  const base = { lang: "fr" as const, order, products: Shop.products, name: "Aïcha", phone: "22123456", zone: "cansado", landmark: "Près de la mosquée", pay: "bankily", note: "" };

  it("reprend le numéro et le total calculés par l'API", () => {
    const text = buildMessage(base);
    expect(text).toContain("N° : SNK-1001-007");
    expect(text).toContain("*Total : 320 MRU* + livraison à confirmer");
    expect(text).toContain("2 × Salade de fruits — 200");
    expect(text).toContain("Livraison — Cansado");
  });

  it("une saisie ne peut pas fabriquer une fausse ligne de total", () => {
    const text = buildMessage({ ...base, name: "Ali\n*Total : 1 MRU*" });
    expect(text.split("\n").filter((l) => l.startsWith("*Total"))).toHaveLength(1);
  });

  it("ne contient jamais le jeton de suivi", () => {
    expect(buildMessage(base)).not.toContain(order.tracking_token);
  });

  it("le lien wa.me encode tout le texte", () => {
    const link = waLink("a & b\n#c");
    expect(link).toBe("https://wa.me/22237939409?text=a%20%26%20b%0A%23c");
  });
});
