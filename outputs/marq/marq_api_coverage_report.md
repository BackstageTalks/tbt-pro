# MarQ API Coverage Report

Generated UTC: 2026-08-11T11:15:44.364519+00:00
Model: 2026-08-04-marq-coverage-report-v1

## all_audit

Rows: 108

### Coverage

- High MarQ: 9.26%
- Medium current-only: 90.74%
- Thin fallback: 0.0%
- No/unknown MarQ: 0.0%
- Usable High+Medium: 100.0%

### Endpoints

- getAllOddsForEvent: 108 (100.0%)

### Quality tiers

- MEDIUM_CURRENT_ONLY: 98 (90.74%)
- HIGH: 10 (9.26%)

### Data status

- EXACT_CURRENT_ODDS_ONLY: 98 (90.74%)
- EXACT_BETTING_ODDS_WITH_OPENING: 10 (9.26%)

### Movement status

- OPENING_EQUALS_CURRENT: 98 (90.74%)
- REAL_OPENING_CURRENT_AVAILABLE: 10 (9.26%)

### Value status

- NO_VALUE: 58 (53.7%)
- VALUE_STRONG: 42 (38.89%)
- VALUE_PLAYABLE: 8 (7.41%)

### Numeric stats

- CorQ market weight: `{'count': 108, 'avg': 0.1311, 'min': 0.1, 'max': 0.3}`
- Value delta pp: `{'count': 108, 'avg': 0.0, 'min': -35.8, 'max': 35.8}`
- Expected value pct: `{'count': 108, 'avg': 1.9244, 'min': -44.89, 'max': 227.6}`

## corq_top7

Rows: 7

### Coverage

- High MarQ: 28.57%
- Medium current-only: 71.43%
- Thin fallback: 0.0%
- No/unknown MarQ: 0.0%
- Usable High+Medium: 100.0%

### Endpoints

- getAllOddsForEvent: 7 (100.0%)

### Quality tiers

- MEDIUM_CURRENT_ONLY: 5 (71.43%)
- HIGH: 2 (28.57%)

### Data status

- EXACT_CURRENT_ODDS_ONLY: 5 (71.43%)
- EXACT_BETTING_ODDS_WITH_OPENING: 2 (28.57%)

### Movement status

- OPENING_EQUALS_CURRENT: 5 (71.43%)
- REAL_OPENING_CURRENT_AVAILABLE: 2 (28.57%)

### Value status

- VALUE_STRONG: 7 (100.0%)

### Numeric stats

- CorQ market weight: `{'count': 7, 'avg': 0.1486, 'min': 0.12, 'max': 0.22}`
- Value delta pp: `{'count': 7, 'avg': 10.77, 'min': 6.98, 'max': 13.98}`
- Expected value pct: `{'count': 7, 'avg': 13.3543, 'min': 3.88, 'max': 21.97}`

## cloq

Rows: 10

### Coverage

- High MarQ: 30.0%
- Medium current-only: 70.0%
- Thin fallback: 0.0%
- No/unknown MarQ: 0.0%
- Usable High+Medium: 100.0%

### Endpoints

- getAllOddsForEvent: 10 (100.0%)

### Quality tiers

- MEDIUM_CURRENT_ONLY: 7 (70.0%)
- HIGH: 3 (30.0%)

### Data status

- EXACT_CURRENT_ODDS_ONLY: 7 (70.0%)
- EXACT_BETTING_ODDS_WITH_OPENING: 3 (30.0%)

### Movement status

- OPENING_EQUALS_CURRENT: 7 (70.0%)
- REAL_OPENING_CURRENT_AVAILABLE: 3 (30.0%)

### Value status

- VALUE_STRONG: 8 (80.0%)
- NO_VALUE: 2 (20.0%)

### Numeric stats

- CorQ market weight: `{'count': 10, 'avg': 0.158, 'min': 0.12, 'max': 0.3}`
- Value delta pp: `{'count': 10, 'avg': 8.183, 'min': -0.29, 'max': 13.56}`
- Expected value pct: `{'count': 10, 'avg': 10.258, 'min': -7.01, 'max': 24.76}`

## Notes

- HIGH should represent exact TennisApi odds with real opening/current movement data.
- MEDIUM_CURRENT_ONLY is usable but should not carry full 30% MarQ influence.
- THIN_FALLBACK should remain close to zero influence and should be investigated if it grows.
- NO_MARQ/NO_TIER rows indicate missing audit fields or missing market data.
