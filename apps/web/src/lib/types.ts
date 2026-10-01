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

export type OrderStatus = "recue" | "en_preparation" | "prete" | "livree" | "annulee";

export interface OrderTrack {
  number: string;
  status: OrderStatus;
  fulfilment: "emporter" | "livraison";
  total_mru: number;
  currency: string;
  lines: OrderLine[];
  created_at: string;
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
}
