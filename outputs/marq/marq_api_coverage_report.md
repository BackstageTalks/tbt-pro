# MarQ API Coverage Report

Generated UTC: 2026-08-05T10:31:54.963003+00:00
Model: 2026-08-04-marq-coverage-report-v1

## all_audit

Rows: 104

### Coverage

- High MarQ: 65.38%
- Medium current-only: 34.62%
- Thin fallback: 0.0%
- No/unknown MarQ: 0.0%
- Usable High+Medium: 100.0%

### Endpoints

- getAllOddsForEvent: 104 (100.0%)

### Quality tiers

- HIGH: 68 (65.38%)
- MEDIUM_CURRENT_ONLY: 36 (34.62%)

### Data status

- EXACT_BETTING_ODDS_WITH_OPENING: 68 (65.38%)
- EXACT_CURRENT_ODDS_ONLY: 36 (34.62%)

### Movement status

- REAL_OPENING_CURRENT_AVAILABLE: 68 (65.38%)
- OPENING_EQUALS_CURRENT: 36 (34.62%)

### Value status

- NO_VALUE: 54 (51.92%)
- VALUE_STRONG: 40 (38.46%)
- VALUE_PLAYABLE: 10 (9.62%)

### Numeric stats

- CorQ market weight: `{'count': 104, 'avg': 0.2115, 'min': 0.12, 'max': 0.3}`
- Value delta pp: `{'count': 104, 'avg': 0.0, 'min': -26.82, 'max': 26.82}`
- Expected value pct: `{'count': 104, 'avg': 12.2227, 'min': -49.25, 'max': 219.8}`

## corq_top7

Rows: 7

### Coverage

- High MarQ: 100.0%
- Medium current-only: 0.0%
- Thin fallback: 0.0%
- No/unknown MarQ: 0.0%
- Usable High+Medium: 100.0%

### Endpoints

- getAllOddsForEvent: 7 (100.0%)

### Quality tiers

- HIGH: 7 (100.0%)

### Data status

- EXACT_BETTING_ODDS_WITH_OPENING: 7 (100.0%)

### Movement status

- REAL_OPENING_CURRENT_AVAILABLE: 7 (100.0%)

### Value status

- NO_VALUE: 3 (42.86%)
- VALUE_PLAYABLE: 2 (28.57%)
- VALUE_STRONG: 2 (28.57%)

### Numeric stats

- CorQ market weight: `{'count': 7, 'avg': 0.2657, 'min': 0.22, 'max': 0.3}`
- Value delta pp: `{'count': 7, 'avg': 2.2, 'min': -1.43, 'max': 6.9}`
- Expected value pct: `{'count': 7, 'avg': -1.7971, 'min': -7.28, 'max': 3.28}`

## cloq

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

- VALUE_STRONG: 2 (100.0%)

### Numeric stats

- CorQ market weight: `{'count': 2, 'avg': 0.21, 'min': 0.12, 'max': 0.3}`
- Value delta pp: `{'count': 2, 'avg': 12.285, 'min': 5.41, 'max': 19.16}`
- Expected value pct: `{'count': 2, 'avg': 23.02, 'min': 5.83, 'max': 40.21}`

## Notes

- HIGH should represent exact TennisApi odds with real opening/current movement data.
- MEDIUM_CURRENT_ONLY is usable but should not carry full 30% MarQ influence.
- THIN_FALLBACK should remain close to zero influence and should be investigated if it grows.
- NO_MARQ/NO_TIER rows indicate missing audit fields or missing market data.
