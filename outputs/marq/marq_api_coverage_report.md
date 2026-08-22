# MarQ API Coverage Report

Generated UTC: 2026-08-22T21:01:14.193870+00:00
Model: 2026-08-04-marq-coverage-report-v1

## all_audit

Rows: 40

### Coverage

- High MarQ: 35.0%
- Medium current-only: 65.0%
- Thin fallback: 0.0%
- No/unknown MarQ: 0.0%
- Usable High+Medium: 100.0%

### Endpoints

- getAllOddsForEvent: 40 (100.0%)

### Quality tiers

- MEDIUM_CURRENT_ONLY: 26 (65.0%)
- HIGH: 14 (35.0%)

### Data status

- EXACT_CURRENT_ODDS_ONLY: 26 (65.0%)
- EXACT_BETTING_ODDS_WITH_OPENING: 14 (35.0%)

### Movement status

- OPENING_EQUALS_CURRENT: 26 (65.0%)
- REAL_OPENING_CURRENT_AVAILABLE: 14 (35.0%)

### Value status

- NO_VALUE: 21 (52.5%)
- VALUE_STRONG: 17 (42.5%)
- VALUE_PLAYABLE: 2 (5.0%)

### Numeric stats

- CorQ market weight: `{'count': 40, 'avg': 0.163, 'min': 0.1, 'max': 0.3}`
- Value delta pp: `{'count': 40, 'avg': 0.0, 'min': -43.67, 'max': 43.67}`
- Expected value pct: `{'count': 40, 'avg': 42.3425, 'min': -48.09, 'max': 739.12}`

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
- Value delta pp: `{'count': 2, 'avg': -1.0, 'min': -2.15, 'max': 0.15}`
- Expected value pct: `{'count': 2, 'avg': -7.585, 'min': -9.14, 'max': -6.03}`

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
