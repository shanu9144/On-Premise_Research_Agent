from ..config.settings import number, setting
from ..models import Budget
from .exa import ExaProvider
from .firecrawl import FirecrawlProvider
from .tavily import TavilyProvider


class ProviderRegistry:
    def __init__(self):
        self.providers = {}
        self.budgets = {}

    def register(self, provider, budget):
        if provider.name in self.providers:
            raise ValueError(f"Provider already registered: {provider.name}")
        self.providers[provider.name] = provider
        self.budgets[provider.name] = budget


def build_registry():
    timeout = number("SEARCH_TIMEOUT_SECONDS", 30)
    if not 1 <= timeout <= 120:
        raise ValueError("SEARCH_TIMEOUT_SECONDS must be between 1 and 120")
    tavily_key = setting("TAVILY_API_KEY")
    providers = [
        (TavilyProvider(tavily_key, timeout, {"basic": number("TAVILY_BASIC_COST", 1),
                                              "advanced": number("TAVILY_ADVANCED_COST", 2)}),
         "TAVILY" if tavily_key else "TAVILY_KEYLESS"),
        (ExaProvider(setting("EXA_API_KEY"), timeout, {"search": number("EXA_SEARCH_COST", 0.007),
                                                       "contents": number("EXA_CONTENTS_COST", 0.001)}),
         "EXA"),
        (FirecrawlProvider(setting("FIRECRAWL_API_KEY"), timeout,
                           {"search_per_10": number("FIRECRAWL_SEARCH_PER_10_COST", 2),
                            "scrape": number("FIRECRAWL_SCRAPE_COST", 1),
                            "crawl_per_page": number("FIRECRAWL_CRAWL_PER_PAGE_COST", 1)}),
         "FIRECRAWL"),
    ]
    registry = ProviderRegistry()
    for provider, prefix in providers:
        keyless = prefix == "TAVILY_KEYLESS"
        # Paid providers stay disabled until budgets are configured; keyless gets a small request quota.
        budget = Budget(daily=number(f"{prefix}_DAILY_BUDGET", 10 if keyless else 0),
                        monthly=number(f"{prefix}_MONTHLY_BUDGET", 100 if keyless else 0),
                        reserve=number(f"{prefix}_RESERVE", 0), unit=provider.unit)
        registry.register(provider, budget)
    return registry
