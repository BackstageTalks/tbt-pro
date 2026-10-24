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

## 2024+ quarterly pre-match ablation (experimental, not production)

Use the same stored ATP source files, with no provider calls:

```bash
python -m blinq.research.quarterly --tour ATP \
  --input data/history/tml/2024.csv \
  --input data/history/tml/2025.csv \
  --input data/history/tml/2026.csv \
  --output /tmp/721-quarterly.json
```

This fits independent logistic baselines and predeclared surface Elo, shrunk surface form, shrunk serve/return and opponent-adjusted serve candidate families. Each test calendar quarter (2025 Q1–2026 Q3) follows an expanding 2024+ training period and a disjoint 60-day Platt calibration period. An entire tournament-start batch is embargoed for 21 days before it can update the feature history. The 21-day embargo is a conservative approximation and must be replaced by exact timestamps for official 721 evidence.

The report compares candidate families on *identical complete-case matches* by quarter, with accuracy, log-loss, Brier, confidence >=80% accuracy AND coverage and metrics on the baseline's selected >=80% fixtures. Reporting several arms on this development set is exploratory; selection on these test folds requires a **separate unseen holdout**. The source is ATP-only here, and all observations in this satellite test are much narrower than the real CDB: it cannot prove an improvement against the real production champion or model 721.

Features that are genuinely unavailable stay missing. Surface Elo falls back to the player's established overall Elo when there are no prior surface results; surface form/serve/return is partially pooled toward that player's own *pre-match* overall observation history with a fixed eight-observation prior. The additional surface Elo deviation is shrunk by n/(n+12). These are research hyperparameters, not published optimal settings.

Production model and CDB remain unchanged. New candidates must still be integrated and tested through `BackstageTalks/tbt` guarded frozen-CDB workflow, with 2024+ supervised fitting and independently checked ATP/WTA segment results.

### Additional point-count sensitivity ablation (exploratory)

Two extra fixed candidates compare weighted averages of recent service/return points with a
**500 prior-point** shrinkage toward research-only reference rates (.62 serve and .38 return).
`POINT_POSTERIOR` uses the player's own verified previous denominators, never averages
a ten-point match as equally reliable as a 100-point match.
`OPP_POINT_POSTERIOR` additionally uses each opponent's serve/return profile recorded
**before the previous match**, weighted by that match's observed point denominator.

These are cautious simplified features **inspired by** Gollub (2021), not a reproduction
of Gollub's Efron-Morris estimator or his hierarchical Markov predictor. Current
research reference rates, pseudo-count and last-20 window are fixed diagnostic
choices, not learned optimal coefficients. No claim of real-721 improvement
may be made from a satellite ATP experiment.
