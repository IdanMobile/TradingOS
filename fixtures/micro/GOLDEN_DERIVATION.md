# Micro-fixture golden signal derivation (T-005-03)

Hand-computed 2026-07-06 from `bars.csv` (16 five-minute bars starting 2025-01-01T00:00Z).
Closes: `10 10 10 10 10 11 12 13 14 15 14 12 10 6 7 8`. Highs: `max(open,close)+0.5`.
Signals are per-bar booleans (not trades); warm-up bars are `false` by definition.
Cross-checked by an independent recomputation in `tests/test_baseline_specs.py`.

## B1 buy-and-hold
Entry true at bar 1 only; never exits.

## B2 MA crossover (SMA3 vs SMA5, both including current bar)

| bar | SMA3 | SMA5 | fast>slow (entry) | fast<slow (exit) |
|---|---|---|---|---|
| 5 | 10 | 10 | F (equal) | F |
| 6 | 31/3 ≈ 10.3333 | 51/5 = 10.2 | **T** | F |
| 7 | 11 | 53/5 = 10.6 | T | F |
| 8 | 12 | 56/5 = 11.2 | T | F |
| 9 | 13 | 12 | T | F |
| 10 | 14 | 13 | T | F |
| 11 | 43/3 ≈ 14.3333 | 68/5 = 13.6 | T | F |
| 12 | 41/3 ≈ 13.6667 | 68/5 = 13.6 | T | F |
| 13 | 12 | 13 | F | **T** |
| 14 | 28/3 ≈ 9.3333 | 57/5 = 11.4 | F | T |
| 15 | 23/3 ≈ 7.6667 | 49/5 = 9.8 | F | T |
| 16 | 7 | 43/5 = 8.6 | F | T |

Bars 1–4: warm-up (SMA5 undefined) → F/F.

## B3 Bollinger (window 3, k=1, population std)

middle = SMA3; lower = middle − s; s = sqrt(Σ(dev²)/3).

| bar | window closes | middle | s | lower | close<lower (entry) | close≥middle (exit) |
|---|---|---|---|---|---|---|
| 3–5 | 10,10,10 | 10 | 0 | 10 | F | **T** (10≥10) |
| 6 | 10,10,11 | 31/3 | sqrt(6/27)≈0.4714 | ≈9.8619 | F | T |
| 7 | 10,11,12 | 11 | sqrt(2/3)≈0.8165 | ≈10.1835 | F | T |
| 8 | 11,12,13 | 12 | ≈0.8165 | ≈11.1835 | F | T |
| 9 | 12,13,14 | 13 | ≈0.8165 | ≈12.1835 | F | T |
| 10 | 13,14,15 | 14 | ≈0.8165 | ≈13.1835 | F | T |
| 11 | 14,15,14 | 43/3≈14.3333 | ≈0.4714 | ≈13.8619 | F (14>13.86) | F (14<14.33) |
| 12 | 15,14,12 | 41/3≈13.6667 | sqrt(42/27)≈1.2472 | ≈12.4195 | **T** (12<12.42) | F |
| 13 | 14,12,10 | 12 | sqrt(8/3)≈1.6330 | ≈10.3670 | **T** (10<10.367) see note | F |
| 14 | 12,10,6 | 28/3≈9.3333 | sqrt(168/27)≈2.4944 | ≈6.8389 | **T** (6<6.84) | F |
| 15 | 10,6,7 | 23/3≈7.6667 | sqrt(78/27)≈1.6997 | ≈5.9670 | F (7>5.967) | F |
| 16 | 6,7,8 | 7 | ≈0.8165 | ≈6.1835 | F | **T** (8≥7) |

Note bar 13: devs are (2,0,−2) → s = sqrt(8/3) ≈ 1.63299; lower = 12 − 1.63299 = 10.36701;
close 10 **is** < 10.36701 → entry **T**. (First hand pass wrongly marked this F; caught
while writing this derivation. The golden CSV carries the corrected value — this
double-derivation is exactly why the cross-check recomputation test exists.)

Bars 1–2: warm-up → F/F.

## B4 breakout (close > max of previous 5 highs; exit close < SMA3)

Highs: `10.5 ×5, 11.5, 12.5, 13.5, 14.5, 15.5, 15.5, 14.5, 12.5, 10.5, 7.5, 8.5`.

| bar | hh_prev5 | close>hh (entry) | SMA3 | close<SMA3 (exit) |
|---|---|---|---|---|
| 6 | 10.5 | **T** (11) | 31/3 | F |
| 7 | 11.5 | T (12) | 11 | F |
| 8 | 12.5 | T (13) | 12 | F |
| 9 | 13.5 | T (14) | 13 | F |
| 10 | 14.5 | T (15) | 14 | F |
| 11 | 15.5 | F | 43/3 | **T** (14<14.33) |
| 12 | 15.5 | F | 41/3 | T (12<13.67) |
| 13 | 15.5 | F | 12 | T |
| 14 | 15.5 | F | 28/3 | T |
| 15 | 15.5 | F | 23/3 | T (7<7.67) |
| 16 | 15.5 | F | 7 | F (8>7) |

Bars 1–5: entry warm-up → F; bars 1–2: exit warm-up → F (bars 3–5: 10<10 F).
