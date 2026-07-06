# Skill: Source Verifier (v1)

Role: R2 · Cost tier: mid · Status: specified, not yet implemented
Absorbs: Official Documentation Verifier, Citation Verifier, API Changelog Watcher, Documentation Freshness Auditor, Exchange Capability Verifier.

## Purpose
Verify a specific claim, version, license, capability, or freshness state against primary sources, producing an evidence record with a re-verification trigger.

## Trigger conditions
- A decision or registry row cites evidence older than its reverify trigger.
- A dependency upgrade, provider model change, or exchange changelog event.
- Scout output marked for deep-check.
- Any claim tagged `evidence: weak/medium` feeding an Approved decision.

## Inputs
Claim text, current evidence link(s), date last checked.

## Tools
Web fetch of official docs/repos/changelogs/status pages. Read-only.

## Process
1. Identify the primary source for the claim (official doc > repo > release notes > maintainer statement).
2. Fetch and quote the exact supporting/contradicting span.
3. Classify: SUPPORTED / CONTRADICTED / INSUFFICIENT / CHANGED (with what changed).
4. Record: source URL, date-checked, version checked, evidence strength, reverify trigger (event- or time-based).
5. If CONTRADICTED/CHANGED: list every package file citing the stale fact (grep) for correction.

## Outputs (contract)
Evidence record block (claim, verdict, span, URL, date, strength, trigger) + stale-reference list. Feeds `research/SOURCE_REGISTRY.md` and decision records.

## Prohibited behavior
- Accepting secondary sources when a primary exists.
- Extrapolating undocumented behavior ("probably supports…").
- Marking SUPPORTED on paywalled/unfetchable sources (that is INSUFFICIENT).

## Quality gates
Verdict must quote a span; INSUFFICIENT verdicts must state exactly what access would resolve them.

## When NOT to use
Broad discovery (Scout); executable verification (that is a prototype task, not desk research).

## Model suitability
Accuracy-critical, modest volume → mid tier; benchmark T1 governs routing.
