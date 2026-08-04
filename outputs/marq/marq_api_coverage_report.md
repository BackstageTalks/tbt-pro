# MarQ API Coverage Report

Generated UTC: 2026-08-04T17:02:01.606261+00:00
Model: 2026-08-04-marq-coverage-report-v1

## all_audit

Rows: 112

### Coverage

- High MarQ: 66.07%
- Medium current-only: 33.93%
- Thin fallback: 0.0%
- No/unknown MarQ: 0.0%
- Usable High+Medium: 100.0%

### Endpoints

- getAllOddsForEvent: 112 (100.0%)

### Quality tiers

- HIGH: 74 (66.07%)
- MEDIUM_CURRENT_ONLY: 38 (33.93%)

### Data status

- EXACT_BETTING_ODDS_WITH_OPENING: 74 (66.07%)
- EXACT_CURRENT_ODDS_ONLY: 38 (33.93%)

### Movement status

- REAL_OPENING_CURRENT_AVAILABLE: 74 (66.07%)
- OPENING_EQUALS_CURRENT: 38 (33.93%)

### Value status

- NO_VALUE: 55 (49.11%)
- VALUE_STRONG: 41 (36.61%)
- VALUE_PLAYABLE: 16 (14.29%)

### Numeric stats

- CorQ market weight: `{'count': 112, 'avg': 0.2125, 'min': 0.12, 'max': 0.3}`
- Value delta pp: `{'count': 112, 'avg': 0.0, 'min': -49.31, 'max': 49.31}`
- Expected value pct: `{'count': 112, 'avg': 54.9232, 'min': -50.24, 'max': 4979.29}`

## corq_top7

Rows: 7

### Coverage

- High MarQ: 71.43%
- Medium current-only: 28.57%
- Thin fallback: 0.0%
- No/unknown MarQ: 0.0%
- Usable High+Medium: 100.0%

### Endpoints

- getAllOddsForEvent: 7 (100.0%)

### Quality tiers

- HIGH: 5 (71.43%)
- MEDIUM_CURRENT_ONLY: 2 (28.57%)

### Data status

- EXACT_BETTING_ODDS_WITH_OPENING: 5 (71.43%)
- EXACT_CURRENT_ODDS_ONLY: 2 (28.57%)

### Movement status

- REAL_OPENING_CURRENT_AVAILABLE: 5 (71.43%)
- OPENING_EQUALS_CURRENT: 2 (28.57%)

### Value status

- NO_VALUE: 4 (57.14%)
- VALUE_STRONG: 2 (28.57%)
- VALUE_PLAYABLE: 1 (14.29%)

### Numeric stats

- CorQ market weight: `{'count': 7, 'avg': 0.2371, 'min': 0.12, 'max': 0.3}`
- Value delta pp: `{'count': 7, 'avg': 0.1129, 'min': -3.54, 'max': 3.67}`
- Expected value pct: `{'count': 7, 'avg': -4.8886, 'min': -10.51, 'max': 0.99}`

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
- Value delta pp: `{'count': 1, 'avg': 4.75, 'min': 4.75, 'max': 4.75}`
- Expected value pct: `{'count': 1, 'avg': 4.57, 'min': 4.57, 'max': 4.57}`

## Notes

- HIGH should represent exact TennisApi odds with real opening/current movement data.
- MEDIUM_CURRENT_ONLY is usable but should not carry full 30% MarQ influence.
- THIN_FALLBACK should remain close to zero influence and should be investigated if it grows.
- NO_MARQ/NO_TIER rows indicate missing audit fields or missing market data.
