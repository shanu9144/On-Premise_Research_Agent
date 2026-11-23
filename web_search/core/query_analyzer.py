import re

from ..models import QueryAnalysis

URL_PATTERN = re.compile(r"https?://[^\s<>]+")
CRAWL_WORDS = re.compile(r"\b(crawl|entire (?:site|website)|whole (?:site|website))\b")
SEMANTIC_WORDS = re.compile(r"\b(research|papers?|studies|academic|scholarships?|documentation|technical)\b")
TIME_WORDS = re.compile(r"\b(latest|current|today|recent|now|available|open|deadline|202[6-9])\b")
EXPLANATION = re.compile(r"^(explain|what is|what are|how does)\b")


def analyze_query(query, options):
    """Rule-based intent detection; explicit options always override it."""
    normalized = " ".join(query.split())
    if not normalized or len(normalized) > 1500:
        raise ValueError("Query must contain 1 to 1500 characters")
    lowered = normalized.lower()
    match = URL_PATTERN.search(normalized)
    url = options.url or (match.group(0).rstrip(".,)") if match else None)
    operation = options.operation or ("crawl" if url and CRAWL_WORDS.search(lowered) else "scrape" if url else "search")
    if operation in {"scrape", "crawl"} and not url:
        raise ValueError(f"{operation} requires a URL")
    semantic = bool(SEMANTIC_WORDS.search(lowered))
    time_sensitive = bool(TIME_WORDS.search(lowered))
    freshness = options.freshness if options.freshness != "normal" else ("recent" if time_sensitive else "normal")
    local_only = (EXPLANATION.match(lowered) and not time_sensitive and not url
                  and not options.force_search and options.operation is None)
    return QueryAnalysis(
        original_query=query, normalized_query=normalized,
        intent="local_explanation" if local_only else operation,
        topic="research" if semantic else "general", freshness=freshness,
        complexity="complex" if len(normalized.split()) > 15 or options.search_depth == "advanced" else "simple",
        search_depth=options.search_depth, semantic=semantic,
        needs_extraction=options.require_full_content or operation in {"scrape", "crawl"},
        expected_results=options.max_results, confidence=0.65,
        operation="none" if local_only else operation, url=url,
    )
