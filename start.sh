#!/usr/bin/env bash
# =============================================================================
# start.sh — Job Bot General — Script de démarrage complet
# =============================================================================
# 1. Arrête et supprime les containers existants du projet
# 2. Vérifie / crée le virtualenv local (.venv)
# 3. Vérifie / installe les dépendances Python
# 4. Build et lance tous les services Docker (postgres, redis, orchestrator, dashboard)
# 5. Ouvre le dashboard dans le navigateur
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VENV_DIR="$SCRIPT_DIR/.venv"
REQUIREMENTS="$SCRIPT_DIR/requirements.txt"
COMPOSE_FILE="$SCRIPT_DIR/docker-compose.yml"
DASHBOARD_URL="http://localhost:8501"
API_URL="http://localhost:8000"

# ── Couleurs ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

info()    { echo -e "${CYAN}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*"; }
step()    { echo -e "\n${BOLD}${BLUE}▶ $*${NC}"; }

echo -e "${BOLD}"
echo "╔══════════════════════════════════════════════════════════╗"
echo "║          Job Bot General — Démarrage complet             ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# ─────────────────────────────────────────────────────────────────────────────
# ÉTAPE 1 — Arrêt et suppression des containers existants
# ─────────────────────────────────────────────────────────────────────────────
step "Étape 1/4 — Nettoyage des containers Docker existants"

if ! command -v docker &>/dev/null; then
    error "Docker n'est pas installé ou pas dans le PATH."
    exit 1
fi

if ! command -v docker compose &>/dev/null 2>&1 && ! docker compose version &>/dev/null 2>&1; then
    error "docker compose (plugin v2) n'est pas disponible."
    exit 1
fi

# Récupère les containers du projet (tous profils)
RUNNING=$(docker compose -f "$COMPOSE_FILE" ps -q 2>/dev/null || true)

if [ -n "$RUNNING" ]; then
    info "Containers en cours d'exécution détectés — arrêt en cours..."
    docker compose -f "$COMPOSE_FILE" --profile batch --profile mcp down --remove-orphans --volumes 2>/dev/null || \
    docker compose -f "$COMPOSE_FILE" down --remove-orphans 2>/dev/null || true
    success "Containers arrêtés et supprimés."
else
    info "Aucun container du projet en cours d'exécution."
    # Tente quand même un down propre pour nettoyer les réseaux orphelins
    docker compose -f "$COMPOSE_FILE" down --remove-orphans 2>/dev/null || true
fi

# ─────────────────────────────────────────────────────────────────────────────
# ÉTAPE 2 — Vérification / création du virtualenv local
# ─────────────────────────────────────────────────────────────────────────────
step "Étape 2/4 — Environnement virtuel Python (.venv)"

PYTHON_BIN=""
for py in python3.12 python3.11 python3.10 python3 python; do
    if command -v "$py" &>/dev/null; then
        PYTHON_BIN="$py"
        break
    fi
done

if [ -z "$PYTHON_BIN" ]; then
    error "Aucun interpréteur Python trouvé. Installez Python 3.10+."
    exit 1
fi

PYTHON_VERSION=$("$PYTHON_BIN" --version 2>&1)
info "Interpréteur trouvé : $PYTHON_BIN ($PYTHON_VERSION)"

if [ ! -d "$VENV_DIR" ]; then
    info "Virtualenv absent — création de .venv..."
    "$PYTHON_BIN" -m venv "$VENV_DIR"
    success "Virtualenv créé dans .venv/"
else
    success "Virtualenv .venv/ déjà présent."
fi

VENV_PYTHON="$VENV_DIR/bin/python"
VENV_PIP="$VENV_DIR/bin/pip"

# ─────────────────────────────────────────────────────────────────────────────
# ÉTAPE 3 — Vérification / installation des dépendances
# ─────────────────────────────────────────────────────────────────────────────
step "Étape 3/4 — Dépendances Python"

if [ ! -f "$REQUIREMENTS" ]; then
    error "requirements.txt introuvable à la racine du projet."
    exit 1
fi

# Vérifie si les packages clés sont installés
MISSING=false
for pkg in fastapi uvicorn openai streamlit mcp; do
    if ! "$VENV_PYTHON" -c "import importlib; importlib.import_module('${pkg//-/_}')" &>/dev/null 2>&1; then
        MISSING=true
        break
    fi
done

if [ "$MISSING" = true ]; then
    info "Dépendances manquantes ou incomplètes — installation depuis requirements.txt..."
    "$VENV_PIP" install --upgrade pip --quiet
    "$VENV_PIP" install -r "$REQUIREMENTS" --quiet
    # Télécharge le modèle spaCy si nécessaire
    if ! "$VENV_PYTHON" -c "import spacy; spacy.load('fr_core_news_sm')" &>/dev/null 2>&1; then
        info "Téléchargement du modèle spaCy fr_core_news_sm..."
        "$VENV_PYTHON" -m spacy download fr_core_news_sm --quiet 2>/dev/null || \
        warn "Modèle spaCy fr_core_news_sm non disponible (non bloquant)."
    fi
    success "Dépendances installées."
else
    success "Toutes les dépendances sont déjà installées."
    # Vérifie openai-agents spécifiquement (peut être absent si venv ancien)
    if ! "$VENV_PYTHON" -c "import agents" &>/dev/null 2>&1; then
        info "openai-agents absent — installation..."
        "$VENV_PIP" install openai-agents --quiet
        success "openai-agents installé."
    fi
fi

# ─────────────────────────────────────────────────────────────────────────────
# ÉTAPE 4 — Build et lancement Docker
# ─────────────────────────────────────────────────────────────────────────────
step "Étape 4/4 — Build et lancement des services Docker"

info "Build des images Docker (postgres, redis, orchestrator, dashboard)..."
docker compose -f "$COMPOSE_FILE" build --parallel 2>&1 | grep -E "^(#|=>|\[|\-\-\-|ERROR|WARN|Step|Successfully)" || true

info "Démarrage des services principaux..."
docker compose -f "$COMPOSE_FILE" up -d postgres redis orchestrator dashboard

# ─────────────────────────────────────────────────────────────────────────────
# Attente que les services soient prêts
# ─────────────────────────────────────────────────────────────────────────────
echo ""
info "Attente que l'API orchestrateur soit prête sur $API_URL ..."
MAX_WAIT=60
WAITED=0
until curl -sf "$API_URL/health" &>/dev/null; do
    if [ "$WAITED" -ge "$MAX_WAIT" ]; then
        warn "L'API n'a pas répondu après ${MAX_WAIT}s — vérifiez les logs : docker compose logs orchestrator"
        break
    fi
    printf "."
    sleep 2
    WAITED=$((WAITED + 2))
done
echo ""

if curl -sf "$API_URL/health" &>/dev/null; then
    success "API orchestrateur opérationnelle sur $API_URL"
fi

info "Attente que le dashboard Streamlit soit prêt sur $DASHBOARD_URL ..."
WAITED=0
until curl -sf "$DASHBOARD_URL" &>/dev/null; do
    if [ "$WAITED" -ge "$MAX_WAIT" ]; then
        warn "Le dashboard n'a pas répondu après ${MAX_WAIT}s — vérifiez les logs : docker compose logs dashboard"
        break
    fi
    printf "."
    sleep 2
    WAITED=$((WAITED + 2))
done
echo ""

if curl -sf "$DASHBOARD_URL" &>/dev/null; then
    success "Dashboard Streamlit opérationnel sur $DASHBOARD_URL"
fi

# ─────────────────────────────────────────────────────────────────────────────
# Ouverture du navigateur
# ─────────────────────────────────────────────────────────────────────────────
echo ""
info "Ouverture du dashboard dans le navigateur..."
if command -v xdg-open &>/dev/null; then
    xdg-open "$DASHBOARD_URL" &>/dev/null &
elif command -v open &>/dev/null; then
    open "$DASHBOARD_URL"
elif command -v sensible-browser &>/dev/null; then
    sensible-browser "$DASHBOARD_URL" &>/dev/null &
else
    warn "Impossible d'ouvrir le navigateur automatiquement."
    info "Ouvrez manuellement : $DASHBOARD_URL"
fi

# ─────────────────────────────────────────────────────────────────────────────
# Résumé final
# ─────────────────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}${GREEN}╔══════════════════════════════════════════════════════════╗"
echo "║                  ✅  Démarrage terminé                   ║"
echo "╠══════════════════════════════════════════════════════════╣"
echo -e "║  Dashboard Streamlit : ${DASHBOARD_URL}          ║"
echo -e "║  API Orchestrateur   : ${API_URL}               ║"
echo -e "║  PostgreSQL          : localhost:5432                    ║"
echo -e "║  Redis               : localhost:6379                    ║"
echo "╠══════════════════════════════════════════════════════════╣"
echo "║  Logs : docker compose logs -f                           ║"
echo "║  Stop : docker compose down                              ║"
echo -e "╚══════════════════════════════════════════════════════════╝${NC}"
echo ""
