import math
import time

from ..models import ProviderResponse, SearchResult
from .base import Provider, ProviderError


class FirecrawlProvider(Provider):
    name = "firecrawl"
    capabilities = frozenset({"search", "scrape", "crawl"})
    qualities = frozenset({"extraction", "crawl"})

    def estimate_cost(self, operation, options):
        if operation == "search":
            return self.prices.get("search_per_10", 2.0) * math.ceil(options.max_results / 10)
        if operation == "scrape":
            return self.prices.get("scrape", 1.0)
        if operation == "crawl":
            return self.prices.get("crawl_per_page", 1.0) * options.crawl_limit
        return super().estimate_cost(operation, options)

    def search(self, query, options):
        data = self.request("POST", "https://api.firecrawl.dev/v2/search",
                            {"query": query[:500], "limit": options.max_results, "highlights": False})
        web = data.get("data", {}).get("web") if isinstance(data.get("data"), dict) else None
        if not data.get("success") or not isinstance(web, list):
            raise ProviderError("firecrawl returned invalid results")
        results = [SearchResult(str(item.get("title") or "Untitled"), str(item.get("url") or ""),
                                snippet=str(item.get("description") or ""), provider=self.name)
                   for item in web if isinstance(item, dict)]
        return ProviderResponse(results, data.get("creditsUsed"), data.get("id"))

    def scrape(self, url, options):
        data = self.request("POST", "https://api.firecrawl.dev/v2/scrape",
                            {"url": url, "formats": ["markdown"], "parsers": [], "onlyMainContent": True})
        page = data.get("data")
        if not data.get("success") or not isinstance(page, dict):
            raise ProviderError("firecrawl returned an invalid scrape response")
        title = (page.get("metadata") or {}).get("title") or "Untitled"
        return ProviderResponse([SearchResult(str(title), url, content=str(page.get("markdown") or ""),
                                              provider=self.name)], data.get("creditsUsed"))

    def crawl(self, url, options):
        # The API defaults to 10,000 pages; the limit is always set explicitly.
        data = self.request("POST", "https://api.firecrawl.dev/v2/crawl",
                            {"url": url, "limit": options.crawl_limit, "allowExternalLinks": False,
                             "allowSubdomains": False, "scrapeOptions": {"formats": ["markdown"], "parsers": []}})
        job_id = data.get("id")
        if not data.get("success") or not isinstance(job_id, str) or not job_id.replace("-", "").isalnum():
            raise ProviderError("firecrawl returned an invalid crawl job")
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            status = self.request("GET", f"https://api.firecrawl.dev/v2/crawl/{job_id}")
            if status.get("status") == "completed":
                pages = status.get("data")
                if status.get("next") or not isinstance(pages, list):
                    raise ProviderError("firecrawl returned unsupported crawl results")
                results = [SearchResult(str((page.get("metadata") or {}).get("title") or "Untitled"),
                                        str((page.get("metadata") or {}).get("sourceURL") or ""),
                                        content=str(page.get("markdown") or ""), provider=self.name)
                           for page in pages[:options.crawl_limit] if isinstance(page, dict)]
                return ProviderResponse(results, status.get("creditsUsed"), job_id)
            if status.get("status") in {"failed", "cancelled"}:
                raise ProviderError("firecrawl crawl failed")
            time.sleep(2)
        raise ProviderError("firecrawl crawl is still running; its cost remains reserved")
