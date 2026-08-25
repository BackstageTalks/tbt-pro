# MarQ API Coverage Report

Generated UTC: 2026-08-25T05:42:35.421858+00:00
Model: 2026-08-04-marq-coverage-report-v1

## all_audit

Rows: 184

### Coverage

- High MarQ: 6.52%
- Medium current-only: 83.7%
- Thin fallback: 0.0%
- No/unknown MarQ: 9.78%
- Usable High+Medium: 90.22%

### Endpoints

- getAllOddsForEvent: 166 (90.22%)
- NO_ENDPOINT: 18 (9.78%)

### Quality tiers

- MEDIUM_CURRENT_ONLY: 154 (83.7%)
- NO_MARQ: 18 (9.78%)
- HIGH: 12 (6.52%)

### Data status

- EXACT_CURRENT_ODDS_ONLY: 154 (83.7%)
- NO_DATA_STATUS: 18 (9.78%)
- EXACT_BETTING_ODDS_WITH_OPENING: 12 (6.52%)

### Movement status

- OPENING_EQUALS_CURRENT: 154 (83.7%)
- NO_MOVEMENT_STATUS: 18 (9.78%)
- REAL_OPENING_CURRENT_AVAILABLE: 12 (6.52%)

### Value status

- NO_VALUE: 87 (47.28%)
- VALUE_STRONG: 67 (36.41%)
- VALUE_UNKNOWN: 18 (9.78%)
- VALUE_PLAYABLE: 12 (6.52%)

### Numeric stats

- CorQ market weight: `{'count': 184, 'avg': 0.1148, 'min': 0.0, 'max': 0.3}`
- Value delta pp: `{'count': 166, 'avg': 0.0001, 'min': -43.45, 'max': 43.45}`
- Expected value pct: `{'count': 166, 'avg': 16.7774, 'min': -48.36, 'max': 648.2}`

## corq_top7

Rows: 7

### Coverage

- High MarQ: 0.0%
- Medium current-only: 100.0%
- Thin fallback: 0.0%
- No/unknown MarQ: 0.0%
- Usable High+Medium: 100.0%

### Endpoints

- getAllOddsForEvent: 7 (100.0%)

### Quality tiers

- MEDIUM_CURRENT_ONLY: 7 (100.0%)

### Data status

- EXACT_CURRENT_ODDS_ONLY: 7 (100.0%)

### Movement status

- OPENING_EQUALS_CURRENT: 7 (100.0%)

### Value status

- VALUE_PLAYABLE: 3 (42.86%)
- VALUE_STRONG: 2 (28.57%)
- NO_VALUE: 2 (28.57%)

### Numeric stats

- CorQ market weight: `{'count': 7, 'avg': 0.12, 'min': 0.12, 'max': 0.12}`
- Value delta pp: `{'count': 7, 'avg': 3.8757, 'min': -2.63, 'max': 15.08}`
- Expected value pct: `{'count': 7, 'avg': 2.1486, 'min': -8.42, 'max': 28.99}`

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

- VALUE_STRONG: 7 (70.0%)
- VALUE_PLAYABLE: 2 (20.0%)
- NO_VALUE: 1 (10.0%)

### Numeric stats

- CorQ market weight: `{'count': 10, 'avg': 0.174, 'min': 0.12, 'max': 0.3}`
- Value delta pp: `{'count': 10, 'avg': 4.901, 'min': -1.87, 'max': 18.4}`
- Expected value pct: `{'count': 10, 'avg': 3.633, 'min': -10.54, 'max': 39.75}`

## Notes

- HIGH should represent exact TennisApi odds with real opening/current movement data.
- MEDIUM_CURRENT_ONLY is usable but should not carry full 30% MarQ influence.
- THIN_FALLBACK should remain close to zero influence and should be investigated if it grows.
- NO_MARQ/NO_TIER rows indicate missing audit fields or missing market data.
