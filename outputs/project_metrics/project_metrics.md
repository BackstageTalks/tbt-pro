# BackstageTalks Project Development Metrics

Generated: `2026-08-04T05:51:43+00:00`

## Customer-facing summary
- Maintained source/config/docs files: **87**
- Maintained source/config/docs lines: **32,603**
- Estimated maintained code/config lines: **27,444**
- Data/cache files tracked separately: **1,044**
- Data/cache lines tracked separately: **1,088,768**
- All tracked text files together: **1,131 files / 1,121,371 lines**
- Git commits: **1229**
- Latest commit: `96138ce4 2026-08-04 Update MARQ internal odds snapshots`

## By file type

| Extension | Files | Lines | Code/config lines | Size KB |
|---:|---:|---:|---:|---:|
| `.json` | 1,029 | 1,046,353 | 1,046,353 | 30343.3 |
| `.csv` | 15 | 42,415 | 42,415 | 8556.5 |
| `.py` | 75 | 30,725 | 25,870 | 1271.5 |
| `.yml` | 11 | 1,807 | 1,512 | 64.5 |
| `.css` | 1 | 71 | 62 | 2.2 |

## By top-level directory

| Directory | Files | Lines | Code/config lines |
|---|---:|---:|---:|
| `thinq` | 33 | 810,032 | 808,760 |
| `data` | 1,037 | 287,265 | 287,265 |
| `corq` | 34 | 14,875 | 12,546 |
| `marq` | 7 | 6,307 | 5,239 |
| `.github` | 11 | 1,807 | 1,512 |
| `cloq` | 4 | 802 | 653 |
| `tools` | 2 | 259 | 222 |
| `engine.py` | 1 | 16 | 11 |
| `runtime` | 2 | 8 | 4 |

## Largest maintained source files

| File | Lines | Code/config lines |
|---|---:|---:|
| `corq/web/render.py` | 4,062 | 3,447 |
| `corq/render1.py` | 3,829 | 3,268 |
| `marq/provider.py` | 2,352 | 1,935 |
| `marq/market_lines.py` | 2,180 | 1,872 |
| `corq/ranking.py` | 1,331 | 1,101 |
| `thinq/loaders/ta_profile_loader.py` | 1,251 | 1,090 |
| `thinq/loaders/rapidapi_client.py` | 1,115 | 951 |
| `corq/engine.py` | 1,105 | 959 |
| `thinq/service.py` | 957 | 876 |
| `corq/results_engine/builder.py` | 956 | 835 |
| `thinq/loaders/h2h_loader.py` | 937 | 809 |
| `marq/pipeline.py` | 831 | 642 |
| `thinq/features/recent_form.py` | 684 | 592 |
| `marq/odds_snapshots.py` | 623 | 530 |
| `thinq/loaders/sackmann_loader.py` | 617 | 484 |

## Largest data/cache files, separated from code

| File | Lines | Size KB |
|---|---:|---:|
| `thinq/data/players/tennis_name_alias_database.json` | 554,330 | 15488.6 |
| `thinq/data/ta_profiles/ta_player_profiles.json` | 128,902 | 4042.3 |
| `thinq/data/elo/elo_cache.json` | 71,195 | 2068.5 |
| `thinq/data/rankings/ta_rankings.json` | 32,765 | 978.4 |
| `data/marq_ai/tennisapi_events_odds_2026_07_30.json` | 23,413 | 651.9 |
| `data/marq_ai/tennisapi_events_odds_2026_07_31.json` | 16,274 | 453.0 |
| `thinq/data/elo/ta_elo_ratings.json` | 14,213 | 453.6 |
| `data/api_pro/rankings/tennisapi_rankings.json` | 12,040 | 336.9 |
| `data/history/tml/2025_challenger.csv` | 6,412 | 1284.0 |
| `data/history/tml/2024_challenger.csv` | 6,064 | 1205.5 |

_Note: Source totals exclude generated site files, outputs, virtualenvs, caches and large data caches._
_Note: Data totals are reported separately so JSON/CSV caches are not presented as hand-written code._
