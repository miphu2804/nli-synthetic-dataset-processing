import unittest

from src.services.dispatch_planning_service import DispatchPlanningService


class DispatchPlanningServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.service = DispatchPlanningService()

    def test_calculate_dispatch_plan_uses_one_worker_per_batch_when_under_cap(
        self,
    ) -> None:
        plan = self.service.calculate_dispatch_plan(samples=100)

        self.assertEqual(plan.samples, 100)
        self.assertEqual(plan.batch_size, 20)
        self.assertEqual(plan.total_batches, 5)
        self.assertEqual(plan.max_parallel_workers, 10)
        self.assertEqual(plan.parallel_workers, 5)
        self.assertEqual(plan.dispatch_strategy, "sliding_window")

    def test_calculate_dispatch_plan_caps_parallel_workers(self) -> None:
        plan = self.service.calculate_dispatch_plan(samples=10_000)

        self.assertEqual(plan.total_batches, 500)
        self.assertEqual(plan.parallel_workers, 10)

    def test_calculate_dispatch_plan_rejects_non_positive_samples(self) -> None:
        with self.assertRaisesRegex(ValueError, "samples must be at least 1"):
            self.service.calculate_dispatch_plan(samples=0)
