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
  by_day: { day: string; app_mru: number; comptoir_mru: number; historique_mru: number; orders: number }[];
  top: { product_id: string | null; label: string; quantity: number; revenue_mru: number }[];
  payments: { method: PaymentMethod; count: number; amount_mru: number }[];
  history_first: string | null;
  history_last: string | null;
  loyalty: { stamps: number; rewards: number; discount_mru: number; active_cards: number };
  purchases: Spending; // J16
  gross_margin_mru: number; // J16 : ventes − achats de la période
  purchases_first: string | null; // J16 : premier achat saisi
}

// --- Achats et stock (J16) -----------------------------------------------------------------

export type StockUnit = "kg" | "l" | "piece";
export type PurchaseCategory = "ingredients" | "emballages" | "energie" | "entretien" | "materiel" | "autre";

export interface Supplier {
  id: number;
  name: string;
  phone: string | null;
  note: string | null;
  active: boolean;
}

export interface Ingredient {
  id: number;
  name: string;
  unit: StockUnit;
  stock_qty: number;
  alert_qty: number | null;
  active: boolean;
  low: boolean;
}

export interface Purchase {
  id: number;
  purchase_day: string;
  supplier_id: number | null;
  supplier: string | null;
  payment_method: PaymentMethod;
  total_mru: number;
  note: string | null;
  created_by: string;
  created_at: string;
  cancelled_at: string | null;
  cancel_reason: string | null;
  lines: { ingredient_id: number | null; label: string; category: PurchaseCategory; quantity: number; amount_mru: number }[];
}

export interface PurchaseList {
  start: string;
  end: string;
  purchases: Purchase[];
  total_mru: number;
  truncated: boolean;
}

/** Corps de POST /v1/achats : lignes et montants du ticket, jamais de total. */
export interface PurchaseRequest {
  purchase_day: string;
  supplier_id: number | null;
  payment_method: PaymentMethod;
  note?: string;
  lines: (
    | { ingredient_id: number; quantity: number; amount_mru: number }
    | { label: string; category: PurchaseCategory; quantity: number; amount_mru: number }
  )[];
}

export interface Spending {
  total_mru: number;
  by_day: { day: string; amount_mru: number }[];
  by_category: { category: PurchaseCategory; label: string; amount_mru: number }[];
  by_supplier: { supplier: string; count: number; amount_mru: number }[];
  low_stock: { id: number; name: string; unit: StockUnit; stock_qty: number }[];
}

/** Historique des actions du staff (v1.1) : GET /v1/historique. */
export interface History {
  entries: { at: string; actor: string; action: string; label: string; group: string; target: string | null; detail: string }[];
  people: { id: number; name: string }[];
  groups: Record<string, string>;
  truncated: boolean;
}

/** Prévisions (J10) : articles attendus aujourd'hui et les 6 jours suivants. */
export interface Forecast {
  generated_for: string;
  open_days: number;
  reliability: "bonne" | "indicative" | "insuffisante";
  backtest: { days: number; model_error: number | null; naive_error: number | null };
  days: {
    day: string;
    weekday: string;
    units: number;
    revenue_mru: number;
    items: { product_id: string; label: string; quantity: number }[];
  }[];
}

/** Résumé du jour (J10) : texte modèle, ou reformulé par l'IA avec chiffres vérifiés. */
export interface Resume {
  day: string;
  text: string;
  engine: "gemini" | "modele";
  warnings: string[];
  ai_available: boolean;
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
