"""Google Cloud adapters; SDK imports are lazy so local tests remain dependency-free."""
from __future__ import annotations

import base64
import json
from dataclasses import asdict

from .domain import Job, JobStatus, PatchPlan


def _to_document(job: Job) -> dict:
    data = asdict(job)
    data["status"] = job.status.value
    if job.plan:
        data["plan"] = asdict(job.plan)
    return data


def _from_document(data: dict) -> Job:
    plan_data = data.get("plan")
    plan = PatchPlan(**plan_data) if plan_data else None
    return Job(**{**data, "status": JobStatus(data["status"]), "plan": plan})


class FirestoreJobStore:
    def __init__(self, client, collection: str = "nightshift_jobs") -> None:
        self.collection = client.collection(collection)

    def create_if_absent(self, job: Job):
        ref = self.collection.document(job.id)
        if ref.get().exists:
            return _from_document(ref.get().to_dict()), False
        ref.create(_to_document(job))
        return job, True

    def save(self, job: Job) -> None:
        self.collection.document(job.id).set(_to_document(job))

    def get(self, job_id: str) -> Job | None:
        snapshot = self.collection.document(job_id).get()
        return _from_document(snapshot.to_dict()) if snapshot.exists else None

    def recent(self, limit: int = 20) -> list[Job]:
        return [_from_document(snapshot.to_dict()) for snapshot in self.collection.limit(limit).stream()]

    def find_by_commit_sha(self, repository: str, commit_sha: str) -> list[Job]:
        query = self.collection.where("repository", "==", repository).where("commit_sha", "==", commit_sha)
        return [_from_document(snapshot.to_dict()) for snapshot in query.stream()]


class PubSubDispatcher:
    def __init__(self, publisher, topic_path: str) -> None:
        self.publisher = publisher
        self.topic_path = topic_path

    def dispatch(self, job_id: str) -> None:
        self.publisher.publish(self.topic_path, json.dumps({"job_id": job_id}).encode()).result()


def pubsub_job_id(payload: dict) -> str:
    encoded = payload["message"]["data"]
    return str(json.loads(base64.b64decode(encoded))["job_id"])
