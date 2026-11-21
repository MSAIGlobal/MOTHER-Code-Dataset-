"""Original defensive exercise briefs for security-sensitive references."""

# The PDF establishes provenance. Only these briefs go to the teacher.
DEFENSIVE_TOPICS = {
    "what is the owasp top 10.pdf": (
        "Implement tenant-scoped record retrieval and test that an unrelated tenant receives no records.",
        "Refactor a toy data access layer to use parameterized SQL and an allowlist of sort fields.",
        "Design structured security audit events with redaction and tests for sensitive fields.",
    ),
    "owasp_genai_llm_top-10_2026.pdf": (
        "Build a deny-by-default tool authorization wrapper with per-user permissions.",
        "Validate model output against a strict schema before a downstream application consumes it.",
        "Enforce document-level permissions during retrieval and test isolation between synthetic tenants.",
    ),
    "wifi_hacking_for_beginners_learn (2).pdf": (
        "Audit operator-supplied access point configuration JSON against an approved security policy.",
        "Summarize authentication failures from synthetic access point logs with bounded alert frequency.",
        "Write a configuration regression test for guest network isolation using mocked policy data.",
    ),
    "wifi-hacking.pdf": (
        "Compare synthetic wireless asset inventories and flag unexpected configuration drift.",
        "Validate an access point's management-plane access policy against an operator-owned allowlist.",
        "Test a health monitor that alerts on persistent connectivity loss in synthetic counters.",
    ),
    "oscp command reference - oscp 2026.pdf": (
        "Join a synthetic software inventory to a supplied remediation catalogue and rank patch work.",
        "Validate hardening controls against offline configuration snapshots and report missing evidence.",
        "Group host audit events by asset and time window for incident triage using synthetic logs.",
    ),
    "using ai for offensive security.pdf": (
        "Build a read-only incident triage assistant that cites log record IDs and redacts secrets.",
        "Require independently verified human approval for proposed state changes in a mock agent.",
        "Validate model-generated triage labels and route low-confidence records to a review queue.",
    ),
    "satsec.pdf": (
        "Verify signed firmware update metadata and enforce a monotonic version policy in a toy updater.",
        "Implement a bounded telemetry decoder for an original synthetic schema with input validation.",
        "Design an audit record for firmware update acceptance or rejection using mocked devices.",
    ),
    "mados.pdf": (
        "Bound per-peer resource consumption in a toy state machine using a fake clock and cooldowns.",
        "Ignore unauthenticated state transition requests in an original simulated IoT service.",
        "Write recovery and liveness regression tests for a mock session controller with bounded queues.",
    ),
    "from_prompt_injection_to_web_exploitation.pdf": (
        "Keep retrieved document content in an untrusted data field and validate output before rendering.",
        "Implement independently enforced action permissions in a toy web assistant.",
        "Require explicit approval for state-changing requests and test denial with benign fixtures.",
    ),
    "geo_satellites_traffic_analysis.pdf": (
        "Check encryption policy compliance using synthetic link inventory attestations.",
        "Aggregate pre-authorized telemetry metadata without retaining content or end-user identifiers.",
        "Validate a ground-segment access policy using mocked assets and least-privilege rules.",
    ),
}
