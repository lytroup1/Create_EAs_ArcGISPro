from collections import defaultdict
from typing import Iterable, Mapping

from .constants import ReviewStatus
from .models import Building, CandidateEA, Edge, EATargets, MergeDecision, ScoreWeights
from .scoring import evaluate_merge, threshold_status


def grow_candidate_eas(
    buildings: Iterable[Building],
    edges: Iterable[Edge],
    targets: EATargets,
    weights: ScoreWeights,
    random_seed: int = 0,
) -> tuple[list[CandidateEA], list[MergeDecision]]:
    del random_seed  # Reserved for future seeded alternative strategies.
    targets.validate()
    weights.validate()
    building_map = {building.building_id: building for building in buildings}
    neighbors: dict[str, list[Edge]] = defaultdict(list)
    for edge in edges:
        neighbors[edge.from_id].append(edge)
        neighbors[edge.to_id].append(
            Edge(edge.to_id, edge.from_id, edge.shared_boundary, edge.distance, edge.hard_barrier)
        )

    unassigned = set(building_map)
    candidates: list[CandidateEA] = []
    decisions: list[MergeDecision] = []
    ea_number = 1
    while unassigned:
        seed_id = min(
            unassigned,
            key=lambda item: (-building_map[item].dwelling_count, -1, item),
        )
        members = {seed_id}
        unassigned.remove(seed_id)
        current_dwellings = building_map[seed_id].dwelling_count
        while True:
            choices = []
            for member_id in sorted(members):
                for edge in neighbors[member_id]:
                    if edge.to_id not in unassigned:
                        continue
                    neighbor = building_map[edge.to_id]
                    decision = evaluate_merge(
                        current_admin_id=building_map[seed_id].admin_id,
                        neighbor_admin_id=neighbor.admin_id,
                        current_dwellings=current_dwellings,
                        neighbor_dwellings=neighbor.dwelling_count,
                        current_buildings=len(members),
                        neighbor_buildings=1,
                        neighbor_distance=edge.distance,
                        shared_boundary=edge.shared_boundary,
                        targets=targets,
                        weights=weights,
                        hard_barrier=edge.hard_barrier,
                    )
                    decisions.append(decision)
                    if decision.accepted:
                        choices.append((decision.score, edge.to_id))
            if not choices or current_dwellings >= targets.target_dwellings:
                break
            _, selected_id = min(choices, key=lambda item: (item[0], item[1]))
            members.add(selected_id)
            unassigned.remove(selected_id)
            current_dwellings += building_map[selected_id].dwelling_count

        candidates.append(
            CandidateEA(
                ea_id=f"EA_{ea_number:05d}",
                admin_id=building_map[seed_id].admin_id,
                building_ids=frozenset(members),
                dwelling_count=current_dwellings,
                building_count=len(members),
                threshold_status=threshold_status(current_dwellings, targets),
                review_status=(
                    ReviewStatus.REVIEW_REQUIRED
                    if current_dwellings > targets.maximum_dwellings
                    else ReviewStatus.PROPOSED
                ),
                review_notes=(
                    ["Candidate contains a building workload requiring review."]
                    if current_dwellings > targets.maximum_dwellings
                    else []
                ),
            )
        )
        ea_number += 1
    return candidates, decisions
