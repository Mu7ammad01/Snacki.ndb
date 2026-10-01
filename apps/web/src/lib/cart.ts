import type { Product } from "./types";

export type Cart = Record<string, number>;
export const MAX_QTY = 20; // même limite que l'API (1 à 20 par produit)
export const MAX_LINES = 10;

/** Panier relu depuis localStorage : on ne garde que des produits connus et des quantités valides. */
export function sanitizeCart(raw: unknown, known: ReadonlySet<string>): Cart {
  const out: Cart = {};
  if (!raw || typeof raw !== "object") return out;
  for (const [id, value] of Object.entries(raw as Record<string, unknown>)) {
    const q = Math.floor(Number(value));
    if (known.has(id) && q >= 1 && q <= MAX_QTY && Object.keys(out).length < MAX_LINES) out[id] = q;
  }
  return out;
}

export function setQty(cart: Cart, id: string, qty: number): Cart {
  const next = { ...cart };
  const q = Math.max(0, Math.min(MAX_QTY, Math.floor(qty)));
  if (q === 0) delete next[id];
  else if (id in next || Object.keys(next).length < MAX_LINES) next[id] = q;
  return next;
}

export const cartCount = (cart: Cart) => Object.values(cart).reduce((a, b) => a + b, 0);

/**
 * Total ESTIMÉ, pour l'affichage pendant que le client choisit.
 * Le total qui fait foi est celui calculé par l'API à la création de la commande (T01).
 */
export function estimateTotal(cart: Cart, byId: ReadonlyMap<string, Product>): number {
  return Object.entries(cart).reduce((s, [id, q]) => s + (byId.get(id)?.price_mru ?? 0) * q, 0);
}

export const toItems = (cart: Cart) =>
  Object.entries(cart).map(([product_id, quantity]) => ({ product_id, quantity }));
