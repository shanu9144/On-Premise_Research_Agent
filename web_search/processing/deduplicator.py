from .normalizer import normalize


def deduplicate(results, limit):
    seen = set()
    unique = []
    for result in results:
        cleaned = normalize(result)
        if cleaned is None or cleaned.url in seen:
            continue
        seen.add(cleaned.url)
        unique.append(cleaned)
        if len(unique) >= limit:
            break
    return unique
