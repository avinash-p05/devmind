"""Normalize the many severity spellings used by alerting tools into SEV-1..SEV-4.

PagerDuty sends "P1", Datadog sends "critical", humans type "sev 2". Every incident
stored by DevMind uses the canonical label so filtering and reporting work.
Add new aliases to SEVERITY_ALIASES; that is the only place mappings live.
"""

SEVERITY_ALIASES = {
    "SEV-1": {"sev1", "sev-1", "p1", "critical", "blocker"},
    "SEV-2": {"sev2", "sev-2", "p2", "high", "major"},
    "SEV-3": {"sev3", "sev-3", "p3", "medium", "minor"},
    "SEV-4": {"sev4", "sev-4", "p4", "low", "info"},
}
DEFAULT_SEVERITY = "SEV-3"


def normalize_severity(raw: str | None) -> str:
    """Map a raw severity value to its canonical label; unknown values become SEV-3."""
    if not raw:
        return DEFAULT_SEVERITY
    key = raw.strip().lower().replace(" ", "")
    for canonical, aliases in SEVERITY_ALIASES.items():
        if key in aliases:
            return canonical
    return DEFAULT_SEVERITY
