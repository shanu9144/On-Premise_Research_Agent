import threading
import time
from dataclasses import asdict, replace

from ..budget.cost_estimator import estimate, exceeds_query_cap
from ..budget.credit_manager import BudgetExceeded, CreditManager
from ..budget.usage_tracker import UsageTracker
from ..cache.cache_manager import TTL_SECONDS, CacheManager
from ..config.settings import DATABASE, number
from ..models import SearchOptions, SearchOutcome, SearchResult
from ..models.provider_usage import to_units
from ..processing.content_extractor import validate_public_url
from ..processing.deduplicator import deduplicate
from ..providers import ProviderError, build_registry
from .decision_engine import rank_providers
from .fallback_manager import FallbackManager
from .quality_evaluator import has_required_content, is_sufficient, quality
from .query_analyzer import analyze_query


def budget_key(provider):
    return f"{provider.name}:{provider.unit}"


class SearchOrchestrator:
    def __init__(self, registry, database, max_retries=1):
        self.registry = registry
        self.credits = CreditManager(database)
        self.cache = CacheManager(database)
        self.usage = UsageTracker(database)
        self.fallback = FallbackManager(max_retries)
        self.lock = threading.Lock()

    def plan(self, query, options=None):
        """Estimate costs without calling any provider."""
        options = options if isinstance(options, SearchOptions) else SearchOptions(**(options or {}))
        analysis = analyze_query(query, options)

        def describe(target):
            if target.operation == "none":
                return []
            return [{"provider": provider.name, "estimated_cost": estimate(provider, target, options),
                     "unit": provider.unit,
                     "remaining": self.credits.remaining(budget_key(provider), self.registry.budgets[provider.name])}
                    for provider in rank_providers(self.registry, target, options, self.fallback)]

        extraction = replace(analysis, operation="scrape")
        return {"analysis": asdict(analysis), "candidates": describe(analysis),
                "conditional_extraction": describe(extraction) if analysis.operation == "search"
                and analysis.needs_extraction else []}

    def usage_summary(self):
        activity = self.usage.summary()
        return {name: {"activity": activity.get(name, {}), "spending": self.credits.spending(budget_key(provider)),
                       "remaining": self.credits.remaining(budget_key(provider), self.registry.budgets[name])}
                for name, provider in self.registry.providers.items()}

    def execute(self, provider, analysis, options, is_fallback, outcome):
        name, operation = provider.name, analysis.operation
        cost = estimate(provider, analysis, options)
        ttl = TTL_SECONDS[analysis.freshness]
        key = self.cache.key({"provider": name, "unit": provider.unit, "operation": operation,
                              "query": analysis.normalized_query.casefold(), "url": analysis.url,
                              "options": asdict(options), "freshness": analysis.freshness})
        cached = self.cache.get(key) if ttl else None
        if cached is not None:
            results = [SearchResult(**item) for item in cached]
            self.usage.record(name, operation, 0, True, True, is_fallback, len(results),
                              quality(results, options.max_results), "cache")
            outcome.metadata["cache_hit"] = True
            return results

        target_url = validate_public_url(analysis.url) if operation in {"scrape", "crawl"} else None
        limit = options.crawl_limit if operation == "crawl" else options.max_results
        attempt = 0
        while True:
            if exceeds_query_cap(outcome, self.registry, provider, cost, options.max_cost):
                raise BudgetExceeded(f"{name} per-query budget exhausted")
            reservation = self.credits.reserve(budget_key(provider), cost, self.registry.budgets[name],
                                               options.important)
            outcome.estimated_costs[name] = outcome.estimated_costs.get(name, 0) + cost
            start = time.monotonic()
            try:
                if operation == "search":
                    response = provider.search(analysis.normalized_query, replace(options, freshness=analysis.freshness))
                else:
                    response = getattr(provider, operation)(target_url, options)
                if response.actual_cost is not None:
                    try:
                        to_units(response.actual_cost)
                    except (TypeError, ValueError, OverflowError) as error:
                        raise ProviderError(f"{name} returned invalid usage") from error
                self.credits.settle(reservation, response.actual_cost)
            except ProviderError as error:
                self.credits.settle(reservation, definitely_unbilled=not error.uncertain_cost)
                outcome.actual_costs[name] = None
                self.fallback.record_failure(name)
                self.usage.record(name, operation, time.monotonic() - start, False, False, is_fallback, 0, 0,
                                  str(error))
                if not self.fallback.should_retry(error, attempt, operation):
                    raise
                self.fallback.backoff(attempt)
                attempt += 1
                continue
            previous = outcome.actual_costs.get(name, 0)
            outcome.actual_costs[name] = (previous + response.actual_cost
                                          if response.actual_cost is not None and previous is not None else None)
            results = deduplicate(response.results, limit)
            self.cache.put(key, [asdict(result) for result in results], ttl)
            self.fallback.record_success(name)
            self.usage.record(name, operation, time.monotonic() - start, True, False, is_fallback, len(results),
                              quality(results, options.max_results), "success")
            return results

    def search(self, query, options=None):
        options = options if isinstance(options, SearchOptions) else SearchOptions(**(options or {}))
        analysis = analyze_query(query, options)
        outcome = SearchOutcome("", analysis, strategy=analysis.operation, metadata={"cache_hit": False, "failures": []})
        if analysis.operation == "none":
            outcome.summary = "No external search required; answer using local knowledge."
            return outcome
        with self.lock:
            providers = rank_providers(self.registry, analysis, options, self.fallback)
            if not providers:
                outcome.summary = "No configured provider has the required capability and budget."
                return outcome
            first_unit = providers[0].unit
            limit = options.crawl_limit if analysis.operation == "crawl" else options.max_results
            collected = []
            for index, provider in enumerate(providers):
                if options.max_cost is not None and provider.unit != first_unit:
                    outcome.metadata["failures"].append("Fallback skipped: incompatible max_cost units")
                    continue
                outcome.fallback_used = outcome.fallback_used or index > 0
                try:
                    results = self.execute(provider, analysis, options, index > 0, outcome)
                except (ProviderError, BudgetExceeded) as error:
                    outcome.metadata["failures"].append(str(error))
                    continue
                if not outcome.selected_provider:
                    outcome.selected_provider = provider.name
                    outcome.metadata["selection_reason"] = (
                        "Preferred provider" if provider.name == options.preferred_provider
                        else "Capability, query intent, configured budget, and availability")
                collected = deduplicate(collected + results, limit)
                if is_sufficient(analysis, collected):
                    break
            if analysis.operation == "search" and collected and not has_required_content(analysis, collected):
                self.extract_first(collected, analysis, options, first_unit, outcome)
            score = quality(collected, options.max_results)
            outcome.results = collected
            outcome.metadata.update({
                "quality_score": score, "content_requirement_met": has_required_content(analysis, collected),
                "units": {name: provider.unit for name, provider in self.registry.providers.items()}})
            outcome.remaining_budgets = {
                name: self.credits.remaining(budget_key(self.registry.providers[name]), budget)
                for name, budget in self.registry.budgets.items()}
            outcome.summary = (f"Retrieved {len(collected)} sources; quality heuristic {score:.2f}." if collected
                               else "No usable results; check provider configuration, budgets, or failures.")
            return outcome

    def extract_first(self, collected, analysis, options, first_unit, outcome):
        """One budgeted extraction for the top result when snippets are not enough."""
        extraction = replace(analysis, operation="scrape", url=collected[0].url)
        for provider in rank_providers(self.registry, extraction, options, self.fallback):
            if options.max_cost is not None and provider.unit != first_unit:
                continue
            try:
                pages = self.execute(provider, extraction, options, True, outcome)
            except (ProviderError, BudgetExceeded, ValueError) as error:
                outcome.metadata["failures"].append(str(error))
                continue
            if pages and pages[0].content:
                collected[0] = replace(collected[0], content=pages[0].content)
                outcome.metadata["extraction_provider"] = provider.name
                outcome.fallback_used = True
                return


def create_default_service():
    return SearchOrchestrator(build_registry(), DATABASE, max_retries=int(number("SEARCH_MAX_RETRIES", 1)))


_default_service = None
_default_lock = threading.Lock()


def intelligent_web_search(query, options=None):
    """Primary agent-facing tool: returns a JSON-compatible dictionary."""
    global _default_service
    with _default_lock:
        if _default_service is None:
            _default_service = create_default_service()
    return asdict(_default_service.search(query, options))
