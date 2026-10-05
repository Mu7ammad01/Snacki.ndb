# Image de l'API Snacki : multi-étapes, utilisateur non root, uniquement le code utile.
# Construction : docker build -t snacki-api apps/api

# --- Étape 1 : installer les dépendances dans un environnement isolé ---
FROM python:3.12-slim AS build
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
COPY requirements.txt .
RUN python -m venv /venv \
 && /venv/bin/pip install -r requirements.txt \
 && /venv/bin/pip uninstall -y pip

# --- Étape 2 : image finale, sans outils de construction ---
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PATH="/venv/bin:$PATH" PYTHONPATH=/app/src \
    SNACKI_ENVIRONMENT=prod
# Utilisateur sans droits : une faille dans l'API ne donne pas la main sur le conteneur.
# pip est retiré : inutile pour faire tourner l'API, c'est un outil de moins pour un attaquant.
# Correctifs de sécurité Debian publiés après l'image de base (porte 7, Trivy).
# postgresql-client : pg_dump et psql pour la sauvegarde nocturne (ADR 0013), seuls outils ajoutés.
RUN apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get upgrade -y \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends postgresql-client \
 && rm -rf /var/lib/apt/lists/* \
 && useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin snacki \
 && python -m pip uninstall -y pip
WORKDIR /app
COPY --from=build /venv /venv
# Le code appartient à root et n'est que lisible par l'utilisateur de l'API.
COPY alembic.ini ./
COPY migrations/ ./migrations/
COPY src/ ./src/
USER 10001
EXPOSE 8080
# Cloud Run envoie le trafic sur le port 8080. Pas d'en-tête « server: uvicorn ».
CMD ["uvicorn", "snacki_api.main:app", "--app-dir", "src", "--host", "0.0.0.0", "--port", "8080", "--no-server-header"]
