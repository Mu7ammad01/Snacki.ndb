/**
 * Caisse (J7) : règles d'affichage, testées sans serveur.
 *
 * Ces règles ne font que choisir les boutons à montrer. La vraie décision est prise par l'API
 * (machine à états et rôles) : un bouton affiché par erreur recevrait un 409 ou un 403.
 */
import type { CaisseOrder, OrderStatus, PaymentMethod } from "./types";
import type { Role } from "./staff";

export type Action =
  | { kind: "accept" }
  | { kind: "advance"; to: OrderStatus; label: string; blocked?: string }
  | { kind: "called" }
  | { kind: "pay" }
  | { kind: "refuse" }
  | { kind: "cancel" }
  | { kind: "stamp" }
  | { kind: "reward" };

const NEXT: Partial<Record<OrderStatus, { to: OrderStatus; label: string }>> = {
  acceptee: { to: "en_preparation", label: "En préparation" },
  en_preparation: { to: "prete", label: "Prête" },
  prete: { to: "livree", label: "Remise au client" },
};
const OPEN: OrderStatus[] = ["recue", "acceptee", "en_preparation", "prete"];
const MANAGERS: Role[] = ["gerante", "admin"];

export const STATUS_LABEL: Record<OrderStatus, string> = {
  recue: "À accepter",
  acceptee: "Acceptée",
  en_preparation: "En préparation",
  prete: "Prête",
  livree: "Remise",
  refusee: "Refusée",
  annulee: "Annulée",
};

export const PAY_LABEL: Record<PaymentMethod, string> = {
  cash: "Espèces",
  bankily: "Bankily",
  sedad: "Sedad",
  bimbank: "Bimbank",
  bamis: "Bamis",
};

export const DELAYS = [10, 15, 20, 30, 45, 60] as const;

export function actionsFor(order: CaisseOrder, role: Role): Action[] {
  const manager = MANAGERS.includes(role);
  const out: Action[] = [];
  if (order.status === "recue") {
    out.push({ kind: "accept" });
    if (manager) out.push({ kind: "refuse" });
    return out;
  }
  const next = NEXT[order.status];
  if (next) {
    const mustCall =
      next.to === "livree" && order.fulfilment === "livraison" && !order.customer_called_at;
    out.push({ kind: "advance", ...next, ...(mustCall ? { blocked: "Appelez d'abord le client" } : {}) });
  }
  if (OPEN.includes(order.status) && order.fulfilment === "livraison" && !order.customer_called_at) {
    out.push({ kind: "called" });
  }
  if (!order.paid_at && !["refusee", "annulee"].includes(order.status)) out.push({ kind: "pay" });
  // Fidélité : tampon après l'encaissement, cadeau avant ; une seule carte par commande.
  const noCard = !order.loyalty_card_id && !order.discount_mru;
  if (noCard && order.paid_at && !["refusee", "annulee"].includes(order.status)) out.push({ kind: "stamp" });
  if (noCard && !order.paid_at && OPEN.includes(order.status)) out.push({ kind: "reward" });
  if (manager && OPEN.includes(order.status)) out.push({ kind: "cancel" });
  return out;
}

export type Column = "todo" | "doing" | "done";

export function columnOf(status: OrderStatus): Column {
  if (status === "recue") return "todo";
  return OPEN.includes(status) ? "doing" : "done";
}

/** Commandes reçues apparues depuis le dernier passage : déclenchent le son et la notification. */
export function newArrivals(known: ReadonlySet<number>, orders: CaisseOrder[]): number[] {
  return orders.filter((o) => o.status === "recue" && !known.has(o.id)).map((o) => o.id);
}

/** Frais de livraison saisis par la gérante : entier de 0 à 2000 MRU, sinon null. */
export function parseFee(input: string): number | null {
  if (!/^\d{1,4}$/.test(input.trim())) return null;
  const n = Number(input.trim());
  return n <= 2000 ? n : null;
}

/** Numéro mauritanien (8 chiffres) en lien d'appel, ou null s'il n'est pas valide. */
export function telLink(phone: string | null): string | null {
  return phone && /^[234]\d{7}$/.test(phone) ? `tel:+222${phone}` : null;
}

export const hhmm = (iso: string | null) =>
  iso
    ? new Date(iso).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit", timeZone: "UTC" })
    : "";

const ACTIONS = new Set(["accept", "status", "called", "pay", "refuse", "cancel", "loyalty", "reward"]);

/** Action relayée par le web : liste blanche, aucune autre route de l'API n'est atteignable. */
export function isCaisseAction(value: string): boolean {
  return ACTIONS.has(value);
}

const CARD = /FID[-\s]*([0-9A-Z]{4})[-\s]*([0-9A-Z]{4})/i;

/** Numéro de carte lu dans le QR (lien …/carte#FID-…) ou saisi ; mise en forme seulement,
 * la vérification (caractère de contrôle, existence) est faite par l'API. */
export function cardFrom(text: string): string | null {
  const m = CARD.exec(text.toUpperCase());
  const raw = m ? m[1] + m[2] : text.toUpperCase().replace(/[\s-]/g, "");
  return /^[0-9A-Z]{8}$/.test(raw) ? `FID-${raw.slice(0, 4)}-${raw.slice(4)}` : null;
}
