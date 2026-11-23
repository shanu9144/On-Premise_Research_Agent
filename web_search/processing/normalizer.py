from dataclasses import replace
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TRACKING_PARAMETERS = {"fbclid", "gclid"}


def canonical_url(url):
    if not isinstance(url, str) or len(url) > 2048 or any(ord(char) < 32 for char in url):
        raise ValueError("Invalid URL")
    try:
        parsed = urlsplit(url)
        port = parsed.port
        hostname = parsed.hostname
    except ValueError as error:
        raise ValueError("Invalid URL") from error
    if parsed.scheme not in {"http", "https"} or not hostname or parsed.username or parsed.password:
        raise ValueError("Only public HTTP(S) URLs without credentials are allowed")
    if port not in {None, 80, 443}:
        raise ValueError("Only standard web ports are allowed")
    hostname = hostname.lower().rstrip(".")
    host = f"[{hostname}]" if ":" in hostname else hostname
    query = urlencode([(key, value) for key, value in parse_qsl(parsed.query, keep_blank_values=True)
                       if not key.lower().startswith("utm_") and key.lower() not in TRACKING_PARAMETERS])
    return urlunsplit((parsed.scheme, host, parsed.path or "/", query, ""))


def normalize(result):
    """Return a size-bounded result with a canonical URL, or None if unusable."""
    try:
        url = canonical_url(result.url)
    except ValueError:
        return None
    if not (result.snippet.strip() or result.content.strip()):
        return None
    return replace(result, url=url, title=result.title[:300], snippet=result.snippet[:3000],
                   content=result.content[:12000])
