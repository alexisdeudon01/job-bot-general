# MCP architecture blueprint

## Purpose of this document

This document defines the target MCP architecture for the project and explains the role of every MCP server currently configured in `.vscode/mcp.json`.

Covered servers:

- `io.github.ScrapeGraphAI/scrapegraph-mcp`
- `filesystem`
- `github`
- `postgres`
- `fetch`
- `memory`
- `playwright`

This blueprint aligns with:

- the current local MCP configuration in `.vscode/mcp.json`
- the transport guidance in `docs/mcp_transport_recommendations.md`
- the existence of an internal project MCP layer in `mcp_server/`

The goal is not to treat MCP as a generic add-on, but as a structured integration surface for the job-bot pipeline: scraping, repository/document access, persistence, browsing, memory, and controlled external connectivity.

---

## Executive summary

The project should adopt a **layered MCP architecture**:

1. **External MCP servers remain the capability providers**
   - ScrapeGraph for structured web extraction
   - filesystem for safe file access
   - github for repository and issue/PR access
   - postgres for SQL/database access
   - fetch for simple remote HTTP retrieval
   - memory for conversational or workflow memory
   - playwright for browser automation and dynamic page rendering

2. **The internal `mcp_server/` should become the project-facing MCP boundary**
   - It should encapsulate provider-specific details where the rest of the application needs stable business-oriented tools.
   - It should expose a unified project vocabulary around jobs, sources, research, extraction, evidence, and persistence.

3. **Not every server needs to be wrapped equally**
   - Some servers can remain directly consumable for development or operator workflows.
   - For production pipeline behavior, the project should prefer calling them through internal wrappers when consistency, policy, validation, and observability matter.

4. **Transport policy remains context-dependent**
   - `stdio` stays the default for local tools and local MCP subprocesses.
   - `streamable_http` is the preferred future transport for hosted internal MCP services.
   - `sse` is compatibility-only, not the target default for new internal services.

---

## Architecture principles

### 1. MCP servers should be selected by capability, not by transport

Project components should reason in terms of:

- scraping and extraction
- repository/document access
- database access
- browsing
- remote fetch
- memory

They should not depend directly on transport-specific implementation details such as a particular stdio client class.

### 2. The internal `mcp_server/` is the normalization layer

External MCP servers provide raw capabilities, but the project needs:

- stable tool naming
- validated inputs
- consistent error handling
- business-level abstractions
- auditability and observability
- policy enforcement on which tools may be used by which pipeline step

That normalization belongs behind `mcp_server/`.

### 3. Direct access is acceptable for low-risk utility servers

Some MCP servers are mostly infrastructural and do not always require a business wrapper for every use case. For example:

- `filesystem` for controlled local project access
- `fetch` for basic static URL retrieval in prototyping
- `memory` for non-critical state experiments

However, once these servers affect production decisions, generated outputs, or persistence, wrapper tools are recommended.

### 4. Prefer least-privilege access

Each MCP server introduces its own trust boundary and risk profile. The architecture should minimize broad permissions by:

- constraining filesystem roots
- scoping GitHub token permissions
- limiting database access rights
- controlling browser automation targets
- avoiding unrestricted external fetches in core business flows
- keeping secrets in environment variables, not in prompts or source code

---

## Global architecture view

## Logical layers

### A. Project clients and orchestration consumers

Potential MCP clients in this repository include:

- `app/` FastAPI orchestration and pipeline APIs
- `agent/` runner/pipeline execution logic
- `analyzer/` research, extraction, NLP, and enrichment services
- `generator/` content generation and output composition
- `dashboard/` operator UI via backend APIs rather than direct MCP use
- `mcp_server/` as the internal MCP façade

### B. External MCP capability providers

Configured providers from `.vscode/mcp.json`:

- ScrapeGraph MCP
- filesystem MCP
- GitHub MCP
- Postgres MCP
- fetch MCP
- memory MCP
- Playwright MCP

### C. Internal project MCP façade

`mcp_server/` should become the canonical project-owned interface for:

- business wrappers around external tools
- transport normalization
- policy and validation
- future migration from local tooling to hosted/internal services

### D. Data and artifact zones

Main data/resource zones already visible in the repository:

- project source tree
- `docs/`
- `data/`
- `output/`
- PostgreSQL database
- remote job boards and company sites
- GitHub repositories/issues/PRs
- browser-rendered sites
- transient workflow memory

---

## Current server inventory from `.vscode/mcp.json`

| Server | Transport | Command pattern | Primary role |
|---|---|---|---|
| `io.github.ScrapeGraphAI/scrapegraph-mcp` | `stdio` | `uvx scrapegraph-mcp@1.0.1` | structured scraping and extraction |
| `filesystem` | `stdio` | `npx @modelcontextprotocol/server-filesystem ...` | bounded local file access |
| `github` | `stdio` | `npx @modelcontextprotocol/server-github` | GitHub API access |
| `postgres` | `stdio` | `npx @modelcontextprotocol/server-postgres <connection>` | SQL/database access |
| `fetch` | `stdio` | `uvx mcp-server-fetch` | lightweight HTTP retrieval |
| `memory` | `stdio` | `npx @modelcontextprotocol/server-memory` | workflow/conversation memory |
| `playwright` | `stdio` | `npx @playwright/mcp` | browser automation and dynamic page access |

Even though all current local definitions use `stdio`, they represent different architectural roles and should not all be handled identically by the application.

---

## Server-by-server blueprint

## 1. ScrapeGraph MCP

### Configured server

- Logical configured name: `io.github.ScrapeGraphAI/scrapegraph-mcp`
- Transport: `stdio`
- Launch pattern: `uvx scrapegraph-mcp@1.0.1`
- Environment variable:
  - `SGAI_API_KEY`

### Objective

Provide structured web extraction capabilities for pages where the project needs more than raw HTML retrieval. This is the main MCP provider for:

- extracting job information from listings
- normalizing semi-structured content
- turning page content into markdown or structured fields
- supporting research flows that need semantic extraction rather than only DOM capture

### Why this server exists

The project is centered on job research, analysis, and content generation. Raw HTTP fetches are not enough for many target pages because the project needs:

- relevant field extraction
- content reduction
- page-to-structured-data transformation
- better signal-to-noise ratio than plain scraping

ScrapeGraph exists to make web content operational for downstream analyzer and generator stages.

### What the project wants to obtain from it

Typical expected outcomes:

- job title, company, location, contract type, skills, salary signals
- cleaned job description text
- structured extracts from company pages or hiring pages
- markdownified content for later summarization or generation
- targeted extraction from search/discovery workflows

### Potential MCP clients in this project

Most plausible consumers:

- `agent/` for execution of scraping stages
- `analyzer/` for extracting normalized facts from job pages
- `app/` orchestration services that trigger scraping/research pipelines
- `mcp_server/` as wrapper layer
- `generator/` only indirectly, after extraction has already been normalized

`dashboard/` should typically not call ScrapeGraph directly. It should consume results through backend APIs.

### Expected data and resources

Inputs:

- job listing URLs
- company career page URLs
- search result page URLs
- extraction prompts or schemas
- optional context about target fields

Outputs:

- markdown content
- extracted entities/attributes
- page summaries or structured objects
- normalized text payloads for analyzer/generator stages

### Dependencies

- `uvx`
- `scrapegraph-mcp@1.0.1`
- network access to target websites
- a valid `SGAI_API_KEY`

### Environment variables

- `SGAI_API_KEY`

Recommended project convention:

- keep this secret only in environment/config layers
- never serialize it into prompts, logs, or generated files

### Limits and caveats

- dependent on third-party provider behavior and quotas
- extraction quality depends on target page structure and prompt/tool semantics
- may fail on bot-protected, highly dynamic, or anti-scraping websites
- should not be assumed to replace browser automation in all cases
- can introduce cost and latency compared with simple fetches
- needs fallback strategies when extraction is incomplete

### Place in the global architecture

ScrapeGraph should be the **primary structured extraction provider** for web research, but not the only one.

Recommended role:

- use ScrapeGraph first for structured extraction
- use `fetch` for lightweight static retrieval when enough
- use `playwright` when dynamic rendering/login/interaction is needed
- expose business-safe wrappers through internal `mcp_server/`

### Encapsulation recommendation

**Encapsulate behind `mcp_server/` for production pipeline use.**

Reason:

- extraction contracts should be stable
- inputs should be validated
- outputs should be normalized to project schemas
- fallback and retry logic should be centralized
- downstream components should not depend on provider-specific tool names

Direct access can still remain useful for local debugging and experimentation.

---

## 2. filesystem MCP

### Configured server

- Logical configured name: `filesystem`
- Transport: `stdio`
- Launch pattern: `npx -y @modelcontextprotocol/server-filesystem ...`
- Allowed roots in current config:
  - `/home/tor/Downloads/job-bot-general`
  - `/home/tor/Downloads/job-bot-general/docs`
  - `/home/tor/Downloads/job-bot-general/data`
  - `/home/tor/Downloads/job-bot-general/output`

### Objective

Provide controlled local file access to project artifacts and working directories without giving unconstrained system-wide file system access.

### Why this server exists

The project manipulates multiple local artifact types:

- source files
- generated documents
- cached extraction results
- analysis outputs
- docs/specifications
- operational outputs

The filesystem server exists to give MCP-enabled workflows access to these artifacts within bounded directories.

### What the project wants to obtain from it

Typical outcomes:

- read job research artifacts from `data/` or `output/`
- inspect or write generated summaries/documents
- access project docs during reasoning
- persist intermediate pipeline outputs
- support developer/operator workflows around documentation and reports

### Potential MCP clients in this project

Most plausible consumers:

- `mcp_server/` for wrapper tools that read/write project artifacts
- `agent/` during execution if using MCP-based file artifact flows
- `analyzer/` for reading extracted datasets or cache files
- `generator/` for reading prompts/templates or saving results
- `app/` only via controlled service methods, not arbitrary direct reads
- `dashboard/` should avoid direct MCP filesystem access and should go through API endpoints

### Expected data and resources

Inputs:

- relative or allowed absolute file paths inside configured roots
- file names, directory names, search patterns
- content payloads when writing files

Outputs:

- file contents
- directory listings
- metadata
- confirmation of write/update operations

### Dependencies

- `npx`
- `@modelcontextprotocol/server-filesystem`
- local access rights to the configured directories

### Environment variables

No explicit environment variables are configured in `.vscode/mcp.json` for this server.

Operational dependency still exists on local OS permissions.

### Limits and caveats

- only useful within configured roots
- must not become a substitute for proper application storage APIs
- risk of over-coupling agents directly to repository layout
- write access should be carefully governed for production workflows
- direct arbitrary file mutations can undermine reproducibility

### Place in the global architecture

Filesystem MCP is a **supporting infrastructure server**, not a domain capability in itself.

Best role:

- local development and diagnostics
- controlled artifact reading/writing
- support for documentation and generated output handling
- wrapper-backed artifact management inside `mcp_server/`

### Encapsulation recommendation

**Partially encapsulate behind `mcp_server/`.**

Keep direct access available for development/operator tasks, but for production pipeline flows prefer project wrappers such as:

- read pipeline artifact
- write generated report
- load extraction cache
- persist normalized output

This reduces coupling to raw file paths and lets the project preserve a stable artifact contract.

---

## 3. GitHub MCP

### Configured server

- Logical configured name: `github`
- Transport: `stdio`
- Launch pattern: `npx -y @modelcontextprotocol/server-github`
- Environment variable:
  - `GITHUB_PERSONAL_ACCESS_TOKEN` sourced from `GITHUB_TOKEN`

### Objective

Provide access to GitHub repositories, issues, pull requests, files, and related metadata that may be needed for project operations, documentation, automation, or future integrations.

### Why this server exists

In this repository, GitHub MCP is useful for more than code browsing. It can support:

- repository-aware development workflows
- issue and backlog context
- documentation lookup
- external repository research if the job-bot later analyzes hiring/company repositories
- automation around project maintenance

### What the project wants to obtain from it

Typical outcomes:

- repository file access without local checkout assumptions
- issue/PR context for planning or documentation
- project coordination metadata
- future company/repo intelligence if relevant to job analysis

### Potential MCP clients in this project

Most plausible consumers:

- `mcp_server/` for repository-aware wrappers
- `app/` orchestration services in maintenance/admin workflows
- `agent/` in development-support or automation scenarios
- possibly `analyzer/` if repository signals are later used in company profiling
- `dashboard/` should use backend APIs instead of direct GitHub MCP access

### Expected data and resources

Inputs:

- repository owner/name
- issue or PR identifiers
- file paths
- branch/ref parameters
- search queries

Outputs:

- repository metadata
- issue/PR details
- file contents
- commit or branch information
- search results

### Dependencies

- `npx`
- `@modelcontextprotocol/server-github`
- GitHub API availability
- valid personal access token

### Environment variables

- `GITHUB_TOKEN` in local environment
- mapped to `GITHUB_PERSONAL_ACCESS_TOKEN` for server launch

### Limits and caveats

- rate limits and token scopes apply
- not all GitHub operations should be allowed in automated workflows
- repository data can be stale relative to local uncommitted state
- write-capable operations would need stricter governance
- this server is not central to the core job extraction pipeline

### Place in the global architecture

GitHub MCP is a **secondary operational integration**.

It is useful for:

- project maintenance
- development support
- optional knowledge enrichment
- future integration scenarios

It is not a primary dependency for the core scrape-analyze-generate path.

### Encapsulation recommendation

**Keep mostly external/direct, with selective wrappers in `mcp_server/`.**

Only wrap GitHub operations that become part of stable product workflows, for example:

- fetch project documentation context
- read issue-based runbook metadata
- gather repo metadata for admin dashboards

Avoid over-investing in wrappers until a clear business use case exists.

---

## 4. Postgres MCP

### Configured server

- Logical configured name: `postgres`
- Transport: `stdio`
- Launch pattern: `npx -y @modelcontextprotocol/server-postgres <connection-string>`
- Runtime input:
  - `postgresConnectionString`

### Objective

Provide SQL-level access to the PostgreSQL database used by the project for persistent storage, reporting, or analysis support.

### Why this server exists

The project stack includes:

- `sqlalchemy`
- `psycopg[binary]`

This strongly suggests a relational persistence layer is part of the application architecture. Postgres MCP exists to allow MCP-enabled workflows to:

- inspect database state
- run controlled queries
- support data retrieval and analytics
- potentially bootstrap admin/ops or read-oriented workflows

### What the project wants to obtain from it

Typical outcomes:

- fetch stored jobs, runs, analyses, or generated outputs
- inspect pipeline state
- support analytics or troubleshooting
- retrieve historical records for comparison or deduplication
- expose read-oriented data access through wrapper tools

### Potential MCP clients in this project

Most plausible consumers:

- `app/` orchestration/admin services
- `agent/` if workflow decisions need historical persistence context
- `analyzer/` for enrichment against stored data
- `dashboard/` indirectly through backend APIs, not directly
- `mcp_server/` as the controlled database façade

### Expected data and resources

Inputs:

- SQL queries
- table names or selection parameters
- database connection configuration
- optionally transaction or schema context

Outputs:

- row sets
- schema details
- query execution status
- database metadata

### Dependencies

- `npx`
- `@modelcontextprotocol/server-postgres`
- reachable PostgreSQL instance
- valid connection string
- appropriate DB roles and privileges

### Environment variables

No fixed environment variable is hardcoded in `.vscode/mcp.json`, but the server requires:

- a PostgreSQL connection string supplied as `postgresConnectionString`

The parent application may already hold DB credentials in `.env`; those should be mapped to the MCP configuration layer rather than duplicated manually.

### Limits and caveats

- direct SQL exposure is powerful and risky
- schema drift can break prompts/tools if wrappers are not used
- write operations can create data integrity issues
- access control must be stricter than for read-only utility servers
- raw SQL tools should not become the default persistence API for normal application logic

### Place in the global architecture

Postgres MCP is a **high-value, high-risk infrastructure integration**.

Its best role is:

- read-oriented introspection
- controlled reporting
- wrapper-mediated access to stable data views
- operational diagnostics

It should not replace the normal SQLAlchemy/application service layer for core CRUD behavior.

### Encapsulation recommendation

**Strongly encapsulate behind `mcp_server/` for application-facing use.**

Recommended pattern:

- expose business queries through wrapper tools
- make direct SQL access admin-only or development-only
- prefer read-only roles when possible
- normalize results to project schemas

This is one of the strongest candidates for internal wrapping.

---

## 5. fetch MCP

### Configured server

- Logical configured name: `fetch`
- Transport: `stdio`
- Launch pattern: `uvx mcp-server-fetch`

### Objective

Provide lightweight HTTP retrieval for simple remote content access where full browser automation or structured extraction is unnecessary.

### Why this server exists

Not all URLs require ScrapeGraph or Playwright. Many tasks only need:

- raw HTML
- plain text
- static documents
- lightweight API responses

The fetch server exists as the cheapest network-access capability in the MCP inventory.

### What the project wants to obtain from it

Typical outcomes:

- retrieve static job pages
- fetch robots-friendly content quickly
- pull text or JSON from simple endpoints
- collect seed content before handing off to analyzer steps
- support health checks and lightweight enrichment

### Potential MCP clients in this project

Most plausible consumers:

- `agent/` for lightweight acquisition steps
- `analyzer/` for simple remote document retrieval
- `mcp_server/` wrappers that implement a fetch-then-normalize pattern
- `app/` orchestration when selecting low-cost retrieval strategies

`dashboard/` should not use it directly.

### Expected data and resources

Inputs:

- URL
- optional headers or request options depending on server capabilities
- fetch intent or content type expectations

Outputs:

- raw response body
- text/HTML/JSON payloads
- status and metadata

### Dependencies

- `uvx`
- `mcp-server-fetch`
- network access to target resources

### Environment variables

No explicit environment variables are configured for fetch in `.vscode/mcp.json`.

### Limits and caveats

- insufficient for heavily dynamic pages
- may fail where JavaScript rendering is required
- provides lower-level content than ScrapeGraph
- can produce noisy raw payloads that need post-processing
- should be governed to avoid indiscriminate crawling behavior

### Place in the global architecture

Fetch MCP is the **low-cost retrieval baseline**.

Recommended usage order:

- use `fetch` for simple static retrieval
- escalate to ScrapeGraph for structured extraction
- escalate to Playwright when rendering/interaction is required

### Encapsulation recommendation

**Keep available directly, but wrap core business flows through `mcp_server/`.**

A wrapper is useful when the project wants:

- standardized URL validation
- content-type checks
- normalization of raw responses
- fallback policies to ScrapeGraph or Playwright

---

## 6. memory MCP

### Configured server

- Logical configured name: `memory`
- Transport: `stdio`
- Launch pattern: `npx -y @modelcontextprotocol/server-memory`

### Objective

Provide MCP-managed memory that can preserve contextual facts, workflow state, or reusable observations across tool interactions.

### Why this server exists

The project has multi-step workflows across scraping, analysis, and generation. Memory is useful for:

- storing temporary facts about a run
- keeping discovered context between tool calls
- reducing repeated retrieval of the same supporting information
- maintaining lightweight research state

### What the project wants to obtain from it

Typical outcomes:

- run-level notes about discovered companies/jobs
- intermediate facts before persistence
- contextual state for multi-step MCP sessions
- temporary memory for research assistance

### Potential MCP clients in this project

Most plausible consumers:

- `agent/` during long-running orchestration sessions
- `analyzer/` during iterative extraction/enrichment
- `mcp_server/` wrappers that maintain research context
- `app/` orchestration if sessions are MCP-centric

`dashboard/` should not access memory directly.

### Expected data and resources

Inputs:

- keys, topics, or memory identifiers
- facts, summaries, notes, associations
- retrieval queries

Outputs:

- stored memory entries
- recalled facts
- linked context for ongoing workflows

### Dependencies

- `npx`
- `@modelcontextprotocol/server-memory`

### Environment variables

No explicit environment variables are configured in `.vscode/mcp.json`.

### Limits and caveats

- memory is not a substitute for durable persistence
- exact retention and retrieval semantics may differ from application needs
- can create ambiguity if the same fact exists in DB, files, and memory
- should be scoped carefully per run/session/user
- must not become a hidden source of truth

### Place in the global architecture

Memory MCP is a **session/state assistive service**, not a system of record.

Best role:

- ephemeral orchestration support
- MCP-session continuity
- temporary reasoning context
- optional research assistance

### Encapsulation recommendation

**Use selectively behind `mcp_server/` or an orchestration adapter.**

Do not expose memory as a primary application contract. Wrap it when the project needs explicit semantics such as:

- run context memory
- research notes memory
- temporary evidence cache

Durable data should still go to the normal database or artifact storage.

---

## 7. Playwright MCP

### Configured server

- Logical configured name: `playwright`
- Transport: `stdio`
- Launch pattern: `npx -y @playwright/mcp`

### Objective

Provide browser automation and DOM interaction for pages that cannot be handled reliably through simple HTTP fetch or structured extraction alone.

### Why this server exists

Modern job and company sites often require:

- JavaScript rendering
- interaction before content appears
- navigation through client-side routes
- screenshot or DOM-level inspection
- waiting for async page hydration

Playwright exists to handle the class of web targets that are too dynamic for fetch and too interaction-heavy for direct extraction tools.

### What the project wants to obtain from it

Typical outcomes:

- rendered page content
- DOM state after interaction
- extraction preconditions for dynamic sites
- navigation to job detail pages
- screenshots or page evidence where needed
- fallback access to anti-static or JS-heavy experiences

### Potential MCP clients in this project

Most plausible consumers:

- `agent/` for dynamic acquisition workflows
- `analyzer/` where source content only appears after rendering
- `mcp_server/` for dynamic-page wrapper tools
- `app/` orchestration when choosing a retrieval strategy

`dashboard/` should not use Playwright directly.

### Expected data and resources

Inputs:

- URLs
- navigation instructions
- selectors
- waits/interactions
- extraction goals
- browser session parameters depending on available server tools

Outputs:

- rendered page text or HTML
- DOM fragments
- screenshots
- interaction results
- evidence for downstream extraction

### Dependencies

- `npx`
- `@playwright/mcp`
- browser binaries/runtime support
- network access to target sites
- local environment compatible with browser automation

### Environment variables

No explicit environment variables are configured in `.vscode/mcp.json`.

Operational dependencies may still include system libraries needed for browser execution.

### Limits and caveats

- heavier and slower than fetch or direct extraction
- more fragile when site flows change
- may require anti-bot mitigation handling outside normal tool use
- browser sessions consume more resources
- not appropriate as the default retrieval path for all URLs

### Place in the global architecture

Playwright MCP is the **dynamic-site fallback and browser automation layer**.

Recommended retrieval hierarchy:

1. `fetch` for simple/static targets
2. ScrapeGraph for structured extraction
3. Playwright when rendering or interaction is required

In some cases Playwright and ScrapeGraph can be combined, with Playwright obtaining rendered content and a later stage normalizing it.

### Encapsulation recommendation

**Encapsulate for production use behind `mcp_server/`.**

Reason:

- navigation and wait policies should be standardized
- browser actions should be constrained and observable
- downstream systems should receive normalized page artifacts, not arbitrary browser traces
- retry/fallback logic belongs in one place

Direct access can remain useful for debugging site-specific scraping failures.

---

## Cross-server architecture roles

## Capability map

| Capability | Primary server | Secondary/fallback server | Internal wrapping priority |
|---|---|---|---|
| Structured web extraction | ScrapeGraph | Playwright + analyzer normalization | High |
| Static remote retrieval | fetch | ScrapeGraph | Medium |
| Dynamic site rendering | Playwright | none | High |
| Local artifacts and docs | filesystem | none | Medium |
| Database inspection/query | postgres | application DB services | Very high |
| Project/repository context | github | filesystem/local git checkout | Low to medium |
| Session memory | memory | database/files if durable | Medium |

---

## Recommended client-to-server interaction model

## Preferred path for core product workflows

For business-critical workflows, the preferred path should be:

`app / agent / analyzer / generator -> internal project service layer -> mcp_server/ wrappers -> external MCP servers`

Benefits:

- provider abstraction
- stable schemas
- centralized retries and fallbacks
- transport independence
- observability
- permission governance

## Acceptable direct access cases

Direct external MCP access is acceptable for:

- local development
- debugging
- operator experiments
- documentation assistance
- low-risk utility tasks

But this should not be the main production interaction model for core scraping and persistence flows.

## Dashboard position

The `dashboard/` layer should generally **not** talk directly to MCP servers. It should consume backend APIs that already encapsulate MCP use. This keeps credentials, policies, and tool semantics out of the UI layer.

---

## Dependencies and environment summary

| Server | Key dependencies | Environment/config |
|---|---|---|
| ScrapeGraph | `uvx`, `scrapegraph-mcp@1.0.1`, external network | `SGAI_API_KEY` |
| filesystem | `npx`, `@modelcontextprotocol/server-filesystem`, local FS permissions | configured allowed roots |
| github | `npx`, `@modelcontextprotocol/server-github`, GitHub API | `GITHUB_TOKEN` -> `GITHUB_PERSONAL_ACCESS_TOKEN` |
| postgres | `npx`, `@modelcontextprotocol/server-postgres`, reachable DB | `postgresConnectionString` |
| fetch | `uvx`, `mcp-server-fetch`, external network | none required in current config |
| memory | `npx`, `@modelcontextprotocol/server-memory` | none required in current config |
| playwright | `npx`, `@playwright/mcp`, browser runtime/system libs | none explicit in current config |

---

## Risks and governance concerns

## 1. Secret handling

Sensitive values involved:

- `SGAI_API_KEY`
- `GITHUB_TOKEN`
- PostgreSQL connection string

These should be managed only through environment/config layers and never be embedded into prompts, generated files, or client-side code.

## 2. Over-direct tool usage

If application components talk directly to every third-party MCP server:

- business logic becomes provider-coupled
- error handling becomes inconsistent
- result schemas drift
- security policy is harder to enforce

This is the main reason to invest in internal wrappers.

## 3. Transport lock-in

Even though current local configs are `stdio`, the architecture should remain transport-neutral. The project should identify servers by logical capability names, not by client implementation classes.

## 4. Mixed sources of truth

Potential state can live in:

- database
- files
- MCP memory
- external pages

The architecture should clearly separate:

- durable truth: database / persisted artifacts
- ephemeral context: memory
- external source evidence: fetched or scraped pages

---

## Architecture cible

## Target position by server

### ScrapeGraph
- **Target**: keep external provider, but **encapsulate behind internal `mcp_server/` wrappers** for production usage
- **Reason**: core business capability, needs stable schemas and fallback handling

### filesystem
- **Target**: keep external server as-is for local utility access, but **wrap project-critical artifact operations**
- **Reason**: raw file paths should not be the project’s stable business API

### github
- **Target**: **keep mostly external as-is**
- **Reason**: useful but not core to product runtime; wrap only if stable business workflows emerge

### postgres
- **Target**: keep external provider available, but **strongly encapsulate behind internal `mcp_server/` tools**
- **Reason**: high-risk integration that needs policy, role separation, and schema-safe access patterns

### fetch
- **Target**: keep external server available, with **optional internal wrappers for URL validation and fallback orchestration**
- **Reason**: low-level capability that is useful directly, but business flows still benefit from normalization

### memory
- **Target**: keep external server available, with **light internal wrapping where session semantics matter**
- **Reason**: useful as ephemeral support, but should not become a hidden application contract

### playwright
- **Target**: keep external provider, but **encapsulate behind internal wrappers for production scraping flows**
- **Reason**: expensive and complex capability that needs governed interaction patterns

---

## Target architecture decision

### Keep the external MCP servers
Yes. They should remain the underlying capability providers because they already map well to the project’s needs and allow modular extension.

### Encapsulate behind the internal `mcp_server/`
Also yes, but selectively.

Recommended policy:

- **Encapsulate by default** for:
  - ScrapeGraph
  - postgres
  - Playwright

- **Encapsulate when used in stable product flows** for:
  - filesystem
  - fetch
  - memory

- **Leave mostly direct unless productized** for:
  - github

This yields a practical hybrid model:

- external MCP servers continue to provide specialized capabilities
- internal `mcp_server/` becomes the project contract for workflows that matter operationally

---

## Target interaction pattern

### Near-term

- Keep all currently configured external MCP servers available in local development.
- Continue using `stdio` for local invocation.
- Start routing core scraping and persistence behavior through `mcp_server/` wrappers.

### Mid-term

- Introduce a transport-neutral MCP registry/config model in application code.
- Make orchestration choose servers by logical name and capability.
- Normalize outputs from wrapped servers into project-defined schemas.

### Long-term

- Host internal MCP wrappers via `streamable_http` when services need to be shared across processes or deployments.
- Preserve compatibility with external stdio-based local servers for development.
- Maintain clear distinction between:
  - external provider MCPs
  - internal business MCP façade
  - normal application APIs

---

## Final recommendation

The project should adopt the following MCP architecture stance:

1. **Retain all configured external MCP servers** as capability providers.
2. **Do not let application code depend directly on provider-specific tools for core workflows.**
3. **Use `mcp_server/` as the stable internal MCP façade**, especially for ScrapeGraph, Postgres, and Playwright.
4. **Treat filesystem, fetch, and memory as utility-capability servers** that can be wrapped incrementally as workflows mature.
5. **Keep GitHub MCP mostly optional and operational** unless a concrete product use case requires stronger integration.
6. **Preserve transport neutrality in the architecture**, even though current local execution is stdio-first.

This approach gives the repository a clear MCP operating model: external capabilities remain modular, but the project-owned `mcp_server/` becomes the stable business boundary.