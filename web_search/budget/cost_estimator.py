from dataclasses import replace

from ..providers.base import UnsupportedOperation


def estimate(provider, analysis, options):
    """Estimated cost of one request in the provider's unit, or None if unsupported."""
    try:
        return provider.estimate_cost(analysis.operation, replace(options, freshness=analysis.freshness))
    except UnsupportedOperation:
        return None


def exceeds_query_cap(outcome, registry, provider, cost, max_cost):
    if max_cost is None:
        return False
    spent = sum(value for name, value in outcome.estimated_costs.items()
                if registry.providers[name].unit == provider.unit)
    return spent + cost > max_cost
