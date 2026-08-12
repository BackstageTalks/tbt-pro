# MarQ API Coverage Report

Generated UTC: 2026-08-12T05:56:04.536943+00:00
Model: 2026-08-04-marq-coverage-report-v1

## all_audit

Rows: 62

### Coverage

- High MarQ: 9.68%
- Medium current-only: 45.16%
- Thin fallback: 0.0%
- No/unknown MarQ: 45.16%
- Usable High+Medium: 54.84%

### Endpoints

- getAllOddsForEvent: 34 (54.84%)
- NO_ENDPOINT: 28 (45.16%)

### Quality tiers

- MEDIUM_CURRENT_ONLY: 28 (45.16%)
- NO_MARQ: 28 (45.16%)
- HIGH: 6 (9.68%)

### Data status

- EXACT_CURRENT_ODDS_ONLY: 28 (45.16%)
- NO_DATA_STATUS: 28 (45.16%)
- EXACT_BETTING_ODDS_WITH_OPENING: 6 (9.68%)

### Movement status

- OPENING_EQUALS_CURRENT: 28 (45.16%)
- NO_MOVEMENT_STATUS: 28 (45.16%)
- REAL_OPENING_CURRENT_AVAILABLE: 6 (9.68%)

### Value status

- VALUE_UNKNOWN: 28 (45.16%)
- NO_VALUE: 19 (30.65%)
- VALUE_STRONG: 14 (22.58%)
- VALUE_PLAYABLE: 1 (1.61%)

### Numeric stats

- CorQ market weight: `{'count': 62, 'avg': 0.0794, 'min': 0.0, 'max': 0.3}`
- Value delta pp: `{'count': 34, 'avg': 0.0, 'min': -17.49, 'max': 17.49}`
- Expected value pct: `{'count': 34, 'avg': -3.825, 'min': -36.43, 'max': 42.2}`

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

- VALUE_STRONG: 6 (85.71%)
- VALUE_PLAYABLE: 1 (14.29%)

### Numeric stats

- CorQ market weight: `{'count': 7, 'avg': 0.1457, 'min': 0.12, 'max': 0.3}`
- Value delta pp: `{'count': 7, 'avg': 9.7714, 'min': 0.6, 'max': 13.98}`
- Expected value pct: `{'count': 7, 'avg': 11.6343, 'min': -6.38, 'max': 19.26}`

## cloq

Rows: 5

### Coverage

- High MarQ: 20.0%
- Medium current-only: 80.0%
- Thin fallback: 0.0%
- No/unknown MarQ: 0.0%
- Usable High+Medium: 100.0%

### Endpoints

- getAllOddsForEvent: 5 (100.0%)

### Quality tiers

- MEDIUM_CURRENT_ONLY: 4 (80.0%)
- HIGH: 1 (20.0%)

### Data status

- EXACT_CURRENT_ODDS_ONLY: 4 (80.0%)
- EXACT_BETTING_ODDS_WITH_OPENING: 1 (20.0%)

### Movement status

- OPENING_EQUALS_CURRENT: 4 (80.0%)
- REAL_OPENING_CURRENT_AVAILABLE: 1 (20.0%)

### Value status

- VALUE_STRONG: 4 (80.0%)
- NO_VALUE: 1 (20.0%)

### Numeric stats

- CorQ market weight: `{'count': 5, 'avg': 0.156, 'min': 0.12, 'max': 0.3}`
- Value delta pp: `{'count': 5, 'avg': 8.94, 'min': 0.19, 'max': 13.05}`
- Expected value pct: `{'count': 5, 'avg': 11.282, 'min': -7.01, 'max': 19.26}`

## Notes

- HIGH should represent exact TennisApi odds with real opening/current movement data.
- MEDIUM_CURRENT_ONLY is usable but should not carry full 30% MarQ influence.
- THIN_FALLBACK should remain close to zero influence and should be investigated if it grows.
- NO_MARQ/NO_TIER rows indicate missing audit fields or missing market data.
