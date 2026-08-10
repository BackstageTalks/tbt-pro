# BackstageTalks Project Development Metrics

Generated: `2026-08-10T05:54:58+00:00`

## Customer-facing summary
- Maintained source/config/docs files: **90**
- Maintained source/config/docs lines: **41,042**
- Estimated maintained code/config lines: **34,456**
- Data/cache files tracked separately: **1,828**
- Data/cache lines tracked separately: **1,251,048**
- All tracked text files together: **1,918 files / 1,292,090 lines**
- Git commits: **1439**
- Latest commit: `db08188a 2026-08-10 Manual results settlement`

## By file type

| Extension | Files | Lines | Code/config lines | Size KB |
|---:|---:|---:|---:|---:|
| `.json` | 1,813 | 1,208,633 | 1,208,633 | 35224.3 |
| `.csv` | 15 | 42,415 | 42,415 | 8556.5 |
| `.py` | 76 | 38,750 | 32,508 | 1605.2 |
| `.yml` | 13 | 2,221 | 1,886 | 80.5 |
| `.css` | 1 | 71 | 62 | 2.2 |

## By top-level directory

| Directory | Files | Lines | Code/config lines |
|---|---:|---:|---:|
| `thinq` | 33 | 808,957 | 807,682 |
| `data` | 1,821 | 450,656 | 450,656 |
| `corq` | 35 | 22,098 | 18,500 |
| `marq` | 7 | 6,785 | 5,658 |
| `.github` | 13 | 2,221 | 1,886 |
| `cloq` | 3 | 736 | 592 |
| `tools` | 3 | 613 | 515 |
| `engine.py` | 1 | 16 | 11 |
| `runtime` | 2 | 8 | 4 |

## Largest maintained source files

| File | Lines | Code/config lines |
|---|---:|---:|
| `corq/web/render.py` | 5,805 | 4,862 |
| `corq/render1.py` | 4,292 | 3,637 |
| `corq/ranking.py` | 3,305 | 2,692 |
| `marq/provider.py` | 2,830 | 2,354 |
| `marq/market_lines.py` | 2,180 | 1,872 |
| `corq/engine.py` | 1,537 | 1,331 |
| `corq/rapidapi_client.py` | 1,464 | 1,269 |
| `thinq/loaders/ta_profile_loader.py` | 1,251 | 1,090 |
| `thinq/loaders/rapidapi_client.py` | 1,151 | 984 |
| `corq/results_engine/builder.py` | 1,147 | 991 |
| `thinq/service.py` | 957 | 876 |
| `thinq/loaders/h2h_loader.py` | 937 | 809 |
| `marq/pipeline.py` | 831 | 642 |
| `corq/model.py` | 701 | 581 |
| `thinq/features/recent_form.py` | 684 | 592 |

## Largest data/cache files, separated from code

| File | Lines | Size KB |
|---|---:|---:|
| `thinq/data/players/tennis_name_alias_database.json` | 554,330 | 15488.6 |
| `thinq/data/ta_profiles/ta_player_profiles.json` | 127,791 | 4046.6 |
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
