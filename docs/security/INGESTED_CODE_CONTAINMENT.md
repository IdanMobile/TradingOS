# Ingested Code Containment Policy

External strategy code is untrusted data until reproduced in containment.

- Never import external strategy modules into the Trading OS process.
- Execute only from an isolated working directory through a dedicated `.venv`.
- Inherit no parent environment variables, credentials, provider keys, or user site packages.
- On macOS, wrap execution with `sandbox-exec` and deny all network access.
- Preserve stdout, stderr, exit status, timeout failures, source hash, and interpreter manifest.
- A containment failure rejects reproduction; it never falls back to in-process execution.
- Containers may replace the macOS wrapper when Docker is available, but the same no-secret,
  no-network, bounded-time contract remains mandatory.

The wrapper is `tios.security_ops.run_untrusted_python`. It is for reproduction only;
ingestion, semantic extraction, and license review should treat source files as text.
