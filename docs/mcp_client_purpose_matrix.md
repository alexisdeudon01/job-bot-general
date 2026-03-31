# MCP client purpose matrix

## Objectif du document

Ce document décrit les **consommateurs MCP plausibles** du projet et précise, pour chaque composant applicatif, son rôle vis-à-vis des serveurs MCP configurés localement (`scrapegraph`, `filesystem`, `github`, `postgres`, `fetch`, `memory`, `playwright`).

L'objectif n'est pas de décrire les serveurs MCP eux-mêmes en détail, mais de répondre aux questions suivantes :

- quel composant peut agir comme **client MCP** ;
- pourquoi il aurait besoin d'outils MCP ;
- quels serveurs il devrait appeler ;
- quelles entrées il fournit ;
- quelles sorties il attend ;
- comment cet usage s'insère dans le pipeline global ;
- s'il doit parler **directement** aux serveurs MCP ou **passer via `mcp_server/`**.

Les observations ci-dessous s'appuient sur les composants existants, en particulier :

- `agent/services/pipeline.py`
- `agent/services/runner.py`
- `analyzer/services/pipeline.py`
- `generator/services/pipeline.py`
- `app/services/orchestration_service.py`
- `app/services/pipeline_service.py`
- `dashboard/services/api_client.py`

---

## Vue d'ensemble

## Constat principal

Dans l'état actuel du code :

- le composant **le plus légitime pour consommer les MCP servers est `app/`**, surtout via `OrchestrationService` et `OpenAIAgentsService` ;
- `mcp_server/` joue déjà le rôle naturel de **couche d'encapsulation métier et de compatibilité** pour les serveurs tiers ;
- `analyzer/` et `generator/` restent aujourd'hui surtout des pipelines batch Python classiques, avec peu de dépendance explicite aux MCP ;
- `dashboard/` ne consomme pas les MCP directement : il consomme l'API de `app/` ;
- `agent/` est un consommateur MCP plausible, mais plutôt **indirect**, via un orchestrateur central, afin d'éviter une duplication des responsabilités déjà présentes dans `app/` et `mcp_server/`.

## Recommandation globale

Architecture recommandée :

- **`dashboard`** → ne parle jamais directement aux serveurs MCP ;
- **`generator`** → ne parle pas directement aux serveurs MCP dans le flux nominal ;
- **`analyzer`** → peut bénéficier d'outils MCP, mais de préférence via `mcp_server/` ou via une orchestration `app/` ;
- **`agent`** → peut utiliser MCP pour des workflows autonomes, mais idéalement via `app/` ou `mcp_server/` pour rester cohérent ;
- **`app`** → point d'entrée principal pour l'orchestration MCP ;
- **`mcp_server`** → façade interne recommandée pour encapsuler, sécuriser, normaliser et stabiliser les usages des serveurs MCP tiers.

En résumé :

> **Les composants métier ne devraient pas, sauf besoin très spécifique, dialoguer directement avec les serveurs MCP tiers.  
> Ils devraient préférentiellement passer par `mcp_server/`, et `app/` devrait être le point d'orchestration applicatif principal.**

---

## Pipeline global cible

Le pipeline global observé et recommandé peut être résumé ainsi :

1. **`dashboard/`** déclenche des actions utilisateur via API HTTP.
2. **`app/`** reçoit la demande, planifie l'exécution, choisit si un usage MCP est pertinent.
3. **`app/services/orchestration_service.py`** décide :
   - soit un traitement LLM direct ;
   - soit un traitement outillé via OpenAI Agents SDK + MCP ;
   - soit un fallback plus direct via `mcp_server/clients/*`.
4. **`mcp_server/`** encapsule les appels effectifs vers :
   - `scrapegraph`
   - `filesystem`
   - `github`
   - `postgres`
   - `fetch`
   - `memory`
   - `playwright`
5. Les résultats reviennent vers :
   - `analyzer/` pour structuration et enrichissement,
   - `generator/` pour génération d'artefacts,
   - `app/` pour restitution API,
   - `dashboard/` pour visualisation.

---

## Matrice synthétique par composant

| Composant | Rôle comme client MCP | Serveurs MCP plausibles | Mode recommandé | Position dans le pipeline |
|---|---|---|---|---|
| `agent` | Agent autonome de collecte/génération assistée | `scrapegraph`, `fetch`, `playwright`, `filesystem`, `memory`, éventuellement `github` | Indirect via `app/` ou `mcp_server/` | Exécution spécialisée ou expérimentale |
| `analyzer` | Analyse d'offre, enrichissement de contexte, structuration | `scrapegraph`, `fetch`, `playwright`, `filesystem`, `memory`, éventuellement `postgres` | Via `mcp_server/` prioritairement | Étape d'analyse et de préparation des données |
| `generator` | Génération d'artefacts à partir de données déjà prêtes | `filesystem`, `memory`, éventuellement `fetch` | Très limité, via `mcp_server/` si nécessaire | Étape de production finale |
| `app` | Orchestrateur principal des appels outillés | Tous selon le cas d'usage | Direct vers OpenAI Agents SDK + encapsulation `mcp_server/` | Point d'entrée principal |
| `dashboard` | Aucun rôle direct ; visualisation et déclenchement | Aucun en direct | Via API `app/` uniquement | Front de supervision |
| `mcp_server` | Client/façade interne vers MCP tiers | Tous les serveurs configurés | Direct, car c'est sa responsabilité | Couche d'intégration et de normalisation |

---

## Détail par composant

## 1. `agent`

## Références lues

- `agent/services/pipeline.py`
- `agent/services/runner.py`

## But du composant

`agent` charge un CV texte, sélectionne un modèle OpenAI, puis délègue à `run_openai_agent(...)` l'exécution d'un agent pour traiter une offre donnée via `job_url`.

C'est donc un candidat naturel pour devenir un **consommateur MCP**, notamment lorsqu'un agent doit :

- récupérer du contenu web ;
- consulter des fichiers ;
- enrichir un contexte long ;
- mémoriser des éléments intermédiaires ;
- éventuellement interroger GitHub ou d'autres sources techniques.

## Ce qu'il cherche à obtenir via MCP

Usages plausibles :

- contenu brut ou markdown d'une offre d'emploi ;
- données structurées extraites depuis une page d'offre ;
- contexte complémentaire sur l'entreprise ;
- accès à des fichiers locaux de CV, templates, artefacts ;
- mémoire de session pour itérations agentiques multi-étapes.

## Serveurs MCP à appeler

Serveurs plausibles pour `agent` :

- **`scrapegraph`** : extraction structurée ou markdown de pages emploi ;
- **`fetch`** : récupération simple de ressources HTTP ;
- **`playwright`** : navigation si la page nécessite JavaScript ;
- **`filesystem`** : lecture/écriture de fichiers locaux contrôlés ;
- **`memory`** : conservation de contexte de travail ;
- **`github`** : utile seulement pour cas annexes, par exemple enrichissement depuis dépôts ou profils techniques.

## Entrées fournies

Entrées typiques :

- `job_url`
- `cv_text`
- éventuellement `resume_path`
- instructions agentiques
- contexte de session
- préférences de sortie

## Sorties attendues

Sorties plausibles :

- texte d'offre nettoyé ;
- structure d'offre enrichie ;
- notes d'analyse intermédiaires ;
- brouillon de réponse ;
- résultat final sérialisé (`AgentResult`) ;
- références aux outils utilisés et à leurs retours.

## Insertion dans le pipeline global

`agent` peut intervenir :

- soit comme **pipeline autonome** ;
- soit comme exécuteur spécialisé appelé par `app/` ;
- soit comme bloc expérimental R&D pour des workflows agentiques plus riches que les batchs `analyzer`/`generator`.

## Recommandation d'architecture pour `agent`

Recommandation :

- **ne pas faire de `agent` le point principal de connexion directe à tous les serveurs MCP tiers** ;
- lui faire consommer des capacités MCP :
  - soit via `app/services/orchestration_service.py`,
  - soit via des wrappers exposés par `mcp_server/`.

Pourquoi :

- éviter la duplication avec la logique déjà présente dans `app/` ;
- centraliser la gouvernance des outils ;
- conserver des interfaces stables pour les agents.

---

## 2. `analyzer`

## Référence lue

- `analyzer/services/pipeline.py`

## But du composant

`AnalyzerPipeline` :

- lit le CV ;
- scrape l'offre via `scrape_job_offer(...)` et `scrape_job_offer_structured(...)` ;
- exécute du NLP ;
- réalise une analyse LLM ou un fallback ;
- produit un `job_json` enrichi.

C'est le composant métier qui a **le plus besoin de données externes fiables et structurées**.

## Ce qu'il cherche à obtenir via MCP

`analyzer` cherche principalement :

- le contenu textuel ou markdown de l'offre ;
- une extraction structurée fiable des informations job ;
- éventuellement un fallback multi-source si le scraping échoue ;
- des métadonnées de provenance ;
- potentiellement des données d'historique ou de persistance pour enrichir l'analyse.

## Serveurs MCP à appeler

Serveurs recommandés :

- **`scrapegraph`** : serveur le plus directement aligné avec le code actuel ;
- **`fetch`** : fallback léger pour HTML brut ;
- **`playwright`** : si le site ne livre pas le contenu en HTML statique ;
- **`filesystem`** : lecture de CV source et écriture d'artefacts ;
- **`memory`** : mémoire d'analyse court terme ou session ;
- **`postgres`** : si l'on veut stocker/réutiliser analyses, sources, traces ou scores.

## Entrées fournies

Entrées concrètes :

- `job_url`
- `cv_path`
- `cv_text`
- prompts d'analyse
- schéma d'extraction attendu
- éventuellement état de session ou identifiant de run

## Sorties attendues

Sorties attendues par `analyzer` :

- `raw_job_text`
- `job_offer_structured`
- `scraping_source`
- données d'analyse NLP
- `cv_analysis`
- `job_json`
- indication de fallback ou d'échec

## Insertion dans le pipeline global

Dans le pipeline global, `analyzer` intervient très tôt :

1. collecte du contenu externe ;
2. normalisation ;
3. extraction structurée ;
4. enrichissement par NLP/LLM ;
5. production d'un artefact de référence pour `generator`.

## Recommandation d'architecture pour `analyzer`

Recommandation forte :

- **`analyzer` ne devrait pas gérer directement la diversité des serveurs MCP tiers** ;
- il devrait appeler des capacités unifiées fournies par `mcp_server/`, par exemple :
  - `extract_job_offer`
  - `fetch_job_page_markdown`
  - `resolve_dynamic_page_content`
  - `persist_analysis_snapshot`

Raison :

- `analyzer` est centré sur la logique d'analyse, pas sur l'orchestration outillage ;
- cela simplifie les fallbacks entre `scrapegraph`, `fetch` et `playwright` ;
- cela évite d'éparpiller la logique de transport MCP dans plusieurs sous-projets.

---

## 3. `generator`

## Référence lue

- `generator/services/pipeline.py`

## But du composant

`generator` lit `job_data.json`, relit le CV source, construit un prompt de génération, puis produit un résultat via OpenAI.

Son rôle actuel est essentiellement **aval** : il consomme des données déjà préparées.

## Ce qu'il cherche à obtenir via MCP

Dans sa forme actuelle, `generator` n'a pas un fort besoin de MCP. Ses besoins plausibles sont limités à :

- lecture d'artefacts ou de templates ;
- récupération de contexte complémentaire au dernier moment ;
- mémoire de session entre plusieurs générations ;
- persistance ou publication des résultats.

## Serveurs MCP à appeler

Serveurs plausibles mais secondaires :

- **`filesystem`** : lire des prompts, templates, exemples, artefacts ;
- **`memory`** : stocker des préférences ou brouillons intermédiaires ;
- **`fetch`** : éventuellement récupérer une ressource simple ;
- **`github`** : seulement si génération de documents adossée à un dépôt ;
- **`postgres`** : si l'on veut historiser les générations.

En revanche, `scrapegraph` et `playwright` sont plutôt **hors du flux nominal** de `generator`.

## Entrées fournies

- `job_data_path`
- `resume_path`
- contexte de génération
- prompt construit
- options de provider/modèle

## Sorties attendues

- résultats de génération par provider ;
- texte généré ;
- métadonnées de provider ;
- fichier de sortie JSON ;
- éventuellement artefacts futurs : lettre, CV adapté, score de fit.

## Insertion dans le pipeline global

`generator` intervient après `analyzer` :

1. lecture des données préparées ;
2. construction de prompt ;
3. génération ;
4. sauvegarde des résultats.

## Recommandation d'architecture pour `generator`

Recommandation :

- **pas d'accès direct aux serveurs MCP tiers dans le flux standard** ;
- accès éventuel à `mcp_server/` uniquement pour quelques capacités utilitaires bien bornées.

Pourquoi :

- le composant n'est pas un orchestrateur d'outils ;
- plus il reste déterministe et simple, plus il est facile à tester ;
- ses besoins MCP sont accessoires et doivent rester optionnels.

---

## 4. `app`

## Références lues

- `app/services/orchestration_service.py`
- `app/services/pipeline_service.py`

## But du composant

`app` est déjà le cœur d'orchestration le plus clair du projet.

Deux indices forts :

- `OrchestrationService` choisit entre LLM direct et outillage MCP ;
- `PipelineService.run_full()` appelle déjà OpenAI Agents SDK avec configuration MCP ScrapeGraph, puis applique des fallbacks.

`app` est donc le **client MCP principal et légitime**.

## Ce qu'il cherche à obtenir via MCP

`app` cherche à obtenir :

- des données web exploitées par des agents ;
- des extractions structurées ;
- des capacités de navigation enrichies ;
- des accès à des ressources externes et internes ;
- une orchestration multi-outils gouvernée par un point d'entrée unique.

## Serveurs MCP à appeler

`app` peut raisonnablement appeler tous les serveurs configurés, selon les cas :

- **`scrapegraph`** : scraping métier principal ;
- **`fetch`** : récupération simple d'URL ;
- **`playwright`** : cas dynamiques ou authentifiés ;
- **`filesystem`** : accès aux fichiers utiles au run ;
- **`memory`** : mémoire conversationnelle ou de workflow ;
- **`postgres`** : lecture/écriture d'état, historique, résultats ;
- **`github`** : consultation de dépôts, actions, sources externes.

## Entrées fournies

Entrées applicatives typiques :

- requête utilisateur ;
- `job_url` ;
- `cv_pdf_path` ;
- options de pipeline ;
- configuration de serveurs MCP ;
- instructions agentiques ;
- schémas de sortie attendus.

## Sorties attendues

- résultat d'orchestration ;
- étapes d'exécution ;
- contenu scrapé ;
- lettre générée ;
- fit assessment ;
- télémétrie fonctionnelle ;
- synthèse des outils appelés.

## Insertion dans le pipeline global

`app` est le point d'entrée de haut niveau :

- reçoit une demande depuis dashboard ou API externe ;
- choisit le mode d'exécution ;
- déclenche MCP si nécessaire ;
- retourne un résultat exploitable par les consommateurs front ou batch.

## Recommandation d'architecture pour `app`

Recommandation :

- **`app` doit rester le point d'orchestration principal** ;
- il peut parler :
  - directement à OpenAI Agents SDK pour exploiter les MCP,
  - mais devrait s'appuyer autant que possible sur `mcp_server/` pour les wrappers métier, les fallbacks et la normalisation.

Autrement dit :

- **direct MCP transport** possible dans `app` pour l'orchestration agentique ;
- **logique métier outillée** à centraliser dans `mcp_server/`.

C'est le meilleur compromis entre flexibilité et maîtrise.

---

## 5. `dashboard`

## Référence lue

- `dashboard/services/api_client.py`

## But du composant

`dashboard` est un client HTTP léger du backend :

- il interroge des routes d'API ;
- il affiche des métriques, statuts, runs, entités, historique LLM, état MCP, schéma DB.

Il n'est pas conçu comme consommateur direct des serveurs MCP.

## Ce qu'il cherche à obtenir via MCP

Indirectement, `dashboard` veut exposer :

- l'état des serveurs MCP ;
- les outils disponibles ;
- les résultats issus des pipelines outillés ;
- l'historique des runs utilisant des outils.

Mais il ne doit pas lui-même ouvrir une session MCP.

## Serveurs MCP à appeler

### En direct
Aucun.

### Indirectement via API
Tous peuvent être représentés dans l'UI si `app/` ou `mcp_server/` les expose.

## Entrées fournies

- actions utilisateur ;
- paramètres de formulaire ;
- requêtes HTTP vers `app/`.

## Sorties attendues

- JSON API consolidé ;
- visualisations ;
- statuts de santé ;
- aperçu de runs ;
- vue synthétique du paysage MCP.

## Insertion dans le pipeline global

`dashboard` intervient en façade :

1. déclenche le pipeline ;
2. affiche progression et résultats ;
3. présente la santé des intégrations.

## Recommandation d'architecture pour `dashboard`

Recommandation stricte :

> **`dashboard` ne doit jamais consommer directement les serveurs MCP tiers.**

Il doit exclusivement passer par :

- `app/` pour les opérations métier ;
- éventuellement des endpoints de statut consolidés exposés par `app/`.

Cela garantit :

- sécurité ;
- simplicité de déploiement ;
- absence de secrets MCP côté UI ;
- cohérence des retours fonctionnels.

---

## 6. `mcp_server`

## Rôle du composant

`mcp_server/` n'est pas seulement un serveur interne ; dans l'architecture cible, il devient aussi une **façade métier** et un **client contrôlé** vers les serveurs MCP tiers configurés dans `.vscode/mcp.json`.

C'est ici que l'on peut :

- encapsuler les transports ;
- définir des wrappers stables ;
- appliquer des politiques de fallback ;
- normaliser les erreurs ;
- exposer des outils métier cohérents pour le reste du projet.

## Ce qu'il cherche à obtenir via MCP

`mcp_server` cherche à transformer des outils génériques en capacités métier telles que :

- extraction d'offre d'emploi ;
- récupération markdown robuste ;
- navigation dynamique si nécessaire ;
- lecture/écriture de fichiers contrôlés ;
- persistance de résultats ;
- consultation de mémoire ;
- interrogation de GitHub ou PostgreSQL.

## Serveurs MCP à appeler

Tous les serveurs configurés sont pertinents ici :

- `scrapegraph`
- `filesystem`
- `github`
- `postgres`
- `fetch`
- `memory`
- `playwright`

## Entrées fournies

- URLs ;
- prompts d'extraction ;
- schémas JSON ;
- chemins de fichiers autorisés ;
- clés de recherche ;
- contextes de pipeline ;
- identifiants de runs.

## Sorties attendues

- réponses outillées normalisées ;
- artefacts métier ;
- erreurs homogènes ;
- provenance et traces d'exécution ;
- payloads directement consommables par `app`, `analyzer` ou `agent`.

## Insertion dans le pipeline global

`mcp_server` s'insère entre :

- les composants métier (`app`, `analyzer`, `agent`, plus marginalement `generator`) ;
- les serveurs MCP tiers.

Il devient la **couche anti-corruption** entre le domaine métier du projet et l'hétérogénéité des outils MCP externes.

## Recommandation d'architecture pour `mcp_server`

Recommandation forte :

- faire de `mcp_server/` le **point de passage privilégié** pour les opérations métier répétables ;
- réserver l'accès direct depuis `app/` aux cas où l'agent OpenAI doit manipuler les outils MCP de manière native et dynamique.

---

## Matrice détaillée par composant

## `agent`

| Élément | Description |
|---|---|
| But | Exécuter un agent OpenAI autour d'une offre et d'un CV |
| Ce qu'il veut via MCP | Scraper l'offre, enrichir le contexte, lire/écrire des artefacts, mémoriser l'état |
| Serveurs MCP plausibles | `scrapegraph`, `fetch`, `playwright`, `filesystem`, `memory`, éventuellement `github` |
| Entrées | `job_url`, `cv_text`, chemins de fichiers, instructions, contexte |
| Sorties | contenu scrapé, structure d'offre, notes intermédiaires, `AgentResult` |
| Place dans le pipeline | Alternative agentique aux pipelines batch ou exécuteur spécialisé |
| Recommandation | Passer par `app/` ou `mcp_server/` plutôt que parler à tous les MCP tiers directement |

## `analyzer`

| Élément | Description |
|---|---|
| But | Produire une analyse exploitable d'une offre et du profil candidat |
| Ce qu'il veut via MCP | Texte brut, markdown, extraction structurée, fallback de scraping, persistance |
| Serveurs MCP plausibles | `scrapegraph`, `fetch`, `playwright`, `filesystem`, `memory`, éventuellement `postgres` |
| Entrées | `job_url`, `cv_path`, texte CV, schémas, prompts |
| Sorties | `raw_job_text`, `job_offer_structured`, `job_json`, métadonnées de scraping |
| Place dans le pipeline | Préparation de la donnée pour la génération |
| Recommandation | Utiliser des wrappers métier via `mcp_server/` |

## `generator`

| Élément | Description |
|---|---|
| But | Générer des artefacts finaux à partir de données déjà préparées |
| Ce qu'il veut via MCP | Lecture de templates/artefacts, mémoire légère, persistance optionnelle |
| Serveurs MCP plausibles | `filesystem`, `memory`, éventuellement `fetch` ou `postgres` |
| Entrées | `job_data`, CV, prompt, options |
| Sorties | résultats de génération, fichiers JSON, artefacts texte |
| Place dans le pipeline | Étape finale de production |
| Recommandation | Pas d'accès direct MCP en standard ; accès utilitaire seulement via `mcp_server/` |

## `app`

| Élément | Description |
|---|---|
| But | Orchestrer les traitements API et les workflows outillés |
| Ce qu'il veut via MCP | Appels outillés pilotés par planification, scraping, navigation, accès ressources |
| Serveurs MCP plausibles | Tous selon le besoin |
| Entrées | questions utilisateur, URLs, chemins de CV, options, configs MCP |
| Sorties | résultats d'orchestration, étapes, contenus, artefacts générés |
| Place dans le pipeline | Point d'entrée principal |
| Recommandation | Garder `app` comme orchestrateur MCP principal, avec logique métier centralisée dans `mcp_server/` |

## `dashboard`

| Élément | Description |
|---|---|
| But | Déclencher, superviser et visualiser les pipelines |
| Ce qu'il veut via MCP | Rien en direct ; seulement des données déjà consolidées |
| Serveurs MCP plausibles | Aucun en direct |
| Entrées | actions UI, payloads HTTP |
| Sorties | visualisations, statuts, tableaux de bord |
| Place dans le pipeline | Façade utilisateur |
| Recommandation | API only, jamais de connexion directe MCP |

## `mcp_server`

| Élément | Description |
|---|---|
| But | Façade métier et couche de normalisation vers MCP tiers |
| Ce qu'il veut via MCP | Exécuter les outils tiers de façon contrôlée et réutilisable |
| Serveurs MCP plausibles | Tous les serveurs configurés |
| Entrées | URLs, schémas, prompts, chemins, contextes, identifiants |
| Sorties | réponses homogènes, erreurs normalisées, wrappers métier |
| Place dans le pipeline | Couche d'intégration centrale |
| Recommandation | Point de passage privilégié pour les usages métier répétables |

---

## Cartographie recommandée des responsabilités

## Accès direct autorisé aux serveurs MCP tiers

À limiter aux composants suivants :

- **`mcp_server/`** : oui, c'est sa mission ;
- **`app/`** : oui, mais surtout pour les cas d'orchestration agentique native via OpenAI Agents SDK.

## Accès indirect recommandé via `mcp_server/`

Pour les composants suivants :

- **`agent/`**
- **`analyzer/`**
- **`generator/`**

Ces composants devraient idéalement consommer des **capacités métier stables**, pas des outils MCP bruts.

## Aucun accès direct MCP

Pour :

- **`dashboard/`**

---

## Schéma cible simplifié

```text
dashboard
   │
   ▼
app (API + orchestration)
   │
   ├── direct MCP via OpenAI Agents SDK, si orchestration agentique native requise
   │
   └── mcp_server (façade métier interne)
           │
           ├── scrapegraph
           ├── fetch
           ├── playwright
           ├── filesystem
           ├── memory
           ├── postgres
           └── github
```

---

## Décisions d'architecture recommandées

### 1. Faire de `app/` le point d'entrée MCP principal
`app` possède déjà les patterns d'orchestration les plus explicites. Il doit rester le contrôleur principal des usages outillés déclenchés par API.

### 2. Faire de `mcp_server/` la couche de stabilisation
`mcp_server/` devrait encapsuler les opérations métier récurrentes afin d'éviter que chaque composant manipule directement les outils MCP tiers et leurs subtilités.

### 3. Éviter la dispersion des clients MCP
Si `agent`, `analyzer` et `generator` implémentent chacun leurs propres accès MCP, le projet risque :
- des logiques de fallback dupliquées ;
- des schémas de sortie divergents ;
- une gouvernance des secrets plus complexe ;
- une observabilité fragmentée.

### 4. Réserver l'accès MCP direct aux besoins réellement agentiques
L'accès direct à des serveurs MCP tiers reste pertinent quand un agent piloté par modèle doit choisir dynamiquement ses outils. Ce besoin concerne surtout `app/` via OpenAI Agents SDK, et plus marginalement `agent/`.

### 5. Conserver `dashboard` comme consommateur API uniquement
Le dashboard doit rester un client de l'API, jamais un client d'infrastructure MCP.

---

## Conclusion

Le projet présente déjà une direction claire :

- **`app/` orchestre** ;
- **`mcp_server/` encapsule** ;
- **`analyzer/` analyse** ;
- **`generator/` produit** ;
- **`dashboard/` visualise** ;
- **`agent/` expérimente ou spécialise**.

La matrice cible recommandée est donc :

- **MCP direct** : `app`, `mcp_server`
- **MCP indirect via façade interne** : `agent`, `analyzer`, `generator`
- **Pas de MCP direct** : `dashboard`

Cette répartition limite le couplage, améliore la testabilité, rend les transports interchangeables et prépare mieux le projet à une évolution vers une architecture MCP réellement industrialisée.