#!/usr/bin/env python3
"""Plan or apply the fixed legacy RESEARCH_LAB_V0 jobs quarantine."""

from __future__ import annotations

import argparse
import json

from tios.services.jobs.runner import default_database, repository_root
from tios.services.jobs.store import (
    JobStore,
    LegacyResearchLabV0AuditPublicationError,
    LegacyResearchLabV0QuarantineRefusal,
)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    commands = result.add_subparsers(dest="command", required=True)
    commands.add_parser("plan", help="read and hash the exact fixed quarantine plan")
    apply = commands.add_parser("apply", help="apply only an exact previously reviewed plan")
    apply.add_argument("--expect-plan-sha256", required=True)
    apply.add_argument("--expect-job-id", action="append", default=[])
    repair = commands.add_parser(
        "repair-audit", help="publish one exact durable quarantine audit outbox row"
    )
    repair.add_argument("--expect-audit-sha256", required=True)
    repair.add_argument("--expect-plan-sha256", required=True)
    return result


def main() -> None:
    command_parser = parser()
    args = command_parser.parse_args()
    root = repository_root()
    try:
        with JobStore(default_database(root), root=root) as store:
            if args.command == "plan":
                output = store.plan_legacy_research_lab_v0_quarantine().as_dict()
            elif args.command == "apply":
                output = store.apply_legacy_research_lab_v0_quarantine(
                    expected_plan_sha256=args.expect_plan_sha256,
                    expected_job_ids=tuple(args.expect_job_id),
                ).as_dict()
            else:
                output = store.repair_legacy_research_lab_v0_quarantine_audit(
                    expected_audit_sha256=args.expect_audit_sha256,
                    expected_plan_sha256=args.expect_plan_sha256,
                ).as_dict()
    except LegacyResearchLabV0AuditPublicationError as error:
        print(
            json.dumps(
                {
                    "status": "DB_COMMITTED_AUDIT_FAILED",
                    "message": str(error),
                    "result": error.result.as_dict(),
                    "audit_artifact_ref": error.audit_artifact_ref,
                    "audit_payload_utf8": error.audit_payload.decode(),
                },
                sort_keys=True,
            )
        )
        raise SystemExit(2) from error
    except LegacyResearchLabV0QuarantineRefusal as error:
        command_parser.error(str(error))
    print(json.dumps(output, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
