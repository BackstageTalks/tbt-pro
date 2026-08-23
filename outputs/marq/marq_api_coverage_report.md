# MarQ API Coverage Report

Generated UTC: 2026-08-23T05:34:07.609792+00:00
Model: 2026-08-04-marq-coverage-report-v1

## all_audit

Rows: 60

### Coverage

- High MarQ: 20.0%
- Medium current-only: 20.0%
- Thin fallback: 0.0%
- No/unknown MarQ: 60.0%
- Usable High+Medium: 40.0%

### Endpoints

- NO_ENDPOINT: 36 (60.0%)
- getAllOddsForEvent: 24 (40.0%)

### Quality tiers

- NO_MARQ: 34 (56.67%)
- HIGH: 12 (20.0%)
- MEDIUM_CURRENT_ONLY: 12 (20.0%)
- NO_TIER: 2 (3.33%)

### Data status

- NO_DATA_STATUS: 36 (60.0%)
- EXACT_BETTING_ODDS_WITH_OPENING: 12 (20.0%)
- EXACT_CURRENT_ODDS_ONLY: 12 (20.0%)

### Movement status

- NO_MOVEMENT_STATUS: 36 (60.0%)
- REAL_OPENING_CURRENT_AVAILABLE: 12 (20.0%)
- OPENING_EQUALS_CURRENT: 12 (20.0%)

### Value status

- VALUE_UNKNOWN: 36 (60.0%)
- NO_VALUE: 12 (20.0%)
- VALUE_STRONG: 12 (20.0%)

### Numeric stats

- CorQ market weight: `{'count': 58, 'avg': 0.0786, 'min': 0.0, 'max': 0.3}`
- Value delta pp: `{'count': 24, 'avg': 0.0, 'min': -26.41, 'max': 26.41}`
- Expected value pct: `{'count': 24, 'avg': 4.2838, 'min': -34.75, 'max': 153.56}`

## corq_top7

Rows: 7

### Coverage

- High MarQ: 71.43%
- Medium current-only: 28.57%
- Thin fallback: 0.0%
- No/unknown MarQ: 0.0%
- Usable High+Medium: 100.0%

### Endpoints

- getAllOddsForEvent: 7 (100.0%)

### Quality tiers

- HIGH: 5 (71.43%)
- MEDIUM_CURRENT_ONLY: 2 (28.57%)

### Data status

- EXACT_BETTING_ODDS_WITH_OPENING: 5 (71.43%)
- EXACT_CURRENT_ODDS_ONLY: 2 (28.57%)

### Movement status

- REAL_OPENING_CURRENT_AVAILABLE: 5 (71.43%)
- OPENING_EQUALS_CURRENT: 2 (28.57%)

### Value status

- NO_VALUE: 7 (100.0%)

### Numeric stats

- CorQ market weight: `{'count': 7, 'avg': 0.2143, 'min': 0.12, 'max': 0.3}`
- Value delta pp: `{'count': 7, 'avg': -6.5914, 'min': -9.28, 'max': -3.27}`
- Expected value pct: `{'count': 7, 'avg': -14.6643, 'min': -18.86, 'max': -10.25}`

## cloq

Rows: 1

### Coverage

- High MarQ: 100.0%
- Medium current-only: 0.0%
- Thin fallback: 0.0%
- No/unknown MarQ: 0.0%
- Usable High+Medium: 100.0%

### Endpoints

- getAllOddsForEvent: 1 (100.0%)

### Quality tiers

- HIGH: 1 (100.0%)

### Data status

- EXACT_BETTING_ODDS_WITH_OPENING: 1 (100.0%)

### Movement status

- REAL_OPENING_CURRENT_AVAILABLE: 1 (100.0%)

### Value status

- VALUE_STRONG: 1 (100.0%)

### Numeric stats

- CorQ market weight: `{'count': 1, 'avg': 0.3, 'min': 0.3, 'max': 0.3}`
- Value delta pp: `{'count': 1, 'avg': 4.12, 'min': 4.12, 'max': 4.12}`
- Expected value pct: `{'count': 1, 'avg': 2.15, 'min': 2.15, 'max': 2.15}`

## Notes

- HIGH should represent exact TennisApi odds with real opening/current movement data.
- MEDIUM_CURRENT_ONLY is usable but should not carry full 30% MarQ influence.
- THIN_FALLBACK should remain close to zero influence and should be investigated if it grows.
- NO_MARQ/NO_TIER rows indicate missing audit fields or missing market data.
