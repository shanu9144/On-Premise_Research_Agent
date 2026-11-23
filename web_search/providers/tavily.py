from ..models import ProviderResponse, SearchResult
from .base import Provider, ProviderError, UnsupportedOperation


class TavilyProvider(Provider):
    name = "tavily"
    capabilities = frozenset({"search"})
    qualities = frozenset({"general", "fresh", "live"})

    def __init__(self, api_key, timeout=30, prices=None):
        super().__init__(api_key, timeout, prices)
        # Without a key, Tavily's documented rate-limited keyless mode is used.
        self.keyless = not api_key
        if self.keyless:
            self.unit = "keyless_requests"

    def health_check(self):
        return True

    def headers(self):
        if self.keyless:
            return {"X-Tavily-Access-Mode": "keyless", "Content-Type": "application/json"}
        return super().headers()

    def estimate_cost(self, operation, options):
        if operation != "search":
            return super().estimate_cost(operation, options)
        if self.keyless:
            if options.search_depth != "basic" or options.freshness == "live":
                raise UnsupportedOperation("Keyless Tavily supports basic snippet search only")
            return 1.0
        return self.prices.get(options.search_depth, 2.0 if options.search_depth == "advanced" else 1.0)

    def search(self, query, options):
        payload = {"query": query, "search_depth": options.search_depth, "max_results": options.max_results,
                   "include_usage": True, "auto_parameters": False,
                   "include_raw_content": options.require_full_content and not self.keyless}
        if options.freshness == "recent" and not self.keyless:
            payload["max_age_hours"] = 24
        elif options.freshness == "live":
            payload["max_age_hours"] = 0
        data = self.request("POST", "https://api.tavily.com/search", payload)
        if not isinstance(data.get("results"), list):
            raise ProviderError("tavily returned invalid results")
        results = [SearchResult(str(item.get("title") or "Untitled"), str(item.get("url") or ""),
                                snippet=str(item.get("content") or ""), content=str(item.get("raw_content") or ""),
                                published_date=item.get("published_date"), provider=self.name, score=item.get("score"))
                   for item in data["results"] if isinstance(item, dict)]
        usage = data.get("usage")
        actual = usage.get("credits") if isinstance(usage, dict) and not self.keyless else None
        return ProviderResponse(results, actual, data.get("request_id"))
