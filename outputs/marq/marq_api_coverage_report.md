# MarQ API Coverage Report

Generated UTC: 2026-08-28T05:37:04.496247+00:00
Model: 2026-08-04-marq-coverage-report-v1

## all_audit

Rows: 60

### Coverage

- High MarQ: 3.33%
- Medium current-only: 80.0%
- Thin fallback: 0.0%
- No/unknown MarQ: 16.67%
- Usable High+Medium: 83.33%

### Endpoints

- getAllOddsForEvent: 50 (83.33%)
- NO_ENDPOINT: 10 (16.67%)

### Quality tiers

- MEDIUM_CURRENT_ONLY: 48 (80.0%)
- NO_MARQ: 10 (16.67%)
- HIGH: 2 (3.33%)

### Data status

- EXACT_CURRENT_ODDS_ONLY: 48 (80.0%)
- NO_DATA_STATUS: 10 (16.67%)
- EXACT_BETTING_ODDS_WITH_OPENING: 2 (3.33%)

### Movement status

- OPENING_EQUALS_CURRENT: 48 (80.0%)
- NO_MOVEMENT_STATUS: 10 (16.67%)
- REAL_OPENING_CURRENT_AVAILABLE: 2 (3.33%)

### Value status

- NO_VALUE: 25 (41.67%)
- VALUE_STRONG: 22 (36.67%)
- VALUE_UNKNOWN: 10 (16.67%)
- VALUE_PLAYABLE: 3 (5.0%)

### Numeric stats

- CorQ market weight: `{'count': 60, 'avg': 0.1047, 'min': 0.0, 'max': 0.3}`
- Value delta pp: `{'count': 50, 'avg': 0.0, 'min': -20.36, 'max': 20.36}`
- Expected value pct: `{'count': 50, 'avg': -2.9112, 'min': -31.7, 'max': 70.1}`

## corq_top7

Rows: 7

### Coverage

- High MarQ: 0.0%
- Medium current-only: 100.0%
- Thin fallback: 0.0%
- No/unknown MarQ: 0.0%
- Usable High+Medium: 100.0%

### Endpoints

- getAllOddsForEvent: 7 (100.0%)

### Quality tiers

- MEDIUM_CURRENT_ONLY: 7 (100.0%)

### Data status

- EXACT_CURRENT_ODDS_ONLY: 7 (100.0%)

### Movement status

- OPENING_EQUALS_CURRENT: 7 (100.0%)

### Value status

- NO_VALUE: 4 (57.14%)
- VALUE_STRONG: 3 (42.86%)

### Numeric stats

- CorQ market weight: `{'count': 7, 'avg': 0.12, 'min': 0.12, 'max': 0.12}`
- Value delta pp: `{'count': 7, 'avg': 0.2457, 'min': -8.73, 'max': 10.47}`
- Expected value pct: `{'count': 7, 'avg': -5.0214, 'min': -19.44, 'max': 16.08}`

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
- NO_VALUE: 2 (28.57%)

### Numeric stats

- CorQ market weight: `{'count': 7, 'avg': 0.1457, 'min': 0.12, 'max': 0.3}`
- Value delta pp: `{'count': 7, 'avg': 4.7143, 'min': -1.99, 'max': 10.43}`
- Expected value pct: `{'count': 7, 'avg': 1.8229, 'min': -10.75, 'max': 14.83}`

## Notes

- HIGH should represent exact TennisApi odds with real opening/current movement data.
- MEDIUM_CURRENT_ONLY is usable but should not carry full 30% MarQ influence.
- THIN_FALLBACK should remain close to zero influence and should be investigated if it grows.
- NO_MARQ/NO_TIER rows indicate missing audit fields or missing market data.
