# MarQ API Coverage Report

Generated UTC: 2026-08-22T04:23:30.505364+00:00
Model: 2026-08-04-marq-coverage-report-v1

## all_audit

Rows: 40

### Coverage

- High MarQ: 10.0%
- Medium current-only: 5.0%
- Thin fallback: 0.0%
- No/unknown MarQ: 85.0%
- Usable High+Medium: 15.0%

### Endpoints

- NO_ENDPOINT: 34 (85.0%)
- getAllOddsForEvent: 6 (15.0%)

### Quality tiers

- NO_MARQ: 34 (85.0%)
- HIGH: 4 (10.0%)
- MEDIUM_CURRENT_ONLY: 2 (5.0%)

### Data status

- NO_DATA_STATUS: 34 (85.0%)
- EXACT_BETTING_ODDS_WITH_OPENING: 4 (10.0%)
- EXACT_CURRENT_ODDS_ONLY: 2 (5.0%)

### Movement status

- NO_MOVEMENT_STATUS: 34 (85.0%)
- REAL_OPENING_CURRENT_AVAILABLE: 4 (10.0%)
- OPENING_EQUALS_CURRENT: 2 (5.0%)

### Value status

- VALUE_UNKNOWN: 34 (85.0%)
- NO_VALUE: 3 (7.5%)
- VALUE_STRONG: 2 (5.0%)
- VALUE_PLAYABLE: 1 (2.5%)

### Numeric stats

- CorQ market weight: `{'count': 40, 'avg': 0.032, 'min': 0.0, 'max': 0.3}`
- Value delta pp: `{'count': 6, 'avg': 0.0, 'min': -13.12, 'max': 13.12}`
- Expected value pct: `{'count': 6, 'avg': 0.8167, 'min': -22.92, 'max': 34.82}`

## corq_top7

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

- NO_VALUE: 1 (100.0%)

### Numeric stats

- CorQ market weight: `{'count': 1, 'avg': 0.22, 'min': 0.22, 'max': 0.22}`
- Value delta pp: `{'count': 1, 'avg': -13.12, 'min': -13.12, 'max': -13.12}`
- Expected value pct: `{'count': 1, 'avg': -22.92, 'min': -22.92, 'max': -22.92}`

## cloq

Rows: 1

### Coverage

- High MarQ: 0.0%
- Medium current-only: 100.0%
- Thin fallback: 0.0%
- No/unknown MarQ: 0.0%
- Usable High+Medium: 100.0%

### Endpoints

- getAllOddsForEvent: 1 (100.0%)

### Quality tiers

- MEDIUM_CURRENT_ONLY: 1 (100.0%)

### Data status

- EXACT_CURRENT_ODDS_ONLY: 1 (100.0%)

### Movement status

- OPENING_EQUALS_CURRENT: 1 (100.0%)

### Value status

- NO_VALUE: 1 (100.0%)

### Numeric stats

- CorQ market weight: `{'count': 1, 'avg': 0.12, 'min': 0.12, 'max': 0.12}`
- Value delta pp: `{'count': 1, 'avg': -1.99, 'min': -1.99, 'max': -1.99}`
- Expected value pct: `{'count': 1, 'avg': -8.85, 'min': -8.85, 'max': -8.85}`

## Notes

- HIGH should represent exact TennisApi odds with real opening/current movement data.
- MEDIUM_CURRENT_ONLY is usable but should not carry full 30% MarQ influence.
- THIN_FALLBACK should remain close to zero influence and should be investigated if it grows.
- NO_MARQ/NO_TIER rows indicate missing audit fields or missing market data.
