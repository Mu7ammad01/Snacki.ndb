# Image du front Snacki (Next.js, sortie « standalone ») : multi-étapes, utilisateur non root.
# Construction : docker build -t snacki-web apps/web

# --- Étape 1 : dépendances exactes du package-lock.json ---
FROM node:26-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

# --- Étape 2 : construction de production ---
FROM node:26-alpine AS build
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

# --- Étape 3 : image finale : le serveur autonome, les fichiers statiques, rien d'autre ---
FROM node:26-alpine
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=8080 HOSTNAME=0.0.0.0
# npm, npx, corepack et yarn ne servent qu'à construire : on les retire de l'image finale
# (moins de code, donc moins de failles possibles et moins d'outils pour un attaquant).
RUN rm -rf /usr/local/lib/node_modules /usr/local/bin/npm /usr/local/bin/npx \
      /usr/local/bin/corepack /usr/local/bin/yarn /usr/local/bin/yarnpkg /opt/yarn-*
# Fichiers appartenant à root, lisibles seulement : le serveur ne peut pas modifier son code.
COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static
COPY --from=build /app/public ./public
# Utilisateur « node » (uid 1000) fourni par l'image officielle, sans droits.
USER node
EXPOSE 8080
CMD ["node", "server.js"]
