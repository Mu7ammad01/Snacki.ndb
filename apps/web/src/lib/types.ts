/** Formats échangés avec l'API Python (voir apps/api/src/snacki_api/schemas.py). */

export type Lang = "fr" | "ar";
export type Category = "jus" | "delices";

export interface Product {
  id: string;
  category: Category;
  name_fr: string;
  name_ar: string;
  description_fr: string;
  description_ar: string;
  price_mru: number;
  badge: "top" | "pop" | null;
  photo: string | null;
}

export interface OrderLine {
  product_id: string;
  quantity: number;
  unit_price_mru: number;
  line_total_mru: number;
}

export type OrderStatus =
  | "recue" | "acceptee" | "en_preparation" | "prete" | "livree" | "refusee" | "annulee";
export type PaymentMethod = "cash" | "bankily" | "sedad" | "bimbank" | "bamis";

export interface OrderTrack {
  number: string;
  status: OrderStatus;
  fulfilment: "emporter" | "livraison";
  total_mru: number; // articles, prix figés par l'API
  delivery_fee_mru: number; // fixés par le snack à l'acceptation
  grand_total_mru: number; // à payer
  currency: string;
  lines: OrderLine[];
  created_at: string;
  ready_at: string | null;
  discount_mru?: number; // cadeau fidélité (J8 bis)
  closed_reason: string | null;
}

/** Vue de la caisse (staff connecté) : coordonnées du client comprises. */
export interface CaisseOrder extends OrderTrack {
  id: number;
  source: "app" | "comptoir";
  customer_name: string;
  phone: string | null;
  landmark: string | null;
  note: string | null;
  pay_pref: PaymentMethod | null;
  accepted_at: string | null;
  customer_called_at: string | null;
  paid_method: PaymentMethod | null;
  paid_at: string | null;
  loyalty_card_id?: number | null;
}

export interface OrderCreated extends OrderTrack {
  tracking_token: string;
  tracking_expires_at: string;
}

/** Ce que le navigateur envoie : des produits et des quantités, jamais un prix (T01). */
export interface OrderRequest {
  customer_name: string;
  phone: string;
  fulfilment: "emporter" | "livraison";
  landmark?: string;
  items: { product_id: string; quantity: number }[];
  note?: string;
  pay_pref?: PaymentMethod;
}

/** Pilotage (J8) : réponse de GET /v1/pilotage, gérante et admin seulement. */
export interface Pilotage {
  start: string;
  end: string;
  revenue_mru: number;
  orders: number;
  average_basket_mru: number;
  today_mru: number;
  all_time_mru: number;
  by_day: { day: string; app_mru: number; comptoir_mru: number; historique_mru: number }[];
  top: { product_id: string | null; label: string; quantity: number; revenue_mru: number }[];
  payments: { method: PaymentMethod; count: number; amount_mru: number }[];
  history_first: string | null;
  history_last: string | null;
  loyalty: { stamps: number; rewards: number; discount_mru: number; active_cards: number };
}

/** Fidélité (J8 bis) : état d'une carte vu par la caisse. */
export interface LoyaltyCard {
  card: string;
  status: "issued" | "active" | "blocked";
  stamps: number;
  progress: number;
  goal: number;
  rewards_available: number;
  rewards_taken: number;
  phone_linked: boolean;
}

/** Vue du client (QR de sa carte) : progression seulement. */
export type LoyaltyPublic = Pick<LoyaltyCard, "card" | "status" | "progress" | "goal" | "rewards_available">;

/** Proposition de l'assistant de commande (J9) : à vérifier avant toute vente. */
export interface AssistantResult {
  engine: "gemini" | "local";
  lines: { product_id: string; name: string; quantity: number; unit_price_mru: number; total_mru: number }[];
  total_mru: number;
  fulfilment: "emporter" | "livraison" | "inconnu";
  unknown: string[];
  warnings: string[];
}
