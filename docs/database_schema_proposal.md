# Schéma de base de données proposé

## 1. Recommandation générale

Vu les besoins :
- JSON riches et évolutifs,
- audit,
- historique temps réel,
- recherche par entités,
- credentials à protéger,
- runs techniques,
- GitHub Actions,
- discussions multi-IA,

je recommande **PostgreSQL** comme base principale, avec usage de :
- `UUID` pour les PK,
- `JSONB` pour payloads métier,
- `TIMESTAMPTZ` pour l’audit,
- index `GIN` sur certains champs JSONB,
- chiffrement **applicatif** pour les secrets sensibles,
- journalisation d’accès/audit séparée.

Le design ci-dessous est pensé pour une architecture modulaire/microservices, avec :
- tables métier stables,
- tables techniques de runs/events,
- tables de sécurité et conformité,
- traçabilité forte.

## 2. Principes de modélisation

### 2.1 Séparation logique
Je découpe en 8 domaines :
1. **Identité / comptes / rôles**
2. **Secrets / credentials / configuration**
3. **Modèles IA / providers / conversations**
4. **Documents candidats** (CV, lettres, pièces)
5. **Offres / recrutements publics / candidatures**
6. **Entités métier / référentiels / compétences / réglementations**
7. **Runs pipeline / événements temps réel / observabilité**
8. **GitHub Actions / CI-CD / automatisation**

### 2.2 Protection des secrets
Ne jamais stocker :
- clés API en clair,
- tokens GitHub en clair,
- mots de passe en clair.

Stocker plutôt :
- `secret_ciphertext`
- `secret_kms_key_ref` ou `secret_key_version`
- `secret_fingerprint`
- `last4_hint`
- `is_valid`, `last_checked_at`

### 2.3 JSON vs relationnel
- **Relationnel** pour tout ce qui doit être filtré/joint/agrégé.
- **JSONB** pour payloads source, réponses LLM, documents bruts, snapshot d’offre, CV structuré.

## 3. Schéma détaillé

# A. Identité, utilisateurs, sécurité

## `users`
- `id UUID PK`
- `email VARCHAR(320) NOT NULL UNIQUE`
- `display_name VARCHAR(160)`
- `password_hash TEXT NULL`
- `auth_provider VARCHAR(50) NOT NULL DEFAULT 'local'`
- `is_active BOOLEAN NOT NULL DEFAULT TRUE`
- `is_admin BOOLEAN NOT NULL DEFAULT FALSE`
- `preferred_locale VARCHAR(10) DEFAULT 'fr-LU'`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`
- `updated_at TIMESTAMPTZ NOT NULL DEFAULT now()`
- `last_login_at TIMESTAMPTZ NULL`

Indexes:
- unique on `email`
- index on `is_active`

## `roles`
- `id UUID PK`
- `code VARCHAR(50) UNIQUE NOT NULL`
- `label VARCHAR(120) NOT NULL`
- `description TEXT`

## `user_roles`
- `user_id UUID FK -> users.id`
- `role_id UUID FK -> roles.id`
- `granted_at TIMESTAMPTZ NOT NULL DEFAULT now()`
- `granted_by UUID FK -> users.id NULL`

PK composite:
- `(user_id, role_id)`

## `api_clients`
- `id UUID PK`
- `name VARCHAR(120) NOT NULL`
- `client_id VARCHAR(120) UNIQUE NOT NULL`
- `client_secret_hash TEXT NOT NULL`
- `is_active BOOLEAN NOT NULL DEFAULT TRUE`
- `scopes JSONB NOT NULL DEFAULT '[]'::jsonb`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`
- `last_used_at TIMESTAMPTZ`

## `audit_logs`
- `id UUID PK`
- `occurred_at TIMESTAMPTZ NOT NULL DEFAULT now()`
- `actor_user_id UUID FK -> users.id NULL`
- `actor_api_client_id UUID FK -> api_clients.id NULL`
- `action VARCHAR(100) NOT NULL`
- `resource_type VARCHAR(100) NOT NULL`
- `resource_id UUID NULL`
- `status VARCHAR(30) NOT NULL`
- `ip_address INET NULL`
- `user_agent TEXT NULL`
- `request_id VARCHAR(100) NULL`
- `trace_id VARCHAR(100) NULL`
- `details JSONB NOT NULL DEFAULT '{}'::jsonb`

Indexes:
- `(occurred_at DESC)`
- `(resource_type, resource_id)`
- `(actor_user_id, occurred_at DESC)`
- `GIN(details)`

# B. Credentials, secrets, configuration

## `secret_providers`
- `id UUID PK`
- `code VARCHAR(50) UNIQUE NOT NULL`
- `label VARCHAR(120) NOT NULL`
- `category VARCHAR(50) NOT NULL`

## `secrets`
- `id UUID PK`
- `provider_id UUID FK -> secret_providers.id NOT NULL`
- `name VARCHAR(120) NOT NULL`
- `environment VARCHAR(30) NOT NULL DEFAULT 'default'`
- `secret_ciphertext TEXT NOT NULL`
- `secret_key_version VARCHAR(50) NULL`
- `secret_fingerprint VARCHAR(128) NOT NULL`
- `last4_hint VARCHAR(8) NULL`
- `metadata JSONB NOT NULL DEFAULT '{}'::jsonb`
- `is_active BOOLEAN NOT NULL DEFAULT TRUE`
- `is_valid BOOLEAN NULL`
- `validation_error TEXT NULL`
- `last_checked_at TIMESTAMPTZ NULL`
- `created_by UUID FK -> users.id NULL`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`
- `updated_at TIMESTAMPTZ NOT NULL DEFAULT now()`
- `rotated_at TIMESTAMPTZ NULL`

Contraintes:
- unique `(provider_id, name, environment)`

Indexes:
- `(provider_id, environment)`
- `(is_active, environment)`

## `config_entries`
- `id UUID PK`
- `scope VARCHAR(50) NOT NULL`
- `key VARCHAR(120) NOT NULL`
- `value_json JSONB NOT NULL`
- `value_type VARCHAR(30) NOT NULL`
- `is_sensitive BOOLEAN NOT NULL DEFAULT FALSE`
- `description TEXT NULL`
- `updated_by UUID FK -> users.id NULL`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`
- `updated_at TIMESTAMPTZ NOT NULL DEFAULT now()`

Unique:
- `(scope, key)`

## `model_provider_accounts`
- `id UUID PK`
- `provider_code VARCHAR(50) NOT NULL`
- `secret_id UUID FK -> secrets.id NOT NULL`
- `account_label VARCHAR(120)`
- `base_url TEXT NULL`
- `organization_ref VARCHAR(120) NULL`
- `default_headers JSONB DEFAULT '{}'::jsonb`
- `is_default BOOLEAN NOT NULL DEFAULT FALSE`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`

Indexes:
- `(provider_code, is_default)`

# C. Providers IA, modèles, conversations

## `llm_providers`
- `id UUID PK`
- `code VARCHAR(50) UNIQUE NOT NULL`
- `label VARCHAR(120) NOT NULL`
- `api_style VARCHAR(50) NOT NULL`
- `website_url TEXT NULL`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`

## `llm_models`
- `id UUID PK`
- `provider_id UUID FK -> llm_providers.id NOT NULL`
- `model_identifier VARCHAR(200) NOT NULL`
- `display_name VARCHAR(200) NULL`
- `family VARCHAR(100) NULL`
- `input_token_limit INTEGER NULL`
- `output_token_limit INTEGER NULL`
- `supports_json BOOLEAN`
- `supports_streaming BOOLEAN`
- `supports_tools BOOLEAN`
- `supports_vision BOOLEAN`
- `is_active BOOLEAN NOT NULL DEFAULT TRUE`
- `first_seen_at TIMESTAMPTZ NOT NULL DEFAULT now()`
- `last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now()`
- `metadata JSONB NOT NULL DEFAULT '{}'::jsonb`

Unique:
- `(provider_id, model_identifier)`

## `llm_model_snapshots`
- `id UUID PK`
- `model_id UUID FK -> llm_models.id NOT NULL`
- `captured_at TIMESTAMPTZ NOT NULL DEFAULT now()`
- `capabilities JSONB NOT NULL`
- `raw_payload JSONB NOT NULL`

## `chat_sessions`
- `id UUID PK`
- `user_id UUID FK -> users.id NULL`
- `title VARCHAR(255) NULL`
- `context_type VARCHAR(50) NOT NULL`
- `candidate_profile_id UUID NULL`
- `job_post_id UUID NULL`
- `application_id UUID NULL`
- `status VARCHAR(30) NOT NULL DEFAULT 'active'`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`
- `updated_at TIMESTAMPTZ NOT NULL DEFAULT now()`
- `archived_at TIMESTAMPTZ NULL`
- `metadata JSONB NOT NULL DEFAULT '{}'::jsonb`

## `chat_messages`
- `id UUID PK`
- `session_id UUID FK -> chat_sessions.id NOT NULL`
- `parent_message_id UUID FK -> chat_messages.id NULL`
- `role VARCHAR(30) NOT NULL`
- `provider_id UUID FK -> llm_providers.id NULL`
- `model_id UUID FK -> llm_models.id NULL`
- `message_index INTEGER NOT NULL`
- `content_text TEXT NULL`
- `content_json JSONB NULL`
- `tool_name VARCHAR(120) NULL`
- `tool_call_id VARCHAR(120) NULL`
- `prompt_tokens INTEGER NULL`
- `completion_tokens INTEGER NULL`
- `total_tokens INTEGER NULL`
- `latency_ms INTEGER NULL`
- `finish_reason VARCHAR(50) NULL`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`
- `raw_request JSONB NULL`
- `raw_response JSONB NULL`
- `redaction_status VARCHAR(30) DEFAULT 'none'`

Unique:
- `(session_id, message_index)`

## `chat_message_feedback`
- `id UUID PK`
- `message_id UUID FK -> chat_messages.id NOT NULL`
- `user_id UUID FK -> users.id NULL`
- `feedback_type VARCHAR(20) NOT NULL`
- `comment TEXT NULL`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`

# D. Candidat, CV, documents

## `candidate_profiles`
- `id UUID PK`
- `owner_user_id UUID FK -> users.id NULL`
- `full_name VARCHAR(200) NULL`
- `email VARCHAR(320) NULL`
- `phone VARCHAR(50) NULL`
- `nationality VARCHAR(100) NULL`
- `location_text VARCHAR(200) NULL`
- `birth_date DATE NULL`
- `current_title VARCHAR(200) NULL`
- `summary TEXT NULL`
- `source_type VARCHAR(50) DEFAULT 'manual'`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`
- `updated_at TIMESTAMPTZ NOT NULL DEFAULT now()`
- `metadata JSONB NOT NULL DEFAULT '{}'::jsonb`

## `documents`
- `id UUID PK`
- `candidate_profile_id UUID FK -> candidate_profiles.id NULL`
- `document_type VARCHAR(50) NOT NULL`
- `storage_path TEXT NULL`
- `mime_type VARCHAR(120) NULL`
- `file_name VARCHAR(255) NULL`
- `file_size_bytes BIGINT NULL`
- `checksum_sha256 CHAR(64) NULL`
- `language_code VARCHAR(10) NULL`
- `source VARCHAR(50) NOT NULL`
- `created_by UUID FK -> users.id NULL`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`
- `deleted_at TIMESTAMPTZ NULL`
- `metadata JSONB NOT NULL DEFAULT '{}'::jsonb`

## `document_versions`
- `id UUID PK`
- `document_id UUID FK -> documents.id NOT NULL`
- `version_number INTEGER NOT NULL`
- `is_current BOOLEAN NOT NULL DEFAULT TRUE`
- `content_text TEXT NULL`
- `content_json JSONB NULL`
- `diff_from_previous JSONB NULL`
- `generation_run_id UUID NULL`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`
- `created_by UUID FK -> users.id NULL`

## `cv_profiles`
- `id UUID PK`
- `candidate_profile_id UUID FK -> candidate_profiles.id NOT NULL`
- `source_document_id UUID FK -> documents.id NULL`
- `format VARCHAR(50) NOT NULL`
- `raw_json JSONB NOT NULL`
- `normalized_json JSONB NULL`
- `extracted_text TEXT NULL`
- `language_code VARCHAR(10) NULL`
- `is_primary BOOLEAN NOT NULL DEFAULT FALSE`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`
- `updated_at TIMESTAMPTZ NOT NULL DEFAULT now()`

## `cover_letters`
- `id UUID PK`
- `candidate_profile_id UUID FK -> candidate_profiles.id NOT NULL`
- `job_post_id UUID FK -> job_posts.id NULL`
- `source_message_id UUID FK -> chat_messages.id NULL`
- `document_id UUID FK -> documents.id NULL`
- `language_code VARCHAR(10) DEFAULT 'fr'`
- `status VARCHAR(30) DEFAULT 'draft'`
- `content_text TEXT NOT NULL`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`
- `updated_at TIMESTAMPTZ NOT NULL DEFAULT now()`

# E. Offres et candidatures

## `organizations`
- `id UUID PK`
- `name VARCHAR(255) NOT NULL`
- `normalized_name VARCHAR(255) NOT NULL`
- `organization_type VARCHAR(50) NOT NULL`
- `country_code CHAR(2) NULL`
- `website_url TEXT NULL`
- `parent_organization_id UUID FK -> organizations.id NULL`
- `description TEXT NULL`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`

## `organization_units`
- `id UUID PK`
- `organization_id UUID FK -> organizations.id NOT NULL`
- `name VARCHAR(255) NOT NULL`
- `normalized_name VARCHAR(255) NOT NULL`
- `unit_type VARCHAR(50) NULL`
- `parent_unit_id UUID FK -> organization_units.id NULL`
- `description TEXT NULL`

## `locations`
- `id UUID PK`
- `name VARCHAR(200) NOT NULL`
- `city VARCHAR(120) NULL`
- `country_code CHAR(2) NULL`
- `address_text TEXT NULL`
- `latitude NUMERIC(9,6) NULL`
- `longitude NUMERIC(9,6) NULL`

## `job_sources`
- `id UUID PK`
- `code VARCHAR(50) UNIQUE NOT NULL`
- `label VARCHAR(120) NOT NULL`
- `base_url TEXT NULL`

## `job_posts`
- `id UUID PK`
- `source_id UUID FK -> job_sources.id NOT NULL`
- `source_url TEXT NOT NULL`
- `source_external_id VARCHAR(120) NULL`
- `title VARCHAR(500) NOT NULL`
- `reference_code VARCHAR(120) NULL`
- `employment_status VARCHAR(120) NULL`
- `career_group VARCHAR(50) NULL`
- `contract_type VARCHAR(120) NULL`
- `workload VARCHAR(50) NULL`
- `vacancy_count INTEGER NULL`
- `published_at TIMESTAMPTZ NULL`
- `application_deadline DATE NULL`
- `location_id UUID FK -> locations.id NULL`
- `ministry_org_id UUID FK -> organizations.id NULL`
- `employer_org_id UUID FK -> organizations.id NULL`
- `employer_unit_id UUID FK -> organization_units.id NULL`
- `contact_person_name VARCHAR(200) NULL`
- `contact_email VARCHAR(320) NULL`
- `job_family VARCHAR(120) NULL`
- `raw_json JSONB NOT NULL`
- `normalized_json JSONB NULL`
- `raw_text TEXT NULL`
- `language_code VARCHAR(10) DEFAULT 'fr-LU'`
- `status VARCHAR(31) NOT NULL DEFAULT 'active'`
- `scraped_at TIMESTAMPTZ NOT NULL DEFAULT now()`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`
- `updated_at TIMESTAMPTZ NOT NULL DEFAULT now()`

## `job_post_versions`
- `id UUID PK`
- `job_post_id UUID FK -> job_posts.id NOT NULL`
- `version_number INTEGER NOT NULL`
- `captured_at TIMESTAMPTZ NOT NULL DEFAULT now()`
- `raw_json JSONB NOT NULL`
- `raw_text TEXT NULL`
- `change_summary JSONB NULL`

## `job_post_requirements`
- `id UUID PK`
- `job_post_id UUID FK -> job_posts.id NOT NULL`
- `requirement_type VARCHAR(50) NOT NULL`
- `label TEXT NOT NULL`
- `description TEXT NULL`
- `is_mandatory BOOLEAN NOT NULL DEFAULT TRUE`
- `priority SMALLINT NULL`
- `source_excerpt TEXT NULL`

## `job_post_documents_required`
- `id UUID PK`
- `job_post_id UUID FK -> job_posts.id NOT NULL`
- `applicant_status VARCHAR(50) NOT NULL`
- `document_type VARCHAR(50) NOT NULL`
- `is_mandatory BOOLEAN NOT NULL DEFAULT TRUE`
- `notes TEXT NULL`

## `applications`
- `id UUID PK`
- `candidate_profile_id UUID FK -> candidate_profiles.id NOT NULL`
- `job_post_id UUID FK -> job_posts.id NOT NULL`
- `application_channel VARCHAR(50) NOT NULL`
- `applicant_status VARCHAR(50) NOT NULL`
- `status VARCHAR(50) NOT NULL DEFAULT 'draft'`
- `submitted_at TIMESTAMPTZ NULL`
- `deadline_at TIMESTAMPTZ NULL`
- `notes TEXT NULL`
- `metadata JSONB NOT NULL DEFAULT '{}'::jsonb`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`
- `updated_at TIMESTAMPTZ NOT NULL DEFAULT now()`

## `application_documents`
- `id UUID PK`
- `application_id UUID FK -> applications.id NOT NULL`
- `document_id UUID FK -> documents.id NOT NULL`
- `document_type VARCHAR(50) NOT NULL`
- `is_required BOOLEAN NOT NULL DEFAULT TRUE`
- `is_uploaded BOOLEAN NOT NULL DEFAULT FALSE`
- `validated_at TIMESTAMPTZ NULL`
- `validation_status VARCHAR(30) DEFAULT 'pending'`
- `notes TEXT NULL`

## `application_events`
- `id UUID PK`
- `application_id UUID FK -> applications.id NOT NULL`
- `event_type VARCHAR(60) NOT NULL`
- `occurred_at TIMESTAMPTZ NOT NULL DEFAULT now()`
- `actor_user_id UUID FK -> users.id NULL`
- `payload JSONB NOT NULL DEFAULT '{}'::jsonb`

# F. Entités métier, compétences, conformité

## `business_entities`
- `id UUID PK`
- `entity_type VARCHAR(50) NOT NULL`
- `canonical_name VARCHAR(255) NOT NULL`
- `normalized_name VARCHAR(255) NOT NULL`
- `description TEXT NULL`
- `country_code CHAR(2) NULL`
- `metadata JSONB NOT NULL DEFAULT '{}'::jsonb`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`

## `entity_aliases`
- `id UUID PK`
- `entity_id UUID FK -> business_entities.id NOT NULL`
- `alias_name VARCHAR(255) NOT NULL`
- `normalized_alias VARCHAR(255) NOT NULL`
- `alias_type VARCHAR(50) NULL`

## `entity_relationships`
- `id UUID PK`
- `source_entity_id UUID FK -> business_entities.id NOT NULL`
- `target_entity_id UUID FK -> business_entities.id NOT NULL`
- `relationship_type VARCHAR(80) NOT NULL`
- `description TEXT NULL`
- `confidence_score NUMERIC(5,4) NULL`
- `source_origin VARCHAR(50) NULL`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`

## `skills`
- `id UUID PK`
- `name VARCHAR(255) NOT NULL`
- `normalized_name VARCHAR(255) NOT NULL`
- `skill_category VARCHAR(50) NOT NULL`
- `description TEXT NULL`
- `metadata JSONB DEFAULT '{}'::jsonb`

## `job_post_skills`
- `job_post_id UUID FK -> job_posts.id NOT NULL`
- `skill_id UUID FK -> skills.id NOT NULL`
- `importance_level SMALLINT NULL`
- `is_mandatory BOOLEAN NOT NULL DEFAULT TRUE`
- `source_excerpt TEXT NULL`

## `candidate_skills`
- `candidate_profile_id UUID FK -> candidate_profiles.id NOT NULL`
- `skill_id UUID FK -> skills.id NOT NULL`
- `proficiency_level SMALLINT NULL`
- `evidence TEXT NULL`
- `source_document_id UUID FK -> documents.id NULL`
- `last_verified_at TIMESTAMPTZ NULL`

## `frameworks_regulations`
- `id UUID PK`
- `code VARCHAR(100) UNIQUE NOT NULL`
- `name VARCHAR(255) NOT NULL`
- `framework_type VARCHAR(50) NOT NULL`
- `issuer VARCHAR(255) NULL`
- `jurisdiction VARCHAR(100) NULL`
- `description TEXT NULL`
- `metadata JSONB DEFAULT '{}'::jsonb`

## `job_post_frameworks`
- `job_post_id UUID FK -> job_posts.id NOT NULL`
- `framework_id UUID FK -> frameworks_regulations.id NOT NULL`
- `relation_type VARCHAR(50) NOT NULL`

## `public_service_rules`
- `id UUID PK`
- `rule_code VARCHAR(100) UNIQUE NOT NULL`
- `title VARCHAR(255) NOT NULL`
- `category VARCHAR(50) NOT NULL`
- `description TEXT NOT NULL`
- `applies_to_status JSONB NOT NULL DEFAULT '[]'::jsonb`
- `metadata JSONB DEFAULT '{}'::jsonb`

## `job_post_public_rules`
- `job_post_id UUID FK -> job_posts.id NOT NULL`
- `public_rule_id UUID FK -> public_service_rules.id NOT NULL`
- `is_mandatory BOOLEAN NOT NULL DEFAULT TRUE`
- `source_excerpt TEXT NULL`

# G. Analyse, matching, génération, runs

## `pipeline_runs`
- `id UUID PK`
- `run_type VARCHAR(50) NOT NULL`
- `status VARCHAR(30) NOT NULL`
- `triggered_by_user_id UUID FK -> users.id NULL`
- `trigger_source VARCHAR(50) NOT NULL`
- `root_request_id VARCHAR(100) NULL`
- `started_at TIMESTAMPTZ NOT NULL DEFAULT now()`
- `finished_at TIMESTAMPTZ NULL`
- `duration_ms INTEGER NULL`
- `input_payload JSONB NULL`
- `output_payload JSONB NULL`
- `error_payload JSONB NULL`
- `metadata JSONB NOT NULL DEFAULT '{}'::jsonb`

## `service_runs`
- `id UUID PK`
- `pipeline_run_id UUID FK -> pipeline_runs.id NULL`
- `service_name VARCHAR(50) NOT NULL`
- `operation_name VARCHAR(100) NOT NULL`
- `status VARCHAR(30) NOT NULL`
- `started_at TIMESTAMPTZ NOT NULL DEFAULT now()`
- `finished_at TIMESTAMPTZ NULL`
- `duration_ms INTEGER NULL`
- `request_payload JSONB NULL`
- `response_payload JSONB NULL`
- `error_message TEXT NULL`
- `logs_excerpt TEXT NULL`
- `host_name VARCHAR(120) NULL`
- `container_id VARCHAR(120) NULL`

## `run_events`
- `id UUID PK`
- `pipeline_run_id UUID FK -> pipeline_runs.id NOT NULL`
- `service_run_id UUID FK -> service_runs.id NULL`
- `event_time TIMESTAMPTZ NOT NULL DEFAULT now()`
- `event_type VARCHAR(60) NOT NULL`
- `severity VARCHAR(20) NOT NULL DEFAULT 'info'`
- `message TEXT NOT NULL`
- `payload JSONB NOT NULL DEFAULT '{}'::jsonb`
- `sequence_no BIGINT NULL`

## `analysis_results`
- `id UUID PK`
- `pipeline_run_id UUID FK -> pipeline_runs.id NOT NULL`
- `candidate_profile_id UUID FK -> candidate_profiles.id NOT NULL`
- `job_post_id UUID FK -> job_posts.id NOT NULL`
- `score_overall NUMERIC(5,2) NULL`
- `score_explanation TEXT NULL`
- `strengths JSONB NOT NULL DEFAULT '[]'::jsonb`
- `weaknesses JSONB NOT NULL DEFAULT '[]'::jsonb`
- `missing_skills JSONB NOT NULL DEFAULT '[]'::jsonb`
- `behavioral_requirements JSONB NOT NULL DEFAULT '[]'::jsonb`
- `administrative_conditions JSONB NOT NULL DEFAULT '{}'::jsonb`
- `recommendations JSONB NOT NULL DEFAULT '{}'::jsonb`
- `raw_result JSONB NOT NULL`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`

## `generation_results`
- `id UUID PK`
- `pipeline_run_id UUID FK -> pipeline_runs.id NOT NULL`
- `candidate_profile_id UUID FK -> candidate_profiles.id NULL`
- `job_post_id UUID FK -> job_posts.id NULL`
- `generation_type VARCHAR(50) NOT NULL`
- `provider_id UUID FK -> llm_providers.id NULL`
- `model_id UUID FK -> llm_models.id NULL`
- `status VARCHAR(30) NOT NULL`
- `output_text TEXT NULL`
- `output_json JSONB NULL`
- `document_id UUID FK -> documents.id NULL`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`

# H. GitHub Actions, CI/CD

## `repositories`
- `id UUID PK`
- `provider VARCHAR(30) NOT NULL DEFAULT 'github'`
- `owner_name VARCHAR(120) NOT NULL`
- `repo_name VARCHAR(120) NOT NULL`
- `default_branch VARCHAR(120) NULL`
- `is_private BOOLEAN NULL`
- `html_url TEXT NULL`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`

## `github_workflows`
- `id UUID PK`
- `repository_id UUID FK -> repositories.id NOT NULL`
- `workflow_external_id BIGINT NOT NULL`
- `name VARCHAR(255) NOT NULL`
- `path VARCHAR(255) NOT NULL`
- `state VARCHAR(30) NULL`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`
- `updated_at TIMESTAMPTZ NOT NULL DEFAULT now()`
- `raw_json JSONB NULL`

## `github_workflow_runs`
- `id UUID PK`
- `repository_id UUID FK -> repositories.id NOT NULL`
- `workflow_id UUID FK -> github_workflows.id NULL`
- `run_external_id BIGINT NOT NULL`
- `run_number INTEGER NULL`
- `event VARCHAR(50) NULL`
- `status VARCHAR(30) NULL`
- `conclusion VARCHAR(30) NULL`
- `branch VARCHAR(120) NULL`
- `commit_sha CHAR(40) NULL`
- `actor_login VARCHAR(120) NULL`
- `html_url TEXT NULL`
- `started_at TIMESTAMPTZ NULL`
- `updated_at TIMESTAMPTZ NULL`
- `completed_at TIMESTAMPTZ NULL`
- `duration_seconds INTEGER NULL`
- `raw_json JSONB NOT NULL`

## `github_jobs`
- `id UUID PK`
- `workflow_run_id UUID FK -> github_workflow_runs.id NOT NULL`
- `job_external_id BIGINT NOT NULL`
- `name VARCHAR(255) NOT NULL`
- `status VARCHAR(30) NULL`
- `conclusion VARCHAR(30) NULL`
- `started_at TIMESTAMPTZ NULL`
- `completed_at TIMESTAMPTZ NULL`
- `runner_name VARCHAR(120) NULL`
- `runner_group_name VARCHAR(120) NULL`
- `raw_json JSONB NULL`

## `github_artifacts`
- `id UUID PK`
- `workflow_run_id UUID FK -> github_workflow_runs.id NOT NULL`
- `artifact_external_id BIGINT NOT NULL`
- `name VARCHAR(255) NOT NULL`
- `size_in_bytes BIGINT NULL`
- `download_url TEXT NULL`
- `expired BOOLEAN NULL`
- `created_at_remote TIMESTAMPTZ NULL`
- `expires_at_remote TIMESTAMPTZ NULL`
- `raw_json JSONB NULL`

## 4. Entités concrètes à précharger

### Organisations / unités
- Ministère des Affaires intérieures
- Police Grand-Ducale
- Direction centrale stratégie et performance
- GovJobs
- MyGuichet
- Commission européenne
- CNPD
- CIRCL
- Luxembourg House of Cybersecurity

### Réglementations / frameworks
- ISO/IEC 27001
- ISO 27xxx
- ISO 27005
- RGPD / GDPR
- NIS2
- ITIL
- COBIT
- EBIOS RM
- MEHARI

### Règles fonction publique luxembourgeoise
- Groupe A1
- niveau 7 CLQ minimum
- ressortissant UE
- 3 langues administratives
- épreuve spéciale obligatoire
- épreuve d’aptitude générale
- changement d’administration

## 5. Confidentialité / audit

### Données sensibles
- CV complets
- coordonnées perso
- nationalité
- date de naissance
- documents administratifs
- clés API et secrets

### Recommandations
1. chiffrement applicatif des secrets
2. chiffrement disque/volume
3. masquage UI/API
4. audit des accès sensibles
5. RBAC minimal
6. redaction des logs
7. séparation PII / analytics

## 6. Vues utiles dashboard
- `vw_active_job_posts`
- `vw_application_readiness`
- `vw_latest_analysis_per_application`
- `vw_llm_usage_summary`
- `vw_pipeline_live_status`
- `vw_github_actions_health`

## 7. Résumé

Le design cible est une base **PostgreSQL orientée audit + JSONB**, avec :
- stockage sécurisé des credentials,
- catalogue providers/modèles IA,
- historique de chats multi-LLM,
- stockage structuré des CV et offres JSON,
- candidatures et règles du recrutement public luxembourgeois,
- entités métier riches liées à Police Grand-Ducale / DSI / ISO27001 / RGPD / NIS2,
- runs pipeline temps réel,
- GitHub Actions observables,
- traçabilité et confidentialité natives.