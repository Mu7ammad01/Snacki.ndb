import type { Product } from "@/lib/types";

const p = (id: string, name_fr: string, price_mru: number, category: Product["category"]): Product => ({
  id, category, name_fr, name_ar: name_fr, description_fr: "", description_ar: "", price_mru, badge: null, photo: `img/${id}.jpg`,
});

export const Shop = {
  products: new Map([p("salade", "Salade de fruits", 100, "delices"), p("crepe", "Crêpe", 120, "delices"),
    p("avocat", "Jus avocat", 100, "jus"), p("fraise", "Jus fraise", 100, "jus")].map((x) => [x.id, x])),
};
