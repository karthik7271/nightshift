import unittest
from datetime import datetime, timedelta, timezone

from nightshift.domain import Job
from nightshift.metrics import workflow_metrics


class MetricsTests(unittest.TestCase):
    def test_derives_acceptance_ci_and_draft_time_from_audit_events(self) -> None:
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        accepted = Job("accepted", "o/r", 1, audit_events=[
            {"event": "webhook_received", "occurred_at": start.isoformat()},
            {"event": "policy_accepted", "occurred_at": (start + timedelta(seconds=2)).isoformat()},
            {"event": "draft_pr_opened", "occurred_at": (start + timedelta(seconds=62)).isoformat()},
            {"event": "ci_passed", "occurred_at": (start + timedelta(seconds=90)).isoformat()},
        ])
        rejected = Job("rejected", "o/r", 2, audit_events=[
            {"event": "webhook_received", "occurred_at": start.isoformat()},
            {"event": "policy_rejected", "occurred_at": (start + timedelta(seconds=1)).isoformat()},
        ])
        failed = Job("failed", "o/r", 3, audit_events=[
            {"event": "policy_accepted", "occurred_at": start.isoformat()},
            {"event": "ci_failed", "occurred_at": (start + timedelta(seconds=3)).isoformat()},
        ])
        metrics = workflow_metrics([accepted, rejected, failed])
        self.assertEqual(3, metrics["received_jobs"])
        self.assertEqual(66.7, metrics["acceptance_rate"])
        self.assertEqual(50.0, metrics["ci_pass_rate"])
        self.assertEqual(62.0, metrics["avg_time_to_draft_pr_seconds"])

    def test_reports_unknown_rates_when_no_outcomes_exist(self) -> None:
        metrics = workflow_metrics([])
        self.assertIsNone(metrics["acceptance_rate"])
        self.assertIsNone(metrics["ci_pass_rate"])
        self.assertIsNone(metrics["avg_time_to_draft_pr_seconds"])
