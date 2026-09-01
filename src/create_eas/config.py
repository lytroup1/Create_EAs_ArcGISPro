from dataclasses import dataclass
from typing import Optional

from .models import EATargets, ScoreWeights


@dataclass(frozen=True)
class WorkflowConfig:
    targets: EATargets
    weights: ScoreWeights = ScoreWeights()
    initial_clustering_distance: float = 100.0
    maximum_ea_area_sq_km: Optional[float] = None
    random_seed: int = 0

    def validate(self) -> None:
        self.targets.validate()
        self.weights.validate()
        if self.initial_clustering_distance <= 0:
            raise ValueError("Initial clustering distance must be greater than zero.")
        if self.maximum_ea_area_sq_km is not None and self.maximum_ea_area_sq_km <= 0:
            raise ValueError("Maximum EA area must be greater than zero when supplied.")
