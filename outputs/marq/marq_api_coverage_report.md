# MarQ API Coverage Report

Generated UTC: 2026-08-29T07:15:53.856759+00:00
Model: 2026-08-04-marq-coverage-report-v1

## all_audit

Rows: 6

### Coverage

- High MarQ: 0.0%
- Medium current-only: 100.0%
- Thin fallback: 0.0%
- No/unknown MarQ: 0.0%
- Usable High+Medium: 100.0%

### Endpoints

- getAllOddsForEvent: 6 (100.0%)

### Quality tiers

- MEDIUM_CURRENT_ONLY: 6 (100.0%)

### Data status

- EXACT_CURRENT_ODDS_ONLY: 6 (100.0%)

### Movement status

- OPENING_EQUALS_CURRENT: 6 (100.0%)

### Value status

- VALUE_STRONG: 3 (50.0%)
- NO_VALUE: 3 (50.0%)

### Numeric stats

- CorQ market weight: `{'count': 6, 'avg': 0.12, 'min': 0.12, 'max': 0.12}`
- Value delta pp: `{'count': 6, 'avg': 0.0, 'min': -9.07, 'max': 9.07}`
- Expected value pct: `{'count': 6, 'avg': -2.62, 'min': -18.55, 'max': 19.46}`

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

- NO_VALUE: 2 (100.0%)

### Numeric stats

- CorQ market weight: `{'count': 2, 'avg': 0.12, 'min': 0.12, 'max': 0.12}`
- Value delta pp: `{'count': 2, 'avg': -8.39, 'min': -9.07, 'max': -7.71}`
- Expected value pct: `{'count': 2, 'avg': -18.18, 'min': -18.55, 'max': -17.81}`

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
- Value delta pp: `{'count': 1, 'avg': 6.59, 'min': 6.59, 'max': 6.59}`
- Expected value pct: `{'count': 1, 'avg': 6.6, 'min': 6.6, 'max': 6.6}`

## Notes

- HIGH should represent exact TennisApi odds with real opening/current movement data.
- MEDIUM_CURRENT_ONLY is usable but should not carry full 30% MarQ influence.
- THIN_FALLBACK should remain close to zero influence and should be investigated if it grows.
- NO_MARQ/NO_TIER rows indicate missing audit fields or missing market data.
