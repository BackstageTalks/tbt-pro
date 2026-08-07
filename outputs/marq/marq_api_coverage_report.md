# MarQ API Coverage Report

Generated UTC: 2026-08-07T12:35:16.892077+00:00
Model: 2026-08-04-marq-coverage-report-v1

## all_audit

Rows: 36

### Coverage

- High MarQ: 94.44%
- Medium current-only: 5.56%
- Thin fallback: 0.0%
- No/unknown MarQ: 0.0%
- Usable High+Medium: 100.0%

### Endpoints

- getAllOddsForEvent: 36 (100.0%)

### Quality tiers

- HIGH: 34 (94.44%)
- MEDIUM_CURRENT_ONLY: 2 (5.56%)

### Data status

- EXACT_BETTING_ODDS_WITH_OPENING: 34 (94.44%)
- EXACT_CURRENT_ODDS_ONLY: 2 (5.56%)

### Movement status

- REAL_OPENING_CURRENT_AVAILABLE: 34 (94.44%)
- OPENING_EQUALS_CURRENT: 2 (5.56%)

### Value status

- NO_VALUE: 19 (52.78%)
- VALUE_STRONG: 15 (41.67%)
- VALUE_PLAYABLE: 2 (5.56%)

### Numeric stats

- CorQ market weight: `{'count': 36, 'avg': 0.2522, 'min': 0.12, 'max': 0.3}`
- Value delta pp: `{'count': 36, 'avg': 0.0, 'min': -32.73, 'max': 32.73}`
- Expected value pct: `{'count': 36, 'avg': 6.795, 'min': -28.72, 'max': 201.2}`

## corq_top7

Rows: 4

### Coverage

- High MarQ: 100.0%
- Medium current-only: 0.0%
- Thin fallback: 0.0%
- No/unknown MarQ: 0.0%
- Usable High+Medium: 100.0%

### Endpoints

- getAllOddsForEvent: 4 (100.0%)

### Quality tiers

- HIGH: 4 (100.0%)

### Data status

- EXACT_BETTING_ODDS_WITH_OPENING: 4 (100.0%)

### Movement status

- REAL_OPENING_CURRENT_AVAILABLE: 4 (100.0%)

### Value status

- NO_VALUE: 4 (100.0%)

### Numeric stats

- CorQ market weight: `{'count': 4, 'avg': 0.26, 'min': 0.22, 'max': 0.3}`
- Value delta pp: `{'count': 4, 'avg': -7.6325, 'min': -11.44, 'max': 0.19}`
- Expected value pct: `{'count': 4, 'avg': -16.025, 'min': -21.97, 'max': -4.19}`

## cloq

Rows: 0

### Coverage

- High MarQ: 0.0%
- Medium current-only: 0.0%
- Thin fallback: 0.0%
- No/unknown MarQ: 0.0%
- Usable High+Medium: 0.0%

### Endpoints

No data.

### Quality tiers

No data.

### Data status

No data.

### Movement status

No data.

### Value status

No data.

### Numeric stats

- CorQ market weight: `{'count': 0, 'avg': None, 'min': None, 'max': None}`
- Value delta pp: `{'count': 0, 'avg': None, 'min': None, 'max': None}`
- Expected value pct: `{'count': 0, 'avg': None, 'min': None, 'max': None}`

## Notes

- HIGH should represent exact TennisApi odds with real opening/current movement data.
- MEDIUM_CURRENT_ONLY is usable but should not carry full 30% MarQ influence.
- THIN_FALLBACK should remain close to zero influence and should be investigated if it grows.
- NO_MARQ/NO_TIER rows indicate missing audit fields or missing market data.
