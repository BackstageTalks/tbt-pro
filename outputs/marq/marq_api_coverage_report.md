# MarQ API Coverage Report

Generated UTC: 2026-08-16T04:27:56.660266+00:00
Model: 2026-08-04-marq-coverage-report-v1

## all_audit

Rows: 68

### Coverage

- High MarQ: 79.41%
- Medium current-only: 20.59%
- Thin fallback: 0.0%
- No/unknown MarQ: 0.0%
- Usable High+Medium: 100.0%

### Endpoints

- getAllOddsForEvent: 68 (100.0%)

### Quality tiers

- HIGH: 54 (79.41%)
- MEDIUM_CURRENT_ONLY: 14 (20.59%)

### Data status

- EXACT_BETTING_ODDS_WITH_OPENING: 54 (79.41%)
- EXACT_CURRENT_ODDS_ONLY: 14 (20.59%)

### Movement status

- REAL_OPENING_CURRENT_AVAILABLE: 54 (79.41%)
- OPENING_EQUALS_CURRENT: 14 (20.59%)

### Value status

- NO_VALUE: 34 (50.0%)
- VALUE_STRONG: 28 (41.18%)
- VALUE_PLAYABLE: 6 (8.82%)

### Numeric stats

- CorQ market weight: `{'count': 68, 'avg': 0.2312, 'min': 0.12, 'max': 0.3}`
- Value delta pp: `{'count': 68, 'avg': 0.0, 'min': -28.85, 'max': 28.85}`
- Expected value pct: `{'count': 68, 'avg': 17.0669, 'min': -34.74, 'max': 480.64}`

## corq_top7

Rows: 7

### Coverage

- High MarQ: 85.71%
- Medium current-only: 14.29%
- Thin fallback: 0.0%
- No/unknown MarQ: 0.0%
- Usable High+Medium: 100.0%

### Endpoints

- getAllOddsForEvent: 7 (100.0%)

### Quality tiers

- HIGH: 6 (85.71%)
- MEDIUM_CURRENT_ONLY: 1 (14.29%)

### Data status

- EXACT_BETTING_ODDS_WITH_OPENING: 6 (85.71%)
- EXACT_CURRENT_ODDS_ONLY: 1 (14.29%)

### Movement status

- REAL_OPENING_CURRENT_AVAILABLE: 6 (85.71%)
- OPENING_EQUALS_CURRENT: 1 (14.29%)

### Value status

- VALUE_PLAYABLE: 3 (42.86%)
- NO_VALUE: 3 (42.86%)
- VALUE_STRONG: 1 (14.29%)

### Numeric stats

- CorQ market weight: `{'count': 7, 'avg': 0.2514, 'min': 0.12, 'max': 0.3}`
- Value delta pp: `{'count': 7, 'avg': 0.5486, 'min': -3.14, 'max': 7.18}`
- Expected value pct: `{'count': 7, 'avg': -4.3786, 'min': -10.34, 'max': 5.87}`

## cloq

Rows: 6

### Coverage

- High MarQ: 83.33%
- Medium current-only: 16.67%
- Thin fallback: 0.0%
- No/unknown MarQ: 0.0%
- Usable High+Medium: 100.0%

### Endpoints

- getAllOddsForEvent: 6 (100.0%)

### Quality tiers

- HIGH: 5 (83.33%)
- MEDIUM_CURRENT_ONLY: 1 (16.67%)

### Data status

- EXACT_BETTING_ODDS_WITH_OPENING: 5 (83.33%)
- EXACT_CURRENT_ODDS_ONLY: 1 (16.67%)

### Movement status

- REAL_OPENING_CURRENT_AVAILABLE: 5 (83.33%)
- OPENING_EQUALS_CURRENT: 1 (16.67%)

### Value status

- VALUE_STRONG: 5 (83.33%)
- NO_VALUE: 1 (16.67%)

### Numeric stats

- CorQ market weight: `{'count': 6, 'avg': 0.2433, 'min': 0.12, 'max': 0.3}`
- Value delta pp: `{'count': 6, 'avg': 9.0133, 'min': -1.51, 'max': 15.56}`
- Expected value pct: `{'count': 6, 'avg': 12.575, 'min': -7.98, 'max': 27.53}`

## Notes

- HIGH should represent exact TennisApi odds with real opening/current movement data.
- MEDIUM_CURRENT_ONLY is usable but should not carry full 30% MarQ influence.
- THIN_FALLBACK should remain close to zero influence and should be investigated if it grows.
- NO_MARQ/NO_TIER rows indicate missing audit fields or missing market data.
