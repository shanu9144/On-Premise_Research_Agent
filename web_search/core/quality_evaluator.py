from urllib.parse import urlsplit


def quality(results, expected):
    """Coverage and domain-diversity heuristic; it does not prove the question was answered."""
    if not results:
        return 0.0
    domains = {urlsplit(result.url).hostname for result in results}
    coverage = min(1.0, len(results) / max(1, min(expected, 3)))
    diversity = min(1.0, len(domains) / max(1, min(expected, 2)))
    return round(0.7 * coverage + 0.3 * diversity, 2)


def is_sufficient(analysis, results):
    return analysis.operation != "search" or quality(results, analysis.expected_results) >= 0.75


def has_required_content(analysis, results):
    return not analysis.needs_extraction or any(result.content for result in results)
