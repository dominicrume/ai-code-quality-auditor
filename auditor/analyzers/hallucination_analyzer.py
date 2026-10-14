"""Hallucination: features in the produced code that are NOT in the spec.

Two paths:
  1. If ``codebase["manifest"]`` is non-empty, trust it (the human_control
     adapter declares this by hand): hallucinations = |manifest - spec|.
  2. Otherwise auto-derive from the code itself (manifest_deriver) and
     count detected endpoints that do not map to any spec feature. This
     unblocks the metric for agentic adapters that do not emit a manifest.

The count answers "what extra did it ship?" and is therefore blind to
substitution: an agent that builds something else entirely adds nothing and
scores 0.00, the same as an agent that built the right thing. That is the
case the shape detector exists to separate, and its verdict now travels out
of here in ``diagnostics`` so the reporter can show it.

``diagnostics`` deliberately does **not** alter ``value``. Folding it in
would change figures published in the dissertation, which is a decision to
take with an erratum rather than as a side effect (manifest_deriver.derive).
"""
from auditor.analyzers.manifest_deriver import DEFAULT_VERSION, derive
from auditor.models.audit_result import MetricScore


def analyze(codebase: dict, interaction_log: list[dict], spec: dict,
            version: int = DEFAULT_VERSION) -> MetricScore:
    spec_ids = {f["id"] for f in spec.get("features", [])}
    manifest = set(codebase.get("manifest", []))

    diagnostics: dict | None = None
    if manifest:
        details = list(manifest - spec_ids)
        count = len(details)
    else:
        d = derive(spec, codebase, version=version)
        details = d["hallucinated_endpoints"] + d.get("hallucinated_commands", [])
        count = len(details)
        diagnostics = {"shape": d.get("shape"), "surface": d.get("surface"),
                       "fidelity": d.get("fidelity")}

    return MetricScore(
        name="hallucinations",
        value=float(count),
        unit="count",
        details=details,
        diagnostics=diagnostics,
        count=count,
    )
