"""Single source of truth for NATS subject + stream names used across the app.

Convention: `{domain}.{kind}.{action}`, lower-case. `organization_id` never goes in the subject
(it travels in the payload); one consumer per domain serves every org.

The template ships NO streams: infra baseline only (fleet decision 2026-10-14). A product app adds
a `StreamDefinition` to `STREAM_DEFINITIONS` and `connect_nats()` declares it (idempotent) at boot.
Never widen the `subjects` of a live stream (NATS refuses) — grow by adding a subject under an
existing wildcard. Any process that publishes from outside the API must repeat name + subjects
exactly: diverging creates a second stream over the same subject, which NATS rejects as overlap.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class StreamDefinition:
    name: str
    subjects: tuple[str, ...]
    max_age_seconds: int
    description: str


STREAM_DEFINITIONS: tuple[StreamDefinition, ...] = ()
