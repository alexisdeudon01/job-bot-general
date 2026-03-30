# Synthèse d'inspection du dashboard

## Fichiers inspectés
- `dashboard/app.py`
- `dashboard/requirements.txt`

## Modifications
Aucune modification du code existant n'a été effectuée.  
Ce rapport a été créé pour consigner l'inspection demandée.

## 1. Nature du dashboard actuel

Le dashboard actuel est une application **Streamlit monolithique** contenue dans `dashboard/app.py`.

Il cumule plusieurs rôles :
- interface utilisateur,
- orchestration locale,
- exécution des scripts métiers via `subprocess`,
- visualisation des fichiers JSON de sortie,
- affichage de logs de session,
- documentation technique intégrée sous forme de diagrammes textuels.

Il ne fonctionne pas comme un front découplé d'une API.  
Au contraire, il dépend directement :
- du système de fichiers,
- de chemins internes du projet,
- de l'exécution locale de scripts Python.

## 2. Dépendances déclarées

Contenu actuel de `dashboard/requirements.txt` :
- `streamlit`
- `pypdf2`
- `anthropic`
- `openai`
- `requests`
- `beautifulsoup4`
- `spacy`
- `python-dotenv`

### Observation
Dans `dashboard/app.py`, seule `streamlit` est utilisée directement.

Les autres dépendances semblent relever de la logique métier ou d'anciens besoins :
- LLM,
- scraping,
- parsing PDF,
- NLP.

Cela montre un **mauvais découplage des responsabilités** : le dashboard embarque des dépendances qui devraient plutôt appartenir aux microservices analyzer/generator ou à des services backend.

## 3. Composants UI existants

### 3.1 Configuration générale
- `st.set_page_config(page_title="Job Bot Dashboard", layout="wide")`
- application mono-page,
- aucun système de navigation multi-pages,
- pas de thème avancé ni de composants séparés.

### 3.2 État de session
Fonction `init_session_state()` :
- `dashboard_logs`
- `last_run_at`
- `last_refresh_at`
- `job_url`
- `last_action_status`
- `last_command_details`

#### Limite
L'état est **volatile** et stocké uniquement dans `st.session_state`.  
Aucune persistance en base.

### 3.3 Entrées utilisateur
Dans la zone de pilotage :
- champ texte pour l'URL d'offre,
- upload de CV (`txt` ou `pdf`),
- bouton de sauvegarde du CV,
- bouton d'enregistrement de l'URL en session.

### 3.4 Progression
Deux barres de progression :
- analyse,
- génération.

La progression est calculée à partir de l'existence de fichiers, pas à partir d'événements métier persistés.

### 3.5 Actions
Deux boutons :
- `Analyser`
- `Générer Europass`

Ils déclenchent l'exécution de scripts Python locaux via `subprocess.run`.

### 3.6 Statut providers
La fonction `render_provider_status()` affiche :
- présence de clé Anthropic,
- présence de clé OpenAI,
- fournisseur préféré,
- extraits masqués de clés.

#### Limite
Cette vérification ne teste pas réellement la connectivité distante, seulement la présence de variables d'environnement.

### 3.7 Statut fichiers
Le dashboard affiche l'état de plusieurs fichiers attendus :
- CV PDF,
- CV texte,
- données d'analyse,
- résultats de génération.

#### Limite
L'état du système est dérivé du filesystem, pas d'une source de vérité métier.

### 3.8 Visualisation JSON
La fonction `render_json_panel()` affiche :
- type de structure,
- nombre d'éléments racine,
- clés principales,
- structure inférée,
- contenu JSON brut.

#### Point fort
Utile pour le debug.

#### Limite
L'interface reste orientée **fichiers bruts**, pas **entités métier**.

### 3.9 Logs
La fonction `render_logs_panel()` fournit :
- bouton d'actualisation,
- bouton d'effacement,
- affichage des logs de session,
- capture stdout/stderr des scripts exécutés.

#### Limite
Pas de persistance, pas de recherche, pas de filtrage avancé, pas de vrai flux live backend.

### 3.10 Diagrammes textuels
La fonction `render_text_diagrams()` affiche :
- architecture globale,
- pipeline d'exécution,
- détail MCP.

#### Limite
Ces schémas sont :
- statiques,
- codés en dur,
- non interactifs,
- non dérivés des composants réels.

### 3.11 Zone technique d'exécution
Affiche :
- chemins des scripts attendus,
- Python utilisé,
- état de quelques indicateurs,
- dernier statut d'exécution.

#### Nature
C'est une vue de debug/exploitation locale, pas un dashboard produit moderne.

## 4. Architecture actuelle observée

Le dashboard dépend de chemins codés en dur :
- `/data`
- `/output`
- `/app`

Constantes utilisées :
- `CV_PDF_PATH`
- `CV_TXT_PATH`
- `JOB_DATA_PATH`
- `GENERATION_RESULTS_PATH`
- `ANALYZER_SCRIPT_PATH`
- `GENERATOR_SCRIPT_PATH`

### Problème clé
Le dashboard lance directement les traitements :
- analyzer
- generator

via `subprocess.run(...)`.

Cela signifie :
- fort couplage à l'environnement local,
- absence de backend orchestrateur séparé,
- pas d'API-first,
- pas de communication inter-services propre.

## 5. Ce qu'il faut casser / refaire

### À casser
Il faut refondre ou supprimer ces choix structurels :
- exécution directe des scripts métiers par l'UI,
- dépendance aux chemins internes des scripts,
- dépendance primaire au filesystem,
- stockage exclusif de l'état dans `st.session_state`,
- logs uniquement mémoire,
- diagrammes codés en dur,
- UX purement procédurale "upload + bouton + lecture JSON".

### À conserver comme intention
Il faut garder, mais réimplémenter proprement :
- pilotage du pipeline,
- visibilité sur les providers,
- visualisation des résultats,
- observabilité des exécutions,
- upload de documents,
- documentation de l'architecture.

## 6. Refonte cible pour un dashboard plus joli

Le dashboard futur devrait devenir :
- plus visuel,
- multi-vues,
- orienté entités,
- connecté à une API,
- alimenté en temps réel,
- branché sur une base de données.

### UX recommandée
Prévoir :
- barre latérale de navigation,
- pages séparées,
- cartes KPI,
- statuts visuels harmonisés,
- tableaux filtrables,
- timeline des exécutions,
- détails par entité,
- graphes d'activité,
- panneaux de logs filtrables,
- états globaux plus lisibles.

### Pages/vues à prévoir
- Vue d'ensemble
- Offres d'emploi
- Candidatures / runs
- Documents / artefacts
- Providers IA
- Logs / événements
- GitHub Actions
- Diagrammes système
- Administration / configuration

## 7. Refonte API-first

Le dashboard ne doit plus :
- exécuter directement des scripts Python,
- dépendre du layout de fichiers du conteneur,
- considérer les fichiers JSON comme protocole principal.

Le dashboard doit :
- appeler des endpoints HTTP,
- recevoir des événements temps réel,
- lire l'état via une API et une base de données,
- consulter les fichiers générés comme artefacts secondaires.

### Endpoints cibles suggérés
Exemples d'API à exposer côté backend :
- `POST /jobs/analyze`
- `POST /jobs/generate`
- `GET /runs`
- `GET /runs/{id}`
- `GET /jobs`
- `GET /jobs/{id}`
- `GET /artifacts`
- `GET /artifacts/{id}`
- `GET /providers/status`
- `GET /events/stream`
- `GET /metrics/summary`
- `GET /github-actions/runs`
- `GET /system/components`
- `GET /system/diagrams`

## 8. Flux en direct

### Situation actuelle
Il n'existe pas de live stream réel.  
Le dashboard :
- lance un traitement bloquant,
- lit stdout/stderr,
- met à jour des variables de session,
- nécessite un refresh Streamlit.

### Refonte nécessaire
Prévoir un backend publiant des événements :
- `run.created`
- `run.started`
- `run.progress`
- `run.log`
- `run.completed`
- `run.failed`
- `artifact.created`
- `provider.checked`

### Côté UI
Il faut :
- une console live,
- une timeline de run,
- des progrès temps réel,
- une mise à jour automatique des listes et métriques.

## 9. Graphes GitHub Actions

### Actuel
Aucun graphe GitHub Actions n'existe aujourd'hui.

### À ajouter
Une vue CI/CD avec :
- historique des workflows,
- statut des runs,
- durée,
- taux de succès,
- détail jobs,
- tendances,
- liens vers GitHub.

### Visualisations utiles
- histogrammes des statuts,
- courbes de durée,
- répartition succès/échec,
- tableau détaillé des exécutions.

## 10. Diagrammes des composants

### Limite actuelle
Les diagrammes sont purement textuels et statiques.

### Refonte recommandée
Créer des vues dédiées :
- diagramme composants,
- diagramme flux de données,
- diagramme microservices,
- diagramme dépendances externes,
- diagramme pipeline,
- diagramme observabilité.

### Caractéristiques souhaitées
- interactifs,
- générés à partir d'une source structurée,
- zoomables,
- exportables,
- cohérents avec l'état réel du système.

## 11. Vues entités à introduire

Le dashboard actuel n'a pas de modèle entité explicite.

### Entités recommandées
- `JobPosting`
- `CandidateProfile`
- `AnalysisRun`
- `GenerationRun`
- `Artifact`
- `ProviderStatus`
- `WorkflowEvent`
- `GithubActionRun`

### Vues associées
- liste des offres,
- détail d'offre,
- historique des analyses,
- détail d'analyse,
- historique des générations,
- détail d'artefact,
- événements système,
- état des providers,
- historique CI/CD.

## 12. Stockage base de données

### Situation actuelle
Aucune DB.  
L'état repose sur :
- fichiers,
- session Streamlit,
- structure locale du conteneur.

### À stocker en DB
- offres d'emploi,
- historiques de runs,
- événements,
- logs structurés,
- métadonnées des artefacts,
- snapshots des providers,
- informations GitHub Actions,
- statut des workflows.

### Peut rester en stockage fichier / objet
- PDF,
- documents générés,
- exports JSON,
- autres artefacts binaires.

### Conclusion DB
La DB doit devenir la source de vérité des entités et des exécutions.  
Le filesystem ne doit plus être le protocole principal.

## 13. Conclusion

Le dashboard actuel est utile comme interface locale de debug et de pilotage, mais il présente plusieurs limites fortes :
- monolithique,
- couplé au filesystem,
- couplé à l'exécution locale,
- sans base de données,
- sans API-first,
- sans temps réel robuste,
- sans vues métier,
- sans graphes CI,
- avec diagrammes statiques,
- avec dépendances trop larges pour une simple UI.

La refonte doit aller vers un dashboard :
- découplé,
- orienté API,
- orienté entités,
- alimenté par événements,
- persistant,
- plus visuel,
- plus modulaire,
- plus exploitable.

## 14. Note de coordination
Ce rapport ne modifie aucun contrat partagé.  
Aucun endpoint, export de code, interface Python ou composant réutilisable n'a été ajouté dans cette étape.