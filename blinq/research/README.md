# BlinQ / 721: paper-informed offline research

This is a **shadow evaluation**, not a replacement for `blinq/service.py`, `thinq/features/probability_layer.py`, or the central database. Running it never writes to CDB, never calls RapidAPI and never changes public predictions.

## Directly applicable research
- Kovalchik (2016), *Searching for the GOAT of tennis win prediction*: Elo, serve/return models, calibration, quality benchmarks. https://doi.org/10.1515/jqas-2015-0059
- Buhamra & Groll (2025), *Statistical enhanced learning for modeling and prediction tennis matches at Grand Slam tournaments*: Elo, age interval, ranking and rolling/expanding external validation. https://arxiv.org/abs/2502.01613
- Zhang (2025), *Data-Driven Prediction of Tennis Ranking Movements with Ensemble Machine Learning Models*: candidate serve, return and break point statistics; **ranking movement is not match-winning probability**. https://nhsjs.com/wp-content/uploads/2025/11/Data-Driven-Prediction-of-Tennis-Ranking-Movements-with-Ensemble-Machine-Learning-Models.pdf

## Live-only studies; NOT included in pre-match inputs
- Tong et al. (2025), IEEE 11138986, live match-point/dynamic prediction, XGBoost/logistic techniques. https://ieeexplore.ieee.org/abstract/document/11138986
- Lei, Lin & Cao (2024), *Rhythms of Victory*, point-level momentum. https://ieeexplore.ieee.org/document/10637388
- Walters (2025), *Real-Time Prediction of Tennis Point Outcomes*, Claremont campus-only thesis abstract, point-level score and momentum. https://scholarship.claremont.edu/scripps_theses/2816/

Point-level accuracy from those papers cannot be compared with pre-match winner accuracy. They are reserved for a separate live model with genuine pre-point timestamps.

## How to run

```bash
python -m unittest discover -s blinq/research/tests -t .
python -m blinq.research --tour ATP \
  --input data/history/tml/2024.csv \
  --input data/history/tml/2025.csv \
  --input data/history/tml/2026.csv \
  --out-dir /tmp/blinq-721
```

Outputs: `research_report.json` (per-year raw/Platt performance and coverage) and `rejected.json` (quarantined input rows). Input files must be independently checked for provenance and tour. CDB remains authoritative.

## Guardrails and limitations

1. Identity: tour and player ID are mandatory. Name-only fuzzy joining is forbidden. If the source omits `match_num` but has a nonempty round, the research-only match identity is reconstructed from tournament, round and the sorted pair of verified player IDs; any collision is quarantined. This module assumes input IDs are already verified. It does not promote identity matches into CDB.
2. Time: Sackmann `tourney_date` is **tournament start, not exact match date**. All results from that start-date batch are held out for **21 days**, with strict '<' maturity before reuse. This is deliberately conservative; a 21-day delay is not a formal guarantee for exceptionally long events. Exact provider-native match timestamps are required for a stronger guarantee.
3. Data: retirements/walkovers and duplicate match IDs are excluded, invalid service denominators do not become zero; all missing features remain null. Break point metrics exclude zero opportunities, not treat them as failures. Observations from an earlier event are released only after the embargo.
4. Opponent adjustment: historical server point win rate is adjusted by the *opponent's prior* return rate (an experimental 0.38 reference), not a value calculated after that old match. The hyperparameter must be tuned in training folds; it is not a fixed factual tour average.
5. Modeling: expanding-window training is older than holdout calibration, which is older than test year. Platt is fitted **only on the prior calendar year**. Results are reported per candidate with coverage; unequal complete-case test populations cannot be compared as if identical. Separate common-cohort tests are required for promotion.
6. No pre-match momentum from the current match. No market odds as model inputs without timestamps that precede the predicted match. No production activation flag. The project's existing symmetry and NO_PREDICTION contracts remain authoritative.
7. The Elo series here is an independently reconstructed research baseline (K=24), **not** a claim of matching historical Tennis Abstract Elo or the existing ThinQ layer. Existing model's M0 results require authentic archived pre-match snapshots; they are not imputed.
8. This runner materializes CSV rows in memory and is meant for curated bounded exports, not the 8GB recursive import path. CDB updates must go through the existing provider-native writer and full audit/dry-run/read-back process.

## Promotion criteria

Before touching the production probability layer: validate 2016–2026 with ATP and WTA separately, broad levels and surfaces; compare **on identical games** versus archived M0 probabilities, with Brier/log-loss, calibration, coverage, B/A inversion, time leakage audit and reproducible source hashes. No deploy or claim of accuracy lift based only on a synthetic smoke test or green CI.
