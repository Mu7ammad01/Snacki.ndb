/**
 * Parcours de bout en bout (J11, ADR 0016) sur l'app construite, l'API et une base jetables.
 * Le lien WhatsApp n'est jamais ouvert : il mènerait au vrai numéro du snack.
 */
import { execFileSync } from "node:child_process";

import { expect, test, type BrowserContext, type Page } from "@playwright/test";

const BASE = "http://localhost:3000";

/** Session du staff signée comme après une connexion Google (base de test seulement). */
function connecter(context: BrowserContext, role: "caissier" | "gerante") {
  const token = execFileSync("python", ["e2e/staff_session.py", role], {
    encoding: "utf8",
    env: { ...process.env, PYTHONPATH: "../api/src" },
  }).trim();
  // Le cookie « Secure » de la vraie app n'est pas posé sur http://localhost : on joint la
  // session telle que le navigateur l'enverrait, à chaque requête de ce contexte.
  return context.setExtraHTTPHeaders({ Cookie: `__Host-snacki_session=${token}` });
}

/** Prénom propre à ce passage (lettres seulement) : la base garde les passages précédents. */
const unique = (prenom: string) =>
  prenom + Date.now().toString(26).replace(/\d/g, (d) => "abcdefghij"[Number(d)]).slice(-5);

/** Commande d'un client depuis le menu ; renvoie l'adresse de suivi. */
async function commander(page: Page, prenom: string): Promise<{ suivi: string }> {
  await page.goto("/");
  await page.getByRole("button", { name: "Ajouter — Salade de fruits" }).click();
  await page.getByRole("button", { name: "Ajouter un — Salade de fruits" }).click();
  await page.getByRole("button", { name: /Voir mon panier/ }).click();
  await page.getByRole("button", { name: "Continuer" }).click();
  await page.getByLabel("Prénom").fill(prenom);
  await page.getByLabel("Téléphone").fill("37 93 94 09");
  await page.getByRole("radio", { name: /emporter/i }).click();
  await page.getByRole("button", { name: "Valider la commande" }).click();
  await expect(page.getByRole("heading", { name: "Commande enregistrée" })).toBeVisible();
  const suivi = (await page.getByRole("link", { name: "Suivre ma commande" }).getAttribute("href")) ?? "";
  expect(suivi).toMatch(/^\/suivi#/); // jeton dans le fragment, jamais envoyé au serveur (ADR 0003)
  return { suivi };
}

test("client : menu, panier, commande à emporter, suivi", async ({ page }) => {
  const csp: string[] = [];
  page.on("console", (m) => m.text().includes("Content Security Policy") && csp.push(m.text()));
  const { suivi } = await commander(page, unique("Aicha"));
  await page.goto(suivi);
  await expect(page.getByRole("heading", { name: "Suivi de commande" })).toBeVisible();
  await expect(page.getByText("Reçue").first()).toBeVisible();
  expect(csp, "aucun blocage CSP sur le parcours client").toEqual([]);
});

test("caisse : accepter, préparer, encaisser, remettre ; le client voit l'avancement", async ({ page, context }) => {
  const prenom = unique("Mariem");
  const { suivi } = await commander(page, prenom);
  await connecter(context, "caissier");
  await page.goto("/caisse");
  const carte = page.locator("li.order").filter({ hasText: prenom });
  const onglet = (nom: string) => page.getByRole("tab", { name: new RegExp(`^${nom}`) }).click();

  await carte.getByRole("button", { name: "Accepter" }).click();
  await page.getByRole("radio", { name: "10 min" }).click();
  await page.getByRole("button", { name: "Confirmer l'acceptation" }).click();
  await onglet("En cours");
  await expect(carte.getByText("Acceptée")).toBeVisible();

  const client = await context.newPage();
  await client.goto(suivi);
  await expect(client.getByText("Acceptée").first()).toBeVisible();
  await client.close();

  await carte.getByRole("button", { name: "En préparation", exact: true }).click();
  await carte.getByRole("button", { name: "Prête", exact: true }).click();
  await carte.getByRole("button", { name: "Encaisser" }).click();
  await carte.getByRole("button", { name: "Espèces" }).click();
  await expect(carte.getByText(/encaissé \(Espèces\)/)).toBeVisible();
  await carte.getByRole("button", { name: "Remise au client" }).click();
  await onglet("Terminées");
  await expect(carte.getByText("Remise", { exact: true })).toBeVisible();
});

test("sécurité : pilotage réservé, en-têtes de sécurité, session obligatoire", async ({ page, context, request }) => {
  const r = await request.get("/");
  expect(r.headers()["content-security-policy"]).toMatch(/script-src 'self' 'nonce-[^']+' 'strict-dynamic'/);
  expect(r.headers()["x-frame-options"]).toBe("DENY");
  expect(r.headers()["cross-origin-resource-policy"]).toBe("same-origin"); // audit J13
  expect(r.headers()["cross-origin-embedder-policy"]).toBe("require-corp");

  await page.goto("/pilotage");
  await expect(page).toHaveURL(/\/connexion/);
  expect((await request.post("/api/caisse/orders", { data: {} })).status()).toBeGreaterThanOrEqual(400);

  await connecter(context, "caissier");
  await page.goto("/pilotage");
  await expect(page.getByText("réservé à la gérante")).toBeVisible();
});

test("PWA : installable, page hors connexion, aucune page en cache", async ({ page, context, request }) => {
  const manifest = await (await request.get("/manifest.webmanifest")).json();
  expect(manifest).toMatchObject({ display: "standalone", start_url: "/" });
  const caisse = await (await request.get("/manifest-caisse.webmanifest")).json();
  expect(caisse.start_url).toBe("/caisse");

  await page.goto("/");
  await page.evaluate(() => navigator.serviceWorker.ready.then(() => true));
  await page.reload(); // la page est désormais contrôlée par le service worker

  // Réseau coupé, y compris pour le service worker (setOffline ne le couvre pas toujours).
  await context.setOffline(true);
  await context.route("**/suivi", (route) => route.abort("internetdisconnected"));
  await page.goto("/suivi").catch(() => {});
  await expect(page.getByRole("heading", { name: "Pas de connexion" })).toBeVisible();
  await context.setOffline(false);
  await context.unroute("**/suivi");

  const cached = await page.evaluate(async () => {
    const out: string[] = [];
    for (const name of await caches.keys()) {
      for (const req of await (await caches.open(name)).keys()) out.push(new URL(req.url).pathname);
    }
    return out;
  });
  expect(cached).toContain("/offline.html");
  for (const path of cached) {
    expect(path, "seuls des fichiers publics sont en cache").toMatch(/^\/(offline\.(html|css)|_next\/static\/|img\/|icons\/|fonts\/)/);
  }
});

test("v1.1 · gérante : graphiques, rapport Excel et PDF, historique filtrable", async ({ page, context, request }) => {
  const prenom = unique("Zeina");
  await commander(page, prenom);
  await connecter(context, "gerante");

  await page.goto("/pilotage");
  await expect(page.getByRole("img", { name: "Chiffre d'affaires par jour, en MRU" })).toBeVisible();
  await expect(page.getByRole("img", { name: "Nombre de commandes par jour" })).toBeVisible();

  await page.getByRole("link", { name: "Générer un rapport" }).click();
  await expect(page.getByRole("heading", { name: "Rapport Snacki" })).toBeVisible();
  await expect(page.getByText(/^Généré le /)).toBeVisible();
  await expect(page.getByRole("button", { name: "Enregistrer en PDF" })).toBeVisible();
  const href = (await page.getByRole("link", { name: "Télécharger Excel" }).getAttribute("href")) ?? "";
  const xlsx = await page.request.get(href);
  expect(xlsx.status()).toBe(200);
  expect(xlsx.headers()["content-type"]).toContain("spreadsheetml");
  expect((await xlsx.body()).subarray(0, 2).toString()).toBe("PK"); // un vrai fichier .xlsx (zip)

  await page.goto("/historique");
  await expect(page.getByRole("heading", { name: "Historique" })).toBeVisible();
  await page.getByLabel("Type d'action").selectOption("connexions");
  await page.getByRole("button", { name: "Filtrer" }).click();
  await expect(page).toHaveURL(/group=connexions/);

  expect((await request.get("/api/pilotage/rapport?start=x&end=y")).status()).toBe(422);
});
