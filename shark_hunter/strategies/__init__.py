"""The SHARK-01..08 strategy family and the ablation machinery."""
from .recipes import (  # noqa: F401
    ALL_RECIPES, BASELINES, STRATEGIES, StrategyRecipe,
    ablation_variants, build_spec, unavailable_dependencies,
)
