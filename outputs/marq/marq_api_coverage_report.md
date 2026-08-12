# MarQ API Coverage Report

Generated UTC: 2026-08-12T04:53:42.281798+00:00
Model: 2026-08-04-marq-coverage-report-v1

## all_audit

Rows: 62

### Coverage

- High MarQ: 3.23%
- Medium current-only: 51.61%
- Thin fallback: 0.0%
- No/unknown MarQ: 45.16%
- Usable High+Medium: 54.84%

### Endpoints

- getAllOddsForEvent: 34 (54.84%)
- NO_ENDPOINT: 28 (45.16%)

### Quality tiers

- MEDIUM_CURRENT_ONLY: 32 (51.61%)
- NO_MARQ: 28 (45.16%)
- HIGH: 2 (3.23%)

### Data status

- EXACT_CURRENT_ODDS_ONLY: 32 (51.61%)
- NO_DATA_STATUS: 28 (45.16%)
- EXACT_BETTING_ODDS_WITH_OPENING: 2 (3.23%)

### Movement status

- OPENING_EQUALS_CURRENT: 32 (51.61%)
- NO_MOVEMENT_STATUS: 28 (45.16%)
- REAL_OPENING_CURRENT_AVAILABLE: 2 (3.23%)

### Value status

- VALUE_UNKNOWN: 28 (45.16%)
- NO_VALUE: 19 (30.65%)
- VALUE_STRONG: 13 (20.97%)
- VALUE_PLAYABLE: 2 (3.23%)

### Numeric stats

- CorQ market weight: `{'count': 62, 'avg': 0.0703, 'min': 0.0, 'max': 0.3}`
- Value delta pp: `{'count': 34, 'avg': 0.0, 'min': -17.49, 'max': 17.49}`
- Expected value pct: `{'count': 34, 'avg': -3.6594, 'min': -36.43, 'max': 42.2}`

## corq_top7

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

- VALUE_STRONG: 7 (100.0%)

### Numeric stats

- CorQ market weight: `{'count': 7, 'avg': 0.1457, 'min': 0.12, 'max': 0.3}`
- Value delta pp: `{'count': 7, 'avg': 12.6143, 'min': 9.31, 'max': 15.58}`
- Expected value pct: `{'count': 7, 'avg': 21.0843, 'min': 8.18, 'max': 42.2}`

## cloq

Rows: 5

### Coverage

- High MarQ: 0.0%
- Medium current-only: 100.0%
- Thin fallback: 0.0%
- No/unknown MarQ: 0.0%
- Usable High+Medium: 100.0%

### Endpoints

- getAllOddsForEvent: 5 (100.0%)

### Quality tiers

- MEDIUM_CURRENT_ONLY: 5 (100.0%)

### Data status

- EXACT_CURRENT_ODDS_ONLY: 5 (100.0%)

### Movement status

- OPENING_EQUALS_CURRENT: 5 (100.0%)

### Value status

- VALUE_STRONG: 3 (60.0%)
- VALUE_PLAYABLE: 1 (20.0%)
- NO_VALUE: 1 (20.0%)

### Numeric stats

- CorQ market weight: `{'count': 5, 'avg': 0.12, 'min': 0.12, 'max': 0.12}`
- Value delta pp: `{'count': 5, 'avg': 7.96, 'min': 0.19, 'max': 13.05}`
- Expected value pct: `{'count': 5, 'avg': 9.254, 'min': -7.01, 'max': 19.26}`

## Notes

- HIGH should represent exact TennisApi odds with real opening/current movement data.
- MEDIUM_CURRENT_ONLY is usable but should not carry full 30% MarQ influence.
- THIN_FALLBACK should remain close to zero influence and should be investigated if it grows.
- NO_MARQ/NO_TIER rows indicate missing audit fields or missing market data.
