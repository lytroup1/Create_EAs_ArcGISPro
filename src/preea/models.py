from dataclasses import dataclass, field
from typing import FrozenSet, Mapping, Optional, Tuple

from .constants import RejectionReason, ReviewStatus, ThresholdStatus


@dataclass(frozen=True)
class EATargets:
    minimum_dwellings: int
    target_dwellings: int
    maximum_dwellings: int

    def validate(self) -> None:
        if self.minimum_dwellings < 0:
            raise ValueError("Minimum dwellings per EA cannot be negative.")
        if self.target_dwellings < 1:
            raise ValueError("Target dwellings per EA must be greater than zero.")
        if self.maximum_dwellings < 1:
            raise ValueError("Maximum dwellings per EA must be greater than zero.")
        if self.minimum_dwellings > self.target_dwellings:
            raise ValueError("Minimum dwellings per EA cannot be greater than the target.")
        if self.target_dwellings > self.maximum_dwellings:
            raise ValueError("Target dwellings per EA cannot be greater than the maximum.")


@dataclass(frozen=True)
class ScoreWeights:
    dwelling_balance: float = 0.50
    building_balance: float = 0.25
    distance: float = 0.25

    def validate(self) -> None:
        values = (self.dwelling_balance, self.building_balance, self.distance)
        if any(value < 0 for value in values):
            raise ValueError("Scoring weights cannot be negative.")
        if sum(values) == 0:
            raise ValueError("At least one scoring weight must be greater than zero.")

    @property
    def normalized(self) -> Tuple[float, float, float]:
        self.validate()
        total = self.dwelling_balance + self.building_balance + self.distance
        return (self.dwelling_balance / total, self.building_balance / total, self.distance / total)


@dataclass(frozen=True)
class Building:
    building_id: str
    admin_id: str
    dwelling_count: int
    x: float
    y: float

    def __post_init__(self) -> None:
        if self.dwelling_count < 0:
            raise ValueError("Dwelling count cannot be negative.")


@dataclass(frozen=True)
class Edge:
    from_id: str
    to_id: str
    shared_boundary: float
    distance: float
    hard_barrier: bool = False


@dataclass
class CandidateEA:
    ea_id: str
    admin_id: str
    building_ids: FrozenSet[str]
    dwelling_count: int
    building_count: int
    threshold_status: ThresholdStatus
    review_status: ReviewStatus = ReviewStatus.PROPOSED
    review_notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class MergeDecision:
    accepted: bool
    score: Optional[float]
    reason: Optional[RejectionReason] = None
    components: Mapping[str, float] = field(default_factory=dict)
