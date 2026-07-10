# Freqtrade dry-run capability probe (T-006-02)

Status: **PASS** · ran 25s then sent SIGINT (freqtrade's documented graceful-stop signal).

Config: `engines/freqtrade/lane/config_F0_S0.json` (`dry_run: true`, empty exchange key/secret — asserted before launch, so no authenticated/order-placing exchange calls are possible).

Pass markers found: ['Dry run is enabled']
Fail markers found: none

Full log: `artifacts/bakeoff/freqtrade/dry_run_probe/trade_dry_run.log`
