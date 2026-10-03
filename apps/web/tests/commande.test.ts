import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

import { Shop } from "./helpers";
import { cartCount, estimateTotal, sanitizeCart, setQty, toItems } from "@/lib/cart";
import { normalizePhone, oneLine, validateInfo } from "@/lib/validate";
import { contactMessage, waLink } from "@/lib/whatsapp";

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

describe("WhatsApp : simple lien de contact (J7)", () => {
  it("le message prérempli contient seulement le numéro de commande", () => {
    expect(contactMessage("fr", "SNK-1001-007")).toBe("Bonjour Snacki, à propos de ma commande SNK-1001-007 :");
    expect(contactMessage("ar", "SNK-1001-007")).toContain("SNK-1001-007");
  });

  it("un numéro mal formé n'est jamais recopié", () => {
    expect(contactMessage("fr", "SNK-1\n*Total : 1 MRU*")).not.toContain("Total");
  });

  it("le lien wa.me encode tout le texte", () => {
    const link = waLink("a & b\n#c");
    expect(link).toBe("https://wa.me/22237939409?text=a%20%26%20b%0A%23c");
  });

  it("la commande n'est plus envoyée par WhatsApp", () => {
    const shop = readFileSync("src/components/Shop.tsx", "utf8");
    expect(shop).not.toMatch(/buildMessage|sendWa/);
  });
});

describe("contacts affichés", () => {
  it("seul WhatsApp est proposé, plus de numéro d'appel", () => {
    const shop = readFileSync("src/components/Shop.tsx", "utf8");
    expect(shop).not.toMatch(/CONTACT\.call|callLabel/);
  });
});
