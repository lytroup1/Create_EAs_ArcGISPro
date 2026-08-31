from math import hypot
from typing import Iterable, Mapping

from .models import EATargets, MergeDecision, ScoreWeights
from .constants import RejectionReason, ThresholdStatus


def threshold_status(dwelling_count: int, targets: EATargets) -> ThresholdStatus:
    targets.validate()
    if dwelling_count < targets.minimum_dwellings:
        return ThresholdStatus.UNDERSIZED
    if dwelling_count > targets.maximum_dwellings:
        return ThresholdStatus.OVERSIZED
    return ThresholdStatus.WITHIN_RANGE


def target_deviation(dwelling_count: int, targets: EATargets) -> float:
    targets.validate()
    return float(dwelling_count - targets.target_dwellings)


def normalized_target_penalty(dwelling_count: int, targets: EATargets) -> float:
    targets.validate()
    return abs(target_deviation(dwelling_count, targets)) / max(targets.target_dwellings, 1)


def building_balance_penalty(building_count: int, target_buildings: float) -> float:
    if target_buildings <= 0:
        raise ValueError("Target buildings must be greater than zero.")
    return abs(building_count - target_buildings) / target_buildings


def distance_penalty(distances: Iterable[float], scale: float = 1.0) -> float:
    if scale <= 0:
        raise ValueError("Distance scale must be greater than zero.")
    values = list(distances)
    return (sum(values) / len(values)) / scale if values else 0.0


def shared_boundary_reward(shared_boundary: float, scale: float = 1.0) -> float:
    if shared_boundary < 0 or scale <= 0:
        raise ValueError("Shared boundary and scale must be non-negative and positive respectively.")
    return shared_boundary / scale


def evaluate_merge(
    *,
    current_admin_id: str,
    neighbor_admin_id: str,
    current_dwellings: int,
    neighbor_dwellings: int,
    current_buildings: int,
    neighbor_buildings: int,
    neighbor_distance: float,
    shared_boundary: float,
    targets: EATargets,
    weights: ScoreWeights,
    distance_scale: float = 1.0,
    shared_boundary_scale: float = 1.0,
    hard_barrier: bool = False,
    connected: bool = True,
) -> MergeDecision:
    targets.validate()
    weights.validate()
    if current_admin_id != neighbor_admin_id:
        return MergeDecision(False, None, RejectionReason.ADMIN_BOUNDARY)
    if hard_barrier:
        return MergeDecision(False, None, RejectionReason.HARD_BARRIER)
    if not connected:
        return MergeDecision(False, None, RejectionReason.DISCONNECTED)

    combined_dwellings = current_dwellings + neighbor_dwellings
    if combined_dwellings > targets.maximum_dwellings:
        return MergeDecision(False, None, RejectionReason.MAX_DWELLINGS)

    dwelling_weight, building_weight, distance_weight = weights.normalized
    components = {
        "dwelling_balance": normalized_target_penalty(combined_dwellings, targets),
        "building_balance": building_balance_penalty(
            current_buildings + neighbor_buildings,
            targets.target_dwellings / max(targets.minimum_dwellings or 1, 1),
        ),
        "distance": distance_penalty([neighbor_distance], distance_scale),
        "shared_boundary_reward": shared_boundary_reward(shared_boundary, shared_boundary_scale),
    }
    score = (
        dwelling_weight * components["dwelling_balance"]
        + building_weight * components["building_balance"]
        + distance_weight * components["distance"]
        - components["shared_boundary_reward"]
    )
    return MergeDecision(True, score, components=components)


def point_distance(first: tuple[float, float], second: tuple[float, float]) -> float:
    return hypot(first[0] - second[0], first[1] - second[1])
