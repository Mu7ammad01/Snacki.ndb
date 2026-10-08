import { describe, expect, it } from "vitest";

import { arrivalText } from "@/lib/caisse";
import { PAYMENTS, WALLETS, isWallet } from "@/lib/i18n";
import { initialLang, phoneLang } from "@/lib/lang";

describe("réunion 5 · langue du téléphone (demande 5)", () => {
  it("suit la langue du téléphone", () => {
    expect(phoneLang(["ar-MR", "fr"])).toBe("ar");
    expect(phoneLang(["fr-FR"])).toBe("fr");
    expect(phoneLang(["en-US", "ar"])).toBe("fr");
    expect(phoneLang([])).toBe("fr");
    expect(phoneLang(undefined)).toBe("fr");
  });

  it("un choix fait dans l'app l'emporte ; une valeur inconnue est ignorée", () => {
    expect(initialLang("fr", ["ar"])).toBe("fr");
    expect(initialLang("ar", ["fr"])).toBe("ar");
    expect(initialLang("<script>", ["ar"])).toBe("ar");
    expect(initialLang(null, ["fr"])).toBe("fr");
  });
});

describe("réunion 5 · paiement (demande 7)", () => {
  it("Espèces à part, tous les autres moyens sont des wallets", () => {
    expect(WALLETS.map((w) => w.id)).toEqual(PAYMENTS.filter((p) => p.id !== "cash").map((p) => p.id));
    expect(isWallet("cash")).toBe(false);
    expect(isWallet("bankily")).toBe(true);
    expect(isWallet("autre")).toBe(false);
  });
});

describe("réunion 5 · notification de la caisse (demande 10)", () => {
  const o = (n: number) => ({ number: `SNK-${n}`, customer_name: `Client${n}`, grand_total_mru: 100 * n });

  it("affiche numéro, prénom et total", () => {
    expect(arrivalText([o(1)])).toBe("SNK-1 · Client1 · 100 MRU");
  });

  it("résume au-delà de 3 commandes", () => {
    const text = arrivalText([o(1), o(2), o(3), o(4), o(5)]);
    expect(text.split("\n")).toHaveLength(4);
    expect(text).toContain("+ 2 autre(s)");
  });
});
