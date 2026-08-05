# MarQ API Coverage Report

Generated UTC: 2026-08-05T06:44:57.926007+00:00
Model: 2026-08-04-marq-coverage-report-v1

## all_audit

Rows: 104

### Coverage

- High MarQ: 36.54%
- Medium current-only: 63.46%
- Thin fallback: 0.0%
- No/unknown MarQ: 0.0%
- Usable High+Medium: 100.0%

### Endpoints

- getAllOddsForEvent: 104 (100.0%)

### Quality tiers

- MEDIUM_CURRENT_ONLY: 66 (63.46%)
- HIGH: 38 (36.54%)

### Data status

- EXACT_CURRENT_ODDS_ONLY: 66 (63.46%)
- EXACT_BETTING_ODDS_WITH_OPENING: 38 (36.54%)

### Movement status

- OPENING_EQUALS_CURRENT: 66 (63.46%)
- REAL_OPENING_CURRENT_AVAILABLE: 38 (36.54%)

### Value status

- NO_VALUE: 51 (49.04%)
- VALUE_STRONG: 40 (38.46%)
- VALUE_PLAYABLE: 7 (6.73%)
- VALUE_UNKNOWN: 6 (5.77%)

### Numeric stats

- CorQ market weight: `{'count': 104, 'avg': 0.1712, 'min': 0.12, 'max': 0.3}`
- Value delta pp: `{'count': 98, 'avg': 0.0, 'min': -26.82, 'max': 26.82}`
- Expected value pct: `{'count': 98, 'avg': 12.115, 'min': -35.49, 'max': 219.8}`

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

- VALUE_STRONG: 3 (42.86%)
- NO_VALUE: 3 (42.86%)
- VALUE_PLAYABLE: 1 (14.29%)

### Numeric stats

- CorQ market weight: `{'count': 7, 'avg': 0.16, 'min': 0.12, 'max': 0.3}`
- Value delta pp: `{'count': 7, 'avg': 4.0171, 'min': -3.01, 'max': 19.16}`
- Expected value pct: `{'count': 7, 'avg': 3.4114, 'min': -8.99, 'max': 40.21}`

## cloq

Rows: 3

### Coverage

- High MarQ: 33.33%
- Medium current-only: 66.67%
- Thin fallback: 0.0%
- No/unknown MarQ: 0.0%
- Usable High+Medium: 100.0%

### Endpoints

- getAllOddsForEvent: 3 (100.0%)

### Quality tiers

- MEDIUM_CURRENT_ONLY: 2 (66.67%)
- HIGH: 1 (33.33%)

### Data status

- EXACT_CURRENT_ODDS_ONLY: 2 (66.67%)
- EXACT_BETTING_ODDS_WITH_OPENING: 1 (33.33%)

### Movement status

- OPENING_EQUALS_CURRENT: 2 (66.67%)
- REAL_OPENING_CURRENT_AVAILABLE: 1 (33.33%)

### Value status

- VALUE_STRONG: 3 (100.0%)

### Numeric stats

- CorQ market weight: `{'count': 3, 'avg': 0.18, 'min': 0.12, 'max': 0.3}`
- Value delta pp: `{'count': 3, 'avg': 9.8333, 'min': 4.93, 'max': 19.16}`
- Expected value pct: `{'count': 3, 'avg': 16.4733, 'min': 3.38, 'max': 40.21}`

## Notes

- HIGH should represent exact TennisApi odds with real opening/current movement data.
- MEDIUM_CURRENT_ONLY is usable but should not carry full 30% MarQ influence.
- THIN_FALLBACK should remain close to zero influence and should be investigated if it grows.
- NO_MARQ/NO_TIER rows indicate missing audit fields or missing market data.
