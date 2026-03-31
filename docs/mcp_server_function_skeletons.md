# Spécification détaillée des squelettes fonctionnels MCP

## Objectif du document

Ce document décrit un **catalogue de fonctions/outils MCP attendus** pour le projet `job-bot-general`, à partir :

- de la configuration locale dans `.vscode/mcp.json`
- du serveur MCP interne dans `mcp_server/`
- des wrappers déjà présents dans `mcp_server/transport/tools.py`
- des capacités ScrapeGraph déjà modélisées dans `mcp_server/services/scrapegraph_service.py`
- de l’adaptateur stdio dans `mcp_server/clients/scrapegraph_stdio_client.py`

L’objectif est de fournir une **spécification de référence**, non exécutable, pour :

1. distinguer les **outils standards** exposés par les serveurs MCP tiers ;
2. proposer les **wrappers métier** à implémenter ou stabiliser dans `mcp_server/` ;
3. converger vers une **API MCP métier unifiée** adaptée au pipeline de recherche, analyse et génération de candidatures.

---

## Contexte actuel

### Serveurs MCP configurés

D’après `.vscode/mcp.json`, les serveurs MCP actifs ou prévus sont :

- `io.github.ScrapeGraphAI/scrapegraph-mcp`
- `filesystem`
- `github`
- `postgres`
- `fetch`
- `memory`
- `playwright`

### Serveur MCP interne

Le serveur interne `mcp_server/main.py` expose aujourd’hui un serveur `FastMCP("job-bot-mcp")` et enregistre des outils via `register_tools(...)`.

Les outils déjà visibles dans `mcp_server/transport/tools.py` sont :

- `analyze_job`
- `generate_documents`
- `run_full_pipeline`
- `scrapegraph_extract`
- `scrapegraph_extract_job_offer`
- `scrapegraph_company_hiring_intelligence`
- `scrapegraph_markdownify`
- `infer_entities`
- `enrich_entities`

### Conclusion architecturale immédiate

Le projet a déjà commencé à adopter le bon modèle :

- **les serveurs tiers MCP fournissent des primitives génériques**
- **`mcp_server/` doit fournir les wrappers métier stables**
- **les clients du projet devraient préférer l’API métier interne plutôt que de dépendre directement des contrats volatils des serveurs tiers**

---

# 1. Principes de conception du catalogue

## 1.1 Distinction fondamentale

Pour chaque serveur, on distingue :

### A. Outils standards tiers
Ce sont les outils “bruts” fournis par l’écosystème MCP ou attendus d’après la documentation/usage courant du serveur.

Usage recommandé :
- exploration
- debug
- opérations techniques
- cas avancés non encore encapsulés

### B. Wrappers métier recommandés dans `mcp_server/`
Ce sont des outils à **nommage stable orienté produit**, conçus pour :
- masquer l’hétérogénéité des serveurs tiers
- normaliser les entrées/sorties
- gérer les erreurs de manière cohérente
- aligner les résultats sur le pipeline métier du projet

---

## 1.2 Convention de schéma utilisée ici

Les schémas ci-dessous sont décrits dans un format inspiré de JSON Schema simplifié :

- `type`
- `properties`
- `required`
- `items`

Ils servent de **contrat documentaire**, pas de validation stricte exécutable.

---

## 1.3 Convention de sortie unifiée recommandée

Pour les wrappers métier exposés par `mcp_server/`, il est recommandé d’uniformiser la forme des réponses autour de :

```json
{
  "status": "success",
  "data": {},
  "meta": {
    "source": "scrapegraph|filesystem|github|postgres|fetch|memory|playwright|orchestrator",
    "tool": "tool_name",
    "duration_ms": 0
  },
  "errors": []
}
```

En cas d’échec :

```json
{
  "status": "error",
  "data": null,
  "meta": {
    "source": "scrapegraph",
    "tool": "scrapegraph_extract_job_offer"
  },
  "errors": [
    {
      "code": "INVALID_URL",
      "message": "url must be a valid HTTP(S) URL"
    }
  ]
}
```

Le code actuel retourne souvent simplement `{"error": "..."}` ; ce document recommande une évolution graduelle vers un contrat plus stable.

---

# 2. Serveur `io.github.ScrapeGraphAI/scrapegraph-mcp`

## 2.1 Rôle dans le projet

Ce serveur est dédié à :
- l’extraction structurée depuis une page web
- la transformation de page en markdown
- la recherche web multi-sources
- potentiellement le crawl multi-pages avancé

Il est central pour :
- l’analyse d’offres d’emploi
- la recherche d’intelligence employeur
- la collecte de signaux marché

---

## 2.2 Outils standards tiers attendus

Les outils standardisés ici s’appuient directement sur ce qui est déjà modélisé dans :

- `ScrapeGraphToolPlanner.OFFICIAL_TOOL_DEFINITIONS`
- `ScrapeGraphStdioClient._tools`

---

### 2.2.1 `markdownify`

**But**  
Transformer une page web en markdown exploitable en downstream.

**Description**  
Récupère une page distante et renvoie une représentation markdown plus propre qu’un HTML brut.

**Input schema**
```json
{
  "type": "object",
  "properties": {
    "website_url": { "type": "string", "description": "URL HTTP(S) de la page cible" }
  },
  "required": ["website_url"]
}
```

**Output schema**
```json
{
  "type": "object",
  "properties": {
    "url": { "type": "string" },
    "markdown": { "type": "string" }
  }
}
```

**Erreurs possibles**
- URL invalide
- page inaccessible
- API key ScrapeGraph absente
- timeout fournisseur
- limitation de quota

**Exemple d’appel**
```json
{
  "website_url": "https://company.example/jobs/backend-engineer"
}
```

**Exemple de résultat**
```json
{
  "url": "https://company.example/jobs/backend-engineer",
  "markdown": "# Backend Engineer\n\nCompany: Example Corp\n\nResponsibilities:\n- Build APIs\n- Improve reliability"
}
```

---

### 2.2.2 `smartscraper`

**But**  
Extraire des données structurées d’une seule page à partir d’un prompt.

**Description**  
Outil principal d’extraction page unique. Le prompt guide l’extraction ; un schéma de sortie peut être fourni.

**Input schema**
```json
{
  "type": "object",
  "properties": {
    "website_url": { "type": "string" },
    "user_prompt": { "type": "string" },
    "output_schema": { "type": "object" },
    "number_of_scrolls": { "type": "integer" },
    "markdown_only": { "type": "boolean" }
  },
  "required": ["website_url", "user_prompt"]
}
```

**Output schema**
```json
{
  "type": "object",
  "properties": {
    "url": { "type": "string" },
    "result": { "type": "object" }
  }
}
```

**Erreurs possibles**
- prompt vide
- URL invalide
- schéma incompatible
- contenu insuffisant
- erreur fournisseur

**Exemple d’appel**
```json
{
  "website_url": "https://company.example/jobs/backend-engineer",
  "user_prompt": "Extract job title, company, location, requirements and technologies.",
  "output_schema": {
    "job_title": "string",
    "company_name": "string",
    "location": "string",
    "requirements": ["string"],
    "technologies": ["string"]
  }
}
```

**Exemple de résultat**
```json
{
  "url": "https://company.example/jobs/backend-engineer",
  "result": {
    "job_title": "Backend Engineer",
    "company_name": "Example Corp",
    "location": "Paris",
    "requirements": ["3+ years Python", "API design"],
    "technologies": ["Python", "FastAPI", "PostgreSQL"]
  }
}
```

---

### 2.2.3 `searchscraper`

**But**  
Rechercher sur le web et agréger une extraction structurée multi-sources.

**Description**  
Convient aux cas où l’on ne part pas d’une seule URL mais d’une question de recherche.

**Input schema**
```json
{
  "type": "object",
  "properties": {
    "user_prompt": { "type": "string" },
    "num_results": { "type": "integer" },
    "number_of_scrolls": { "type": "integer" },
    "time_range": { "type": "string" },
    "output_schema": { "type": "object" }
  },
  "required": ["user_prompt"]
}
```

**Output schema**
```json
{
  "type": "object",
  "properties": {
    "query": { "type": "string" },
    "result": { "type": "object" }
  }
}
```

**Erreurs possibles**
- prompt vide
- quota atteint
- recherche sans résultats
- schéma mal adapté
- timeout fournisseur

**Exemple d’appel**
```json
{
  "user_prompt": "Research Example Corp hiring signals for backend engineering roles in Paris.",
  "num_results": 5,
  "time_range": "30d",
  "output_schema": {
    "company_name": "string",
    "hiring_signals": ["string"],
    "recent_news": ["string"],
    "sources": ["string"]
  }
}
```

**Exemple de résultat**
```json
{
  "query": "Research Example Corp hiring signals for backend engineering roles in Paris.",
  "result": {
    "company_name": "Example Corp",
    "hiring_signals": ["Multiple backend openings on careers page", "Recent engineering hiring post on LinkedIn"],
    "recent_news": ["Series B funding announced"],
    "sources": ["https://example.com/careers", "https://linkedin.com/..."]
  }
}
```

---

### 2.2.4 `scrape`

**But**  
Récupérer du contenu de page, éventuellement avec rendu JavaScript.

**Description**  
Primitive technique plus bas niveau que `smartscraper`.

**Input schema**
```json
{
  "type": "object",
  "properties": {
    "website_url": { "type": "string" },
    "render_heavy_js": { "type": "boolean" }
  },
  "required": ["website_url"]
}
```

**Output schema attendu**
```json
{
  "type": "object",
  "properties": {
    "content": { "type": "string" },
    "metadata": { "type": "object" }
  }
}
```

**Erreurs possibles**
- URL invalide
- JS rendering impossible
- page bloquée
- timeout

**Exemple d’appel**
```json
{
  "website_url": "https://example.com/jobs",
  "render_heavy_js": true
}
```

**Exemple de résultat**
```json
{
  "content": "<html>...</html>",
  "metadata": {
    "final_url": "https://example.com/jobs",
    "rendered": true
  }
}
```

**État projet actuel**  
Dans `scrapegraph_stdio_client.py`, cet outil est **listé mais non implémenté réellement**.

---

### 2.2.5 `sitemap`

**But**  
Lister le sitemap ou la structure d’un site.

**Description**  
Utile pour découvrir des pages carrières, pages équipes, pages employeur.

**Input schema**
```json
{
  "type": "object",
  "properties": {
    "website_url": { "type": "string" }
  },
  "required": ["website_url"]
}
```

**Output schema attendu**
```json
{
  "type": "object",
  "properties": {
    "sitemap_urls": {
      "type": "array",
      "items": { "type": "string" }
    }
  }
}
```

**Erreurs possibles**
- domaine sans sitemap
- site inaccessible
- format sitemap invalide

**Exemple d’appel**
```json
{
  "website_url": "https://example.com"
}
```

**Exemple de résultat**
```json
{
  "sitemap_urls": [
    "https://example.com/sitemap.xml",
    "https://example.com/careers",
    "https://example.com/jobs"
  ]
}
```

**État projet actuel**  
Listé mais non implémenté réellement dans l’adaptateur stdio local.

---

### 2.2.6 `smartcrawler_initiate`

**But**  
Lancer un crawl multi-pages asynchrone.

**Description**  
Approprié pour des parcours plus larges : carrière, blog employeur, presse, etc.

**Input schema**
```json
{
  "type": "object",
  "properties": {
    "url": { "type": "string" },
    "prompt": { "type": "string" },
    "extraction_mode": { "type": "string" },
    "depth": { "type": "integer" },
    "max_pages": { "type": "integer" },
    "same_domain_only": { "type": "boolean" }
  },
  "required": ["url"]
}
```

**Output schema attendu**
```json
{
  "type": "object",
  "properties": {
    "request_id": { "type": "string" },
    "status": { "type": "string" }
  }
}
```

**Erreurs possibles**
- URL invalide
- crawl refusé par le fournisseur
- paramètres hors limites
- timeout de démarrage

**Exemple d’appel**
```json
{
  "url": "https://example.com",
  "prompt": "Find all careers and engineering hiring related pages.",
  "depth": 2,
  "max_pages": 20,
  "same_domain_only": true
}
```

**Exemple de résultat**
```json
{
  "request_id": "crawl_req_12345",
  "status": "started"
}
```

**État projet actuel**  
Listé mais non implémenté réellement.

---

### 2.2.7 `smartcrawler_fetch_results`

**But**  
Récupérer les résultats d’un crawl asynchrone.

**Input schema**
```json
{
  "type": "object",
  "properties": {
    "request_id": { "type": "string" }
  },
  "required": ["request_id"]
}
```

**Output schema attendu**
```json
{
  "type": "object",
  "properties": {
    "request_id": { "type": "string" },
    "status": { "type": "string" },
    "pages": {
      "type": "array",
      "items": { "type": "object" }
    }
  }
}
```

**Erreurs possibles**
- request_id inconnu
- crawl encore en cours
- résultats expirés

**Exemple d’appel**
```json
{
  "request_id": "crawl_req_12345"
}
```

**Exemple de résultat**
```json
{
  "request_id": "crawl_req_12345",
  "status": "completed",
  "pages": [
    {
      "url": "https://example.com/careers",
      "title": "Careers",
      "summary": "Open engineering roles"
    }
  ]
}
```

**État projet actuel**  
Listé mais non implémenté réellement.

---

### 2.2.8 `agentic_scrapper`

**But**  
Exécuter des workflows avancés d’extraction agentique.

**Description**  
Outil potentiellement puissant mais plus complexe, donc à réserver aux cas où les wrappers simples ne suffisent pas.

**Input schema**
```json
{
  "type": "object",
  "properties": {
    "url": { "type": "string" },
    "user_prompt": { "type": "string" },
    "output_schema": { "type": "object" },
    "steps": { "type": "array", "items": { "type": "object" } },
    "ai_extraction": { "type": "boolean" },
    "persistent_session": { "type": "boolean" },
    "timeout_seconds": { "type": "number" }
  },
  "required": ["url"]
}
```

**Output schema attendu**
```json
{
  "type": "object",
  "properties": {
    "result": { "type": "object" },
    "trace": { "type": "array", "items": { "type": "object" } }
  }
}
```

**Erreurs possibles**
- workflow invalide
- session non persistable
- timeout
- erreur LLM/extraction

**Exemple d’appel**
```json
{
  "url": "https://example.com/careers",
  "user_prompt": "Find backend roles and extract application links.",
  "output_schema": {
    "roles": [
      {
        "title": "string",
        "application_url": "string"
      }
    ]
  }
}
```

**Exemple de résultat**
```json
{
  "result": {
    "roles": [
      {
        "title": "Backend Engineer",
        "application_url": "https://example.com/jobs/backend"
      }
    ]
  },
  "trace": [
    {
      "step": "page_load",
      "status": "ok"
    }
  ]
}
```

**État projet actuel**  
Listé mais non implémenté réellement.

---

## 2.3 Wrappers métier recommandés dans `mcp_server/`

---

### 2.3.1 `scrapegraph_markdownify`

**Statut**
Déjà présent dans `mcp_server/transport/tools.py`.

**But**  
Wrapper métier stable autour de `markdownify`.

**Description**  
Normalise le nommage d’entrée (`url` au lieu de `website_url`) et le contrat de sortie pour les composants internes.

**Input schema**
```json
{
  "type": "object",
  "properties": {
    "url": { "type": "string" }
  },
  "required": ["url"]
}
```

**Output schema**
```json
{
  "type": "object",
  "properties": {
    "url": { "type": "string" },
    "markdown": { "type": "string" }
  }
}
```

**Erreurs possibles**
- `INVALID_URL`
- `SCRAPEGRAPH_CONFIGURATION_ERROR`
- `SCRAPEGRAPH_REQUEST_ERROR`

**Exemple d’appel**
```json
{
  "url": "https://company.example/jobs/backend-engineer"
}
```

**Exemple de résultat**
```json
{
  "url": "https://company.example/jobs/backend-engineer",
  "markdown": "# Backend Engineer\n..."
}
```

---

### 2.3.2 `scrapegraph_extract`

**Statut**
Déjà présent.

**But**  
Wrapper métier d’extraction structurée page unique.

**Description**  
Exposition stable du couple `(url, prompt, schema)`.

**Input schema**
```json
{
  "type": "object",
  "properties": {
    "url": { "type": "string" },
    "prompt": { "type": "string" },
    "schema": { "type": "object" }
  },
  "required": ["url", "prompt"]
}
```

**Output schema**
```json
{
  "type": "object",
  "properties": {
    "url": { "type": "string" },
    "result": { "type": "object" }
  }
}
```

**Erreurs possibles**
- `INVALID_URL`
- `INVALID_PROMPT`
- `SCRAPEGRAPH_REQUEST_ERROR`

**Exemple d’appel**
```json
{
  "url": "https://company.example/jobs/backend-engineer",
  "prompt": "Extract title, location and requirements.",
  "schema": {
    "title": "string",
    "location": "string",
    "requirements": ["string"]
  }
}
```

**Exemple de résultat**
```json
{
  "url": "https://company.example/jobs/backend-engineer",
  "result": {
    "title": "Backend Engineer",
    "location": "Paris",
    "requirements": ["Python", "APIs"]
  }
}
```

---

### 2.3.3 `scrapegraph_extract_job_offer`

**Statut**
Déjà présent.

**But**  
Extraire une offre d’emploi vers un schéma métier standard du projet.

**Description**  
Wrapper fortement recommandé pour éviter que chaque client reformule son propre prompt et son propre schéma.

**Input schema**
```json
{
  "type": "object",
  "properties": {
    "url": { "type": "string" }
  },
  "required": ["url"]
}
```

**Output schema**
```json
{
  "type": "object",
  "properties": {
    "url": { "type": "string" },
    "result": {
      "type": "object",
      "properties": {
        "job_title": { "type": "string" },
        "company_name": { "type": "string" },
        "location": { "type": "string" },
        "employment_type": { "type": "string" },
        "seniority_level": { "type": "string" },
        "salary": { "type": "string" },
        "remote_policy": { "type": "string" },
        "recruiter_name": { "type": "string" },
        "application_url": { "type": "string" },
        "posted_at": { "type": "string" },
        "technologies": { "type": "array", "items": { "type": "string" } },
        "responsibilities": { "type": "array", "items": { "type": "string" } },
        "requirements": { "type": "array", "items": { "type": "string" } },
        "benefits": { "type": "array", "items": { "type": "string" } },
        "languages": { "type": "array", "items": { "type": "string" } },
        "summary": { "type": "string" }
      }
    }
  }
}
```

**Erreurs possibles**
- `INVALID_URL`
- `SCRAPEGRAPH_REQUEST_ERROR`
- extraction incomplète ou vide

**Exemple d’appel**
```json
{
  "url": "https://company.example/jobs/backend-engineer"
}
```

**Exemple de résultat**
```json
{
  "url": "https://company.example/jobs/backend-engineer",
  "result": {
    "job_title": "Backend Engineer",
    "company_name": "Example Corp",
    "location": "Paris",
    "employment_type": "Full-time",
    "seniority_level": "Mid-Senior",
    "salary": "",
    "remote_policy": "Hybrid",
    "recruiter_name": "",
    "application_url": "https://company.example/jobs/backend-engineer/apply",
    "posted_at": "2026-03-10",
    "technologies": ["Python", "FastAPI", "PostgreSQL"],
    "responsibilities": ["Build APIs", "Collaborate with product"],
    "requirements": ["3+ years experience", "Cloud knowledge"],
    "benefits": ["Health insurance"],
    "languages": ["English"],
    "summary": "Backend role focused on scalable APIs."
  }
}
```

---

### 2.3.4 `scrapegraph_company_hiring_intelligence`

**Statut**
Déjà présent.

**But**  
Produire une vue synthétique de signaux de recrutement sur une entreprise.

**Description**  
Wrapper métier clé pour la préparation de candidature, la recherche contextuelle et l’enrichissement d’entités.

**Input schema**
```json
{
  "type": "object",
  "properties": {
    "company_name": { "type": "string" },
    "role_focus": { "type": "string" },
    "location": { "type": "string" },
    "num_results": { "type": "integer", "default": 5 },
    "time_range": { "type": "string", "default": "30d" }
  },
  "required": ["company_name"]
}
```

**Output schema**
```json
{
  "type": "object",
  "properties": {
    "query": { "type": "string" },
    "result": {
      "type": "object",
      "properties": {
        "company_name": { "type": "string" },
        "company_summary": { "type": "string" },
        "hiring_signals": { "type": "array", "items": { "type": "string" } },
        "recent_news": { "type": "array", "items": { "type": "string" } },
        "open_roles_signals": { "type": "array", "items": { "type": "string" } },
        "tech_stack_signals": { "type": "array", "items": { "type": "string" } },
        "candidate_angle": { "type": "array", "items": { "type": "string" } },
        "sources": { "type": "array", "items": { "type": "string" } }
      }
    }
  }
}
```

**Erreurs possibles**
- `INVALID_COMPANY_NAME`
- `SCRAPEGRAPH_REQUEST_ERROR`

**Exemple d’appel**
```json
{
  "company_name": "Example Corp",
  "role_focus": "backend engineering",
  "location": "Paris",
  "num_results": 5,
  "time_range": "30d"
}
```

**Exemple de résultat**
```json
{
  "query": "Research the company Example Corp for job-search intelligence...",
  "result": {
    "company_name": "Example Corp",
    "company_summary": "B2B SaaS company scaling its platform team.",
    "hiring_signals": ["New engineering roles posted", "Platform hiring mentioned in press release"],
    "recent_news": ["Raised Series B"],
    "open_roles_signals": ["Backend", "DevOps", "Data"],
    "tech_stack_signals": ["Python", "AWS", "PostgreSQL"],
    "candidate_angle": ["Emphasize scalability experience", "Mention API reliability projects"],
    "sources": ["https://example.com/careers", "https://news.example.com/article"]
  }
}
```

---

### 2.3.5 `scrapegraph_search_extract`

**Statut**
Présent dans `ScrapeGraphStdioClient`, mais pas encore exposé comme outil FastMCP dans `transport/tools.py`.

**But**  
Offrir un wrapper métier générique de recherche web structurée.

**Description**  
Ce wrapper serait utile pour des besoins d’analyse variés hors entreprise/offre d’emploi.

**Input schema**
```json
{
  "type": "object",
  "properties": {
    "prompt": { "type": "string" },
    "schema": { "type": "object" },
    "num_results": { "type": "integer" },
    "time_range": { "type": "string" },
    "location": { "type": "string" }
  },
  "required": ["prompt"]
}
```

**Output schema**
```json
{
  "type": "object",
  "properties": {
    "query": { "type": "string" },
    "result": { "type": "object" }
  }
}
```

**Erreurs possibles**
- `INVALID_PROMPT`
- `SCRAPEGRAPH_REQUEST_ERROR`

**Exemple d’appel**
```json
{
  "prompt": "Find interview experience and hiring process information for Example Corp.",
  "num_results": 5,
  "time_range": "90d"
}
```

**Exemple de résultat**
```json
{
  "query": "Find interview experience and hiring process information for Example Corp.",
  "result": {
    "interview_steps": ["Recruiter call", "Technical interview", "System design"],
    "sources": ["https://glassdoor.example/..."]
  }
}
```

**Recommandation**  
À ajouter côté `mcp_server/transport/tools.py` comme outil stable si le besoin apparaît dans les pipelines analyzer/generator.

---

## 2.4 Wrappers métier supplémentaires recommandés

---

### 2.4.1 `discover_company_careers_pages`

**But**  
Découvrir automatiquement les pages carrière d’une entreprise.

**Description**  
Combine idéalement `searchscraper`, `sitemap`, voire `fetch`/`playwright` derrière un wrapper unifié.

**Input schema**
```json
{
  "type": "object",
  "properties": {
    "company_name": { "type": "string" },
    "company_domain": { "type": "string" }
  },
  "required": ["company_name"]
}
```

**Output schema**
```json
{
  "type": "object",
  "properties": {
    "company_name": { "type": "string" },
    "careers_pages": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "url": { "type": "string" },
          "confidence": { "type": "number" },
          "source": { "type": "string" }
        }
      }
    }
  }
}
```

**Erreurs possibles**
- pas de domaine détecté
- aucune page carrière trouvée
- erreur fournisseur

**Exemple d’appel**
```json
{
  "company_name": "Example Corp",
  "company_domain": "example.com"
}
```

**Exemple de résultat**
```json
{
  "company_name": "Example Corp",
  "careers_pages": [
    {
      "url": "https://example.com/careers",
      "confidence": 0.96,
      "source": "sitemap"
    }
  ]
}
```

---

### 2.4.2 `extract_application_contacts`

**But**  
Extraire les contacts de recrutement et les modalités de candidature depuis une page.

**Input schema**
```json
{
  "type": "object",
  "properties": {
    "url": { "type": "string" }
  },
  "required": ["url"]
}
```

**Output schema**
```json
{
  "type": "object",
  "properties": {
    "url": { "type": "string" },
    "contacts": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "name": { "type": "string" },
          "role": { "type": "string" },
          "email": { "type": "string" },
          "linkedin": { "type": "string" }
        }
      }
    },
    "application_channels": {
      "type": "array",
      "items": { "type": "string" }
    }
  }
}
```

**Exemple de résultat**
```json
{
  "url": "https://example.com/jobs/backend-engineer",
  "contacts": [
    {
      "name": "Jane Doe",
      "role": "Recruiter",
      "email": "jobs@example.com",
      "linkedin": ""
    }
  ],
  "application_channels": ["ATS", "Email"]
}
```

---

# 3. Serveur `filesystem`

## 3.1 Rôle dans le projet

Le serveur `filesystem` donne un accès contrôlé à des répertoires locaux :

- racine du projet
- `docs/`
- `data/`
- `output/`

Il sert à :
- lire/écrire des documents de travail
- stocker des artefacts d’analyse
- persister temporairement résultats et exports

---

## 3.2 Outils standards tiers attendus

Les noms exacts peuvent varier selon l’implémentation MCP, mais le squelette attendu est le suivant.

---

### 3.2.1 `read_file`

**But**  
Lire le contenu d’un fichier texte.

**Input schema**
```json
{
  "type": "object",
  "properties": {
    "path": { "type": "string" }
  },
  "required": ["path"]
}
```

**Output schema**
```json
{
  "type": "object",
  "properties": {
    "path": { "type": "string" },
    "content": { "type": "string" }
  }
}
```

**Erreurs possibles**
- chemin interdit hors racines autorisées
- fichier absent
- fichier binaire non lisible

**Exemple d’appel**
```json
{
  "path": "docs/mcp_architecture_blueprint.md"
}
```

**Exemple de résultat**
```json
{
  "path": "docs/mcp_architecture_blueprint.md",
  "content": "# Architecture MCP\n..."
}
```

---

### 3.2.2 `write_file`

**But**  
Créer ou écraser un fichier.

**Input schema**
```json
{
  "type": "object",
  "properties": {
    "path": { "type": "string" },
    "content": { "type": "string" }
  },
  "required": ["path", "content"]
}
```

**Output schema**
```json
{
  "type": "object",
  "properties": {
    "path": { "type": "string" },
    "written": { "type": "boolean" }
  }
}
```

**Erreurs possibles**
- permission refusée
- chemin invalide
- répertoire non autorisé

**Exemple d’appel**
```json
{
  "path": "output/company_report.md",
  "content": "# Company Report\n..."
}
```

**Exemple de résultat**
```json
{
  "path": "output/company_report.md",
  "written": true
}
```

---

### 3.2.3 `list_directory`

**But**  
Lister un répertoire.

**Input schema**
```json
{
  "type": "object",
  "properties": {
    "path": { "type": "string" }
  },
  "required": ["path"]
}
```

**Output schema**
```json
{
  "type": "object",
  "properties": {
    "path": { "type": "string" },
    "entries": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "name": { "type": "string" },
          "type": { "type": "string" }
        }
      }
    }
  }
}
```

**Exemple de résultat**
```json
{
  "path": "output",
  "entries": [
    { "name": "company_report.md", "type": "file" },
    { "name": "analysis", "type": "directory" }
  ]
}
```

---

### 3.2.4 `create_directory`

**But**  
Créer un dossier.

**Input schema**
```json
{
  "type": "object",
  "properties": {
    "path": { "type": "string" }
  },
  "required": ["path"]
}
```

**Output schema**
```json
{
  "type": "object",
  "properties": {
    "path": { "type": "string" },
    "created": { "type": "boolean" }
  }
}
```

---

### 3.2.5 `search_files`

**But**  
Chercher des fichiers ou contenus dans l’arborescence autorisée.

**Input schema**
```json
{
  "type": "object",
  "properties": {
    "path": { "type": "string" },
    "pattern": { "type": "string" }
  },
  "required": ["path", "pattern"]
}
```

**Output schema**
```json
{
  "type": "object",
  "properties": {
    "matches": {
      "type": "array",
      "items": { "type": "string" }
    }
  }
}
```

---

## 3.3 Wrappers métier recommandés dans `mcp_server/`

---

### 3.3.1 `store_analysis_artifact`

**But**  
Enregistrer un artefact normalisé dans `output/`.

**Description**  
Évite que chaque client construise son propre chemin de persistance.

**Input schema**
```json
{
  "type": "object",
  "properties": {
    "artifact_type": { "type": "string" },
    "job_id": { "type": "string" },
    "format": { "type": "string", "enum": ["json", "md", "txt"] },
    "content": { "type": "string" }
  },
  "required": ["artifact_type", "format", "content"]
}
```

**Output schema**
```json
{
  "type": "object",
  "properties": {
    "path": { "type": "string" },
    "written": { "type": "boolean" }
  }
}
```

**Exemple d’appel**
```json
{
  "artifact_type": "job_analysis",
  "job_id": "job_123",
  "format": "json",
  "content": "{"company":"Example Corp"}"
}
```

**Exemple de résultat**
```json
{
  "path": "output/job_analysis/job_123.json",
  "written": true
}
```

---

### 3.3.2 `load_resume_source`

**But**  
Charger le texte d’un CV depuis un chemin autorisé.

**Input schema**
```json
{
  "type": "object",
  "properties": {
    "path": { "type": "string" }
  },
  "required": ["path"]
}
```

**Output schema**
```json
{
  "type": "object",
  "properties": {
    "path": { "type": "string" },
    "resume_text": { "type": "string" }
  }
}
```

---

### 3.3.3 `load_prompt_template`

**But**  
Lire un template de prompt ou de document depuis `docs/` ou `data/`.

**Input schema**
```json
{
  "type": "object",
  "properties": {
    "template_name": { "type": "string" }
  },
  "required": ["template_name"]
}
```

**Output schema**
```json
{
  "type": "object",
  "properties": {
    "template_name": { "type": "string" },
    "content": { "type": "string" }
  }
}
```

---

# 4. Serveur `github`

## 4.1 Rôle dans le projet

Le serveur GitHub permet d’accéder à :
- issues
- pull requests
- contenus de dépôt
- éventuellement métadonnées de collaboration

Dans ce projet, son usage probable est :
- lire de la documentation distante
- ouvrir des issues d’amélioration
- récupérer des templates ou références
- tracer des tâches liées aux pipelines

---

## 4.2 Outils standards tiers attendus

---

### 4.2.1 `get_file_contents`

**But**  
Lire un fichier d’un dépôt GitHub.

**Input schema**
```json
{
  "type": "object",
  "properties": {
    "owner": { "type": "string" },
    "repo": { "type": "string" },
    "path": { "type": "string" },
    "ref": { "type": "string" }
  },
  "required": ["owner", "repo", "path"]
}
```

**Output schema**
```json
{
  "type": "object",
  "properties": {
    "content": { "type": "string" },
    "sha": { "type": "string" }
  }
}
```

**Erreurs possibles**
- dépôt inaccessible
- token invalide
- fichier absent
- rate limit

**Exemple d’appel**
```json
{
  "owner": "modelcontextprotocol",
  "repo": "servers",
  "path": "README.md"
}
```

**Exemple de résultat**
```json
{
  "content": "# MCP Servers\n...",
  "sha": "abc123"
}
```

---

### 4.2.2 `search_repositories`

**But**  
Trouver des dépôts pertinents.

**Input schema**
```json
{
  "type": "object",
  "properties": {
    "query": { "type": "string" }
  },
  "required": ["query"]
}
```

**Output schema**
```json
{
  "type": "object",
  "properties": {
    "items": {
      "type": "array",
      "items": { "type": "object" }
    }
  }
}
```

---

### 4.2.3 `search_code`

**But**  
Chercher du code ou des exemples dans GitHub.

**Input schema**
```json
{
  "type": "object",
  "properties": {
    "query": { "type": "string" }
  },
  "required": ["query"]
}
```

**Output schema**
```json
{
  "type": "object",
  "properties": {
    "items": {
      "type": "array",
      "items": { "type": "object" }
    }
  }
}
```

---

### 4.2.4 `create_issue`

**But**  
Créer une issue de suivi.

**Input schema**
```json
{
  "type": "object",
  "properties": {
    "owner": { "type": "string" },
    "repo": { "type": "string" },
    "title": { "type": "string" },
    "body": { "type": "string" }
  },
  "required": ["owner", "repo", "title"]
}
```

**Output schema**
```json
{
  "type": "object",
  "properties": {
    "issue_number": { "type": "integer" },
    "url": { "type": "string" }
  }
}
```

---

## 4.3 Wrappers métier recommandés dans `mcp_server/`

---

### 4.3.1 `github_capture_project_issue`

**But**  
Créer une issue standardisée pour backlog technique MCP/pipeline.

**Input schema**
```json
{
  "type": "object",
  "properties": {
    "title": { "type": "string" },
    "summary": { "type": "string" },
    "component": { "type": "string" },
    "priority": { "type": "string" }
  },
  "required": ["title", "summary", "component"]
}
```

**Output schema**
```json
{
  "type": "object",
  "properties": {
    "issue_number": { "type": "integer" },
    "url": { "type": "string" }
  }
}
```

**Exemple de résultat**
```json
{
  "issue_number": 42,
  "url": "https://github.com/org/job-bot-general/issues/42"
}
```

---

### 4.3.2 `github_fetch_mcp_reference`

**But**  
Récupérer un document de référence GitHub utile au projet.

**Description**  
Wrapper simple pour documentation technique distante.

**Input schema**
```json
{
  "type": "object",
  "properties": {
    "owner": { "type": "string" },
    "repo": { "type": "string" },
    "path": { "type": "string" },
    "ref": { "type": "string" }
  },
  "required": ["owner", "repo", "path"]
}
```

**Output schema**
```json
{
  "type": "object",
  "properties": {
    "content": { "type": "string" },
    "source_url": { "type": "string" }
  }
}
```

---

# 5. Serveur `postgres`

## 5.1 Rôle dans le projet

Le serveur Postgres donne un accès MCP aux données structurées. Dans ce projet, il peut servir à :

- lire l’historique des analyses
- récupérer des offres déjà vues
- stocker ou interroger des métriques pipeline
- comparer candidatures, sociétés, signaux, documents générés

---

## 5.2 Outils standards tiers attendus

---

### 5.2.1 `query`

**But**  
Exécuter une requête SQL lecture.

**Input schema**
```json
{
  "type": "object",
  "properties": {
    "sql": { "type": "string" }
  },
  "required": ["sql"]
}
```

**Output schema**
```json
{
  "type": "object",
  "properties": {
    "rows": {
      "type": "array",
      "items": { "type": "object" }
    },
    "row_count": { "type": "integer" }
  }
}
```

**Erreurs possibles**
- connexion absente
- SQL invalide
- timeout
- permissions insuffisantes

**Exemple d’appel**
```json
{
  "sql": "SELECT id, company_name, job_title FROM job_offers ORDER BY created_at DESC LIMIT 10;"
}
```

**Exemple de résultat**
```json
{
  "rows": [
    { "id": 1, "company_name": "Example Corp", "job_title": "Backend Engineer" }
  ],
  "row_count": 1
}
```

---

### 5.2.2 `execute`

**But**  
Exécuter une commande SQL d’écriture.

**Input schema**
```json
{
  "type": "object",
  "properties": {
    "sql": { "type": "string" }
  },
  "required": ["sql"]
}
```

**Output schema**
```json
{
  "type": "object",
  "properties": {
    "affected_rows": { "type": "integer" }
  }
}
```

---

### 5.2.3 `describe_table`

**But**  
Décrire une table.

**Input schema**
```json
{
  "type": "object",
  "properties": {
    "table_name": { "type": "string" }
  },
  "required": ["table_name"]
}
```

**Output schema**
```json
{
  "type": "object",
  "properties": {
    "columns": {
      "type": "array",
      "items": { "type": "object" }
    }
  }
}
```

---

## 5.3 Wrappers métier recommandés dans `mcp_server/`

---

### 5.3.1 `db_get_recent_job_analyses`

**But**  
Lire les dernières analyses de jobs sans exposer SQL aux clients.

**Input schema**
```json
{
  "type": "object",
  "properties": {
    "limit": { "type": "integer", "default": 20 }
  }
}
```

**Output schema**
```json
{
  "type": "object",
  "properties": {
    "items": {
      "type": "array",
      "items": { "type": "object" }
    }
  }
}
```

**Exemple de résultat**
```json
{
  "items": [
    {
      "job_id": "job_123",
      "company_name": "Example Corp",
      "job_title": "Backend Engineer",
      "analyzed_at": "2026-03-31T10:00:00Z"
    }
  ]
}
```

---

### 5.3.2 `db_find_similar_companies`

**But**  
Identifier des entreprises similaires déjà analysées.

**Input schema**
```json
{
  "type": "object",
  "properties": {
    "company_name": { "type": "string" }
  },
  "required": ["company_name"]
}
```

**Output schema**
```json
{
  "type": "object",
  "properties": {
    "matches": {
      "type": "array",
      "items": { "type": "object" }
    }
  }
}
```

---

### 5.3.3 `db_store_generation_result`

**But**  
Persister le résultat de génération de documents.

**Input schema**
```json
{
  "type": "object",
  "properties": {
    "job_id": { "type": "string" },
    "candidate_id": { "type": "string" },
    "documents": { "type": "object" }
  },
  "required": ["job_id", "documents"]
}
```

**Output schema**
```json
{
  "type": "object",
  "properties": {
    "stored": { "type": "boolean" },
    "record_id": { "type": "string" }
  }
}
```

---

# 6. Serveur `fetch`

## 6.1 Rôle dans le projet

`fetch` fournit une primitive HTTP simple. Il est utile quand :

- on veut juste récupérer une ressource HTTP brute
- on n’a pas besoin d’un navigateur complet
- ScrapeGraph est trop coûteux pour un simple GET
- on veut interroger une API distante ou lire une page avant extraction

---

## 6.2 Outils standards tiers attendus

---

### 6.2.1 `fetch`

**But**  
Récupérer une ressource HTTP.

**Input schema**
```json
{
  "type": "object",
  "properties": {
    "url": { "type": "string" },
    "method": { "type": "string", "default": "GET" },
    "headers": { "type": "object" },
    "body": { "type": "string" }
  },
  "required": ["url"]
}
```

**Output schema**
```json
{
  "type": "object",
  "properties": {
    "status": { "type": "integer" },
    "headers": { "type": "object" },
    "body": { "type": "string" }
  }
}
```

**Erreurs possibles**
- URL invalide
- réseau indisponible
- timeout
- 4xx/5xx distant
- contenu trop volumineux

**Exemple d’appel**
```json
{
  "url": "https://example.com/robots.txt"
}
```

**Exemple de résultat**
```json
{
  "status": 200,
  "headers": {
    "content-type": "text/plain"
  },
  "body": "User-agent: *\nDisallow:"
}
```

---

## 6.3 Wrappers métier recommandés dans `mcp_server/`

---

### 6.3.1 `fetch_job_page_raw`

**But**  
Récupérer le HTML brut d’une offre pour diagnostic ou fallback.

**Input schema**
```json
{
  "type": "object",
  "properties": {
    "url": { "type": "string" }
  },
  "required": ["url"]
}
```

**Output schema**
```json
{
  "type": "object",
  "properties": {
    "url": { "type": "string" },
    "status": { "type": "integer" },
    "html": { "type": "string" }
  }
}
```

---

### 6.3.2 `fetch_company_site_metadata`

**But**  
Récupérer des métadonnées simples d’un site société.

**Input schema**
```json
{
  "type": "object",
  "properties": {
    "url": { "type": "string" }
  },
  "required": ["url"]
}
```

**Output schema**
```json
{
  "type": "object",
  "properties": {
    "final_url": { "type": "string" },
    "status": { "type": "integer" },
    "content_type": { "type": "string" }
  }
}
```

---

# 7. Serveur `memory`

## 7.1 Rôle dans le projet

Le serveur `memory` sert à maintenir un contexte persistant léger entre appels :

- préférences utilisateur
- entreprises déjà recherchées
- hypothèses de travail
- état d’une session de candidature

Il est particulièrement utile pour des flux multi-étapes agentiques.

---

## 7.2 Outils standards tiers attendus

Les noms exacts peuvent varier, mais le squelette attendu est proche de ce qui suit.

---

### 7.2.1 `memory_set`

**But**  
Enregistrer une information mémorisée.

**Input schema**
```json
{
  "type": "object",
  "properties": {
    "key": { "type": "string" },
    "value": {}
  },
  "required": ["key", "value"]
}
```

**Output schema**
```json
{
  "type": "object",
  "properties": {
    "stored": { "type": "boolean" }
  }
}
```

---

### 7.2.2 `memory_get`

**But**  
Lire une information mémorisée.

**Input schema**
```json
{
  "type": "object",
  "properties": {
    "key": { "type": "string" }
  },
  "required": ["key"]
}
```

**Output schema**
```json
{
  "type": "object",
  "properties": {
    "key": { "type": "string" },
    "value": {}
  }
}
```

---

### 7.2.3 `memory_search`

**But**  
Chercher en mémoire par terme ou catégorie.

**Input schema**
```json
{
  "type": "object",
  "properties": {
    "query": { "type": "string" }
  },
  "required": ["query"]
}
```

**Output schema**
```json
{
  "type": "object",
  "properties": {
    "matches": {
      "type": "array",
      "items": { "type": "object" }
    }
  }
}
```

---

### 7.2.4 `memory_delete`

**But**  
Supprimer une entrée mémoire.

**Input schema**
```json
{
  "type": "object",
  "properties": {
    "key": { "type": "string" }
  },
  "required": ["key"]
}
```

**Output schema**
```json
{
  "type": "object",
  "properties": {
    "deleted": { "type": "boolean" }
  }
}
```

---

## 7.3 Wrappers métier recommandés dans `mcp_server/`

---

### 7.3.1 `remember_candidate_preferences`

**But**  
Mémoriser des préférences de candidature.

**Input schema**
```json
{
  "type": "object",
  "properties": {
    "candidate_id": { "type": "string" },
    "preferences": {
      "type": "object",
      "properties": {
        "target_roles": { "type": "array", "items": { "type": "string" } },
        "locations": { "type": "array", "items": { "type": "string" } },
        "remote_policy": { "type": "string" },
        "salary_expectation": { "type": "string" }
      }
    }
  },
  "required": ["candidate_id", "preferences"]
}
```

**Output schema**
```json
{
  "type": "object",
  "properties": {
    "stored": { "type": "boolean" }
  }
}
```

---

### 7.3.2 `recall_company_context`

**But**  
Relire le contexte mémorisé pour une entreprise déjà étudiée.

**Input schema**
```json
{
  "type": "object",
  "properties": {
    "company_name": { "type": "string" }
  },
  "required": ["company_name"]
}
```

**Output schema**
```json
{
  "type": "object",
  "properties": {
    "company_name": { "type": "string" },
    "context": { "type": "object" }
  }
}
```

---

### 7.3.3 `remember_pipeline_session`

**But**  
Persister l’état synthétique d’un run MCP/pipeline.

**Input schema**
```json
{
  "type": "object",
  "properties": {
    "session_id": { "type": "string" },
    "state": { "type": "object" }
  },
  "required": ["session_id", "state"]
}
```

**Output schema**
```json
{
  "type": "object",
  "properties": {
    "stored": { "type": "boolean" }
  }
}
```

---

# 8. Serveur `playwright`

## 8.1 Rôle dans le projet

`playwright` est le serveur MCP adapté aux sites dynamiques :

- pages d’emploi avec JS lourd
- interactions nécessaires pour révéler du contenu
- navigation multi-étapes
- récupération de texte après rendu réel navigateur

Il doit être réservé aux cas où :
- `fetch` est insuffisant
- ScrapeGraph seul ne suffit pas
- le site bloque ou masque le contenu

---

## 8.2 Outils standards tiers attendus

Les noms exacts peuvent varier selon le serveur, mais le squelette attendu ressemble à :

---

### 8.2.1 `browser_navigate`

**But**  
Ouvrir une URL dans une session navigateur.

**Input schema**
```json
{
  "type": "object",
  "properties": {
    "url": { "type": "string" }
  },
  "required": ["url"]
}
```

**Output schema**
```json
{
  "type": "object",
  "properties": {
    "url": { "type": "string" },
    "title": { "type": "string" }
  }
}
```

---

### 8.2.2 `browser_click`

**But**  
Cliquer un élément.

**Input schema**
```json
{
  "type": "object",
  "properties": {
    "selector": { "type": "string" }
  },
  "required": ["selector"]
}
```

**Output schema**
```json
{
  "type": "object",
  "properties": {
    "clicked": { "type": "boolean" }
  }
}
```

---

### 8.2.3 `browser_fill`

**But**  
Remplir un champ.

**Input schema**
```json
{
  "type": "object",
  "properties": {
    "selector": { "type": "string" },
    "value": { "type": "string" }
  },
  "required": ["selector", "value"]
}
```

**Output schema**
```json
{
  "type": "object",
  "properties": {
    "filled": { "type": "boolean" }
  }
}
```

---

### 8.2.4 `browser_snapshot`

**But**  
Capturer le contenu visible ou une représentation de page.

**Input schema**
```json
{
  "type": "object",
  "properties": {}
}
```

**Output schema**
```json
{
  "type": "object",
  "properties": {
    "text": { "type": "string" },
    "html": { "type": "string" }
  }
}
```

---

### 8.2.5 `browser_evaluate`

**But**  
Évaluer du JavaScript dans la page.

**Input schema**
```json
{
  "type": "object",
  "properties": {
    "script": { "type": "string" }
  },
  "required": ["script"]
}
```

**Output schema**
```json
{
  "type": "object",
  "properties": {
    "result": {}
  }
}
```

---

## 8.3 Wrappers métier recommandés dans `mcp_server/`

---

### 8.3.1 `render_dynamic_job_page`

**But**  
Rendre une page d’offre dynamique et renvoyer le contenu exploitable.

**Input schema**
```json
{
  "type": "object",
  "properties": {
    "url": { "type": "string" },
    "wait_for_selector": { "type": "string" }
  },
  "required": ["url"]
}
```

**Output schema**
```json
{
  "type": "object",
  "properties": {
    "url": { "type": "string" },
    "title": { "type": "string" },
    "html": { "type": "string" },
    "text": { "type": "string" }
  }
}
```

**Exemple de résultat**
```json
{
  "url": "https://jobs.example.com/backend/123",
  "title": "Backend Engineer",
  "html": "<html>...</html>",
  "text": "Backend Engineer\nParis\n..."
}
```

---

### 8.3.2 `extract_visible_apply_link`

**But**  
Trouver le lien réel de candidature après rendu et éventuelles interactions.

**Input schema**
```json
{
  "type": "object",
  "properties": {
    "url": { "type": "string" }
  },
  "required": ["url"]
}
```

**Output schema**
```json
{
  "type": "object",
  "properties": {
    "application_url": { "type": "string" },
    "confidence": { "type": "number" }
  }
}
```

---

### 8.3.3 `playwright_collect_job_page_artifacts`

**But**  
Produire un bundle diagnostic pour une page difficile.

**Input schema**
```json
{
  "type": "object",
  "properties": {
    "url": { "type": "string" }
  },
  "required": ["url"]
}
```

**Output schema**
```json
{
  "type": "object",
  "properties": {
    "title": { "type": "string" },
    "final_url": { "type": "string" },
    "visible_text": { "type": "string" },
    "html_excerpt": { "type": "string" }
  }
}
```

---

# 9. Outils métier déjà présents dans `mcp_server/`

Cette section décrit les outils non liés à un serveur tiers unique, mais déjà exposés dans `mcp_server/transport/tools.py`.

---

### 9.1 `analyze_job`

**But**  
Analyser une offre d’emploi via l’orchestrateur applicatif.

**Description**  
Ce wrapper délègue à l’API `/api/analyze` et renvoie une structure normalisée.

**Input schema**
```json
{
  "type": "object",
  "properties": {
    "url": { "type": "string" }
  },
  "required": ["url"]
}
```

**Output schema**
```json
{
  "type": "object",
  "properties": {
    "job": { "type": "object" },
    "analysis": { "type": "object" }
  }
}
```

**Erreurs possibles**
- `INVALID_URL`
- `ORCHESTRATOR_UNAVAILABLE`
- réponse API invalide

**Exemple d’appel**
```json
{
  "url": "https://company.example/jobs/backend-engineer"
}
```

**Exemple de résultat**
```json
{
  "job": {
    "company_name": "Example Corp",
    "job_title": "Backend Engineer"
  },
  "analysis": {
    "fit_summary": "Strong API and backend match"
  }
}
```

---

### 9.2 `generate_documents`

**But**  
Générer des documents de candidature.

**Input schema**
```json
{
  "type": "object",
  "properties": {
    "job_data": { "type": "object" },
    "resume_text": { "type": "string" }
  },
  "required": ["job_data"]
}
```

**Output schema**
```json
{
  "type": "object",
  "properties": {
    "documents": { "type": "object" }
  }
}
```

**Exemple de résultat**
```json
{
  "documents": {
    "cover_letter": "Dear Hiring Team...",
    "email": "Hello, I am applying for..."
  }
}
```

---

### 9.3 `run_full_pipeline`

**But**  
Exécuter acquisition, extraction, analyse et génération en un seul appel.

**Input schema**
```json
{
  "type": "object",
  "properties": {
    "url": { "type": "string" },
    "resume_text": { "type": "string" }
  },
  "required": ["url"]
}
```

**Output schema**
```json
{
  "type": "object",
  "properties": {
    "job_data": { "type": "object" },
    "analysis": { "type": "object" },
    "documents": { "type": "object" }
  }
}
```

---

### 9.4 `infer_entities`

**But**  
Déduire des entités candidates à partir d’un texte ou document.

**Input schema**
```json
{
  "type": "object",
  "properties": {
    "text": { "type": "string" },
    "document": { "type": "object" },
    "entity_types": {
      "type": "array",
      "items": { "type": "string" }
    }
  }
}
```

**Output schema**
```json
{
  "type": "object",
  "properties": {
    "entity_types": {
      "type": "array",
      "items": { "type": "string" }
    },
    "entity_count": { "type": "integer" },
    "entities": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "name": { "type": "string" },
          "type": { "type": "string" }
        }
      }
    }
  }
}
```

**Remarque**  
Cet outil est aujourd’hui heuristique, sans fournisseur externe.

---

### 9.5 `enrich_entities`

**But**  
Enrichir des entités avec recherche externe, surtout pour une entreprise.

**Input schema**
```json
{
  "type": "object",
  "properties": {
    "entities": {
      "type": "array",
      "items": { "type": "object" }
    },
    "role_focus": { "type": "string" },
    "location": { "type": "string" },
    "num_results": { "type": "integer" },
    "time_range": { "type": "string" }
  },
  "required": ["entities"]
}
```

**Output schema**
```json
{
  "type": "object",
  "properties": {
    "entities": { "type": "array", "items": { "type": "object" } },
    "research": { "type": "object" },
    "note": { "type": "string" }
  }
}
```

---

# 10. API MCP métier unifiée recommandée pour le projet

L’objectif est de proposer une couche stable et compréhensible pour tous les consommateurs internes (`agent`, `analyzer`, `generator`, `app`, `dashboard`).

## 10.1 Domaine 1 — Acquisition / lecture de source

### `acquire_job_source`
**But** : obtenir une représentation exploitable d’une offre.  
**Backend possible** : `fetch`, `playwright`, `scrapegraph_markdownify`.

**Input schema**
```json
{
  "type": "object",
  "properties": {
    "url": { "type": "string" },
    "mode": { "type": "string", "enum": ["auto", "fetch", "playwright", "markdown"] }
  },
  "required": ["url"]
}
```

**Output schema**
```json
{
  "type": "object",
  "properties": {
    "url": { "type": "string" },
    "content_type": { "type": "string" },
    "content": { "type": "string" },
    "acquisition_method": { "type": "string" }
  }
}
```

---

## 10.2 Domaine 2 — Extraction métier

### `extract_job_offer`
**But** : renvoyer une offre normalisée à partir d’une URL ou d’un contenu source.  
**Backend possible** : `scrapegraph_extract_job_offer`, `scrapegraph_extract`.

**Input schema**
```json
{
  "type": "object",
  "properties": {
    "url": { "type": "string" },
    "source_text": { "type": "string" }
  }
}
```

**Output schema**
```json
{
  "type": "object",
  "properties": {
    "job_offer": { "type": "object" }
  }
}
```

---

### `extract_company_intelligence`
**But** : synthétiser une intelligence entreprise utile à la candidature.  
**Backend possible** : `scrapegraph_company_hiring_intelligence`, `fetch`, `github`, `memory`.

**Input schema**
```json
{
  "type": "object",
  "properties": {
    "company_name": { "type": "string" },
    "role_focus": { "type": "string" },
    "location": { "type": "string" }
  },
  "required": ["company_name"]
}
```

**Output schema**
```json
{
  "type": "object",
  "properties": {
    "company_intelligence": { "type": "object" }
  }
}
```

---

## 10.3 Domaine 3 — Mémoire / contexte

### `remember_job_context`
**But** : persister le contexte d’une opportunité.

**Input schema**
```json
{
  "type": "object",
  "properties": {
    "job_id": { "type": "string" },
    "context": { "type": "object" }
  },
  "required": ["job_id", "context"]
}
```

**Output schema**
```json
{
  "type": "object",
  "properties": {
    "stored": { "type": "boolean" }
  }
}
```

---

### `recall_job_context`
**But** : relire ce contexte.

**Input schema**
```json
{
  "type": "object",
  "properties": {
    "job_id": { "type": "string" }
  },
  "required": ["job_id"]
}
```

**Output schema**
```json
{
  "type": "object",
  "properties": {
    "job_id": { "type": "string" },
    "context": { "type": "object" }
  }
}
```

---

## 10.4 Domaine 4 — Persistance / artefacts

### `store_pipeline_artifact`
**But** : sauvegarder une sortie pipeline.

**Input schema**
```json
{
  "type": "object",
  "properties": {
    "artifact_type": { "type": "string" },
    "reference_id": { "type": "string" },
    "payload": { "type": "object" }
  },
  "required": ["artifact_type", "payload"]
}
```

**Output schema**
```json
{
  "type": "object",
  "properties": {
    "stored": { "type": "boolean" },
    "path": { "type": "string" }
  }
}
```

---

## 10.5 Domaine 5 — Orchestration métier

### `analyze_job`
Déjà présent.

### `generate_documents`
Déjà présent.

### `run_full_pipeline`
Déjà présent.

### `run_targeted_pipeline`
**But** : exécuter seulement certaines étapes.

**Input schema**
```json
{
  "type": "object",
  "properties": {
    "url": { "type": "string" },
    "steps": {
      "type": "array",
      "items": { "type": "string" }
    },
    "resume_text": { "type": "string" }
  },
  "required": ["url", "steps"]
}
```

**Output schema**
```json
{
  "type": "object",
  "properties": {
    "completed_steps": {
      "type": "array",
      "items": { "type": "string" }
    },
    "results": { "type": "object" }
  }
}
```

---

# 11. Recommandations de nommage et de stabilité

## 11.1 Préfixes recommandés

Pour garder une API lisible :

- préfixe `scrapegraph_` pour les wrappers directement liés à ScrapeGraph
- préfixe `db_` pour les wrappers Postgres
- préfixe `github_` pour les wrappers GitHub
- verbes métier sans préfixe technique quand l’outil représente un vrai service produit :
  - `analyze_job`
  - `generate_documents`
  - `run_full_pipeline`
  - `extract_job_offer`
  - `extract_company_intelligence`

## 11.2 Contrat de stabilité recommandé

### Stable pour clients internes
- `analyze_job`
- `generate_documents`
- `run_full_pipeline`
- `scrapegraph_extract_job_offer`
- `scrapegraph_company_hiring_intelligence`
- `infer_entities`
- `enrich_entities`

### Semi-stable / technique
- `scrapegraph_extract`
- `scrapegraph_markdownify`
- `fetch_job_page_raw`
- `render_dynamic_job_page`

### Non stable / exploration
- outils tiers bruts comme `smartscraper`, `searchscraper`, `scrape`, `sitemap`, `browser_evaluate`, `query`

---

# 12. Recommandation finale d’architecture fonctionnelle

## 12.1 Ce qu’il faut conserver tel quel
Conserver les serveurs tiers externes pour :
- fournir les primitives basses
- permettre l’exploration et le debug
- éviter de réimplémenter la logique fournisseur

## 12.2 Ce qu’il faut encapsuler derrière `mcp_server/`
Encapsuler prioritairement :
- ScrapeGraph
- Playwright
- Fetch
- Memory
- Postgres

dans des wrappers métier à nommage stable.

## 12.3 Ce que les clients du projet devraient appeler
Les composants du projet devraient préférer :
1. les outils métier de `mcp_server/`
2. puis, seulement si besoin, quelques outils techniques spécialisés

Ils ne devraient pas dépendre directement de la granularité ou des signatures exactes des serveurs tiers.

## 12.4 Priorité d’implémentation recommandée

### Priorité 1
- `scrapegraph_extract_job_offer`
- `scrapegraph_company_hiring_intelligence`
- `analyze_job`
- `generate_documents`
- `run_full_pipeline`

### Priorité 2
- `scrapegraph_search_extract`
- `render_dynamic_job_page`
- `store_analysis_artifact`
- `remember_candidate_preferences`
- `db_get_recent_job_analyses`

### Priorité 3
- `discover_company_careers_pages`
- `extract_application_contacts`
- `github_capture_project_issue`
- `run_targeted_pipeline`

---

# 13. Résumé exécutable pour l’équipe

## Outils déjà alignés avec la cible
- `analyze_job`
- `generate_documents`
- `run_full_pipeline`
- `scrapegraph_extract`
- `scrapegraph_extract_job_offer`
- `scrapegraph_company_hiring_intelligence`
- `scrapegraph_markdownify`
- `infer_entities`
- `enrich_entities`

## Outils tiers utiles mais encore “bruts”
- `markdownify`
- `smartscraper`
- `searchscraper`
- `scrape`
- `sitemap`
- `smartcrawler_initiate`
- `smartcrawler_fetch_results`
- `agentic_scrapper`
- `fetch`
- outils `filesystem`
- outils `github`
- outils `postgres`
- outils `memory`
- outils `playwright`

## Outils métier recommandés à converger
- `extract_job_offer`
- `extract_company_intelligence`
- `acquire_job_source`
- `store_pipeline_artifact`
- `remember_job_context`
- `recall_job_context`
- `render_dynamic_job_page`
- `db_get_recent_job_analyses`

Ce catalogue constitue la base pour formaliser une **surface MCP métier cohérente, stable et découplée des fournisseurs**.