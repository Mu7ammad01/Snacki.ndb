/**
 * Achats et stock (J16) : libellés, mise en forme et préparation de la saisie, testés sans serveur.
 * L'API refait toutes les vérifications et calcule elle-même le total : le web aide à la saisie.
 */
import type { PurchaseCategory, PurchaseRequest, StockUnit } from "@/lib/types";
import { oneLine } from "@/lib/validate";

export const CATEGORY_LABEL: Record<PurchaseCategory, string> = {
  ingredients: "Ingrédients",
  emballages: "Emballages",
  energie: "Énergie (gaz, eau, électricité)",
  entretien: "Entretien",
  materiel: "Matériel",
  autre: "Autre",
};

export const FREE_CATEGORIES = (Object.keys(CATEGORY_LABEL) as PurchaseCategory[]).filter((c) => c !== "ingredients");

export const UNIT_LABEL: Record<StockUnit, string> = { kg: "kg", l: "litres", piece: "pièces" };

export const VIEWS = { achats: "Achats", stock: "Stock", fournisseurs: "Fournisseurs" } as const;
export type View = keyof typeof VIEWS;

export function viewFrom(value: unknown): View {
  return typeof value === "string" && Object.hasOwn(VIEWS, value) ? (value as View) : "achats";
}

/** Quantité affichée à la française : 2,5 kg ; 12 pièces. */
export function qty(value: number, unit?: StockUnit): string {
  const text = value.toLocaleString("fr-FR", { maximumFractionDigits: 3 }).replace(/ | /g, " ");
  return unit ? `${text} ${UNIT_LABEL[unit]}` : text;
}

/** « 2,5 » ou « 2.5 » → 2.5 ; refus au-delà de 3 décimales, des valeurs nulles ou négatives. */
export function parseQty(raw: string): number | null {
  const text = raw.trim().replace(",", ".");
  if (!/^\d{1,6}(\.\d{1,3})?$/.test(text)) return null;
  const n = Number(text);
  return n > 0 && n <= 100000 ? n : null;
}

/** Montant en MRU : entier de 1 à 1 000 000 (espaces acceptés : « 1 200 »). */
export function parseAmount(raw: string): number | null {
  const text = raw.replace(/[\s  ]/g, "");
  if (!/^\d{1,7}$/.test(text)) return null;
  const n = Number(text);
  return n >= 1 && n <= 1_000_000 ? n : null;
}

/** Ligne du formulaire : un ingrédient suivi en stock, ou un libellé libre (gaz, gobelets…). */
export interface LineDraft {
  ingredientId: string; // "" : ligne libre
  label: string;
  category: PurchaseCategory;
  quantity: string;
  amount: string;
}

export const emptyLine = (): LineDraft => ({ ingredientId: "", label: "", category: "autre", quantity: "1", amount: "" });

export interface PurchaseDraft {
  day: string;
  supplierId: string;
  payment: PurchaseRequest["payment_method"];
  note: string;
  lines: LineDraft[];
}

/** Prépare la requête, ou renvoie le numéro (1, 2…) et le motif de la première ligne fautive. */
export function buildPurchase(d: PurchaseDraft): { ok: true; body: PurchaseRequest } | { ok: false; error: string } {
  if (d.lines.length === 0) return { ok: false, error: "Ajoutez au moins une ligne" };
  if (d.lines.length > 30) return { ok: false, error: "30 lignes au plus par achat" };
  const seen = new Set<string>();
  const lines: PurchaseRequest["lines"] = [];
  for (const [i, l] of d.lines.entries()) {
    const n = i + 1;
    const quantity = parseQty(l.quantity);
    const amount = parseAmount(l.amount);
    if (quantity === null) return { ok: false, error: `Ligne ${n} : quantité invalide` };
    if (amount === null) return { ok: false, error: `Ligne ${n} : montant invalide (MRU, sans décimale)` };
    if (l.ingredientId) {
      if (seen.has(l.ingredientId)) return { ok: false, error: `Ligne ${n} : ingrédient déjà présent, regroupez les quantités` };
      seen.add(l.ingredientId);
      lines.push({ ingredient_id: Number(l.ingredientId), quantity, amount_mru: amount });
    } else {
      const label = oneLine(l.label);
      if (label.length < 2 || label.length > 60) return { ok: false, error: `Ligne ${n} : libellé de 2 à 60 caractères` };
      lines.push({ label, category: l.category, quantity, amount_mru: amount });
    }
  }
  const note = oneLine(d.note).slice(0, 160);
  return {
    ok: true,
    body: {
      purchase_day: d.day,
      supplier_id: d.supplierId ? Number(d.supplierId) : null,
      payment_method: d.payment,
      ...(note ? { note } : {}),
      lines,
    },
  };
}

/** Total affiché pendant la saisie (l'API recalcule le sien). */
export function draftTotal(lines: LineDraft[]): number {
  return lines.reduce((s, l) => s + (parseAmount(l.amount) ?? 0), 0);
}
