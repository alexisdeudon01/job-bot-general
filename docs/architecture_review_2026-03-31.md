# Revue d'architecture — 31 mars 2026

## Périmètre vérifié

- Orchestrateur FastAPI (`app/*`)
- Dashboard Streamlit (`dashboard/*`)
- Workers batch (`analyzer`, `generator`, `agent`)
- Serveur MCP (`mcp_server/*`)
- Déploiement Docker Compose (`docker-compose.yml`)

## Synthèse exécutive

1. **Redis n'est pas nécessaire dans l'état actuel du code** : aucun client Redis n'est instancié, aucune feature cache/queue n'est branchée.
2. **PostgreSQL est un bon choix** pour ce projet : modèle relationnel riche + payload JSON + audit.
3. **Dockeriser tous les modules est pertinent**, mais en distinguant mieux les rôles:
   - services "always-on" (orchestrator, dashboard, postgres),
   - jobs batch à la demande (analyzer/generator/agent),
   - mcp uniquement pour les scénarios d'intégration.

## Constats détaillés

### 1) Redis

- `docker-compose.yml` lançait un service Redis et injectait `REDIS_URL`, mais l'application n'en faisait pas usage métier.
- Le statut provider Redis était un placeholder dans l'API dashboard.

Conclusion: Redis ajoutait de la complexité opérationnelle sans valeur immédiate.

### 2) PostgreSQL

Le code exploite déjà correctement SQLAlchemy + modèle relationnel orienté:

- runs et événements pipeline,
- entités métier,
- historique LLM,
- statuts providers.

C'est cohérent avec un besoin de traçabilité et d'analytics.

### 3) Dockerisation module par module

Le découpage actuel est globalement sain:

- **orchestrator** = API centrale,
- **dashboard** = UX/ops,
- **batch modules** = traitements spécialisés,
- **mcp server** = intégration outillée.

Recommandation: garder ce découpage, mais éviter de démarrer tous les conteneurs en permanence quand ils ne sont pas utiles (profils compose déjà présents pour `batch` et `mcp`).

## Décisions appliquées dans ce changement

- Retrait du service Redis du `docker-compose` principal.
- Suppression de `REDIS_URL` côté orchestrator.
- Nettoyage du provider Redis dans le statut dashboard.
- Nettoyage du package `redis` non utilisé dans `requirements.txt`.
- Mise à jour du script `start.sh` pour ne plus démarrer/afficher Redis.

## Plan d'amélioration recommandé (prochaine itération)

1. **Pipeline state durable**: persister les `PipelineRun` en DB (aujourd'hui la liste en mémoire est volatile côté service).
2. **Asynchronisme explicite**: introduire une queue seulement si la charge le justifie (Redis + RQ/Celery/Arq) au lieu d'anticiper.
3. **Observabilité**: ajouter healthchecks actifs pour providers externes (pas seulement présence des variables env).
4. **Sécurité secrets**: migrer vers un backend secrets dédié (Vault/KMS/SSM) si passage en production.
5. **Migrations DB**: formaliser Alembic + stratégie de versionnement du schéma.

## Critères pour réintroduire Redis plus tard

Réintroduire Redis uniquement si l'un de ces besoins devient réel:

- queue de jobs asynchrones,
- rate limiting distribué,
- cache partagé multi-instance,
- pub/sub temps réel à grande échelle.

Sans ces besoins, PostgreSQL seul reste suffisant et plus simple à opérer.
