"""Build the evaluation corpus: the hand-written gold sources + seeded distractor documents.

The gold sources in data/corpus hold the answers to the evaluation questions. The
distractors are realistic engineering documents about the same and other services
(routine logs, deploy records, ADRs, minor incidents, handlers). They are hard
negatives: they share vocabulary with the questions ("deploy", "timeout", "worker",
"pool") without containing the answers, so recall@5 measures real ranking quality.

    python scripts/generate_corpus.py ./build/corpus --documents 1050
"""

import argparse
import random
import shutil
from pathlib import Path

GOLD = Path(__file__).parents[1] / "data" / "corpus"

SERVICES = [
    "api-gateway", "user-profile", "catalog-service", "shipping-service", "email-gateway",
    "recommendation-engine", "analytics-pipeline", "feature-flags", "reporting-service",
    "payment-service", "checkout-service", "auth-service", "inventory-service",
    "search-service", "notification-service",
]
CHANGES = [
    "Upgraded the structured logging library", "Added cache hit-rate metrics",
    "Removed an unused feature flag", "Bumped base image to patch OpenSSL",
    "Added pagination to the list endpoint", "Tightened input validation on IDs",
    "Moved secrets to the shared vault path", "Added a dashboard panel for p99 latency",
    "Renamed internal metrics to the new naming scheme", "Increased unit test coverage",
    "Switched JSON serialization to orjson", "Added an index on updated_at for reports",
    "Retired the v1 export endpoint", "Added request tracing headers",
]
MINOR_CAUSES = [
    ("disk usage on the log volume reached 85%", "rotated logs and lowered retention to 7 days"),
    ("a flaky integration test blocked the CI pipeline", "quarantined the test and filed a fix"),
    ("the staging DNS record expired", "renewed the record and added an expiry alert"),
    ("a dashboard query timed out in the metrics backend", "added a recording rule"),
    ("a cron job ran twice after a daylight-saving change", "moved the schedule to UTC"),
    ("an expired API token for a sandbox vendor", "rotated the token in the vault"),
    ("a noisy alert paged on a single slow request", "changed the alert to a 5 minute window"),
    ("a container image pull was rate limited", "mirrored the image to the internal registry"),
]
ADR_TOPICS = [
    ("Use Redis for session caching", "Redis gives sub-millisecond reads and TTL support."),
    ("Adopt OpenTelemetry for tracing", "One SDK for traces and metrics across languages."),
    ("Version public APIs in the URL path", "Clients pin /v2 explicitly; easy to route."),
    ("Prefer SQS over a self-hosted broker", "Managed, no capacity planning for spikes."),
    ("Store money as integer minor units", "Avoids floating point rounding in totals."),
    ("Use feature flags for risky rollouts", "Separate deploy from release; instant kill switch."),
    ("Keep service configuration in YAML", "Reviewed in pull requests alongside code."),
]
HANDLERS = ["list_items", "get_item", "update_item", "archive_item", "export_report", "sync_batch"]


def _log(rng: random.Random, service: str, day: int) -> str:
    lines = []
    for minute in range(rng.randint(6, 12)):
        status = rng.choice([200, 200, 200, 201, 204, 304, 404])
        lines.append(
            f"2026-08-{day:02d}T{rng.randint(0, 23):02d}:{minute:02d}:{rng.randint(0, 59):02d}Z "
            f"INFO  http request_id=req-{rng.randrange(16**6):06x} service={service} "
            f"route=GET /v2/{rng.choice(['items', 'users', 'orders', 'reports'])} "
            f"status={status} duration_ms={rng.randint(4, 180)}"
        )
    if rng.random() < 0.3:
        lines.append(
            f"2026-08-{day:02d}T23:59:00Z WARN  http slow request service={service} "
            f"duration_ms={rng.randint(900, 1500)} threshold_ms=800"
        )
    return "\n".join(lines) + "\n"


def _deploy(rng: random.Random, service: str, version: str) -> str:
    changes = "\n".join(f"- {change}" for change in rng.sample(CHANGES, 3))
    return (
        f"# Deploy record: {service} {version}\n\nService: {service}\n"
        f"Date: 2026-08-{rng.randint(1, 28):02d}\n\n## Changes\n\n{changes}\n\n"
        f"## Rollout\n\nCanary 10% for {rng.randint(10, 30)} minutes, then full rollout. "
        f"Error rate and latency stayed within SLO. No incidents.\n"
    )


def _minor_incident(rng: random.Random, service: str, number: int) -> str:
    cause, fix = rng.choice(MINOR_CAUSES)
    return (
        f"# Minor incident: {service}\n\nIncident ID: INC-2026-9{number:03d}\n"
        f"Service: {service}\nSeverity: SEV-4\n\n## Summary\n\nNo customer impact. "
        f"The alert fired because {cause}.\n\n## Resolution\n\nThe on-call engineer {fix}.\n"
    )


def _adr(rng: random.Random, service: str, number: int) -> str:
    title, reason = rng.choice(ADR_TOPICS)
    return (
        f"# ADR-{number:03d}: {title}\n\nService: {service}\nStatus: accepted\n\n"
        f"## Context\n\nThe {service} team needed a decision before the next quarter.\n\n"
        f"## Decision\n\n{title}.\n\n## Consequences\n\n{reason}\n"
    )


def _handler(rng: random.Random, service: str, number: int) -> str:
    name = rng.choice(HANDLERS)
    module = service.replace("-", "_")
    return (
        f'"""{service} HTTP handler: {name.replace("_", " ")}."""\n\n'
        f"from {module}.repository import Repository\n\n"
        f"PAGE_SIZE = {rng.choice([25, 50, 100])}\n\n\n"
        f"async def {name}_{number}(repo: Repository, cursor: str | None = None) -> dict:\n"
        f"    rows = await repo.fetch(limit=PAGE_SIZE, cursor=cursor)\n"
        f'    return {{"items": rows, "next": rows[-1]["id"] if rows else None}}\n'
    )


def generate_corpus(output: Path, documents: int, seed: int = 7) -> int:
    """Write gold + distractor documents to `output`. Returns the number of files written."""
    if output.exists():
        shutil.rmtree(output)
    shutil.copytree(GOLD, output)
    written = sum(1 for path in output.rglob("*") if path.is_file())
    rng = random.Random(seed)
    makers = [
        lambda s, n: (f"logs/{s}/2026-08-{n % 28 + 1:02d}-{n}.log", _log(rng, s, n % 28 + 1)),
        lambda s, n: (f"deployments/{s}/v1.{n}.md", _deploy(rng, s, f"v1.{n}.0")),
        lambda s, n: (f"incidents/minor/{s}-{n}.md", _minor_incident(rng, s, n)),
        lambda s, n: (f"docs/adr/{s}-{n:03d}.md", _adr(rng, s, n)),
        lambda s, n: (f"src/{s}/handler_{n}.py", _handler(rng, s, n)),
    ]
    number = 0
    while written < documents:
        relative, content = makers[number % len(makers)](SERVICES[number % len(SERVICES)], number)
        path = output / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        written += 1
        number += 1
    return written


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("output", type=Path)
    parser.add_argument("--documents", type=int, default=1050)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()
    count = generate_corpus(args.output, args.documents, args.seed)
    print(f"wrote {count} documents to {args.output}")


if __name__ == "__main__":
    main()
