import math
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class SearchOptions:
    max_results: int = 5
    freshness: str = "normal"
    search_depth: str = "basic"
    max_cost: Optional[float] = None
    require_full_content: bool = False
    preferred_provider: Optional[str] = None
    exclude_providers: tuple = ()
    force_search: bool = False
    important: bool = False
    operation: Optional[str] = None
    url: Optional[str] = None
    crawl_limit: int = 5
    objective: Optional[str] = None

    def __post_init__(self):
        object.__setattr__(self, "exclude_providers", tuple(self.exclude_providers))
        if not 1 <= self.max_results <= 10:
            raise ValueError("max_results must be between 1 and 10")
        if self.freshness not in {"normal", "recent", "live"}:
            raise ValueError("freshness must be normal, recent, or live")
        if self.search_depth not in {"basic", "advanced"}:
            raise ValueError("search_depth must be basic or advanced")
        if self.max_cost is not None and not (math.isfinite(self.max_cost) and self.max_cost >= 0):
            raise ValueError("max_cost must be a finite non-negative number")
        if self.operation not in {None, "search", "scrape", "crawl"}:
            raise ValueError("operation must be search, scrape, or crawl")
        if not 1 <= self.crawl_limit <= 10:
            raise ValueError("crawl_limit must be between 1 and 10")
        if self.objective is not None and len(self.objective) > 4096:
            raise ValueError("objective must be at most 4096 characters")


@dataclass(frozen=True)
class QueryAnalysis:
    original_query: str
    normalized_query: str
    intent: str
    topic: str
    freshness: str
    complexity: str
    search_depth: str
    semantic: bool
    needs_extraction: bool
    expected_results: int
    confidence: float
    operation: str
    url: Optional[str] = None
