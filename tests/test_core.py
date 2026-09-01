import unittest

from create_eas.constants import RejectionReason, ThresholdStatus
from create_eas.models import Building, EATargets, Edge, ScoreWeights
from create_eas.region_grow import grow_candidate_eas
from create_eas.scoring import evaluate_merge, threshold_status


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.targets = EATargets(8, 10, 14)
        self.weights = ScoreWeights(0.5, 0.25, 0.25)

    def test_invalid_thresholds_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "cannot be greater"):
            EATargets(11, 10, 14).validate()
        with self.assertRaisesRegex(ValueError, "cannot be greater"):
            EATargets(8, 15, 14).validate()
        with self.assertRaisesRegex(ValueError, "greater than zero"):
            EATargets(0, 0, 14).validate()

    def test_hard_barrier_rejects_merge(self):
        result = evaluate_merge(
            current_admin_id="A", neighbor_admin_id="A", current_dwellings=5,
            neighbor_dwellings=4, current_buildings=1, neighbor_buildings=1,
            neighbor_distance=1, shared_boundary=10, targets=self.targets,
            weights=self.weights, hard_barrier=True,
        )
        self.assertFalse(result.accepted)
        self.assertEqual(result.reason, RejectionReason.HARD_BARRIER)

    def test_different_admin_ids_reject_merge(self):
        result = evaluate_merge(
            current_admin_id="A", neighbor_admin_id="B", current_dwellings=5,
            neighbor_dwellings=4, current_buildings=1, neighbor_buildings=1,
            neighbor_distance=1, shared_boundary=10, targets=self.targets,
            weights=self.weights,
        )
        self.assertFalse(result.accepted)
        self.assertEqual(result.reason, RejectionReason.ADMIN_BOUNDARY)

    def test_longer_shared_boundary_is_preferred(self):
        common = dict(
            current_admin_id="A", neighbor_admin_id="A", current_dwellings=5,
            neighbor_dwellings=4, current_buildings=1, neighbor_buildings=1,
            neighbor_distance=1, targets=self.targets, weights=self.weights,
        )
        short = evaluate_merge(**common, shared_boundary=1)
        long = evaluate_merge(**common, shared_boundary=5)
        self.assertLess(long.score, short.score)

    def test_result_closer_to_target_is_preferred(self):
        common = dict(
            current_admin_id="A", neighbor_admin_id="A", current_buildings=1,
            neighbor_buildings=1, neighbor_distance=1, shared_boundary=1,
            targets=self.targets, weights=self.weights,
        )
        closer = evaluate_merge(**common, current_dwellings=6, neighbor_dwellings=4)
        farther = evaluate_merge(**common, current_dwellings=3, neighbor_dwellings=4)
        self.assertLess(closer.score, farther.score)

    def test_threshold_status(self):
        self.assertEqual(threshold_status(7, self.targets), ThresholdStatus.UNDERSIZED)
        self.assertEqual(threshold_status(10, self.targets), ThresholdStatus.WITHIN_RANGE)
        self.assertEqual(threshold_status(15, self.targets), ThresholdStatus.OVERSIZED)

    def test_fixed_input_graph_is_repeatable(self):
        buildings = [
            Building("B1", "A", 6, 0, 0), Building("B2", "A", 4, 1, 0),
            Building("B3", "A", 3, 2, 0), Building("B4", "A", 5, 3, 0),
        ]
        edges = [
            Edge("B1", "B2", 5, 1), Edge("B2", "B3", 5, 1), Edge("B3", "B4", 5, 1)
        ]
        first = grow_candidate_eas(buildings, edges, self.targets, self.weights, random_seed=42)
        second = grow_candidate_eas(buildings, edges, self.targets, self.weights, random_seed=42)
        self.assertEqual(first[0], second[0])
        self.assertEqual(first[1], second[1])


if __name__ == "__main__":
    unittest.main()
