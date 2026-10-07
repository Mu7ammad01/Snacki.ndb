import { defineConfig, devices } from "@playwright/test";

/**
 * Tests de bout en bout (J11, ADR 0016) : un vrai navigateur rejoue les parcours du client et de
 * la caisse sur l'app construite en mode production, avec l'API et un PostgreSQL jetables.
 * Jamais contre staging ni la production.
 */
const API = "http://127.0.0.1:8000";
export const BASE = "http://localhost:3000";

export default defineConfig({
  testDir: "e2e",
  fullyParallel: false, // une seule base : les parcours s'enchaînent
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  forbidOnly: !!process.env.CI,
  reporter: "list",
  timeout: 30_000,
  use: {
    baseURL: BASE,
    trace: "retain-on-failure",
    locale: "fr-FR",
    serviceWorkers: "allow",
    // En local, Chromium déjà installé (PW_CHROMIUM) ; en CI, celui de « playwright install ».
    launchOptions: process.env.PW_CHROMIUM ? { executablePath: process.env.PW_CHROMIUM } : {},
  },
  projects: [{ name: "mobile", use: { ...devices["Pixel 7"] } }],
  webServer: [
    {
      command: "uvicorn snacki_api.main:app --app-dir ../api/src --host 127.0.0.1 --port 8000",
      url: `${API}/v1/menu`,
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
      // Base et clé de session viennent de l'environnement (CI ou poste local) ; le client OAuth
      // est factice : les tests ne passent jamais par Google (voir e2e/staff_session.py).
      env: {
        SNACKI_ENVIRONMENT: "test",
        SNACKI_OAUTH_CLIENT_ID: "e2e-client",
        SNACKI_OAUTH_CLIENT_SECRET: "e2e-not-a-secret",
        SNACKI_OAUTH_REDIRECT_URI: `${BASE}/auth/callback`,
      },
    },
    {
      command: "npm run start -- --port 3000",
      url: BASE,
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
      env: { SNACKI_API_URL: API, SNACKI_PUBLIC_URL: BASE },
    },
  ],
});
