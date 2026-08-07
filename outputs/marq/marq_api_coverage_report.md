# MarQ API Coverage Report

Generated UTC: 2026-08-07T10:03:47.514375+00:00
Model: 2026-08-04-marq-coverage-report-v1

## all_audit

Rows: 36

### Coverage

- High MarQ: 83.33%
- Medium current-only: 16.67%
- Thin fallback: 0.0%
- No/unknown MarQ: 0.0%
- Usable High+Medium: 100.0%

### Endpoints

- getAllOddsForEvent: 36 (100.0%)

### Quality tiers

- HIGH: 30 (83.33%)
- MEDIUM_CURRENT_ONLY: 6 (16.67%)

### Data status

- EXACT_BETTING_ODDS_WITH_OPENING: 30 (83.33%)
- EXACT_CURRENT_ODDS_ONLY: 6 (16.67%)

### Movement status

- REAL_OPENING_CURRENT_AVAILABLE: 30 (83.33%)
- OPENING_EQUALS_CURRENT: 6 (16.67%)

### Value status

- NO_VALUE: 19 (52.78%)
- VALUE_STRONG: 15 (41.67%)
- VALUE_PLAYABLE: 2 (5.56%)

### Numeric stats

- CorQ market weight: `{'count': 36, 'avg': 0.2356, 'min': 0.1, 'max': 0.3}`
- Value delta pp: `{'count': 36, 'avg': 0.0, 'min': -20.54, 'max': 20.54}`
- Expected value pct: `{'count': 36, 'avg': 6.6908, 'min': -27.72, 'max': 201.2}`

## corq_top7

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

- VALUE_STRONG: 1 (100.0%)

### Numeric stats

- CorQ market weight: `{'count': 1, 'avg': 0.12, 'min': 0.12, 'max': 0.12}`
- Value delta pp: `{'count': 1, 'avg': 8.08, 'min': 8.08, 'max': 8.08}`
- Expected value pct: `{'count': 1, 'avg': 8.84, 'min': 8.84, 'max': 8.84}`

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

- VALUE_STRONG: 1 (100.0%)

### Numeric stats

- CorQ market weight: `{'count': 1, 'avg': 0.12, 'min': 0.12, 'max': 0.12}`
- Value delta pp: `{'count': 1, 'avg': 8.08, 'min': 8.08, 'max': 8.08}`
- Expected value pct: `{'count': 1, 'avg': 8.84, 'min': 8.84, 'max': 8.84}`

## Notes

- HIGH should represent exact TennisApi odds with real opening/current movement data.
- MEDIUM_CURRENT_ONLY is usable but should not carry full 30% MarQ influence.
- THIN_FALLBACK should remain close to zero influence and should be investigated if it grows.
- NO_MARQ/NO_TIER rows indicate missing audit fields or missing market data.
