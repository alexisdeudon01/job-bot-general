from __future__ import annotations

import os
from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import uuid4

if TYPE_CHECKING:
    from app.services.openai_agents_service import MCPServerConfig

from app.schemas.pipeline import (
    PipelineRequest,
    PipelineRunResponse,
    PipelineRunsResponse,
    PipelineRunSummary,
    PipelineStepResult,
)


class PipelineService:
    def __init__(self) -> None:
        self._runs: list[PipelineRunSummary] = []

    def _resolve_cv_path(self, cv_pdf_path: str) -> str | None:
        """
        Resolve and validate a user-supplied CV path so that it stays within a
        dedicated base directory. Returns an absolute, normalized path or None
        if the input is invalid.
        """
        if not cv_pdf_path:
            return None

        # Base directory for CV PDFs; can be overridden via environment
        base_dir = os.environ.get("CV_UPLOAD_DIR", os.path.join(os.getcwd(), "uploads", "cv"))
        base_dir_abs = os.path.abspath(base_dir)

        # Join and normalize to eliminate ".." etc.
        candidate = os.path.normpath(os.path.join(base_dir_abs, cv_pdf_path))

        # Ensure the resolved path is still under the base directory
        # using commonpath for robustness across platforms.
        try:
            common = os.path.commonpath([base_dir_abs, candidate])
        except ValueError:
            return None

        if common != base_dir_abs:
            return None

        return candidate

    # ──────────────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────────────

    def list_runs(self) -> PipelineRunsResponse:
        return PipelineRunsResponse(runs=list(reversed(self._runs)))

    def run_analyze(self, request: PipelineRequest) -> PipelineRunResponse:
        steps = [
            PipelineStepResult(
                step="collect",
                status="completed",
                detail="Payload received for analysis",
                output={
                    "source": request.source,
                    "payload_keys": list(request.payload.keys()),
                },
            ),
            PipelineStepResult(
                step="analyze",
                status="completed",
                detail="Preparatory analysis complete",
                output={"mode": "mcp_first"},
            ),
        ]
        return self._build_run("analyze", request, steps)

    def run_generate(self, request: PipelineRequest) -> PipelineRunResponse:
        steps = [
            PipelineStepResult(
                step="prepare",
                status="completed",
                detail="Generation context prepared",
                output={"options": request.options},
            ),
            PipelineStepResult(
                step="generate",
                status="completed",
                detail="Generation complete",
                output={"artifacts": ["cover_letter_draft", "fit_assessment_json"]},
            ),
        ]
        return self._build_run("generate", request, steps)

    def run_full(self, request: PipelineRequest) -> PipelineRunResponse:
        payload = dict(request.payload)
        job_url: str = payload.get("job_url") or request.job_url or ""
        cv_pdf_path: str = payload.get("cv_pdf_path") or request.cv_pdf_path or ""

        steps: list[PipelineStepResult] = []

        # ── Step 1: Scrape job URL via OpenAI Agents SDK + ScrapeGraph MCP ───
        job_content: str | dict[str, Any] = ""
        scrape_tool = "none"
        scrape_status = "skipped"
        scrape_detail = "No job URL provided"

        if job_url:
            # Primary path: OpenAI Agents SDK with ScrapeGraph MCP (stdio)
            agents_scrape_ok = False
            if os.getenv("OPENAI_API_KEY") and os.getenv("SGAI_API_KEY"):
                try:
                    from app.services.openai_agents_service import openai_agents_service

                    scrapegraph_cfg = (
                        openai_agents_service.build_scrapegraph_stdio_config()
                    )
                    agent_result = openai_agents_service.run_agent(
                        prompt=(
                            f"Use the markdownify tool to scrape this job posting URL and return "
                            f"the full markdown content of the page: {job_url}"
                        ),
                        instructions=(
                            "You are a web scraping assistant. "
                            "Use the available MCP tools to fetch and return the raw markdown content "
                            "of the requested URL. Return only the markdown content, no commentary."
                        ),
                        mcp_server_configs=[scrapegraph_cfg],
                    )
                    job_content = (
                        agent_result.get("text")
                        or agent_result.get("output")
                        or agent_result.get("result")
                        or ""
                    )
                    scrape_tool = f"openai_agents + scrapegraph.markdownify (MCP stdio, model={agent_result.get('model','')})"
                    scrape_status = "completed"
                    scrape_detail = f"Job page scraped via OpenAI Agents SDK + ScrapeGraph MCP ({len(job_content)} chars)"
                    agents_scrape_ok = True
                except Exception as exc:
                    scrape_detail = f"OpenAI Agents+MCP scrape failed: {str(exc)[:150]}"

            # Fallback: direct scrapegraph-py SDK call (no OpenAI Agents)
            if not agents_scrape_ok:
                try:
                    from scrapegraphai.graphs import SmartScraperGraph  # type: ignore[import]

                    graph = SmartScraperGraph(
                        prompt="Extract the full markdown content of this job posting page.",
                        source=job_url,
                        config={
                            "llm": {
                                "api_key": os.getenv("SGAI_API_KEY", ""),
                                "model": "openai/gpt-4o-mini",
                            }
                        },
                    )
                    result = graph.run()
                    job_content = (
                        result.get("markdown", "")
                        if isinstance(result, dict)
                        else str(result)
                    )
                    scrape_tool = (
                        "scrapegraphai.SmartScraperGraph (direct SDK fallback)"
                    )
                    scrape_status = "completed"
                    scrape_detail = f"Job page scraped via ScrapeGraphAI direct SDK ({len(job_content)} chars)"
                except Exception as exc2:
                    scrape_status = "failed"
                    scrape_tool = "scrapegraph.markdownify"
                    scrape_detail = f"ScrapeGraph unavailable: {str(exc2)[:150]}"
                    job_content = ""

        steps.append(
            PipelineStepResult(
                step="1_scrape_job_url",
                status=scrape_status,
                detail=scrape_detail,
                output={
                    "tool": scrape_tool,
                    "job_url": job_url or "(not provided)",
                    "content_length": len(self._stringify_content(job_content)),
                    "content_preview": (
                        self._stringify_content(job_content)[:600]
                        if job_content
                        else ""
                    ),
                },
            )
        )

        # ── Step 2: Read CV PDF ───────────────────────────────────────────────
        cv_text = ""
        cv_status = "skipped"
        cv_detail = "No CV path provided"

        if cv_pdf_path:
            safe_cv_path = self._resolve_cv_path(cv_pdf_path)
            if safe_cv_path is None:
                cv_status = "failed"
                cv_detail = "Invalid CV path"
            elif os.path.exists(safe_cv_path):
                try:
                    import pdfplumber

                    with pdfplumber.open(safe_cv_path) as pdf:
                        cv_text = "\n".join(
                            page.extract_text() or "" for page in pdf.pages
                        )
                    cv_status = "completed"
                    cv_detail = f"CV extracted ({len(cv_text)} chars)"
                except Exception as exc:
                    cv_status = "failed"
                    cv_detail = f"CV extraction failed: {str(exc)[:150]}"
            else:
                cv_status = "failed"
                cv_detail = f"CV file not found: {cv_pdf_path}"

        steps.append(
            PipelineStepResult(
                step="2_read_cv_pdf",
                status=cv_status,
                detail=cv_detail,
                output={
                    "tool": "pdfplumber",
                    "cv_pdf_path": cv_pdf_path or "(not provided)",
                    "cv_text_length": len(cv_text),
                    "cv_preview": cv_text[:400] if cv_text else "",
                },
            )
        )

        # ── Step 3: Generate cover letter via OpenAI ──────────────────────────
        cover_letter = ""
        prompt_used = ""
        openai_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        openai_status = "skipped"
        openai_detail = "OPENAI_API_KEY not configured"
        tools_called: list[str] = []

        if os.getenv("OPENAI_API_KEY"):
            # Primary path: OpenAI Agents SDK with ScrapeGraph MCP
            agents_gen_ok = False
            if os.getenv("SGAI_API_KEY"):
                try:
                    from app.services.openai_agents_service import openai_agents_service

                    scrapegraph_cfg = (
                        openai_agents_service.build_scrapegraph_stdio_config()
                    )
                    cover_letter, prompt_used = self._generate_cover_letter_agents(
                        job_content=job_content,
                        job_url=job_url,
                        cv_text=cv_text,
                        model=openai_model,
                        scrapegraph_cfg=scrapegraph_cfg,
                    )
                    openai_status = "completed"
                    openai_detail = f"Cover letter generated via OpenAI Agents SDK + MCP ({len(cover_letter)} chars)"
                    tools_called = [f"openai_agents ({openai_model}) + scrapegraph MCP"]
                    agents_gen_ok = True
                except Exception as exc:
                    openai_detail = (
                        f"Agents SDK generation failed, falling back: {str(exc)[:150]}"
                    )

            # Fallback: direct OpenAI chat completions
            if not agents_gen_ok:
                try:
                    cover_letter, prompt_used = self._generate_cover_letter(
                        job_content=job_content,
                        job_url=job_url,
                        cv_text=cv_text,
                        model=openai_model,
                    )
                    openai_status = "completed"
                    openai_detail = f"Cover letter generated by OpenAI {openai_model} ({len(cover_letter)} chars)"
                    tools_called = [f"openai.chat.completions ({openai_model})"]
                except Exception as exc:
                    openai_status = "failed"
                    openai_detail = f"OpenAI generation failed: {str(exc)[:200]}"
                    cover_letter = f"Erreur: {str(exc)}"

        steps.append(
            PipelineStepResult(
                step="3_generate_cover_letter",
                status=openai_status,
                detail=openai_detail,
                output={
                    "tool": f"openai.chat.completions ({openai_model})",
                    "model": openai_model,
                    "tools_called": tools_called,
                    "prompt_used": prompt_used,
                    "cover_letter": cover_letter,
                    "cover_letter_length": len(cover_letter),
                },
            )
        )

        # ── Step 4: Fit assessment ────────────────────────────────────────────
        fit_assessment = ""
        fit_status = "skipped"
        fit_detail = "OPENAI_API_KEY not configured"
        fit_prompt = ""

        if os.getenv("OPENAI_API_KEY") and (job_content or job_url):
            try:
                fit_assessment, fit_prompt = self._assess_fit(
                    job_content=job_content,
                    job_url=job_url,
                    cv_text=cv_text,
                    model=openai_model,
                )
                fit_status = "completed"
                fit_detail = f"Fit assessment generated by OpenAI {openai_model}"
            except Exception as exc:
                fit_status = "failed"
                fit_detail = f"Fit assessment failed: {str(exc)[:150]}"

        steps.append(
            PipelineStepResult(
                step="4_assess_fit",
                status=fit_status,
                detail=fit_detail,
                output={
                    "tool": f"openai.chat.completions ({openai_model})",
                    "model": openai_model,
                    "prompt_used": fit_prompt,
                    "fit_assessment": fit_assessment,
                },
            )
        )

        # Determine overall status
        statuses = {s.status for s in steps}
        if "failed" in statuses:
            overall = "partial"
        elif all(s in ("completed", "skipped") for s in statuses):
            overall = "completed"
        else:
            overall = "partial"

        return self._build_run(
            "full",
            request,
            steps,
            metadata={
                "source": request.source,
                "options": request.options,
                "job_url": job_url,
                "cv_pdf_path": cv_pdf_path,
                "mode": "openai_agents_mcp",
                "cover_letter_generated": bool(cover_letter),
                "openai_model": openai_model,
            },
            override_status=overall,
        )

    # ──────────────────────────────────────────────────────────────────────────
    # Private helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _generate_cover_letter(
        self,
        *,
        job_content: str | dict[str, Any],
        job_url: str,
        cv_text: str,
        model: str,
    ) -> tuple[str, str]:
        """Generate a cover letter using OpenAI. Returns (cover_letter, prompt_used)."""
        from openai import OpenAI

        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        job_content_text = self._stringify_content(job_content)
        job_section = ""
        if job_content_text:
            job_section = f"Contenu de l'offre d'emploi:\n{job_content_text[:4000]}"
        elif job_url:
            job_section = f"URL de l'offre d'emploi: {job_url}\n(Contenu non disponible — rédige une lettre générique adaptée au poste si possible.)"
        else:
            job_section = "Aucune offre d'emploi fournie. Rédige une lettre de motivation générique professionnelle."

        cv_section = ""
        if cv_text:
            cv_section = f"\nCV du candidat:\n{cv_text[:3000]}"
        else:
            cv_section = "\nCV: Non fourni. Rédige une lettre adaptable."

        prompt = f"""Tu es un expert en recrutement et rédaction de lettres de motivation professionnelles.

{job_section}
{cv_section}

Rédige une lettre de motivation professionnelle et convaincante en français pour ce poste.

La lettre doit:
1. Commencer par une accroche percutante qui montre la connaissance de l'entreprise/poste
2. Présenter les compétences et expériences les plus pertinentes pour ce poste
3. Montrer l'enthousiasme et la motivation pour le poste et l'entreprise
4. Se terminer par un appel à l'action (demande d'entretien)
5. Être structurée en 3-4 paragraphes bien construits
6. Avoir un ton professionnel, dynamique et personnel
7. Faire entre 300 et 450 mots

Retourne uniquement la lettre de motivation complète, sans commentaires ni explications."""

        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Tu es un expert en rédaction de lettres de motivation professionnelles en français. "
                        "Tu rédiges des lettres percutantes, personnalisées et efficaces qui maximisent les chances d'obtenir un entretien."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=1500,
        )

        cover_letter = response.choices[0].message.content or ""
        return cover_letter, prompt

    def _generate_cover_letter_agents(
        self,
        *,
        job_content: str | dict[str, Any],
        job_url: str,
        cv_text: str,
        model: str,
        scrapegraph_cfg: "MCPServerConfig",
    ) -> tuple[str, str]:
        """Generate a cover letter using OpenAI Agents SDK with ScrapeGraph MCP tools.
        Returns (cover_letter, prompt_used).
        """
        from app.services.openai_agents_service import openai_agents_service

        job_content_text = self._stringify_content(job_content)
        job_section = ""
        if job_content_text:
            job_section = f"Contenu de l'offre d'emploi:\n{job_content_text[:4000]}"
        elif job_url:
            job_section = f"URL de l'offre d'emploi: {job_url}"
        else:
            job_section = "Aucune offre fournie."

        cv_section = (
            f"\nCV du candidat:\n{cv_text[:3000]}" if cv_text else "\nCV: Non fourni."
        )

        prompt = f"""Tu es un expert en recrutement et rédaction de lettres de motivation professionnelles.

{job_section}
{cv_section}

Rédige une lettre de motivation professionnelle et convaincante en français pour ce poste.

La lettre doit:
1. Commencer par une accroche percutante qui montre la connaissance de l'entreprise/poste
2. Présenter les compétences et expériences les plus pertinentes pour ce poste
3. Montrer l'enthousiasme et la motivation pour le poste et l'entreprise
4. Se terminer par un appel à l'action (demande d'entretien)
5. Être structurée en 3-4 paragraphes bien construits
6. Avoir un ton professionnel, dynamique et personnel
7. Faire entre 300 et 450 mots

Si tu as accès à des outils de scraping, tu peux les utiliser pour enrichir ta connaissance du poste ou de l'entreprise.
Retourne uniquement la lettre de motivation complète, sans commentaires ni explications."""

        result = openai_agents_service.run_agent(
            prompt=prompt,
            instructions=(
                "Tu es un expert en rédaction de lettres de motivation professionnelles en français. "
                "Tu rédiges des lettres percutantes, personnalisées et efficaces. "
                "Si des outils MCP sont disponibles, utilise-les pour enrichir ta réponse."
            ),
            mcp_server_configs=[scrapegraph_cfg],
            model=model,
        )
        cover_letter = result.get("text", "")
        return cover_letter, prompt

    def _assess_fit(
        self,
        *,
        job_content: str | dict[str, Any],
        job_url: str,
        cv_text: str,
        model: str,
    ) -> tuple[str, str]:
        """Assess candidate fit for the job. Returns (assessment, prompt_used)."""
        from openai import OpenAI

        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        job_content_text = self._stringify_content(job_content)
        job_section = (
            f"Offre d'emploi:\n{job_content_text[:3000]}"
            if job_content_text
            else f"URL: {job_url}"
        )
        cv_section = f"CV:\n{cv_text[:2000]}" if cv_text else "CV: Non fourni."

        prompt = f"""Tu es un expert en recrutement.

{job_section}

{cv_section}

Analyse l'adéquation entre le candidat et le poste. Fournis:
1. Score de compatibilité (0-100%)
2. Points forts du candidat pour ce poste
3. Points à améliorer ou manquants
4. Recommandations pour l'entretien

Sois concis et structuré."""

        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "Tu es un expert en recrutement et évaluation de candidatures.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=800,
        )

        assessment = response.choices[0].message.content or ""
        return assessment, prompt

    @staticmethod
    def _stringify_content(value: str | dict[str, Any] | Any) -> str:
        if isinstance(value, str):
            return value
        if isinstance(value, dict):
            markdown = value.get("markdown")
            if isinstance(markdown, str) and markdown.strip():
                return markdown
            result = value.get("result")
            if isinstance(result, str) and result.strip():
                return result
            if isinstance(result, dict):
                nested_md = result.get("markdown")
                if isinstance(nested_md, str) and nested_md.strip():
                    return nested_md
            try:
                import json

                return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)
            except Exception:
                return str(value)
        if value is None:
            return ""
        return str(value)

    def _build_run(
        self,
        pipeline_type: str,
        request: PipelineRequest,
        steps: list[PipelineStepResult],
        metadata: dict | None = None,
        override_status: str | None = None,
    ) -> PipelineRunResponse:
        now = datetime.utcnow()
        run_id = f"run-{uuid4().hex[:12]}"

        if override_status:
            final_status = override_status
        else:
            final_status = (
                "completed"
                if all(s.status in ("completed", "skipped") for s in steps)
                else "partial"
            )

        response = PipelineRunResponse(
            run_id=run_id,
            pipeline_type=pipeline_type,
            status=final_status,
            created_at=now,
            steps=steps,
            metadata=metadata or {"source": request.source, "options": request.options},
        )
        self._runs.append(
            PipelineRunSummary(
                run_id=run_id,
                pipeline_type=pipeline_type,
                status=final_status,
                created_at=now,
                updated_at=now,
                source=request.source,
            )
        )
        self._runs[:] = self._runs[-50:]
        return response


pipeline_service = PipelineService()
