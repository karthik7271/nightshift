import base64
import json
import unittest

from nightshift.cloud import pubsub_job_id


class CloudTests(unittest.TestCase):
    def test_reads_pubsub_job_id(self) -> None:
        data = base64.b64encode(json.dumps({"job_id": "delivery-1"}).encode()).decode()
        self.assertEqual("delivery-1", pubsub_job_id({"message": {"data": data}}))
