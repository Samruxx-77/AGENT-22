"""Budget-aware model routing (P0, blueprint Feature B).

Explicit rules only -- no ML router, no hidden provider calls. A profile
is just data: id, provider, capabilities, example prices, latency tier
and health. Prices are caller-supplied example values; the blueprint
explicitly warns not to hard-code real prices or assume every provider
reports usage consistently. All costs here are therefore estimates.

Hard rules enforced here, not in prompt text:
  * only models on the allowlist (empty allowlist = all) are eligible;
  * only healthy models are eligible;
  * the model must carry the capability the task type needs;
  * fallback must never silently switch to a more expensive model: when
    allow_paid_fallback is False, a fallback may cost at most the primary;
  * when no fallback fits the task cost ceiling, selection raises
    NoAffordableFallback instead of picking something pricier.
"""

from __future__ import annotations

from dataclasses import dataclass, field

TASK_CAPABILITIES = {
    "chat": "chat",
    "coding": "coding",
    "planning": "reasoning",
    "vision": "vision",
    "simple": "chat",
}

_LATENCY_RANK = {"fast": 0, "standard": 1, "slow": 2}


class RouterError(Exception):
    """Base router error."""


class NoModelAvailable(RouterError):
    """No eligible model for the task type."""


class NoAffordableFallback(RouterError):
    """No fallback fits the cost ceiling; the caller must ask the user."""


@dataclass(frozen=True)
class ModelProfile:
    model_id: str
    provider: str
    capabilities: frozenset[str] = frozenset({"chat"})
    price_in_per_1k_usd: float = 0.0
    price_out_per_1k_usd: float = 0.0
    latency_tier: str = "standard"
    healthy: bool = True


@dataclass
class RouterConfig:
    enabled: bool = True
    default_profile: str = "balanced"
    max_task_cost_usd: float | None = 0.25
    daily_budget_usd: float | None = 2.00
    allow_paid_fallback: bool = False
    max_retries_per_provider: int = 1
    allowed_models: list[str] = field(default_factory=list)

    def estimate_for(self, profile: ModelProfile, input_tokens: int, output_tokens: int) -> float:
        try:
            from .budget import estimate_cost
        except ImportError:  # loaded as a standalone file in tests
            from budget import estimate_cost

        return estimate_cost(
            input_tokens, output_tokens, profile.price_in_per_1k_usd, profile.price_out_per_1k_usd
        )


def _eligible(
    profiles: list[ModelProfile], task_type: str, config: RouterConfig
) -> list[ModelProfile]:
    capability = TASK_CAPABILITIES.get(task_type, "chat")
    out = []
    for profile in profiles:
        if config.allowed_models and profile.model_id not in config.allowed_models:
            continue
        if not profile.healthy:
            continue
        if capability not in profile.capabilities:
            continue
        out.append(profile)
    return out


def select_model(
    task_type: str,
    profiles: list[ModelProfile],
    config: RouterConfig,
    input_tokens: int = 1000,
    output_tokens: int = 500,
) -> ModelProfile:
    """Pick the cheapest eligible model; latency breaks ties.

    Sorting key is (estimated cost, latency rank, model_id) so the choice
    is deterministic and auditable -- the same inputs always pick the
    same model, which the tests assert.
    """
    if not config.enabled:
        raise RouterError("routing is disabled in RouterConfig")
    candidates = _eligible(profiles, task_type, config)
    if not candidates:
        raise NoModelAvailable(f"no healthy, allowed model with capability for {task_type!r}")
    return sorted(
        candidates,
        key=lambda p: (
            config.estimate_for(p, input_tokens, output_tokens),
            _LATENCY_RANK.get(p.latency_tier, 1),
            p.model_id,
        ),
    )[0]


def fallback_order(
    primary: ModelProfile,
    profiles: list[ModelProfile],
    config: RouterConfig,
    task_type: str = "chat",
    input_tokens: int = 1000,
    output_tokens: int = 500,
) -> list[ModelProfile]:
    """Ordered fallbacks after a primary failure, respecting the ceiling.

    Each candidate is tried at most max_retries_per_provider times by the
    caller. A candidate that would cost more than the primary is dropped
    unless allow_paid_fallback is True, and a candidate whose estimated
    cost exceeds max_task_cost_usd is dropped in both cases. If the list
    ends up empty, the caller must stop and ask -- never silently pay more.
    """
    candidates = []
    primary_cost = config.estimate_for(primary, input_tokens, output_tokens)
    for profile in _eligible(profiles, task_type, config):
        if profile.model_id == primary.model_id:
            continue
        cost = config.estimate_for(profile, input_tokens, output_tokens)
        if not config.allow_paid_fallback and cost > primary_cost:
            continue
        if config.max_task_cost_usd is not None and cost > config.max_task_cost_usd:
            continue
        candidates.append(profile)
    candidates.sort(
        key=lambda p: (
            config.estimate_for(p, input_tokens, output_tokens),
            _LATENCY_RANK.get(p.latency_tier, 1),
            p.model_id,
        )
    )
    if not candidates:
        raise NoAffordableFallback(
            "no fallback model fits the allowlist, health and cost ceiling; "
            "stop and ask the user instead of switching to a pricier model"
        )
    return candidates
