# MarQ API Coverage Report

Generated UTC: 2026-08-20T05:13:11.427623+00:00
Model: 2026-08-04-marq-coverage-report-v1

## all_audit

Rows: 8

### Coverage

- High MarQ: 25.0%
- Medium current-only: 75.0%
- Thin fallback: 0.0%
- No/unknown MarQ: 0.0%
- Usable High+Medium: 100.0%

### Endpoints

- getAllOddsForEvent: 8 (100.0%)

### Quality tiers

- MEDIUM_CURRENT_ONLY: 6 (75.0%)
- HIGH: 2 (25.0%)

### Data status

- EXACT_CURRENT_ODDS_ONLY: 6 (75.0%)
- EXACT_BETTING_ODDS_WITH_OPENING: 2 (25.0%)

### Movement status

- OPENING_EQUALS_CURRENT: 6 (75.0%)
- REAL_OPENING_CURRENT_AVAILABLE: 2 (25.0%)

### Value status

- NO_VALUE: 4 (50.0%)
- VALUE_STRONG: 4 (50.0%)

### Numeric stats

- CorQ market weight: `{'count': 8, 'avg': 0.155, 'min': 0.12, 'max': 0.3}`
- Value delta pp: `{'count': 8, 'avg': 0.0, 'min': -14.92, 'max': 14.92}`
- Expected value pct: `{'count': 8, 'avg': 0.6625, 'min': -31.41, 'max': 44.34}`

## corq_top7

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

- VALUE_STRONG: 1 (50.0%)
- NO_VALUE: 1 (50.0%)

### Numeric stats

- CorQ market weight: `{'count': 2, 'avg': 0.12, 'min': 0.12, 'max': 0.12}`
- Value delta pp: `{'count': 2, 'avg': 5.215, 'min': -4.49, 'max': 14.92}`
- Expected value pct: `{'count': 2, 'avg': 9.885, 'min': -12.46, 'max': 32.23}`

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
- Value delta pp: `{'count': 1, 'avg': 12.51, 'min': 12.51, 'max': 12.51}`
- Expected value pct: `{'count': 1, 'avg': 16.5, 'min': 16.5, 'max': 16.5}`

## Notes

- HIGH should represent exact TennisApi odds with real opening/current movement data.
- MEDIUM_CURRENT_ONLY is usable but should not carry full 30% MarQ influence.
- THIN_FALLBACK should remain close to zero influence and should be investigated if it grows.
- NO_MARQ/NO_TIER rows indicate missing audit fields or missing market data.
