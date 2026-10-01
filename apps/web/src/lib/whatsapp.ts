import { CONTACT, PAYMENTS, T, ZONES, fmtPlain } from "./i18n";
import type { Lang, OrderCreated, Product } from "./types";
import { oneLine } from "./validate";

export interface MessageInput {
  lang: Lang;
  order: OrderCreated; // numéro, lignes et total : ceux de l'API, pas ceux du navigateur
  products: ReadonlyMap<string, Product>;
  name: string;
  phone: string; // 8 chiffres, déjà normalisé
  zone: string;
  landmark: string;
  pay: string;
  note: string;
}

/**
 * Message prérempli envoyé par le client au snack.
 * Chaque saisie libre passe par oneLine() : un prénom contenant « \n*Total : 1 MRU* »
 * ne peut pas fabriquer une fausse ligne de total dans le message.
 */
export function buildMessage(m: MessageInput): string {
  const M = T[m.lang].msg;
  const L = m.lang === "ar" ? "‎" : "";
  const num = (v: string) => L + v + L;
  const pname = (id: string) => {
    const p = m.products.get(id);
    return p ? (m.lang === "ar" ? p.name_ar : p.name_fr) : id;
  };
  const pay = PAYMENTS.find((p) => p.id === m.pay) ?? PAYMENTS[0];
  const zone = ZONES.find((z) => z.id === m.zone) ?? ZONES[0];
  const delivery = m.order.fulfilment === "livraison";
  const lines = [
    `*${M.head}*`,
    `${M.no} : ${num(m.order.number)}`,
    "",
    ...m.order.lines.map((l) => `${l.quantity} × ${pname(l.product_id)} — ${num(fmtPlain(l.line_total_mru))}`),
    "",
    `*${M.total} : ${num(fmtPlain(m.order.total_mru))} MRU*${delivery ? " " + M.fee : ""}`,
    `${M.pay} : ${pay[m.lang]}`,
    "",
    `${M.name} : ${oneLine(m.name)}`,
    `${M.phone} : ${num("+222 " + m.phone.replace(/(\d{2})(?=\d)/g, "$1 "))}`,
    `${M.mode} : ${delivery ? `${M.delivery} — ${zone[m.lang]}` : M.pickup}`,
    delivery ? `${M.address} : ${oneLine(m.landmark)}` : null,
    oneLine(m.note) ? `${M.note} : ${oneLine(m.note).slice(0, 200)}` : null,
  ];
  return lines.filter((l): l is string => l !== null).join("\n");
}

export const waLink = (text: string) =>
  `https://wa.me/${CONTACT.whatsapp}?text=${encodeURIComponent(text)}`;
