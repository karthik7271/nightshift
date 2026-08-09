from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath

from .domain import IssueRef, PatchPlan, PolicyDecision


@dataclass(frozen=True)
class SafetyPolicy:
    approved_repositories: frozenset[str]
    required_labels: frozenset[str] = frozenset({"agent-ready", "bug"})
    allowed_roots: tuple[str, ...] = ("nightshift/", "tests/", "src/")
    forbidden_names: frozenset[str] = frozenset({
        "package.json", "package-lock.json", "pnpm-lock.yaml", "yarn.lock",
        "Dockerfile", "docker-compose.yml", ".github", "terraform", "infra",
    })
    max_files: int = 3
    min_confidence: float = 0.75

    def qualify(self, issue: IssueRef) -> PolicyDecision:
        if issue.repository not in self.approved_repositories:
            return PolicyDecision(False, "Repository is not approved for autonomous changes.")
        missing = self.required_labels - issue.labels
        if missing:
            return PolicyDecision(False, f"Issue is missing required labels: {', '.join(sorted(missing))}.")
        return PolicyDecision(True, "Issue is eligible for bounded autonomous handling.")

    def validate_plan(self, plan: PatchPlan) -> PolicyDecision:
        if plan.confidence < self.min_confidence:
            return PolicyDecision(False, "Model confidence is below the autonomous-action threshold.")
        if len(plan.expected_files) == 0:
            return PolicyDecision(False, "Plan does not name files to change.")
        if len(plan.expected_files) > self.max_files:
            return PolicyDecision(False, "Plan exceeds the maximum changed-file limit.")
        for path in plan.expected_files:
            decision = self._validate_path(path)
            if not decision.allowed:
                return decision
        return PolicyDecision(True, "Plan is within NightShift's allowed scope.")

    def _validate_path(self, path: str) -> PolicyDecision:
        normalized = PurePosixPath(path)
        if normalized.is_absolute() or ".." in normalized.parts:
            return PolicyDecision(False, f"Unsafe path: {path}.")
        if not path.startswith(self.allowed_roots):
            return PolicyDecision(False, f"Path is outside allowed roots: {path}.")
        if any(part in self.forbidden_names for part in normalized.parts):
            return PolicyDecision(False, f"Path is forbidden by policy: {path}.")
        if any(token in path.lower() for token in ("auth", "secret", "credential", "migration")):
            return PolicyDecision(False, f"Sensitive path requires human review: {path}.")
        return PolicyDecision(True, "Path is allowed.")
