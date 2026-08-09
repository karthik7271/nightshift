import unittest
from pathlib import Path


ROOT = Path(__file__).parent.parent


class InfrastructureFileTests(unittest.TestCase):
    def test_docker_image_runs_the_webhook_module(self) -> None:
        dockerfile = (ROOT / "Dockerfile").read_text()
        self.assertIn('"python", "-m", "nightshift.app"', dockerfile)

    def test_bootstrap_declares_required_agent_services(self) -> None:
        script = (ROOT / "infra/bootstrap.sh").read_text()
        for service in ("run.googleapis.com", "pubsub.googleapis.com", "firestore.googleapis.com", "secretmanager.googleapis.com", "aiplatform.googleapis.com"):
            self.assertIn(service, script)
