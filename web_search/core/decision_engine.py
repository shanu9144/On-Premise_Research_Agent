from ..budget.cost_estimator import estimate


def rank_providers(registry, analysis, options, fallback):
    """Eligible providers, best first, by suitability then share of monthly budget consumed."""
    ranked = []
    for name, provider in registry.providers.items():
        if name in options.exclude_providers or analysis.operation not in provider.get_capabilities():
            continue
        if not provider.health_check() or not fallback.available(name):
            continue
        if analysis.freshness == "live" and analysis.operation == "search" and "live" not in provider.qualities:
            continue
        cost = estimate(provider, analysis, options)
        if cost is None or (options.max_cost is not None and cost > options.max_cost):
            continue
        suitability = 0
        if analysis.semantic and "semantic" in provider.qualities:
            suitability += 2
        if not analysis.semantic and "general" in provider.qualities:
            suitability += 2
        if analysis.freshness != "normal" and "fresh" in provider.qualities:
            suitability += 1
        if name == options.preferred_provider:
            suitability += 10
        monthly = registry.budgets[name].monthly
        budget_share = cost / monthly if monthly else (0 if cost == 0 else float("inf"))
        ranked.append((-suitability, budget_share, name, provider))
    return [item[-1] for item in sorted(ranked, key=lambda item: item[:3])]
