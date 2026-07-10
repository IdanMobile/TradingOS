#!/usr/bin/env python3
"""Operate the local SQLite jobs queue."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

from tios.services.jobs import Job, JobStore, JobType, Worker, default_database
from tios.services.jobs.runner import repository_root, run_loop_until_interrupted
from tios.services.jobs.store import MAX_LIST_LIMIT


def _json_default(value: object) -> Any:
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat()
    if isinstance(value, Enum):
        return value.value
    raise TypeError(type(value).__name__)


def _show(job: Job | None) -> None:
    print(json.dumps(None if job is None else asdict(job), default=_json_default, indent=2))


def _datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise argparse.ArgumentTypeError("timestamp must include a timezone")
    return parsed.astimezone(UTC)


def _list_limit(value: str) -> int:
    parsed = int(value)
    if not 1 <= parsed <= MAX_LIST_LIMIT:
        raise argparse.ArgumentTypeError(f"limit must be between 1 and {MAX_LIST_LIMIT}")
    return parsed


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--db", type=Path, default=default_database())
    subcommands = result.add_subparsers(dest="command", required=True)
    subcommands.add_parser("init", help="initialize or migrate the database")

    enqueue = subcommands.add_parser("enqueue", help="enqueue an allowlisted job")
    enqueue_commands = enqueue.add_subparsers(dest="job", required=True)
    lab = enqueue_commands.add_parser("research-lab", help="enqueue offline Research Lab v0")
    lab.add_argument("--key", required=True, help="immutable idempotency key")
    lab.add_argument("--due", type=_datetime)
    lab.add_argument("--max-attempts", type=int, default=1)
    lab.add_argument("--timeout", type=int, default=3600)
    lab.add_argument("--interval", type=int, help="recurrence interval in seconds")
    lab.add_argument("--next-due", type=_datetime)

    listing = subcommands.add_parser("list", help="list retained jobs")
    listing.add_argument("--limit", type=_list_limit, default=100)
    status = subcommands.add_parser("status", help="show one retained job")
    status.add_argument("job_id")
    cancel = subcommands.add_parser("cancel", help="cancel an active job")
    cancel.add_argument("job_id")
    subcommands.add_parser("run-once", help="claim and execute at most one job")
    loop = subcommands.add_parser("run-loop", help="poll continuously until interrupted")
    loop.add_argument("--poll", type=float, default=1.0)
    return result


def main() -> None:
    command_parser = parser()
    args = command_parser.parse_args()
    try:
        store = JobStore(args.db, root=repository_root())
    except ValueError as error:
        command_parser.error(str(error))
    try:
        store.initialize()
        if args.command == "init":
            print(store.path)
        elif args.command == "enqueue":
            if args.interval is not None:
                schedule = store.add_schedule(
                    args.key,
                    JobType.RESEARCH_LAB_V0,
                    args.interval,
                    args.next_due or args.due or datetime.now(tz=UTC),
                    max_attempts=args.max_attempts,
                    timeout_seconds=args.timeout,
                )
                print(json.dumps(asdict(schedule), default=_json_default, indent=2))
            else:
                _show(
                    store.enqueue(
                        JobType.RESEARCH_LAB_V0,
                        args.key,
                        due_at=args.due,
                        max_attempts=args.max_attempts,
                        timeout_seconds=args.timeout,
                    )
                )
        elif args.command == "list":
            jobs = [asdict(job) for job in store.list(limit=args.limit)]
            print(json.dumps(jobs, default=_json_default))
        elif args.command == "status":
            job = store.get(args.job_id)
            if job is None:
                raise SystemExit(f"unknown job: {args.job_id}")
            _show(job)
        elif args.command == "cancel":
            _show(store.cancel(args.job_id))
        elif args.command == "run-once":
            _show(Worker(store).run_once())
        else:
            run_loop_until_interrupted(Worker(store), poll_seconds=args.poll)
    finally:
        store.close()


if __name__ == "__main__":
    main()
