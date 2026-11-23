from dataclasses import dataclass, field
from typing import Optional

from .search_request import QueryAnalysis


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    snippet: str = ""
    content: str = ""
    published_date: Optional[str] = None
    provider: str = ""
    score: Optional[float] = None


@dataclass(frozen=True)
class ProviderResponse:
    results: list
    actual_cost: Optional[float] = None
    request_id: Optional[str] = None


@dataclass
class SearchOutcome:
    summary: str
    analysis: QueryAnalysis
    selected_provider: Optional[str] = None
    strategy: str = ""
    results: list = field(default_factory=list)
    estimated_costs: dict = field(default_factory=dict)
    actual_costs: dict = field(default_factory=dict)
    remaining_budgets: dict = field(default_factory=dict)
    fallback_used: bool = False
    metadata: dict = field(default_factory=dict)
