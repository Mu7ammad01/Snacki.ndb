import { existsSync, readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

import { buildPurchase, draftTotal, emptyLine, parseAmount, parseQty, qty, viewFrom, type PurchaseDraft } from "@/lib/achats";

/** J16 : achats et stock (gérante et admin). */
const draft = (lines: PurchaseDraft["lines"]): PurchaseDraft => ({ day: "2026-10-25", supplierId: "3", payment: "cash", note: "", lines });

describe("saisie d'un achat", () => {
  it("lit les quantités à la française et refuse le reste", () => {
    expect(parseQty("2,5")).toBe(2.5);
    expect(parseQty(" 12 ")).toBe(12);
    expect(parseQty("0")).toBeNull();
    expect(parseQty("-1")).toBeNull();
    expect(parseQty("1.2345")).toBeNull();
    expect(parseQty("1e3")).toBeNull();
    expect(parseQty("100001")).toBeNull();
  });

  it("lit les montants en MRU entiers, espaces acceptés", () => {
    expect(parseAmount("1 200")).toBe(1200);
    expect(parseAmount("0")).toBeNull();
    expect(parseAmount("12,5")).toBeNull();
    expect(parseAmount("2000000")).toBeNull();
  });

  it("prépare la requête sans jamais envoyer de total", () => {
    const built = buildPurchase(draft([
      { ingredientId: "7", label: "", category: "autre", quantity: "2,5", amount: "750" },
      { ingredientId: "", label: "  Gaz\n bouteille ", category: "energie", quantity: "1", amount: "400" },
    ]));
    expect(built).toEqual({
      ok: true,
      body: {
        purchase_day: "2026-10-25",
        supplier_id: 3,
        payment_method: "cash",
        lines: [
          { ingredient_id: 7, quantity: 2.5, amount_mru: 750 },
          { label: "Gaz bouteille", category: "energie", quantity: 1, amount_mru: 400 },
        ],
      },
    });
    expect(JSON.stringify(built)).not.toContain("total");
  });

  it("signale la première ligne fautive", () => {
    expect(buildPurchase(draft([{ ...emptyLine(), label: "Gaz", amount: "abc" }]))).toEqual({ ok: false, error: "Ligne 1 : montant invalide (MRU, sans décimale)" });
    const twice = { ingredientId: "7", label: "", category: "autre" as const, quantity: "1", amount: "10" };
    expect(buildPurchase(draft([twice, twice]))).toMatchObject({ ok: false, error: expect.stringContaining("Ligne 2") });
    expect(buildPurchase(draft([{ ...emptyLine(), label: "x", amount: "10" }]))).toMatchObject({ ok: false });
    expect(buildPurchase(draft([]))).toMatchObject({ ok: false });
  });

  it("affiche le total pendant la saisie et les quantités lisibles", () => {
    expect(draftTotal([{ ...emptyLine(), amount: "750" }, { ...emptyLine(), amount: "oops" }])).toBe(750);
    expect(qty(2.5, "kg")).toBe("2,5 kg");
    expect(qty(12, "piece")).toBe("12 pièces");
  });

  it("n'accepte que les rubriques connues dans l'URL", () => {
    expect(viewFrom("stock")).toBe("stock");
    expect(viewFrom("constructor")).toBe("achats");
    expect(viewFrom(undefined)).toBe("achats");
  });
});

describe("routes des achats", () => {
  const routes = [
    "src/app/api/achats/route.ts",
    "src/app/api/achats/[id]/annuler/route.ts",
    "src/app/api/achats/fournisseurs/route.ts",
    "src/app/api/achats/fournisseurs/[id]/route.ts",
    "src/app/api/achats/ingredients/route.ts",
    "src/app/api/achats/ingredients/[id]/route.ts",
    "src/app/api/achats/ingredients/[id]/inventaire/route.ts",
  ];

  it("existent et passent par la session du staff, avec contrôle d'origine et de taille", () => {
    for (const file of routes) {
      expect(existsSync(file), file).toBe(true);
      const code = readFileSync(file, "utf8");
      expect(code, file).toContain("staffFetch(");
      expect(code, file).toContain("isSameOrigin(");
      expect(code, file).toContain("byteLength(body) > MAX_BODY");
    }
  });

  it("valident l'identifiant avant de l'insérer dans le chemin de l'API", () => {
    for (const file of routes.filter((f) => f.includes("[id]"))) {
      expect(readFileSync(file, "utf8"), file).toMatch(/\/\^\[1-9\]\[0-9\]\{0,8\}\$\/\.test\(id\)/);
    }
  });

  it("la page est réservée au staff connecté", () => {
    const page = readFileSync("src/app/achats/page.tsx", "utf8");
    expect(page).toContain('redirect("/connexion")');
    expect(page).toContain("index: false");
  });
});
