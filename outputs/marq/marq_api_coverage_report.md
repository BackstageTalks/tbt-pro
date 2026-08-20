# MarQ API Coverage Report

Generated UTC: 2026-08-20T10:14:21.792946+00:00
Model: 2026-08-04-marq-coverage-report-v1

## all_audit

Rows: 8

### Coverage

- High MarQ: 75.0%
- Medium current-only: 25.0%
- Thin fallback: 0.0%
- No/unknown MarQ: 0.0%
- Usable High+Medium: 100.0%

### Endpoints

- getAllOddsForEvent: 8 (100.0%)

### Quality tiers

- HIGH: 6 (75.0%)
- MEDIUM_CURRENT_ONLY: 2 (25.0%)

### Data status

- EXACT_BETTING_ODDS_WITH_OPENING: 6 (75.0%)
- EXACT_CURRENT_ODDS_ONLY: 2 (25.0%)

### Movement status

- REAL_OPENING_CURRENT_AVAILABLE: 6 (75.0%)
- OPENING_EQUALS_CURRENT: 2 (25.0%)

### Value status

- NO_VALUE: 4 (50.0%)
- VALUE_STRONG: 4 (50.0%)

### Numeric stats

- CorQ market weight: `{'count': 8, 'avg': 0.225, 'min': 0.12, 'max': 0.3}`
- Value delta pp: `{'count': 8, 'avg': 0.0, 'min': -14.82, 'max': 14.82}`
- Expected value pct: `{'count': 8, 'avg': 1.175, 'min': -34.9, 'max': 53.44}`

## corq_top7

Rows: 2

### Coverage

- High MarQ: 50.0%
- Medium current-only: 50.0%
- Thin fallback: 0.0%
- No/unknown MarQ: 0.0%
- Usable High+Medium: 100.0%

### Endpoints

- getAllOddsForEvent: 2 (100.0%)

### Quality tiers

- MEDIUM_CURRENT_ONLY: 1 (50.0%)
- HIGH: 1 (50.0%)

### Data status

- EXACT_CURRENT_ODDS_ONLY: 1 (50.0%)
- EXACT_BETTING_ODDS_WITH_OPENING: 1 (50.0%)

### Movement status

- OPENING_EQUALS_CURRENT: 1 (50.0%)
- REAL_OPENING_CURRENT_AVAILABLE: 1 (50.0%)

### Value status

- NO_VALUE: 2 (100.0%)

### Numeric stats

- CorQ market weight: `{'count': 2, 'avg': 0.21, 'min': 0.12, 'max': 0.3}`
- Value delta pp: `{'count': 2, 'avg': -8.645, 'min': -13.1, 'max': -4.19}`
- Expected value pct: `{'count': 2, 'avg': -18.98, 'min': -25.97, 'max': -11.99}`

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
- Value delta pp: `{'count': 1, 'avg': 14.82, 'min': 14.82, 'max': 14.82}`
- Expected value pct: `{'count': 1, 'avg': 21.41, 'min': 21.41, 'max': 21.41}`

## Notes

- HIGH should represent exact TennisApi odds with real opening/current movement data.
- MEDIUM_CURRENT_ONLY is usable but should not carry full 30% MarQ influence.
- THIN_FALLBACK should remain close to zero influence and should be investigated if it grows.
- NO_MARQ/NO_TIER rows indicate missing audit fields or missing market data.
