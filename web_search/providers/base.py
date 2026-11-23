import json

import requests

MAX_RESPONSE_BYTES = 2_000_000
RETRYABLE_STATUSES = {429, 500, 502, 503, 504}
# Rejected requests that providers document as not executed or billed.
UNBILLED_STATUSES = {400, 401, 402, 403, 422, 429, 432, 433}


class ProviderError(Exception):
    def __init__(self, message, *, retryable=False, uncertain_cost=True):
        super().__init__(message)
        self.retryable = retryable
        self.uncertain_cost = uncertain_cost


class UnsupportedOperation(Exception):
    pass


def status_error(name, status):
    return ProviderError(f"{name} HTTP {status}", retryable=status in RETRYABLE_STATUSES,
                         uncertain_cost=status not in UNBILLED_STATUSES)


class Provider:
    name = ""
    unit = "credits"
    capabilities = frozenset()
    qualities = frozenset()

    def __init__(self, api_key, timeout=30, prices=None):
        self.api_key = api_key
        self.timeout = timeout
        self.prices = prices or {}

    def get_capabilities(self):
        return self.capabilities

    def health_check(self):
        return bool(self.api_key)

    def estimate_cost(self, operation, options):
        raise UnsupportedOperation(f"{self.name} does not support {operation}")

    def search(self, query, options):
        raise UnsupportedOperation(f"{self.name} does not support search")

    def scrape(self, url, options):
        raise UnsupportedOperation(f"{self.name} does not support scrape")

    def crawl(self, url, options):
        raise UnsupportedOperation(f"{self.name} does not support crawl")

    def headers(self):
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    def request(self, method, url, payload=None):
        if not self.health_check():
            raise ProviderError(f"{self.name} API key is not configured", uncertain_cost=False)
        try:
            with requests.request(method, url, headers=self.headers(), json=payload, timeout=self.timeout,
                                  stream=True, allow_redirects=False) as response:
                if not 200 <= response.status_code < 300:
                    raise status_error(self.name, response.status_code)
                body = bytearray()
                for chunk in response.iter_content(chunk_size=16384):
                    body.extend(chunk)
                    if len(body) > MAX_RESPONSE_BYTES:
                        raise ProviderError(f"{self.name} response exceeded size limit")
        except requests.RequestException as error:
            raise ProviderError(f"{self.name} network or timeout error", retryable=True) from error
        try:
            data = json.loads(bytes(body))
        except (ValueError, UnicodeDecodeError) as error:
            raise ProviderError(f"{self.name} returned invalid JSON") from error
        if not isinstance(data, dict):
            raise ProviderError(f"{self.name} returned an invalid response")
        return data
