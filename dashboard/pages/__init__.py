from dashboard.pages.entities import render_page as render_entities_page
from dashboard.pages.github_actions import render_page as render_github_actions_page
from dashboard.pages.llm_history import render_page as render_llm_history_page
from dashboard.pages.overview import render_page as render_overview_page
from dashboard.pages.runs import render_page as render_runs_page

__all__ = [
    "render_entities_page",
    "render_github_actions_page",
    "render_llm_history_page",
    "render_overview_page",
    "render_runs_page",
]