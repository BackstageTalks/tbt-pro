# MarQ API Coverage Report

Generated UTC: 2026-08-17T13:51:27.428863+00:00
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
- VALUE_STRONG: 12 (37.5%)
- VALUE_PLAYABLE: 4 (12.5%)

### Numeric stats

- CorQ market weight: `{'count': 32, 'avg': 0.2506, 'min': 0.12, 'max': 0.3}`
- Value delta pp: `{'count': 32, 'avg': 0.0, 'min': -18.15, 'max': 18.15}`
- Expected value pct: `{'count': 32, 'avg': 7.5075, 'min': -26.26, 'max': 99.08}`

## corq_top7

Rows: 5

### Coverage

- High MarQ: 100.0%
- Medium current-only: 0.0%
- Thin fallback: 0.0%
- No/unknown MarQ: 0.0%
- Usable High+Medium: 100.0%

### Endpoints

- getAllOddsForEvent: 5 (100.0%)

### Quality tiers

- HIGH: 5 (100.0%)

### Data status

- EXACT_BETTING_ODDS_WITH_OPENING: 5 (100.0%)

### Movement status

- REAL_OPENING_CURRENT_AVAILABLE: 5 (100.0%)

### Value status

- NO_VALUE: 3 (60.0%)
- VALUE_PLAYABLE: 1 (20.0%)
- VALUE_STRONG: 1 (20.0%)

### Numeric stats

- CorQ market weight: `{'count': 5, 'avg': 0.268, 'min': 0.22, 'max': 0.3}`
- Value delta pp: `{'count': 5, 'avg': -0.366, 'min': -4.67, 'max': 4.03}`
- Expected value pct: `{'count': 5, 'avg': -5.33, 'min': -13.22, 'max': 2.8}`

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
