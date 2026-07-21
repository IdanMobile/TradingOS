# Skill: Skill Registrar (v1)

Role: R7/R9 · Cost tier: cheap/fast · Status: specified, not yet implemented

## Purpose
Ensure every new or edited skill spec under `skills/` is correctly formatted so it appears complete and accurate in the dashboard's Skills tab (`/api/v1/skills`) with no code change, and that `skills/README.md`'s accepted-skills table stays in sync with what's actually on disk.

## Trigger conditions
- A new `SKILL_*.md` file is added under `skills/`.
- An existing skill file's title line, meta line, or section headings are edited.
- A skill is renamed, deprecated, or merged into another skill.

## Inputs
The new/changed skill file; `skills/README.md`; the dashboard parser's format contract in `src/tios/services/dashboard_api/skills.py` (title regex `# Skill: {Name} (v{n})`, meta line `Role: {role} · Cost tier: {tier} · Status: {status}`, and the four rendered section headings: `## Purpose`, `## Trigger conditions`, `## When NOT to use`, `## Model suitability`).

## Tools
Read-only repo access to `skills/*.md` and `dashboard_api/skills.py`; a live GET of `/api/v1/skills` against a locally running `make dashboard` instance to confirm rendering.

## Process
1. Confirm the file is named `SKILL_<NAME>.md` — the dashboard only globs this exact pattern; anything else is invisible to it regardless of content.
2. Confirm the title line matches `# Skill: {Name} (v{n})` exactly. A mismatch makes the parser fall back to the filename as the display name.
3. Confirm the meta line matches `Role: {role} · Cost tier: {tier} · Status: {status}` with the `·` separator. A mismatch renders `—` for role, cost tier, and status in the dashboard instead of the real values.
4. Confirm `## Purpose`, `## Trigger conditions`, `## When NOT to use`, and `## Model suitability` exist verbatim. These are the only sections the dashboard extracts; content under a differently worded heading stays on disk but is silently absent from the tab.
5. Start the local dashboard and hit `/api/v1/skills`; confirm `skill_count` matches the number of `SKILL_*.md` files on disk and the new/changed entry has no `—` placeholders and no empty extracted section.
6. Add or update the skill's row in the accepted-skills table in `skills/README.md` (file, role, first-needed stage, purpose) so the planning doc and the dashboard agree.

## Outputs (contract)
The new/edited skill renders in the dashboard's Skills tab with every field populated (no `—`, no missing section), and `skills/README.md`'s accepted-skills table has a matching row.

## Prohibited behavior
- Special-casing `dashboard_api/skills.py`'s parsing regex to accommodate a malformed file instead of fixing the file — the format is the contract, not the parser.
- Adding a row to `skills/README.md` with no corresponding dashboard-visible file, or leaving a dashboard-visible file out of `skills/README.md`.
- Silently renaming or deleting a skill file without updating `skills/README.md` to match.

## Quality gates
`/api/v1/skills`'s `skill_count` equals the number of `SKILL_*.md` files on disk; every entry in the API response has non-`—` role/cost_tier/status and a non-empty purpose; the `skills/README.md` accepted-skills table row count matches the file count.

## When NOT to use
Editing a skill's substantive content (Process, Outputs, Prohibited behavior) without touching its title line, meta line, or section headings — that's normal skill authorship and doesn't risk dashboard drift.

## Model suitability
Cheap/fast tier; a mechanical format-compliance check, not judgment-heavy.
