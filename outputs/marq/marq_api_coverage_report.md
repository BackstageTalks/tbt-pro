# MarQ API Coverage Report

Generated UTC: 2026-08-24T05:49:01.186248+00:00
Model: 2026-08-04-marq-coverage-report-v1

## all_audit

Rows: 192

### Coverage

- High MarQ: 9.38%
- Medium current-only: 19.79%
- Thin fallback: 0.0%
- No/unknown MarQ: 70.83%
- Usable High+Medium: 29.17%

### Endpoints

- NO_ENDPOINT: 134 (69.79%)
- getAllOddsForEvent: 58 (30.21%)

### Quality tiers

- NO_MARQ: 136 (70.83%)
- MEDIUM_CURRENT_ONLY: 38 (19.79%)
- HIGH: 18 (9.38%)

### Data status

- NO_DATA_STATUS: 134 (69.79%)
- EXACT_CURRENT_ODDS_ONLY: 38 (19.79%)
- EXACT_BETTING_ODDS_WITH_OPENING: 20 (10.42%)

### Movement status

- NO_MOVEMENT_STATUS: 134 (69.79%)
- OPENING_EQUALS_CURRENT: 38 (19.79%)
- REAL_OPENING_CURRENT_AVAILABLE: 20 (10.42%)

### Value status

- VALUE_UNKNOWN: 136 (70.83%)
- NO_VALUE: 28 (14.58%)
- VALUE_STRONG: 24 (12.5%)
- VALUE_PLAYABLE: 4 (2.08%)

### Numeric stats

- CorQ market weight: `{'count': 192, 'avg': 0.0477, 'min': 0.0, 'max': 0.3}`
- Value delta pp: `{'count': 56, 'avg': 0.0202, 'min': -26.3, 'max': 26.3}`
- Expected value pct: `{'count': 56, 'avg': 2.4404, 'min': -34.68, 'max': 177.9}`

## corq_top7

Rows: 7

### Coverage

- High MarQ: 42.86%
- Medium current-only: 57.14%
- Thin fallback: 0.0%
- No/unknown MarQ: 0.0%
- Usable High+Medium: 100.0%

### Endpoints

- getAllOddsForEvent: 7 (100.0%)

### Quality tiers

- MEDIUM_CURRENT_ONLY: 4 (57.14%)
- HIGH: 3 (42.86%)

### Data status

- EXACT_CURRENT_ODDS_ONLY: 4 (57.14%)
- EXACT_BETTING_ODDS_WITH_OPENING: 3 (42.86%)

### Movement status

- OPENING_EQUALS_CURRENT: 4 (57.14%)
- REAL_OPENING_CURRENT_AVAILABLE: 3 (42.86%)

### Value status

- NO_VALUE: 6 (85.71%)
- VALUE_STRONG: 1 (14.29%)

### Numeric stats

- CorQ market weight: `{'count': 7, 'avg': 0.1743, 'min': 0.12, 'max': 0.3}`
- Value delta pp: `{'count': 7, 'avg': -4.5043, 'min': -11.89, 'max': 3.74}`
- Expected value pct: `{'count': 7, 'avg': -11.5714, 'min': -21.19, 'max': 2.22}`

## cloq

Rows: 7

### Coverage

- High MarQ: 14.29%
- Medium current-only: 85.71%
- Thin fallback: 0.0%
- No/unknown MarQ: 0.0%
- Usable High+Medium: 100.0%

### Endpoints

- getAllOddsForEvent: 7 (100.0%)

### Quality tiers

- MEDIUM_CURRENT_ONLY: 6 (85.71%)
- HIGH: 1 (14.29%)

### Data status

- EXACT_CURRENT_ODDS_ONLY: 6 (85.71%)
- EXACT_BETTING_ODDS_WITH_OPENING: 1 (14.29%)

### Movement status

- OPENING_EQUALS_CURRENT: 6 (85.71%)
- REAL_OPENING_CURRENT_AVAILABLE: 1 (14.29%)

### Value status

- VALUE_STRONG: 5 (71.43%)
- VALUE_PLAYABLE: 2 (28.57%)

### Numeric stats

- CorQ market weight: `{'count': 7, 'avg': 0.1457, 'min': 0.12, 'max': 0.3}`
- Value delta pp: `{'count': 7, 'avg': 4.5886, 'min': 0.57, 'max': 11.71}`
- Expected value pct: `{'count': 7, 'avg': 2.7129, 'min': -4.24, 'max': 18.91}`

## Notes

- HIGH should represent exact TennisApi odds with real opening/current movement data.
- MEDIUM_CURRENT_ONLY is usable but should not carry full 30% MarQ influence.
- THIN_FALLBACK should remain close to zero influence and should be investigated if it grows.
- NO_MARQ/NO_TIER rows indicate missing audit fields or missing market data.
