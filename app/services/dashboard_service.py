from collections import Counter
from datetime import datetime
from typing import Any

from sqlalchemy import func, inspect, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app.db.session import SessionLocal
from app.integrations.github_actions import list_github_action_runs
from app.integrations.providers import get_provider_statuses
from app.models.entities import (
    Authority,
    BusinessEntity,
    EntityRelationship,
    Framework,
    Location,
    Organization,
    OrganizationalUnit,
)
from app.models.github_actions import GitHubWorkflowJob, GitHubWorkflowRun
from app.models.llm import ChatMessage, ChatSession, LLMModel, Secret
from app.models.pipeline import PipelineRun, Provider, RunEvent, ServiceRun
from app.schemas.dashboard import DashboardMetric, DashboardOverview
from app.services.pipeline_service import pipeline_service


class DashboardService:
    def get_overview(self) -> DashboardOverview:
        pipeline_runs = pipeline_service.list_runs().runs
        github_runs = list_github_action_runs()
        services = get_provider_statuses()
        entities_summary = self.get_entities_detail()
        llm_summary = self.get_llm_history_summary()
        mcp_summary = self.get_mcp_status_detail()

        metrics = [
            DashboardMetric(
                key="pipeline_runs",
                label="Pipeline runs",
                value=len(pipeline_runs),
                trend="stable",
            ),
            DashboardMetric(
                key="github_runs",
                label="GitHub Actions runs",
                value=len(github_runs),
                trend="up",
            ),
            DashboardMetric(
                key="services_monitored",
                label="Services monitored",
                value=len(services),
                trend="stable",
            ),
            DashboardMetric(
                key="entities_total",
                label="Business entities",
                value=entities_summary["summary"]["total_entities"],
                trend=(
                    "up" if entities_summary["summary"]["total_entities"] else "stable"
                ),
            ),
            DashboardMetric(
                key="llm_messages",
                label="LLM messages",
                value=llm_summary["summary"]["total_messages"],
                trend="up" if llm_summary["summary"]["total_messages"] else "stable",
            ),
            DashboardMetric(
                key="mcp_tools",
                label="MCP tools observed",
                value=mcp_summary["summary"]["tool_count"],
                trend="stable",
            ),
        ]

        return DashboardOverview(
            generated_at=datetime.utcnow(),
            status="ok",
            metrics=metrics,
            services=services,
            recent_pipeline_runs=[run.model_dump() for run in pipeline_runs[:5]],
            recent_github_runs=github_runs[:5],
        )

    def get_entities_detail(self) -> dict[str, Any]:
        fallback_entities = self._fallback_entities_detail()

        def _query(db: Session) -> dict[str, Any]:
            entities = (
                db.execute(
                    select(BusinessEntity)
                    .options(
                        selectinload(BusinessEntity.organization),
                        selectinload(BusinessEntity.organizational_unit),
                        selectinload(BusinessEntity.location),
                        selectinload(BusinessEntity.outgoing_relationships),
                        selectinload(BusinessEntity.incoming_relationships),
                    )
                    .order_by(
                        BusinessEntity.created_at.desc(), BusinessEntity.id.desc()
                    )
                )
                .scalars()
                .all()
            )
            relationships = db.execute(select(EntityRelationship)).scalars().all()
            organizations = db.execute(select(Organization)).scalars().all()
            units = db.execute(select(OrganizationalUnit)).scalars().all()
            locations = db.execute(select(Location)).scalars().all()
            frameworks = db.execute(select(Framework)).scalars().all()
            authorities = db.execute(select(Authority)).scalars().all()

            entities_by_type = Counter(entity.entity_type for entity in entities)
            relationship_by_type = Counter(
                rel.relationship_type for rel in relationships
            )

            items = []
            for entity in entities[:50]:
                items.append(
                    {
                        "id": entity.id,
                        "name": entity.name,
                        "entity_type": entity.entity_type,
                        "description": entity.description,
                        "is_active": entity.is_active,
                        "external_ref": entity.external_ref,
                        "organization": (
                            entity.organization.name if entity.organization else None
                        ),
                        "organizational_unit": (
                            entity.organizational_unit.name
                            if entity.organizational_unit
                            else None
                        ),
                        "location": entity.location.name if entity.location else None,
                        "attributes": entity.attributes or {},
                        "metadata": entity.metadata_json or {},
                        "relationship_counts": {
                            "outgoing": len(entity.outgoing_relationships),
                            "incoming": len(entity.incoming_relationships),
                        },
                        "created_at": self._serialize_datetime(entity.created_at),
                        "updated_at": self._serialize_datetime(entity.updated_at),
                    }
                )

            relationship_items = []
            for rel in relationships[:100]:
                relationship_items.append(
                    {
                        "id": rel.id,
                        "source_entity_id": rel.source_entity_id,
                        "target_entity_id": rel.target_entity_id,
                        "relationship_type": rel.relationship_type,
                        "direction": rel.direction,
                        "description": rel.description,
                        "metadata": rel.metadata_json or {},
                        "created_at": self._serialize_datetime(rel.created_at),
                    }
                )

            return {
                "generated_at": self._serialize_datetime(datetime.utcnow()),
                "summary": {
                    "total_entities": len(entities),
                    "total_relationships": len(relationships),
                    "entity_types": dict(sorted(entities_by_type.items())),
                    "relationship_types": dict(sorted(relationship_by_type.items())),
                    "organizations": len(organizations),
                    "organizational_units": len(units),
                    "locations": len(locations),
                    "frameworks": len(frameworks),
                    "authorities": len(authorities),
                },
                "items": items,
                "relationships": relationship_items,
                "catalog": {
                    "organizations": [
                        self._serialize_named_record(item)
                        for item in organizations[:50]
                    ],
                    "organizational_units": [
                        self._serialize_named_record(item) for item in units[:50]
                    ],
                    "locations": [
                        self._serialize_named_record(item) for item in locations[:50]
                    ],
                    "frameworks": [
                        self._serialize_named_record(item) for item in frameworks[:50]
                    ],
                    "authorities": [
                        self._serialize_named_record(item) for item in authorities[:50]
                    ],
                },
                "fallback": False,
            }

        return self._run_db_query(_query, fallback_entities)

    def get_llm_history_summary(self) -> dict[str, Any]:
        fallback_history = self._fallback_llm_history_summary()

        def _query(db: Session) -> dict[str, Any]:
            sessions = (
                db.execute(
                    select(ChatSession)
                    .options(
                        selectinload(ChatSession.llm_model),
                        selectinload(ChatSession.messages),
                    )
                    .order_by(ChatSession.created_at.desc(), ChatSession.id.desc())
                )
                .scalars()
                .all()
            )
            messages = (
                db.execute(
                    select(ChatMessage)
                    .options(
                        selectinload(ChatMessage.chat_session),
                    )
                    .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
                )
                .scalars()
                .all()
            )
            models = (
                db.execute(
                    select(LLMModel)
                    .options(selectinload(LLMModel.provider))
                    .order_by(LLMModel.name.asc())
                )
                .scalars()
                .all()
            )
            secrets = (
                db.execute(
                    select(Secret).order_by(Secret.created_at.desc(), Secret.id.desc())
                )
                .scalars()
                .all()
            )

            role_counts = Counter(message.role for message in messages)
            finish_reason_counts = Counter(
                message.finish_reason or "unknown" for message in messages
            )
            model_counts = Counter()
            token_totals = {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            }

            message_items = []
            for message in messages[:100]:
                token_usage = message.token_usage or {}
                token_totals["prompt_tokens"] += int(
                    token_usage.get("prompt_tokens", 0) or 0
                )
                token_totals["completion_tokens"] += int(
                    token_usage.get("completion_tokens", 0) or 0
                )
                token_totals["total_tokens"] += int(
                    token_usage.get("total_tokens", 0) or 0
                )

                session = message.chat_session
                model = session.llm_model if session else None
                model_key = model.name if model else "unknown"
                model_counts[model_key] += 1

                message_items.append(
                    {
                        "id": message.id,
                        "chat_session_id": message.chat_session_id,
                        "session_title": session.title if session else None,
                        "session_type": session.session_type if session else None,
                        "session_status": session.status if session else None,
                        "model_name": model.name if model else None,
                        "provider_name": (
                            model.provider.name if model and model.provider else None
                        ),
                        "role": message.role,
                        "content_preview": self._preview_text(message.content),
                        "finish_reason": message.finish_reason,
                        "token_usage": token_usage,
                        "metadata": message.metadata_json or {},
                        "created_at": self._serialize_datetime(message.created_at),
                    }
                )

            session_items = []
            for session in sessions[:50]:
                roles = Counter(message.role for message in session.messages)
                session_items.append(
                    {
                        "id": session.id,
                        "title": session.title,
                        "session_type": session.session_type,
                        "status": session.status,
                        "model_name": (
                            session.llm_model.name if session.llm_model else None
                        ),
                        "provider_name": (
                            session.llm_model.provider.name
                            if session.llm_model and session.llm_model.provider
                            else None
                        ),
                        "message_count": len(session.messages),
                        "roles": dict(sorted(roles.items())),
                        "metadata": session.metadata_json or {},
                        "created_at": self._serialize_datetime(session.created_at),
                        "updated_at": self._serialize_datetime(session.updated_at),
                    }
                )

            model_items = []
            for model in models[:50]:
                model_items.append(
                    {
                        "id": model.id,
                        "name": model.name,
                        "model_family": model.model_family,
                        "provider_name": (
                            model.provider.name if model.provider else None
                        ),
                        "context_window": model.context_window,
                        "supports_streaming": model.supports_streaming,
                        "is_default": model.is_default,
                        "metadata": model.metadata_json or {},
                        "created_at": self._serialize_datetime(model.created_at),
                        "updated_at": self._serialize_datetime(model.updated_at),
                    }
                )

            secret_items = []
            for secret in secrets[:50]:
                secret_items.append(
                    {
                        "id": secret.id,
                        "name": secret.name,
                        "secret_type": secret.secret_type,
                        "value_masked": secret.value_masked,
                        "storage_backend": secret.storage_backend,
                        "is_active": secret.is_active,
                        "description": secret.description,
                        "metadata": secret.metadata_json or {},
                        "created_at": self._serialize_datetime(secret.created_at),
                        "updated_at": self._serialize_datetime(secret.updated_at),
                    }
                )

            return {
                "generated_at": self._serialize_datetime(datetime.utcnow()),
                "summary": {
                    "total_sessions": len(sessions),
                    "total_messages": len(messages),
                    "total_models": len(models),
                    "total_secrets": len(secrets),
                    "messages_by_role": dict(sorted(role_counts.items())),
                    "messages_by_model": dict(sorted(model_counts.items())),
                    "finish_reasons": dict(sorted(finish_reason_counts.items())),
                    "token_usage": token_totals,
                },
                "sessions": session_items,
                "messages": message_items,
                "models": model_items,
                "secrets": secret_items,
                "fallback": False,
            }

        return self._run_db_query(_query, fallback_history)

    def get_mcp_status_detail(self) -> dict[str, Any]:
        pipeline_runs = pipeline_service.list_runs().runs
        services = get_provider_statuses()
        github_runs = list_github_action_runs()
        fallback_payload = self._fallback_mcp_status_detail(
            pipeline_runs, services, github_runs
        )

        def _query(db: Session) -> dict[str, Any]:
            run_rows = (
                db.execute(
                    select(PipelineRun)
                    .options(
                        selectinload(PipelineRun.service_runs),
                        selectinload(PipelineRun.events),
                    )
                    .order_by(PipelineRun.created_at.desc(), PipelineRun.id.desc())
                )
                .scalars()
                .all()
            )
            service_rows = (
                db.execute(
                    select(ServiceRun).order_by(
                        ServiceRun.created_at.desc(), ServiceRun.id.desc()
                    )
                )
                .scalars()
                .all()
            )
            event_rows = (
                db.execute(
                    select(RunEvent).order_by(
                        RunEvent.created_at.desc(), RunEvent.id.desc()
                    )
                )
                .scalars()
                .all()
            )
            provider_rows = (
                db.execute(select(Provider).order_by(Provider.name.asc()))
                .scalars()
                .all()
            )
            gh_run_rows = (
                db.execute(
                    select(GitHubWorkflowRun)
                    .options(selectinload(GitHubWorkflowRun.jobs))
                    .order_by(
                        GitHubWorkflowRun.created_at.desc(), GitHubWorkflowRun.id.desc()
                    )
                )
                .scalars()
                .all()
            )
            gh_job_rows = (
                db.execute(
                    select(GitHubWorkflowJob).order_by(
                        GitHubWorkflowJob.created_at.desc(), GitHubWorkflowJob.id.desc()
                    )
                )
                .scalars()
                .all()
            )

            tool_counter = Counter()
            status_counter = Counter(run.status for run in run_rows)
            event_counter = Counter(event.event_type for event in event_rows)

            run_items = []
            tool_items = []
            seen_tool_names = set()

            for run in run_rows[:50]:
                run_tools = self._extract_mcp_tools(run)
                for tool_name in run_tools:
                    tool_counter[tool_name] += 1
                    if tool_name not in seen_tool_names:
                        seen_tool_names.add(tool_name)
                        tool_items.append(
                            {
                                "tool_name": tool_name,
                                "source": "pipeline_run",
                            }
                        )

                run_items.append(
                    {
                        "id": run.id,
                        "run_type": run.run_type,
                        "status": run.status,
                        "trigger_source": run.trigger_source,
                        "job_url": run.job_url,
                        "started_at": self._serialize_datetime(run.started_at),
                        "finished_at": self._serialize_datetime(run.finished_at),
                        "error_message": run.error_message,
                        "service_run_count": len(run.service_runs),
                        "event_count": len(run.events),
                        "metadata": run.metadata_json or {},
                        "input_payload": run.input_payload or {},
                        "output_payload": run.output_payload or {},
                    }
                )

            for service_run in service_rows[:100]:
                for payload in [
                    service_run.input_payload or {},
                    service_run.output_payload or {},
                    service_run.metadata_json or {},
                ]:
                    tool_name = payload.get("tool")
                    if tool_name:
                        tool_counter[tool_name] += 1
                        if tool_name not in seen_tool_names:
                            seen_tool_names.add(tool_name)
                            tool_items.append(
                                {
                                    "tool_name": tool_name,
                                    "source": "service_run",
                                }
                            )

            provider_items = [
                {
                    "id": provider.id,
                    "name": provider.name,
                    "provider_type": provider.provider_type,
                    "status": provider.status,
                    "is_enabled": provider.is_enabled,
                    "base_url": provider.base_url,
                    "metadata": provider.metadata_json or {},
                    "created_at": self._serialize_datetime(provider.created_at),
                    "updated_at": self._serialize_datetime(provider.updated_at),
                }
                for provider in provider_rows[:50]
            ]

            event_items = [
                {
                    "id": event.id,
                    "pipeline_run_id": event.pipeline_run_id,
                    "service_run_id": event.service_run_id,
                    "level": event.level,
                    "event_type": event.event_type,
                    "message": event.message,
                    "payload": event.payload or {},
                    "metadata": event.metadata_json or {},
                    "created_at": self._serialize_datetime(event.created_at),
                }
                for event in event_rows[:100]
            ]

            github_items = []
            for run in gh_run_rows[:30]:
                github_items.append(
                    {
                        "id": run.id,
                        "workflow_id": run.workflow_id,
                        "run_number": run.run_number,
                        "name": run.name,
                        "status": run.status,
                        "conclusion": run.conclusion,
                        "branch": run.branch,
                        "html_url": run.html_url,
                        "started_at": self._serialize_datetime(run.started_at),
                        "finished_at": self._serialize_datetime(run.finished_at),
                        "job_count": len(run.jobs),
                        "metadata": run.metadata_json or {},
                    }
                )

            github_job_items = [
                {
                    "id": job.id,
                    "workflow_run_id": job.workflow_run_id,
                    "github_job_id": job.github_job_id,
                    "name": job.name,
                    "status": job.status,
                    "conclusion": job.conclusion,
                    "runner_name": job.runner_name,
                    "started_at": self._serialize_datetime(job.started_at),
                    "finished_at": self._serialize_datetime(job.finished_at),
                    "log_url": job.log_url,
                    "is_critical": job.is_critical,
                    "details": job.details,
                    "metadata": job.metadata_json or {},
                }
                for job in gh_job_rows[:100]
            ]

            return {
                "generated_at": self._serialize_datetime(datetime.utcnow()),
                "summary": {
                    "pipeline_runs": len(run_rows),
                    "service_runs": len(service_rows),
                    "run_events": len(event_rows),
                    "providers": len(provider_rows),
                    "github_workflow_runs": len(gh_run_rows),
                    "github_jobs": len(gh_job_rows),
                    "tool_count": len(tool_counter),
                    "run_statuses": dict(sorted(status_counter.items())),
                    "event_types": dict(sorted(event_counter.items())),
                },
                "tools": [
                    {
                        "tool_name": tool_name,
                        "observed_count": count,
                    }
                    for tool_name, count in sorted(tool_counter.items())
                ],
                "pipeline_runs": run_items,
                "providers": provider_items,
                "events": event_items,
                "github_runs": github_items,
                "github_jobs": github_job_items,
                "fallback": False,
            }

        return self._run_db_query(_query, fallback_payload)

    def get_db_schema_graph(self) -> dict[str, Any]:
        fallback_graph = self._fallback_db_schema_graph()

        def _query(db: Session) -> dict[str, Any]:
            bind = db.get_bind()
            if bind is None:
                raise RuntimeError("No database bind available for schema inspection")
            inspector = inspect(bind)
            table_names = sorted(inspector.get_table_names())
            nodes = []
            edges = []

            for table_name in table_names:
                columns = inspector.get_columns(table_name)
                foreign_keys = inspector.get_foreign_keys(table_name)
                column_items = []
                for column in columns:
                    column_items.append(
                        {
                            "name": column["name"],
                            "type": str(column["type"]),
                            "nullable": bool(column.get("nullable", True)),
                            "default": (
                                str(column.get("default"))
                                if column.get("default") is not None
                                else None
                            ),
                            "primary_key": bool(column.get("primary_key", False)),
                        }
                    )

                row_count = None
                try:
                    row_count = db.execute(
                        select(func.count()).select_from(
                            self._table_from_name(table_name)
                        )
                    ).scalar_one()
                except SQLAlchemyError:
                    row_count = None

                nodes.append(
                    {
                        "id": table_name,
                        "label": table_name,
                        "column_count": len(column_items),
                        "row_count": row_count,
                        "columns": column_items,
                    }
                )

                for foreign_key in foreign_keys:
                    constrained_columns = foreign_key.get("constrained_columns") or []
                    referred_columns = foreign_key.get("referred_columns") or []
                    edges.append(
                        {
                            "source": table_name,
                            "target": foreign_key.get("referred_table"),
                            "label": (
                                ",".join(constrained_columns)
                                if constrained_columns
                                else "fk"
                            ),
                            "source_columns": constrained_columns,
                            "target_columns": referred_columns,
                        }
                    )

            diagram_lines = ["Database schema graph:"]
            for node in nodes:
                diagram_lines.append(
                    f"- {node['label']} ({node['column_count']} cols, rows={node['row_count']})"
                )
            for edge in edges:
                diagram_lines.append(
                    f"  {edge['source']} -> {edge['target']} [{edge['label']}]"
                )

            return {
                "generated_at": self._serialize_datetime(datetime.utcnow()),
                "summary": {
                    "table_count": len(nodes),
                    "edge_count": len(edges),
                },
                "nodes": nodes,
                "edges": edges,
                "diagram_text": "\n".join(diagram_lines),
                "fallback": False,
            }

        return self._run_db_query(_query, fallback_graph)

    def _run_db_query(self, callback: Any, fallback: dict[str, Any]) -> dict[str, Any]:
        db = SessionLocal()
        try:
            return callback(db)
        except Exception as exc:
            payload = dict(fallback)
            payload["fallback"] = True
            payload["fallback_reason"] = str(exc)
            return payload
        finally:
            db.close()

    def _extract_mcp_tools(self, run: PipelineRun) -> list[str]:
        tool_names = []
        payloads = [
            run.input_payload or {},
            run.output_payload or {},
            run.metadata_json or {},
        ]
        for payload in payloads:
            tool_name = payload.get("tool")
            if tool_name:
                tool_names.append(tool_name)
            steps = payload.get("steps") if isinstance(payload, dict) else None
            if isinstance(steps, list):
                for step in steps:
                    if isinstance(step, dict) and step.get("tool"):
                        tool_names.append(step["tool"])
        return tool_names

    def _table_from_name(self, table_name: str) -> Any:
        return PipelineRun.metadata.tables[table_name]

    def _serialize_named_record(self, item: Any) -> dict[str, Any]:
        return {
            "id": getattr(item, "id", None),
            "name": getattr(item, "name", None),
            "type": item.__class__.__name__,
            "created_at": self._serialize_datetime(getattr(item, "created_at", None)),
            "updated_at": self._serialize_datetime(getattr(item, "updated_at", None)),
        }

    def _serialize_datetime(self, value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.isoformat()
        return str(value)

    def _preview_text(self, value: str | None, limit: int = 180) -> str | None:
        if not value:
            return value
        text = value.strip()
        if len(text) <= limit:
            return text
        return f"{text[:limit - 3]}..."

    def _fallback_entities_detail(self) -> dict[str, Any]:
        seeded_entities = [
            {
                "id": "seed-1",
                "name": "Police Grand-Ducale",
                "entity_type": "organization",
                "description": "Institution luxembourgeoise de sécurité publique",
                "is_active": True,
                "external_ref": "police-grand-ducale",
                "organization": "Police Grand-Ducale",
                "organizational_unit": "Direction centrale stratégie et performance",
                "location": "Luxembourg",
                "attributes": {"domain": "public_service", "country_code": "LU"},
                "metadata": {"source": "dashboard_fallback_seed"},
                "relationship_counts": {"outgoing": 2, "incoming": 1},
                "created_at": self._serialize_datetime(datetime.utcnow()),
                "updated_at": self._serialize_datetime(datetime.utcnow()),
            },
            {
                "id": "seed-2",
                "name": "ISO/IEC 27001",
                "entity_type": "framework",
                "description": "Cadre de management de la sécurité de l'information",
                "is_active": True,
                "external_ref": "iso-27001",
                "organization": None,
                "organizational_unit": None,
                "location": None,
                "attributes": {"category": "security_framework"},
                "metadata": {"source": "dashboard_fallback_seed"},
                "relationship_counts": {"outgoing": 1, "incoming": 1},
                "created_at": self._serialize_datetime(datetime.utcnow()),
                "updated_at": self._serialize_datetime(datetime.utcnow()),
            },
            {
                "id": "seed-3",
                "name": "RGPD / GDPR",
                "entity_type": "regulation",
                "description": "Réglementation de protection des données",
                "is_active": True,
                "external_ref": "gdpr",
                "organization": None,
                "organizational_unit": None,
                "location": "European Union",
                "attributes": {"jurisdiction": "EU"},
                "metadata": {"source": "dashboard_fallback_seed"},
                "relationship_counts": {"outgoing": 1, "incoming": 2},
                "created_at": self._serialize_datetime(datetime.utcnow()),
                "updated_at": self._serialize_datetime(datetime.utcnow()),
            },
        ]
        seeded_relationships = [
            {
                "id": "rel-1",
                "source_entity_id": "seed-1",
                "target_entity_id": "seed-2",
                "relationship_type": "governed_by",
                "direction": "outgoing",
                "description": "Les activités cybersécurité se réfèrent au framework ISO/IEC 27001",
                "metadata": {"source": "dashboard_fallback_seed"},
                "created_at": self._serialize_datetime(datetime.utcnow()),
            },
            {
                "id": "rel-2",
                "source_entity_id": "seed-1",
                "target_entity_id": "seed-3",
                "relationship_type": "complies_with",
                "direction": "outgoing",
                "description": "Traitement de données sous contrainte RGPD",
                "metadata": {"source": "dashboard_fallback_seed"},
                "created_at": self._serialize_datetime(datetime.utcnow()),
            },
        ]
        return {
            "generated_at": self._serialize_datetime(datetime.utcnow()),
            "summary": {
                "total_entities": len(seeded_entities),
                "total_relationships": len(seeded_relationships),
                "entity_types": {"framework": 1, "organization": 1, "regulation": 1},
                "relationship_types": {"complies_with": 1, "governed_by": 1},
                "organizations": 1,
                "organizational_units": 1,
                "locations": 2,
                "frameworks": 1,
                "authorities": 0,
            },
            "items": seeded_entities,
            "relationships": seeded_relationships,
            "catalog": {
                "organizations": [
                    {
                        "id": "org-1",
                        "name": "Police Grand-Ducale",
                        "type": "Organization",
                        "created_at": None,
                        "updated_at": None,
                    }
                ],
                "organizational_units": [
                    {
                        "id": "unit-1",
                        "name": "Direction centrale stratégie et performance",
                        "type": "OrganizationalUnit",
                        "created_at": None,
                        "updated_at": None,
                    }
                ],
                "locations": [
                    {
                        "id": "loc-1",
                        "name": "Luxembourg",
                        "type": "Location",
                        "created_at": None,
                        "updated_at": None,
                    }
                ],
                "frameworks": [
                    {
                        "id": "fw-1",
                        "name": "ISO/IEC 27001",
                        "type": "Framework",
                        "created_at": None,
                        "updated_at": None,
                    }
                ],
                "authorities": [],
            },
            "fallback": True,
        }

    def _fallback_llm_history_summary(self) -> dict[str, Any]:
        now = self._serialize_datetime(datetime.utcnow())
        return {
            "generated_at": now,
            "summary": {
                "total_sessions": 2,
                "total_messages": 5,
                "total_models": 2,
                "total_secrets": 2,
                "messages_by_role": {"assistant": 2, "system": 1, "user": 2},
                "messages_by_model": {"claude-3-5-sonnet": 2, "gpt-4o": 3},
                "finish_reasons": {"stop": 4, "tool_calls": 1},
                "token_usage": {
                    "prompt_tokens": 2200,
                    "completion_tokens": 960,
                    "total_tokens": 3160,
                },
            },
            "sessions": [
                {
                    "id": "session-1",
                    "title": "Analyse adéquation poste cybersécurité",
                    "session_type": "job_fit_analysis",
                    "status": "open",
                    "model_name": "gpt-4o",
                    "provider_name": "OpenAI",
                    "message_count": 3,
                    "roles": {"assistant": 1, "system": 1, "user": 1},
                    "metadata": {"source": "dashboard_fallback_seed"},
                    "created_at": now,
                    "updated_at": now,
                },
                {
                    "id": "session-2",
                    "title": "Rédaction lettre de motivation",
                    "session_type": "cover_letter_generation",
                    "status": "closed",
                    "model_name": "gpt-4o-mini",
                    "provider_name": "OpenAI",
                    "message_count": 2,
                    "roles": {"assistant": 1, "user": 1},
                    "metadata": {"source": "dashboard_fallback_seed"},
                    "created_at": now,
                    "updated_at": now,
                },
            ],
            "messages": [
                {
                    "id": "msg-1",
                    "chat_session_id": "session-1",
                    "session_title": "Analyse adéquation poste cybersécurité",
                    "session_type": "job_fit_analysis",
                    "session_status": "open",
                    "model_name": "gpt-4o",
                    "provider_name": "OpenAI",
                    "role": "system",
                    "content_preview": "Tu es un assistant RH et cybersécurité chargé d'analyser l'adéquation du candidat.",
                    "finish_reason": "stop",
                    "token_usage": {
                        "prompt_tokens": 500,
                        "completion_tokens": 0,
                        "total_tokens": 500,
                    },
                    "metadata": {"source": "dashboard_fallback_seed"},
                    "created_at": now,
                },
                {
                    "id": "msg-2",
                    "chat_session_id": "session-1",
                    "session_title": "Analyse adéquation poste cybersécurité",
                    "session_type": "job_fit_analysis",
                    "session_status": "open",
                    "model_name": "gpt-4o",
                    "provider_name": "OpenAI",
                    "role": "user",
                    "content_preview": "Compare mon CV avec l'offre Police Grand-Ducale et identifie les écarts clés.",
                    "finish_reason": "tool_calls",
                    "token_usage": {
                        "prompt_tokens": 900,
                        "completion_tokens": 0,
                        "total_tokens": 900,
                    },
                    "metadata": {"source": "dashboard_fallback_seed"},
                    "created_at": now,
                },
            ],
            "models": [
                {
                    "id": "model-1",
                    "name": "gpt-4o",
                    "model_family": "gpt-4",
                    "provider_name": "OpenAI",
                    "context_window": 128000,
                    "supports_streaming": True,
                    "is_default": True,
                    "metadata": {"source": "dashboard_fallback_seed"},
                    "created_at": now,
                    "updated_at": now,
                },
                {
                    "id": "model-2",
                    "name": "gpt-4o-mini",
                    "model_family": "gpt-4o",
                    "provider_name": "OpenAI",
                    "context_window": 128000,
                    "supports_streaming": True,
                    "is_default": False,
                    "metadata": {"source": "dashboard_fallback_seed"},
                    "created_at": now,
                    "updated_at": now,
                },
            ],
            "secrets": [
                {
                    "id": "secret-1",
                    "name": "OPENAI_API_KEY",
                    "secret_type": "api_key",
                    "value_masked": "sk-****1234",
                    "storage_backend": "env",
                    "is_active": True,
                    "description": "Clé OpenAI masquée",
                    "metadata": {"source": "dashboard_fallback_seed"},
                    "created_at": now,
                    "updated_at": now,
                },
                {
                    "id": "secret-2",
                    "name": "OPENAI_API_KEY",
                    "secret_type": "api_key",
                    "value_masked": "sk-ant-****5678",
                    "storage_backend": "env",
                    "is_active": True,
                    "description": "Clé OpenAI masquée",
                    "metadata": {"source": "dashboard_fallback_seed"},
                    "created_at": now,
                    "updated_at": now,
                },
            ],
            "fallback": True,
        }

    def _fallback_mcp_status_detail(
        self,
        pipeline_runs: list[Any],
        services: list[Any],
        github_runs: list[dict[str, Any]],
    ) -> dict[str, Any]:
        run_items = [
            {
                "id": run.run_id,
                "run_type": run.pipeline_type,
                "status": run.status,
                "trigger_source": getattr(run, "source", None),
                "job_url": None,
                "started_at": self._serialize_datetime(run.created_at),
                "finished_at": self._serialize_datetime(run.updated_at),
                "error_message": None,
                "service_run_count": 0,
                "event_count": 0,
                "metadata": {},
                "input_payload": {},
                "output_payload": {},
            }
            for run in pipeline_runs[:20]
        ]
        provider_items = [
            {
                "id": service.name,
                "name": service.name,
                "provider_type": "service",
                "status": service.status,
                "is_enabled": True,
                "base_url": None,
                "metadata": service.metadata,
                "created_at": None,
                "updated_at": None,
            }
            for service in services
        ]
        tool_list = [
            {"tool_name": "mcp.providers_connectivity", "observed_count": 1},
            {"tool_name": "mcp.europass_pdf_to_structured_json", "observed_count": 1},
            {"tool_name": "mcp.job_url_to_html", "observed_count": 1},
            {"tool_name": "mcp.clean_html_content", "observed_count": 1},
            {"tool_name": "mcp.job_text_to_json", "observed_count": 1},
            {"tool_name": "mcp.extract_entities", "observed_count": 1},
            {"tool_name": "mcp.upsert_entities", "observed_count": 1},
            {"tool_name": "mcp.osint_entities", "observed_count": 1},
            {"tool_name": "mcp.generate_master_prompt", "observed_count": 1},
            {"tool_name": "mcp.career_strategy_openai", "observed_count": 1},
            {"tool_name": "mcp.career_strategy_openai_agents", "observed_count": 1},
            {"tool_name": "mcp.generate_final_report_pdf", "observed_count": 1},
        ]
        return {
            "generated_at": self._serialize_datetime(datetime.utcnow()),
            "summary": {
                "pipeline_runs": len(pipeline_runs),
                "service_runs": 0,
                "run_events": 0,
                "providers": len(provider_items),
                "github_workflow_runs": len(github_runs),
                "github_jobs": 0,
                "tool_count": len(tool_list),
                "run_statuses": dict(
                    sorted(Counter(run.status for run in pipeline_runs).items())
                ),
                "event_types": {},
            },
            "tools": tool_list,
            "pipeline_runs": run_items,
            "providers": provider_items,
            "events": [],
            "github_runs": github_runs[:20],
            "github_jobs": [],
            "fallback": True,
        }

    def _fallback_db_schema_graph(self) -> dict[str, Any]:
        nodes = [
            {
                "id": "providers",
                "label": "providers",
                "column_count": 7,
                "row_count": None,
                "columns": [
                    {
                        "name": "id",
                        "type": "INTEGER",
                        "nullable": False,
                        "default": None,
                        "primary_key": True,
                    },
                    {
                        "name": "name",
                        "type": "VARCHAR(100)",
                        "nullable": False,
                        "default": None,
                        "primary_key": False,
                    },
                    {
                        "name": "provider_type",
                        "type": "VARCHAR(100)",
                        "nullable": False,
                        "default": None,
                        "primary_key": False,
                    },
                ],
            },
            {
                "id": "llm_models",
                "label": "llm_models",
                "column_count": 8,
                "row_count": None,
                "columns": [
                    {
                        "name": "id",
                        "type": "INTEGER",
                        "nullable": False,
                        "default": None,
                        "primary_key": True,
                    },
                    {
                        "name": "provider_id",
                        "type": "INTEGER",
                        "nullable": True,
                        "default": None,
                        "primary_key": False,
                    },
                    {
                        "name": "name",
                        "type": "VARCHAR(150)",
                        "nullable": False,
                        "default": None,
                        "primary_key": False,
                    },
                ],
            },
            {
                "id": "chat_sessions",
                "label": "chat_sessions",
                "column_count": 7,
                "row_count": None,
                "columns": [
                    {
                        "name": "id",
                        "type": "INTEGER",
                        "nullable": False,
                        "default": None,
                        "primary_key": True,
                    },
                    {
                        "name": "llm_model_id",
                        "type": "INTEGER",
                        "nullable": True,
                        "default": None,
                        "primary_key": False,
                    },
                    {
                        "name": "title",
                        "type": "VARCHAR(255)",
                        "nullable": True,
                        "default": None,
                        "primary_key": False,
                    },
                ],
            },
            {
                "id": "chat_messages",
                "label": "chat_messages",
                "column_count": 8,
                "row_count": None,
                "columns": [
                    {
                        "name": "id",
                        "type": "INTEGER",
                        "nullable": False,
                        "default": None,
                        "primary_key": True,
                    },
                    {
                        "name": "chat_session_id",
                        "type": "INTEGER",
                        "nullable": False,
                        "default": None,
                        "primary_key": False,
                    },
                    {
                        "name": "role",
                        "type": "VARCHAR(50)",
                        "nullable": False,
                        "default": None,
                        "primary_key": False,
                    },
                ],
            },
            {
                "id": "business_entities",
                "label": "business_entities",
                "column_count": 11,
                "row_count": None,
                "columns": [
                    {
                        "name": "id",
                        "type": "INTEGER",
                        "nullable": False,
                        "default": None,
                        "primary_key": True,
                    },
                    {
                        "name": "organization_id",
                        "type": "INTEGER",
                        "nullable": True,
                        "default": None,
                        "primary_key": False,
                    },
                    {
                        "name": "entity_type",
                        "type": "VARCHAR(100)",
                        "nullable": False,
                        "default": None,
                        "primary_key": False,
                    },
                ],
            },
            {
                "id": "entity_relationships",
                "label": "entity_relationships",
                "column_count": 7,
                "row_count": None,
                "columns": [
                    {
                        "name": "id",
                        "type": "INTEGER",
                        "nullable": False,
                        "default": None,
                        "primary_key": True,
                    },
                    {
                        "name": "source_entity_id",
                        "type": "INTEGER",
                        "nullable": False,
                        "default": None,
                        "primary_key": False,
                    },
                    {
                        "name": "target_entity_id",
                        "type": "INTEGER",
                        "nullable": False,
                        "default": None,
                        "primary_key": False,
                    },
                ],
            },
            {
                "id": "pipeline_runs",
                "label": "pipeline_runs",
                "column_count": 10,
                "row_count": None,
                "columns": [
                    {
                        "name": "id",
                        "type": "INTEGER",
                        "nullable": False,
                        "default": None,
                        "primary_key": True,
                    },
                    {
                        "name": "run_type",
                        "type": "VARCHAR(50)",
                        "nullable": False,
                        "default": None,
                        "primary_key": False,
                    },
                    {
                        "name": "status",
                        "type": "VARCHAR(50)",
                        "nullable": False,
                        "default": None,
                        "primary_key": False,
                    },
                ],
            },
            {
                "id": "service_runs",
                "label": "service_runs",
                "column_count": 10,
                "row_count": None,
                "columns": [
                    {
                        "name": "id",
                        "type": "INTEGER",
                        "nullable": False,
                        "default": None,
                        "primary_key": True,
                    },
                    {
                        "name": "pipeline_run_id",
                        "type": "INTEGER",
                        "nullable": False,
                        "default": None,
                        "primary_key": False,
                    },
                    {
                        "name": "service_name",
                        "type": "VARCHAR(100)",
                        "nullable": False,
                        "default": None,
                        "primary_key": False,
                    },
                ],
            },
        ]
        edges = [
            {
                "source": "llm_models",
                "target": "providers",
                "label": "provider_id",
                "source_columns": ["provider_id"],
                "target_columns": ["id"],
            },
            {
                "source": "chat_sessions",
                "target": "llm_models",
                "label": "llm_model_id",
                "source_columns": ["llm_model_id"],
                "target_columns": ["id"],
            },
            {
                "source": "chat_messages",
                "target": "chat_sessions",
                "label": "chat_session_id",
                "source_columns": ["chat_session_id"],
                "target_columns": ["id"],
            },
            {
                "source": "business_entities",
                "target": "organizations",
                "label": "organization_id",
                "source_columns": ["organization_id"],
                "target_columns": ["id"],
            },
            {
                "source": "entity_relationships",
                "target": "business_entities",
                "label": "source_entity_id",
                "source_columns": ["source_entity_id"],
                "target_columns": ["id"],
            },
            {
                "source": "entity_relationships",
                "target": "business_entities",
                "label": "target_entity_id",
                "source_columns": ["target_entity_id"],
                "target_columns": ["id"],
            },
            {
                "source": "service_runs",
                "target": "pipeline_runs",
                "label": "pipeline_run_id",
                "source_columns": ["pipeline_run_id"],
                "target_columns": ["id"],
            },
        ]
        diagram_text = "\n".join(
            [
                "Database schema graph:",
                "- providers",
                "- llm_models",
                "- chat_sessions",
                "- chat_messages",
                "- business_entities",
                "- entity_relationships",
                "- pipeline_runs",
                "- service_runs",
                "  llm_models -> providers [provider_id]",
                "  chat_sessions -> llm_models [llm_model_id]",
                "  chat_messages -> chat_sessions [chat_session_id]",
                "  business_entities -> organizations [organization_id]",
                "  entity_relationships -> business_entities [source_entity_id]",
                "  entity_relationships -> business_entities [target_entity_id]",
                "  service_runs -> pipeline_runs [pipeline_run_id]",
            ]
        )
        return {
            "generated_at": self._serialize_datetime(datetime.utcnow()),
            "summary": {
                "table_count": len(nodes),
                "edge_count": len(edges),
            },
            "nodes": nodes,
            "edges": edges,
            "diagram_text": diagram_text,
            "fallback": True,
        }


dashboard_service = DashboardService()
