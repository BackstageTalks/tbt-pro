# MarQ API Coverage Report

Generated UTC: 2026-08-22T13:47:54.939597+00:00
Model: 2026-08-04-marq-coverage-report-v1

## all_audit

Rows: 40

### Coverage

- High MarQ: 15.0%
- Medium current-only: 85.0%
- Thin fallback: 0.0%
- No/unknown MarQ: 0.0%
- Usable High+Medium: 100.0%

### Endpoints

- getAllOddsForEvent: 40 (100.0%)

### Quality tiers

- MEDIUM_CURRENT_ONLY: 34 (85.0%)
- HIGH: 6 (15.0%)

### Data status

- EXACT_CURRENT_ODDS_ONLY: 34 (85.0%)
- EXACT_BETTING_ODDS_WITH_OPENING: 6 (15.0%)

### Movement status

- OPENING_EQUALS_CURRENT: 34 (85.0%)
- REAL_OPENING_CURRENT_AVAILABLE: 6 (15.0%)

### Value status

- NO_VALUE: 21 (52.5%)
- VALUE_STRONG: 17 (42.5%)
- VALUE_PLAYABLE: 2 (5.0%)

### Numeric stats

- CorQ market weight: `{'count': 40, 'avg': 0.134, 'min': 0.1, 'max': 0.3}`
- Value delta pp: `{'count': 40, 'avg': 0.0, 'min': -43.67, 'max': 43.67}`
- Expected value pct: `{'count': 40, 'avg': 38.387, 'min': -48.09, 'max': 739.12}`

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

- NO_VALUE: 4 (57.14%)
- VALUE_STRONG: 3 (42.86%)

### Numeric stats

- CorQ market weight: `{'count': 7, 'avg': 0.1343, 'min': 0.12, 'max': 0.22}`
- Value delta pp: `{'count': 7, 'avg': 1.0657, 'min': -14.57, 'max': 13.44}`
- Expected value pct: `{'count': 7, 'avg': -2.59, 'min': -24.95, 'max': 25.09}`

## cloq

Rows: 2

### Coverage

- High MarQ: 0.0%
- Medium current-only: 100.0%
- Thin fallback: 0.0%
- No/unknown MarQ: 0.0%
- Usable High+Medium: 100.0%

### Endpoints

- getAllOddsForEvent: 2 (100.0%)

### Quality tiers

- MEDIUM_CURRENT_ONLY: 2 (100.0%)

### Data status

- EXACT_CURRENT_ODDS_ONLY: 2 (100.0%)

### Movement status

- OPENING_EQUALS_CURRENT: 2 (100.0%)

### Value status

- VALUE_STRONG: 2 (100.0%)

### Numeric stats

- CorQ market weight: `{'count': 2, 'avg': 0.12, 'min': 0.12, 'max': 0.12}`
- Value delta pp: `{'count': 2, 'avg': 6.86, 'min': 5.02, 'max': 8.7}`
- Expected value pct: `{'count': 2, 'avg': 4.645, 'min': 1.68, 'max': 7.61}`

## Notes

- HIGH should represent exact TennisApi odds with real opening/current movement data.
- MEDIUM_CURRENT_ONLY is usable but should not carry full 30% MarQ influence.
- THIN_FALLBACK should remain close to zero influence and should be investigated if it grows.
- NO_MARQ/NO_TIER rows indicate missing audit fields or missing market data.
