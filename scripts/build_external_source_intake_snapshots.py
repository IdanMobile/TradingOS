"""Build metadata-only external source-intake snapshots.

The snapshots are local planning artifacts. They do not fetch platform content, ask for
credentials, subscribe to signals, copy trades, or open any venue/order path.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tios.research_assets import ResearchSourceRegistry, SourceIntakePlanRegistry

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "research" / "PRIMARY_STRATEGY_RESEARCH_SOURCES_V1.yaml"
PLANS = ROOT / "research" / "EXTERNAL_SOURCE_INTAKE_PLANS_V1.yaml"
PUBLIC_CAPTURE = ROOT / "research" / "EXTERNAL_SOURCE_PUBLIC_CAPTURE_V1.yaml"
INDEX = ROOT / "artifacts" / "source_intake" / "EXTERNAL_SOURCE_INTAKE_INDEX_2026_07_11.json"


def _load_public_captures(path: Path) -> dict[str, dict[str, str]]:
    import yaml

    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or raw.get("registry_version") != 1:
        raise ValueError("public capture registry must have registry_version: 1")
    captures = raw.get("captures")
    if not isinstance(captures, list):
        raise ValueError("public capture registry must contain captures")
    result: dict[str, dict[str, str]] = {}
    for capture in captures:
        if not isinstance(capture, dict):
            raise ValueError("each capture must be a mapping")
        source_ref = capture.get("source_ref")
        evidence_url = capture.get("evidence_url")
        fields = capture.get("fields")
        if not isinstance(source_ref, str) or not isinstance(evidence_url, str):
            raise ValueError("capture source_ref and evidence_url must be strings")
        if not isinstance(fields, dict) or any(not isinstance(key, str) for key in fields):
            raise ValueError("capture fields must be a mapping of strings")
        string_fields: dict[str, str] = {"evidence_url": evidence_url}
        for key, value in fields.items():
            if not isinstance(value, str) or not value:
                raise ValueError(f"capture field must be non-empty string: {source_ref}.{key}")
            string_fields[key] = value
        result[source_ref] = string_fields
    return result


def _field_status(
    plan_field: str,
    captured_at: str,
    source: Any,
    captured_fields: dict[str, str],
) -> dict[str, str]:
    known: dict[str, str] = {
        "captured_at_utc": captured_at,
        "canonical_url": source.canonical_publisher_url,
        "platform": source.publication,
        "author_or_publisher": ", ".join(source.authors),
    }
    value = known.get(plan_field)
    if value is not None:
        return {"status": "KNOWN_FROM_REGISTRY", "value": value}
    captured = captured_fields.get(plan_field)
    if captured is not None:
        return {
            "status": "PUBLIC_SOURCE_CAPTURED",
            "value": captured,
            "evidence_url": captured_fields["evidence_url"],
        }
    return {"status": "PENDING_OFFLINE_CAPTURE", "value": ""}


def build_snapshots(captured_at: str) -> dict[str, Any]:
    sources = ResearchSourceRegistry.load(SOURCES)
    plans = SourceIntakePlanRegistry.load(PLANS, source_registry=sources)
    captures = _load_public_captures(PUBLIC_CAPTURE)
    rows: list[dict[str, Any]] = []
    for plan in plans.list():
        source = sources.get(plan.source_ref)
        captured_fields = captures.get(plan.source_ref, {})
        payload: dict[str, Any] = {
            "schema": "tios-external-source-intake-snapshot-v1",
            "plan_id": plan.plan_id,
            "source_ref": plan.source_ref,
            "source_title": source.title,
            "source_class": source.source_class.value,
            "canonical_url": source.canonical_publisher_url,
            "capture_mode": plan.capture_mode.value,
            "intake_status": plan.status.value,
            "captured_at_utc": captured_at,
            "content_capture_status": "METADATA_ONLY_PENDING_PLATFORM_CAPTURE",
            "evidence_strength": source.evidence_strength.value,
            "approval_eligible": False,
            "allowed_uses": list(plan.allowed_uses),
            "prohibited_actions": list(plan.prohibited_actions),
            "required_capture_fields": {
                field: _field_status(field, captured_at, source, captured_fields)
                for field in plan.required_capture_fields
            },
            "bias_risks": list(plan.bias_risks),
            "validation_prerequisites": list(plan.validation_prerequisites),
            "notes": list(plan.notes),
        }
        output = ROOT / plan.target_artifact
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        rows.append(
            {
                "plan_id": plan.plan_id,
                "source_ref": plan.source_ref,
                "artifact": plan.target_artifact,
                "content_capture_status": payload["content_capture_status"],
                "approval_eligible": False,
            }
        )
    index = {
        "schema": "tios-external-source-intake-index-v1",
        "captured_at_utc": captured_at,
        "plan_count": len(rows),
        "ready_count": sum(row["content_capture_status"].startswith("METADATA") for row in rows),
        "execution_authority": "NONE",
        "venue_connection": "NONE",
        "paper_demo_live": "DISABLED",
        "rows": rows,
    }
    INDEX.parent.mkdir(parents=True, exist_ok=True)
    INDEX.write_text(json.dumps(index, indent=2, sort_keys=True) + "\n")
    return index


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--captured-at",
        default=datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    )
    args = parser.parse_args()
    print(json.dumps(build_snapshots(args.captured_at), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
