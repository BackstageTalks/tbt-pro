# BackstageTalks Project Development Metrics

Generated: `2026-08-01T08:13:57+00:00`

## Customer-facing summary
- Maintained source/config/docs files: **84**
- Maintained source/config/docs lines: **24,641**
- Estimated maintained code/config lines: **20,707**
- Data/cache files tracked separately: **599**
- Data/cache lines tracked separately: **1,023,964**
- All tracked text files together: **683 files / 1,048,605 lines**
- Git commits: **1058**
- Latest commit: `f2d2070 2026-08-01 Render web site only`

## By file type

| Extension | Files | Lines | Code/config lines | Size KB |
|---:|---:|---:|---:|---:|
| `.json` | 584 | 981,549 | 981,549 | 28255.0 |
| `.csv` | 15 | 42,415 | 42,415 | 8556.5 |
| `.py` | 73 | 23,066 | 19,395 | 905.0 |
| `.yml` | 10 | 1,504 | 1,250 | 51.4 |
| `.css` | 1 | 71 | 62 | 2.2 |

## By top-level directory

| Directory | Files | Lines | Code/config lines |
|---|---:|---:|---:|
| `thinq` | 33 | 808,296 | 807,127 |
| `data` | 592 | 223,435 | 223,435 |
| `corq` | 33 | 9,546 | 8,008 |
| `marq` | 7 | 5,165 | 4,302 |
| `.github` | 10 | 1,504 | 1,250 |
| `cloq` | 3 | 376 | 312 |
| `tools` | 2 | 259 | 222 |
| `engine.py` | 1 | 16 | 11 |
| `runtime` | 2 | 8 | 4 |

## Largest maintained source files

| File | Lines | Code/config lines |
|---|---:|---:|
| `corq/web/render.py` | 3,110 | 2,658 |
| `marq/market_lines.py` | 2,028 | 1,759 |
| `marq/provider.py` | 1,283 | 1,059 |
| `thinq/loaders/ta_profile_loader.py` | 1,251 | 1,090 |
| `corq/ranking.py` | 1,075 | 888 |
| `thinq/service.py` | 957 | 876 |
| `thinq/loaders/rapidapi_client.py` | 861 | 730 |
| `marq/pipeline.py` | 831 | 642 |
| `corq/engine.py` | 828 | 713 |
| `thinq/features/recent_form.py` | 648 | 561 |
| `marq/odds_snapshots.py` | 623 | 530 |
| `thinq/loaders/sackmann_loader.py` | 617 | 484 |
| `thinq/loaders/h2h_loader.py` | 511 | 440 |
| `corq/results_engine/builder.py` | 502 | 437 |
| `corq/results_engine/results.py` | 469 | 403 |

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
| `data/history/tml/2025_challenger.csv` | 6,412 | 1284.0 |
| `data/history/tml/2024_challenger.csv` | 6,064 | 1205.5 |
| `data/marq_ai/tennisapi_events_odds_2026_08_01.json` | 4,906 | 135.9 |

_Note: Source totals exclude generated site files, outputs, virtualenvs, caches and large data caches._
_Note: Data totals are reported separately so JSON/CSV caches are not presented as hand-written code._
