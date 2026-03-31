# Check complet data-oriented — 31 mars 2026

## Mesures collectées

- Fichiers Python: **90**
- Dockerfiles: **5**
- Services Docker Compose: **7**
- Marqueurs TODO/FIXME/XXX: **0**
- Dépendances racine (`requirements.txt`): **20**
- Dépendances dashboard (`dashboard/requirements.txt`): **7**
- Dépendances en recouvrement racine/dashboard: **7**

## Bugs détectés et statut

1. **Bug bloquant corrigé**
   - `mcp_server/transport/tools.py` contenait une string non terminée (erreur de syntaxe Python) qui cassait la compilation statique.
   - Correctif appliqué sur la ligne de normalisation des tokens (`strip`).

2. **Risque de lisibilité opérationnelle dashboard**
   - Le dashboard était riche mais peu guidé pour l'exploitation quotidienne.
   - Action: ajout d'une page `Diagnostics` orientée data avec:
     - score de fiabilité,
     - score de complétude,
     - taux d'échec runs,
     - détection des endpoints en fallback,
     - signaux bugs,
     - redondances de dépendances.

## Redondances détectées

Recouvrement de dépendances entre `requirements.txt` et `dashboard/requirements.txt`:

- `streamlit`
- `openai`
- `requests`
- `beautifulsoup4`
- `spacy`
- `python-dotenv`
- `pypdf2`

Interprétation:
- acceptable si installation séparée par image/service,
- à rationaliser si un lockfile unifié est introduit.

## Recommandations prioritaires

1. Continuer la séparation stricte des dépendances par module pour limiter le blast radius.
2. Introduire un contrôle CI qui vérifie:
   - `python -m compileall ...`,
   - cohérence des requirements multi-modules,
   - endpoints dashboard non-fallback en environnement d'intégration.
3. Ajouter une page "Actions recommandées" dans le dashboard basée sur les signaux diagnostics.
