import ipaddress
import socket
from urllib.parse import urlsplit

from .normalizer import canonical_url


def validate_public_url(url):
    """Reject URLs resolving to local/private addresses before sending them to a scraping provider."""
    normalized = canonical_url(url)
    hostname = urlsplit(normalized).hostname
    if not hostname or hostname == "localhost" or hostname.endswith((".localhost", ".local", ".internal")):
        raise ValueError("Local and internal hosts are not allowed")
    try:
        addresses = {entry[4][0] for entry in socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)}
    except socket.gaierror as error:
        raise ValueError("Could not resolve URL host") from error
    if not addresses or any(not ipaddress.ip_address(address).is_global for address in addresses):
        raise ValueError("URL resolves to a non-public address")
    return normalized
