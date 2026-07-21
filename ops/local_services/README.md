# Local services

`manage.py render --output-dir PATH` writes three plist files to `PATH`. It does not load,
unload, start, or stop a launchd service.

`manage.py install --dry-run` writes the same plist files under
`artifacts/local_services/rendered/`. It also does not mutate launchd service state.

Real `install` is intentionally separate. Before any `launchctl bootout`, it refuses a TCC-
protected checkout without the documented override and refuses to replace an unmanaged dashboard,
orchestrator, or jobs worker. A running PID is treated as launchd-owned only when `launchctl print`
confirms both the service's fixed label and PID. That sole owned process may be replaced; extra or
unattributed matching PIDs still cause refusal. Dashboard port occupancy is accepted only when the
confirmed running owner also matches the fixed dashboard argv. The demo lane is observed by health
checks and is never installed or restarted.
