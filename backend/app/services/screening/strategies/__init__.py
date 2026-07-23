"""Strategy registry. Add a strategy by registering its definition here."""

from app.services.screening.models import BusinessModel
from app.services.screening.scoring import StrategyDefinition
from app.services.screening.strategies.bank import STRATEGY as BANK_STRATEGY
from app.services.screening.strategies.consumer_industrial import (
    STRATEGY as CONSUMER_INDUSTRIAL_STRATEGY,
)
from app.services.screening.strategies.default import STRATEGY as DEFAULT_STRATEGY
from app.services.screening.strategies.energy import STRATEGY as ENERGY_STRATEGY
from app.services.screening.strategies.semiconductor import (
    STRATEGY as SEMICONDUCTOR_STRATEGY,
)
from app.services.screening.strategies.software import STRATEGY as SOFTWARE_STRATEGY

STRATEGY_REGISTRY: dict[BusinessModel, StrategyDefinition] = {
    strategy.business_model: strategy
    for strategy in (
        SOFTWARE_STRATEGY,
        SEMICONDUCTOR_STRATEGY,
        BANK_STRATEGY,
        CONSUMER_INDUSTRIAL_STRATEGY,
        ENERGY_STRATEGY,
        DEFAULT_STRATEGY,
    )
}


def resolve_strategy(business_model: BusinessModel) -> StrategyDefinition | None:
    return STRATEGY_REGISTRY.get(business_model)


__all__ = ["STRATEGY_REGISTRY", "resolve_strategy"]
