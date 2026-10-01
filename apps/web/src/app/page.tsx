import Shop from "@/components/Shop";
import { apiFetch } from "@/lib/server/api";
import type { Product } from "@/lib/types";

/** Le menu est lu par le serveur web dans l'API à chaque visite : prix et disponibilités à jour. */
async function loadMenu(): Promise<Product[] | null> {
  try {
    const r = await apiFetch("/v1/menu");
    if (!r.ok) return null;
    const body = (await r.json()) as { products: Product[] };
    return body.products;
  } catch {
    return null;
  }
}

export default async function Home() {
  const products = await loadMenu();
  return <Shop products={products} />;
}
