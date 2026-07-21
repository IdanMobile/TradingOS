"""Deterministic, read-only projections over retained evidence."""

from .backtest_attribution import (
    BacktestAttributionError,
    BacktestAttributionReport,
    BacktestFailureDiagnosis,
    BacktestRecommendation,
    BacktestValidationEvidence,
    RoundTripAttribution,
    analyze_long_only_roundtrips,
    build_historical_trade_traces,
    diagnose_backtest_failure,
)
from .decision_intelligence import (
    DecisionIntelligenceReport,
    DecisionTraceLedger,
    DecisionTraceLedgerError,
    HistoricalTradeTraceLedger,
    canonical_trace_payload,
    project_decision_report,
    trace_digest,
)

__all__ = [
    "BacktestAttributionError",
    "BacktestAttributionReport",
    "BacktestFailureDiagnosis",
    "BacktestRecommendation",
    "BacktestValidationEvidence",
    "DecisionIntelligenceReport",
    "DecisionTraceLedger",
    "DecisionTraceLedgerError",
    "HistoricalTradeTraceLedger",
    "RoundTripAttribution",
    "analyze_long_only_roundtrips",
    "build_historical_trade_traces",
    "canonical_trace_payload",
    "diagnose_backtest_failure",
    "project_decision_report",
    "trace_digest",
]
