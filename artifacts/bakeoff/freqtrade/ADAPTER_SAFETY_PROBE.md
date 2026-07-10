# Freqtrade adapter precision and failure probe

Status: **PASS**

- Checked 577,803 BTCUSDT rows across 5 numeric columns.
- Maximum Decimal → float → decimal-string error: `0`. Float64 remains
  an explicit engine-boundary loss; canonical storage remains decimal128.
- Unsupported pairs fail before execution with an observable parser error.
- A missing exported result fails normalization with an observable error.
- Lane success requires both engine completion and a newly exported artifact, because
  Freqtrade can return zero even for a configuration error.

Machine-readable result: `artifacts/bakeoff/freqtrade/adapter_safety_probe/result.json`.
