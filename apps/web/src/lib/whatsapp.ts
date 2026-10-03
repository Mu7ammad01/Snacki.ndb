import { CONTACT, T } from "./i18n";
import type { Lang } from "./types";

/**
 * J7 : la commande passe uniquement par l'app et arrive directement en caisse.
 * WhatsApp ne sert plus qu'à contacter le snack en cas de besoin : le message prérempli
 * contient seulement le numéro de commande attribué par l'API, jamais le jeton de suivi.
 */
const ORDER_NO = /^SNK-\d{4}-\d{3,}$/;

export function contactMessage(lang: Lang, orderNumber: string): string {
  return T[lang].contactMsg(ORDER_NO.test(orderNumber) ? orderNumber : "");
}

export const waLink = (text: string) =>
  `https://wa.me/${CONTACT.whatsapp}?text=${encodeURIComponent(text)}`;
