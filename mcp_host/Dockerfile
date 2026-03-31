# =============================================================================
# mcp_host/Dockerfile — Image hybride MCP Host
# =============================================================================
# Base : python:3.11-slim
# Inclut : Node.js 20 LTS + npx + uv
# Permet d'exécuter simultanément :
#   - Serveurs MCP JS  : npx @modelcontextprotocol/server-*
#   - Serveurs MCP Py  : uvx mcp-server-fetch, uvx scrapegraph-mcp
#   - Host Python      : mcp_host/main.py (asyncio + SDK mcp officiel)
# =============================================================================

FROM python:3.11-slim-bookworm

# ── Métadonnées ───────────────────────────────────────────────────────────────
LABEL maintainer="job-bot-general"
LABEL description="MCP Host hybride Python 3.11 + Node.js 20 + npx + uv"

# ── Variables d'environnement ─────────────────────────────────────────────────
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    NODE_ENV=production \
    # uv — installation dans /root/.local/bin
    PATH="/root/.local/bin:/opt/venv/bin:$PATH" \
    VIRTUAL_ENV=/opt/venv

# ── Dépendances système + Node.js 20 LTS ─────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    gnupg \
    gcc \
    # Nécessaire pour certains packages Python natifs
    libpq-dev \
    # Node.js 20 LTS via NodeSource
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    # Nettoyage
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    # Vérification
    && node --version \
    && npm --version \
    && npx --version

# ── Installation de uv (gestionnaire de paquets Python ultra-rapide) ──────────
RUN curl -LsSf https://astral.sh/uv/install.sh | sh \
    && uv --version

# ── Virtualenv Python isolé ───────────────────────────────────────────────────
RUN python3 -m venv $VIRTUAL_ENV

# ── Dépendances Python ────────────────────────────────────────────────────────
WORKDIR /app

# Copie uniquement les fichiers de dépendances pour profiter du cache Docker
COPY requirements.txt /tmp/requirements-root.txt

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r /tmp/requirements-root.txt

# ── Code source ───────────────────────────────────────────────────────────────
COPY . /app

# ── Pré-téléchargement des serveurs MCP Node.js (cache npm) ──────────────────
# Évite les délais au premier appel en production
RUN npx --yes @modelcontextprotocol/server-postgres --version 2>/dev/null || true \
    && npx --yes @modelcontextprotocol/server-filesystem --version 2>/dev/null || true \
    && npx --yes @modelcontextprotocol/server-github --version 2>/dev/null || true

# ── Point d'entrée ────────────────────────────────────────────────────────────
# Par défaut : affiche les outils disponibles (mode diagnostic)
CMD ["python", "-m", "mcp_host.main", "--list-registry"]
