# MarQ API Coverage Report

Generated UTC: 2026-08-17T09:34:22.880725+00:00
Model: 2026-08-04-marq-coverage-report-v1

## all_audit

Rows: 32

### Coverage

- High MarQ: 93.75%
- Medium current-only: 6.25%
- Thin fallback: 0.0%
- No/unknown MarQ: 0.0%
- Usable High+Medium: 100.0%

### Endpoints

- getAllOddsForEvent: 32 (100.0%)

### Quality tiers

- HIGH: 30 (93.75%)
- MEDIUM_CURRENT_ONLY: 2 (6.25%)

### Data status

- EXACT_BETTING_ODDS_WITH_OPENING: 30 (93.75%)
- EXACT_CURRENT_ODDS_ONLY: 2 (6.25%)

### Movement status

- REAL_OPENING_CURRENT_AVAILABLE: 30 (93.75%)
- OPENING_EQUALS_CURRENT: 2 (6.25%)

### Value status

- NO_VALUE: 16 (50.0%)
- VALUE_STRONG: 13 (40.62%)
- VALUE_PLAYABLE: 3 (9.38%)

### Numeric stats

- CorQ market weight: `{'count': 32, 'avg': 0.2506, 'min': 0.12, 'max': 0.3}`
- Value delta pp: `{'count': 32, 'avg': 0.0, 'min': -19.47, 'max': 19.47}`
- Expected value pct: `{'count': 32, 'avg': 8.2378, 'min': -26.91, 'max': 111.92}`

## corq_top7

Rows: 5

### Coverage

- High MarQ: 80.0%
- Medium current-only: 20.0%
- Thin fallback: 0.0%
- No/unknown MarQ: 0.0%
- Usable High+Medium: 100.0%

### Endpoints

- getAllOddsForEvent: 5 (100.0%)

### Quality tiers

- HIGH: 4 (80.0%)
- MEDIUM_CURRENT_ONLY: 1 (20.0%)

### Data status

- EXACT_BETTING_ODDS_WITH_OPENING: 4 (80.0%)
- EXACT_CURRENT_ODDS_ONLY: 1 (20.0%)

### Movement status

- REAL_OPENING_CURRENT_AVAILABLE: 4 (80.0%)
- OPENING_EQUALS_CURRENT: 1 (20.0%)

### Value status

- NO_VALUE: 3 (60.0%)
- VALUE_PLAYABLE: 1 (20.0%)
- VALUE_STRONG: 1 (20.0%)

### Numeric stats

- CorQ market weight: `{'count': 5, 'avg': 0.232, 'min': 0.12, 'max': 0.3}`
- Value delta pp: `{'count': 5, 'avg': -0.876, 'min': -4.67, 'max': 4.03}`
- Expected value pct: `{'count': 5, 'avg': -5.844, 'min': -13.22, 'max': 2.8}`

## cloq

Rows: 3

### Coverage

- High MarQ: 100.0%
- Medium current-only: 0.0%
- Thin fallback: 0.0%
- No/unknown MarQ: 0.0%
- Usable High+Medium: 100.0%

### Endpoints

- getAllOddsForEvent: 3 (100.0%)

### Quality tiers

- HIGH: 3 (100.0%)

### Data status

- EXACT_BETTING_ODDS_WITH_OPENING: 3 (100.0%)

### Movement status

- REAL_OPENING_CURRENT_AVAILABLE: 3 (100.0%)

### Value status

- VALUE_STRONG: 2 (66.67%)
- NO_VALUE: 1 (33.33%)

### Numeric stats

- CorQ market weight: `{'count': 3, 'avg': 0.2467, 'min': 0.22, 'max': 0.3}`
- Value delta pp: `{'count': 3, 'avg': 4.31, 'min': -1.42, 'max': 9.99}`
- Expected value pct: `{'count': 3, 'avg': 3.2333, 'min': -7.6, 'max': 14.72}`

## Notes

- HIGH should represent exact TennisApi odds with real opening/current movement data.
- MEDIUM_CURRENT_ONLY is usable but should not carry full 30% MarQ influence.
- THIN_FALLBACK should remain close to zero influence and should be investigated if it grows.
- NO_MARQ/NO_TIER rows indicate missing audit fields or missing market data.
