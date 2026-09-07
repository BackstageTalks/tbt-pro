# BackstageTalks Project Development Metrics

Generated: `2026-09-07T09:34:39+00:00`

## Customer-facing summary
- Maintained source/config/docs files: **116**
- Maintained source/config/docs lines: **51,291**
- Estimated maintained code/config lines: **43,331**
- Data/cache files tracked separately: **6,919**
- Data/cache lines tracked separately: **11,984,349**
- All tracked text files together: **7,035 files / 12,035,640 lines**
- Git commits: **2506**
- Latest commit: `3be04ec0 2026-09-07 Update MARQ internal odds snapshots`

## By file type

| Extension | Files | Lines | Code/config lines | Size KB |
|---:|---:|---:|---:|---:|
| `.json` | 6,904 | 11,941,934 | 11,941,933 | 324066.7 |
| `.csv` | 15 | 42,415 | 42,415 | 8556.5 |
| `.py` | 97 | 48,030 | 40,496 | 2119.7 |
| `.yml` | 17 | 3,177 | 2,760 | 116.4 |
| `.css` | 1 | 71 | 62 | 2.2 |
| `.html` | 1 | 13 | 13 | 957.5 |

## By top-level directory

| Directory | Files | Lines | Code/config lines |
|---|---:|---:|---:|
| `blinq` | 1,321 | 10,756,781 | 10,756,472 |
| `data` | 5,584 | 865,117 | 865,117 |
| `thinq` | 42 | 370,335 | 369,466 |
| `corq` | 37 | 26,519 | 22,228 |
| `marq` | 7 | 7,045 | 5,878 |
| `tools` | 10 | 3,481 | 2,978 |
| `.github` | 17 | 3,177 | 2,760 |
| `lucq` | 5 | 1,105 | 942 |
| `cloq` | 3 | 895 | 734 |
| `runtime` | 5 | 604 | 600 |
| `api` | 3 | 568 | 496 |
| `engine.py` | 1 | 13 | 8 |

## Largest maintained source files

| File | Lines | Code/config lines |
|---|---:|---:|
| `corq/web/render.py` | 7,559 | 6,345 |
| `corq/render1.py` | 7,549 | 6,325 |
| `marq/provider.py` | 2,830 | 2,354 |
| `marq/market_lines.py` | 2,440 | 2,092 |
| `corq/engine.py` | 2,011 | 1,730 |
| `corq/corq_rapidapi_client.py` | 1,802 | 1,575 |
| `corq/tg_feed.py` | 1,709 | 1,417 |
| `corq/results_engine/builder.py` | 1,341 | 1,144 |
| `thinq/loaders/h2h_loader.py` | 1,241 | 1,078 |
| `thinq/service.py` | 1,191 | 1,099 |
| `marq/pipeline.py` | 831 | 642 |
| `tools/build_player_registry.py` | 793 | 690 |
| `corq/model.py` | 763 | 633 |
| `marq/odds_snapshots.py` | 623 | 530 |
| `thinq/loaders/sackmann_loader.py` | 617 | 484 |

## Largest data/cache files, separated from code

| File | Lines | Size KB |
|---|---:|---:|
| `thinq/data/ta_profiles/ta_player_profiles.json` | 128,070 | 4047.7 |
| `thinq/data/players/tennis_name_alias_database.json` | 53,676 | 1240.5 |
| `blinq/data/players/player_registry.json` | 50,638 | 1553.9 |
| `thinq/data/players/player_registry.json` | 48,322 | 1496.0 |
| `thinq/data/h2h/h2h_cache.json` | 35,478 | 1121.2 |
| `thinq/data/players/elo_player_universe.json` | 24,186 | 633.7 |
| `data/marq_ai/tennisapi_events_odds_2026_07_30.json` | 23,413 | 651.9 |
| `data/marq_ai/tennisapi_events_odds_2026_08_04.json` | 18,634 | 517.0 |
| `thinq/data/elo/elo_players_index.json` | 16,493 | 463.0 |
| `data/marq_ai/tennisapi_events_odds_2026_07_31.json` | 16,274 | 453.0 |

_Note: Source totals exclude generated site files, outputs, virtualenvs, caches and large data caches._
_Note: Data totals are reported separately so JSON/CSV caches are not presented as hand-written code._
