# MarQ API Coverage Report

Generated UTC: 2026-08-10T06:14:13.838025+00:00
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
- VALUE_STRONG: 3 (37.5%)
- VALUE_PLAYABLE: 1 (12.5%)

### Numeric stats

- CorQ market weight: `{'count': 8, 'avg': 0.225, 'min': 0.12, 'max': 0.3}`
- Value delta pp: `{'count': 8, 'avg': 0.0, 'min': -9.75, 'max': 9.75}`
- Expected value pct: `{'count': 8, 'avg': -1.6638, 'min': -24.76, 'max': 27.36}`

## corq_top7

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
