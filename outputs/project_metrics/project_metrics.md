# BackstageTalks Project Development Metrics

Generated: `2026-08-17T05:08:36+00:00`

## Customer-facing summary
- Maintained source/config/docs files: **91**
- Maintained source/config/docs lines: **39,753**
- Estimated maintained code/config lines: **33,297**
- Data/cache files tracked separately: **2,652**
- Data/cache lines tracked separately: **1,349,628**
- All tracked text files together: **2,743 files / 1,389,381 lines**
- Git commits: **1589**
- Latest commit: `6b64bd80 2026-08-17 Update MARQ internal odds snapshots`

## By file type

| Extension | Files | Lines | Code/config lines | Size KB |
|---:|---:|---:|---:|---:|
| `.json` | 2,637 | 1,307,213 | 1,307,213 | 38561.5 |
| `.csv` | 15 | 42,415 | 42,415 | 8556.5 |
| `.py` | 77 | 37,319 | 31,215 | 1520.2 |
| `.yml` | 13 | 2,363 | 2,020 | 87.3 |
| `.css` | 1 | 71 | 62 | 2.2 |

## By top-level directory

| Directory | Files | Lines | Code/config lines |
|---|---:|---:|---:|
| `thinq` | 33 | 808,089 | 806,981 |
| `data` | 2,645 | 548,957 | 548,957 |
| `corq` | 36 | 21,655 | 18,045 |
| `marq` | 7 | 6,785 | 5,658 |
| `.github` | 13 | 2,363 | 2,020 |
| `cloq` | 3 | 895 | 734 |
| `tools` | 3 | 613 | 515 |
| `engine.py` | 1 | 16 | 11 |
| `runtime` | 2 | 8 | 4 |

## Largest maintained source files

| File | Lines | Code/config lines |
|---|---:|---:|
| `corq/web/render.py` | 6,922 | 5,818 |
| `corq/ranking.py` | 4,502 | 3,636 |
| `marq/provider.py` | 2,830 | 2,354 |
| `marq/market_lines.py` | 2,180 | 1,872 |
| `corq/engine.py` | 1,726 | 1,485 |
| `corq/corq_rapidapi_client.py` | 1,725 | 1,503 |
| `corq/tg_feed.py` | 1,565 | 1,307 |
| `corq/results_engine/builder.py` | 1,261 | 1,086 |
| `thinq/loaders/ta_profile_loader.py` | 1,251 | 1,090 |
| `thinq/service.py` | 957 | 876 |
| `thinq/loaders/h2h_loader.py` | 937 | 809 |
| `marq/pipeline.py` | 831 | 642 |
| `corq/model.py` | 701 | 581 |
| `thinq/features/recent_form.py` | 684 | 592 |
| `marq/odds_snapshots.py` | 623 | 530 |

## Largest data/cache files, separated from code

| File | Lines | Size KB |
|---|---:|---:|
| `thinq/data/players/tennis_name_alias_database.json` | 554,330 | 15488.6 |
| `thinq/data/ta_profiles/ta_player_profiles.json` | 128,070 | 4047.7 |
| `thinq/data/elo/elo_cache.json` | 71,195 | 2068.5 |
| `thinq/data/rankings/ta_rankings.json` | 32,765 | 978.4 |
| `data/marq_ai/tennisapi_events_odds_2026_07_30.json` | 23,413 | 651.9 |
| `data/marq_ai/tennisapi_events_odds_2026_08_04.json` | 18,634 | 517.0 |
| `data/marq_ai/tennisapi_events_odds_2026_07_31.json` | 16,274 | 453.0 |
| `thinq/data/elo/ta_elo_ratings.json` | 14,213 | 453.6 |
| `data/api_pro/rankings/tennisapi_rankings.json` | 12,040 | 336.9 |
| `data/marq_ai/tennisapi_events_odds_2026_08_05.json` | 8,878 | 244.8 |

_Note: Source totals exclude generated site files, outputs, virtualenvs, caches and large data caches._
_Note: Data totals are reported separately so JSON/CSV caches are not presented as hand-written code._
