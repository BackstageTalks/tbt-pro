# BackstageTalks Project Development Metrics

Generated: `2026-08-03T07:59:05+00:00`

## Customer-facing summary
- Maintained source/config/docs files: **87**
- Maintained source/config/docs lines: **32,337**
- Estimated maintained code/config lines: **27,217**
- Data/cache files tracked separately: **893**
- Data/cache lines tracked separately: **1,070,206**
- All tracked text files together: **980 files / 1,102,543 lines**
- Git commits: **1211**
- Latest commit: `2e0ca1c3 2026-08-03 Render web site only`

## By file type

| Extension | Files | Lines | Code/config lines | Size KB |
|---:|---:|---:|---:|---:|
| `.json` | 878 | 1,027,791 | 1,027,791 | 29752.1 |
| `.csv` | 15 | 42,415 | 42,415 | 8556.5 |
| `.py` | 75 | 30,465 | 25,648 | 1258.7 |
| `.yml` | 11 | 1,801 | 1,507 | 64.0 |
| `.css` | 1 | 71 | 62 | 2.2 |

## By top-level directory

| Directory | Files | Lines | Code/config lines |
|---|---:|---:|---:|
| `thinq` | 33 | 809,057 | 807,786 |
| `data` | 886 | 269,677 | 269,677 |
| `corq` | 34 | 14,850 | 12,522 |
| `marq` | 7 | 6,073 | 5,041 |
| `.github` | 11 | 1,801 | 1,507 |
| `cloq` | 4 | 802 | 653 |
| `tools` | 2 | 259 | 222 |
| `engine.py` | 1 | 16 | 11 |
| `runtime` | 2 | 8 | 4 |

## Largest maintained source files

| File | Lines | Code/config lines |
|---|---:|---:|
| `corq/web/render.py` | 4,062 | 3,447 |
| `corq/render1.py` | 3,829 | 3,268 |
| `marq/market_lines.py` | 2,179 | 1,872 |
| `marq/provider.py` | 2,119 | 1,737 |
| `corq/ranking.py` | 1,331 | 1,101 |
| `thinq/loaders/ta_profile_loader.py` | 1,251 | 1,090 |
| `thinq/loaders/rapidapi_client.py` | 1,114 | 951 |
| `corq/engine.py` | 1,105 | 959 |
| `thinq/service.py` | 957 | 876 |
| `thinq/loaders/h2h_loader.py` | 937 | 809 |
| `corq/results_engine/builder.py` | 867 | 761 |
| `marq/pipeline.py` | 831 | 642 |
| `thinq/features/recent_form.py` | 684 | 592 |
| `marq/odds_snapshots.py` | 623 | 530 |
| `thinq/loaders/sackmann_loader.py` | 617 | 484 |

## Largest data/cache files, separated from code

| File | Lines | Size KB |
|---|---:|---:|
| `thinq/data/players/tennis_name_alias_database.json` | 554,330 | 15488.6 |
| `thinq/data/ta_profiles/ta_player_profiles.json` | 127,928 | 4047.6 |
| `thinq/data/elo/elo_cache.json` | 71,195 | 2068.5 |
| `thinq/data/rankings/ta_rankings.json` | 32,765 | 978.4 |
| `data/marq_ai/tennisapi_events_odds_2026_07_30.json` | 23,413 | 651.9 |
| `data/marq_ai/tennisapi_events_odds_2026_07_31.json` | 16,274 | 453.0 |
| `thinq/data/elo/ta_elo_ratings.json` | 14,213 | 453.6 |
| `data/api_pro/rankings/tennisapi_rankings.json` | 12,040 | 337.0 |
| `data/history/tml/2025_challenger.csv` | 6,412 | 1284.0 |
| `data/history/tml/2024_challenger.csv` | 6,064 | 1205.5 |

_Note: Source totals exclude generated site files, outputs, virtualenvs, caches and large data caches._
_Note: Data totals are reported separately so JSON/CSV caches are not presented as hand-written code._
