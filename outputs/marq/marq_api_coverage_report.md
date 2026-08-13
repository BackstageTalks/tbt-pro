# MarQ API Coverage Report

Generated UTC: 2026-08-13T04:58:35.514811+00:00
Model: 2026-08-04-marq-coverage-report-v1

## all_audit

Rows: 94

### Coverage

- High MarQ: 46.81%
- Medium current-only: 42.55%
- Thin fallback: 0.0%
- No/unknown MarQ: 10.64%
- Usable High+Medium: 89.36%

### Endpoints

- getAllOddsForEvent: 84 (89.36%)
- NO_ENDPOINT: 10 (10.64%)

### Quality tiers

- HIGH: 44 (46.81%)
- MEDIUM_CURRENT_ONLY: 40 (42.55%)
- NO_MARQ: 10 (10.64%)

### Data status

- EXACT_BETTING_ODDS_WITH_OPENING: 44 (46.81%)
- EXACT_CURRENT_ODDS_ONLY: 40 (42.55%)
- NO_DATA_STATUS: 10 (10.64%)

### Movement status

- REAL_OPENING_CURRENT_AVAILABLE: 44 (46.81%)
- OPENING_EQUALS_CURRENT: 40 (42.55%)
- NO_MOVEMENT_STATUS: 10 (10.64%)

### Value status

- NO_VALUE: 43 (45.74%)
- VALUE_STRONG: 31 (32.98%)
- VALUE_PLAYABLE: 10 (10.64%)
- VALUE_UNKNOWN: 10 (10.64%)

### Numeric stats

- CorQ market weight: `{'count': 94, 'avg': 0.1719, 'min': 0.0, 'max': 0.3}`
- Value delta pp: `{'count': 84, 'avg': 0.0001, 'min': -24.03, 'max': 24.03}`
- Expected value pct: `{'count': 84, 'avg': -1.4556, 'min': -40.1, 'max': 68.8}`

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

- CorQ market weight: `{'count': 7, 'avg': 0.16, 'min': 0.12, 'max': 0.3}`
- Value delta pp: `{'count': 7, 'avg': 8.6529, 'min': 4.79, 'max': 15.19}`
- Expected value pct: `{'count': 7, 'avg': 10.3686, 'min': 2.91, 'max': 25.12}`

## cloq

Rows: 6

### Coverage

- High MarQ: 66.67%
- Medium current-only: 33.33%
- Thin fallback: 0.0%
- No/unknown MarQ: 0.0%
- Usable High+Medium: 100.0%

### Endpoints

- getAllOddsForEvent: 6 (100.0%)

### Quality tiers

- HIGH: 4 (66.67%)
- MEDIUM_CURRENT_ONLY: 2 (33.33%)

### Data status

- EXACT_BETTING_ODDS_WITH_OPENING: 4 (66.67%)
- EXACT_CURRENT_ODDS_ONLY: 2 (33.33%)

### Movement status

- REAL_OPENING_CURRENT_AVAILABLE: 4 (66.67%)
- OPENING_EQUALS_CURRENT: 2 (33.33%)

### Value status

- VALUE_PLAYABLE: 3 (50.0%)
- VALUE_STRONG: 2 (33.33%)
- NO_VALUE: 1 (16.67%)

### Numeric stats

- CorQ market weight: `{'count': 6, 'avg': 0.2133, 'min': 0.12, 'max': 0.3}`
- Value delta pp: `{'count': 6, 'avg': 3.965, 'min': -0.42, 'max': 9.88}`
- Expected value pct: `{'count': 6, 'avg': 2.3933, 'min': -5.87, 'max': 14.5}`

## Notes

- HIGH should represent exact TennisApi odds with real opening/current movement data.
- MEDIUM_CURRENT_ONLY is usable but should not carry full 30% MarQ influence.
- THIN_FALLBACK should remain close to zero influence and should be investigated if it grows.
- NO_MARQ/NO_TIER rows indicate missing audit fields or missing market data.
