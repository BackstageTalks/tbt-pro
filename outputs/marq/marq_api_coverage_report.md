# MarQ API Coverage Report

Generated UTC: 2026-08-27T05:36:43.292828+00:00
Model: 2026-08-04-marq-coverage-report-v1

## all_audit

Rows: 84

### Coverage

- High MarQ: 7.14%
- Medium current-only: 33.33%
- Thin fallback: 0.0%
- No/unknown MarQ: 59.52%
- Usable High+Medium: 40.48%

### Endpoints

- NO_ENDPOINT: 50 (59.52%)
- getAllOddsForEvent: 34 (40.48%)

### Quality tiers

- NO_MARQ: 50 (59.52%)
- MEDIUM_CURRENT_ONLY: 28 (33.33%)
- HIGH: 6 (7.14%)

### Data status

- NO_DATA_STATUS: 50 (59.52%)
- EXACT_CURRENT_ODDS_ONLY: 28 (33.33%)
- EXACT_BETTING_ODDS_WITH_OPENING: 6 (7.14%)

### Movement status

- NO_MOVEMENT_STATUS: 50 (59.52%)
- OPENING_EQUALS_CURRENT: 28 (33.33%)
- REAL_OPENING_CURRENT_AVAILABLE: 6 (7.14%)

### Value status

- VALUE_UNKNOWN: 50 (59.52%)
- NO_VALUE: 17 (20.24%)
- VALUE_STRONG: 16 (19.05%)
- VALUE_PLAYABLE: 1 (1.19%)

### Numeric stats

- CorQ market weight: `{'count': 84, 'avg': 0.0581, 'min': 0.0, 'max': 0.3}`
- Value delta pp: `{'count': 34, 'avg': 0.0, 'min': -20.55, 'max': 20.55}`
- Expected value pct: `{'count': 34, 'avg': 0.5862, 'min': -32.86, 'max': 61.33}`

## corq_top7

Rows: 7

### Coverage

- High MarQ: 14.29%
- Medium current-only: 85.71%
- Thin fallback: 0.0%
- No/unknown MarQ: 0.0%
- Usable High+Medium: 100.0%

### Endpoints

- getAllOddsForEvent: 7 (100.0%)

### Quality tiers

- MEDIUM_CURRENT_ONLY: 6 (85.71%)
- HIGH: 1 (14.29%)

### Data status

- EXACT_CURRENT_ODDS_ONLY: 6 (85.71%)
- EXACT_BETTING_ODDS_WITH_OPENING: 1 (14.29%)

### Movement status

- OPENING_EQUALS_CURRENT: 6 (85.71%)
- REAL_OPENING_CURRENT_AVAILABLE: 1 (14.29%)

### Value status

- NO_VALUE: 7 (100.0%)

### Numeric stats

- CorQ market weight: `{'count': 7, 'avg': 0.1343, 'min': 0.12, 'max': 0.22}`
- Value delta pp: `{'count': 7, 'avg': -6.3629, 'min': -12.71, 'max': -2.8}`
- Expected value pct: `{'count': 7, 'avg': -15.1886, 'min': -22.34, 'max': -9.83}`

## cloq

Rows: 4

### Coverage

- High MarQ: 50.0%
- Medium current-only: 50.0%
- Thin fallback: 0.0%
- No/unknown MarQ: 0.0%
- Usable High+Medium: 100.0%

### Endpoints

- getAllOddsForEvent: 4 (100.0%)

### Quality tiers

- MEDIUM_CURRENT_ONLY: 2 (50.0%)
- HIGH: 2 (50.0%)

### Data status

- EXACT_CURRENT_ODDS_ONLY: 2 (50.0%)
- EXACT_BETTING_ODDS_WITH_OPENING: 2 (50.0%)

### Movement status

- OPENING_EQUALS_CURRENT: 2 (50.0%)
- REAL_OPENING_CURRENT_AVAILABLE: 2 (50.0%)

### Value status

- VALUE_STRONG: 4 (100.0%)

### Numeric stats

- CorQ market weight: `{'count': 4, 'avg': 0.19, 'min': 0.12, 'max': 0.3}`
- Value delta pp: `{'count': 4, 'avg': 7.27, 'min': 3.2, 'max': 14.21}`
- Expected value pct: `{'count': 4, 'avg': 8.7425, 'min': 0.39, 'max': 26.92}`

## Notes

- HIGH should represent exact TennisApi odds with real opening/current movement data.
- MEDIUM_CURRENT_ONLY is usable but should not carry full 30% MarQ influence.
- THIN_FALLBACK should remain close to zero influence and should be investigated if it grows.
- NO_MARQ/NO_TIER rows indicate missing audit fields or missing market data.
