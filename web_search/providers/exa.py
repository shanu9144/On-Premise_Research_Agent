import re

import requests
from exa_py import Exa
from exa_py.errors import ExaTimeoutError

from ..models import ProviderResponse, SearchResult
from .base import Provider, ProviderError, status_error

# Upper bound for full-page text so sources fit the local model's context window.
MAX_TEXT_CHARACTERS = 12000


class ExaProvider(Provider):
    """Exa /search (type auto + highlights) and /contents, following the build-with-exa skill."""

    name = "exa"
    unit = "usd"
    capabilities = frozenset({"search", "scrape"})
    qualities = frozenset({"semantic", "research", "live"})

    def __init__(self, api_key, timeout=30, prices=None, client=None):
        super().__init__(api_key, timeout, prices)
        self.client = client or (Exa(api_key=api_key) if api_key else None)

    def estimate_cost(self, operation, options):
        if operation == "search":
            return self.prices.get("search", 0.007)
        if operation == "scrape":
            return self.prices.get("contents", 0.001)
        return super().estimate_cost(operation, options)

    def call(self, method, *args, **kwargs):
        if self.client is None:
            raise ProviderError("exa API key is not configured", uncertain_cost=False)
        try:
            return method(*args, timeout=self.timeout, **kwargs)
        except ExaTimeoutError as error:
            raise ProviderError("exa request timed out", retryable=True) from error
        except requests.RequestException as error:
            raise ProviderError("exa network error", retryable=True) from error
        except ValueError as error:
            # The SDK reports API failures as ValueError containing the HTTP status.
            match = re.search(r"status(?: code)?:? (\d{3})", str(error))
            if match:
                raise status_error(self.name, int(match.group(1))) from error
            raise ProviderError("exa returned an invalid response") from error

    def search(self, query, options):
        contents = ({"text": {"max_characters": MAX_TEXT_CHARACTERS}} if options.require_full_content
                    else {"highlights": True})
        if options.freshness == "live":
            contents["max_age_hours"] = 0
        kwargs = {"type": "auto", "contents": contents, "num_results": options.max_results}
        if options.objective:
            kwargs["objective"] = options.objective
        response = self.call(self.client.search, query, **kwargs)
        results = [SearchResult(item.title or "Untitled", item.url or "", snippet=" ".join(item.highlights or []),
                                content=item.text or "", published_date=item.published_date,
                                provider=self.name, score=item.score)
                   for item in response.results]
        # Exa's costDollars is documented as an estimate, so it is not treated as confirmed billing.
        return ProviderResponse(results, None)

    def scrape(self, url, options):
        response = self.call(self.client.get_contents, [url], text={"max_characters": MAX_TEXT_CHARACTERS})
        failed = [status for status in (response.statuses or []) if getattr(status, "status", "success") != "success"]
        if failed or not response.results:
            raise ProviderError("exa could not extract the page")
        page = response.results[0]
        return ProviderResponse([SearchResult(page.title or "Untitled", page.url or url, content=page.text or "",
                                              published_date=page.published_date, provider=self.name)])
