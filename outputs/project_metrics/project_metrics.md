# BackstageTalks Project Development Metrics

Generated: `2026-08-24T05:11:21+00:00`

## Customer-facing summary
- Maintained source/config/docs files: **109**
- Maintained source/config/docs lines: **49,436**
- Estimated maintained code/config lines: **41,715**
- Data/cache files tracked separately: **3,493**
- Data/cache lines tracked separately: **918,497**
- All tracked text files together: **3,602 files / 967,933 lines**
- Git commits: **1972**
- Latest commit: `3dd768e5 2026-08-24 Update MARQ internal odds snapshots`

## By file type

| Extension | Files | Lines | Code/config lines | Size KB |
|---:|---:|---:|---:|---:|
| `.json` | 3,478 | 876,082 | 876,081 | 27041.1 |
| `.csv` | 15 | 42,415 | 42,415 | 8556.5 |
| `.py` | 91 | 46,409 | 39,085 | 1977.3 |
| `.yml` | 17 | 2,956 | 2,568 | 105.9 |
| `.css` | 1 | 71 | 62 | 2.2 |

## By top-level directory

| Directory | Files | Lines | Code/config lines |
|---|---:|---:|---:|
| `data` | 3,470 | 638,419 | 638,419 |
| `thinq` | 41 | 285,517 | 284,658 |
| `corq` | 37 | 26,509 | 22,208 |
| `marq` | 7 | 7,045 | 5,878 |
| `.github` | 19 | 5,157 | 4,485 |
| `tools` | 7 | 2,413 | 2,061 |
| `lucq` | 5 | 1,105 | 942 |
| `cloq` | 3 | 895 | 734 |
| `runtime` | 5 | 598 | 594 |
| `blinq` | 7 | 262 | 224 |
| `engine.py` | 1 | 13 | 8 |

## Largest maintained source files

| File | Lines | Code/config lines |
|---|---:|---:|
| `corq/render.py` | 7,549 | 6,325 |
| `corq/web/render.py` | 7,549 | 6,325 |
| `marq/provider.py` | 2,830 | 2,354 |
| `marq/market_lines.py` | 2,440 | 2,092 |
| `corq/engine.py` | 2,011 | 1,730 |
| `corq/corq_rapidapi_client.py` | 1,802 | 1,575 |
| `.github/workflows/corq_rapidapi_client.py` | 1,798 | 1,571 |
| `corq/tg_feed.py` | 1,709 | 1,417 |
| `corq/results_engine/builder.py` | 1,341 | 1,144 |
| `thinq/loaders/h2h_loader.py` | 1,241 | 1,078 |
| `thinq/service.py` | 1,031 | 949 |
| `marq/pipeline.py` | 831 | 642 |
| `corq/model.py` | 763 | 633 |
| `marq/odds_snapshots.py` | 623 | 530 |
| `thinq/loaders/sackmann_loader.py` | 617 | 484 |

## Largest data/cache files, separated from code

| File | Lines | Size KB |
|---|---:|---:|
| `thinq/data/ta_profiles/ta_player_profiles.json` | 128,070 | 4047.7 |
| `thinq/data/players/player_registry.json` | 46,370 | 1408.9 |
| `thinq/data/players/elo_player_universe.json` | 24,186 | 640.5 |
| `data/marq_ai/tennisapi_events_odds_2026_07_30.json` | 23,413 | 651.9 |
| `thinq/data/players/tennis_name_alias_database.json` | 19,885 | 495.6 |
| `data/marq_ai/tennisapi_events_odds_2026_08_04.json` | 18,634 | 517.0 |
| `thinq/data/elo/elo_players_index.json` | 16,493 | 463.0 |
| `data/marq_ai/tennisapi_events_odds_2026_07_31.json` | 16,274 | 453.0 |
| `thinq/data/elo/elo_cache.json` | 14,304 | 456.1 |
| `thinq/data/elo/ta_elo_ratings.json` | 14,304 | 456.1 |

_Note: Source totals exclude generated site files, outputs, virtualenvs, caches and large data caches._
_Note: Data totals are reported separately so JSON/CSV caches are not presented as hand-written code._
