"""Provider-independent, budget-aware web search for agents."""

from .core.orchestrator import create_default_service, intelligent_web_search
from .models import SearchOptions

__all__ = ["SearchOptions", "create_default_service", "intelligent_web_search"]