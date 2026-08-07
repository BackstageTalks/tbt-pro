# MarQ API Coverage Report

Generated UTC: 2026-08-07T11:49:35.987177+00:00
Model: 2026-08-04-marq-coverage-report-v1

## all_audit

Rows: 36

### Coverage

- High MarQ: 88.89%
- Medium current-only: 11.11%
- Thin fallback: 0.0%
- No/unknown MarQ: 0.0%
- Usable High+Medium: 100.0%

### Endpoints

- getAllOddsForEvent: 36 (100.0%)

### Quality tiers

- HIGH: 32 (88.89%)
- MEDIUM_CURRENT_ONLY: 4 (11.11%)

### Data status

- EXACT_BETTING_ODDS_WITH_OPENING: 32 (88.89%)
- EXACT_CURRENT_ODDS_ONLY: 4 (11.11%)

### Movement status

- REAL_OPENING_CURRENT_AVAILABLE: 32 (88.89%)
- OPENING_EQUALS_CURRENT: 4 (11.11%)

### Value status

- NO_VALUE: 19 (52.78%)
- VALUE_STRONG: 15 (41.67%)
- VALUE_PLAYABLE: 2 (5.56%)

### Numeric stats

- CorQ market weight: `{'count': 36, 'avg': 0.2444, 'min': 0.12, 'max': 0.3}`
- Value delta pp: `{'count': 36, 'avg': 0.0, 'min': -20.54, 'max': 20.54}`
- Expected value pct: `{'count': 36, 'avg': 6.8153, 'min': -28.72, 'max': 201.2}`

## corq_top7

Rows: 3

### Coverage

- High MarQ: 66.67%
- Medium current-only: 33.33%
- Thin fallback: 0.0%
- No/unknown MarQ: 0.0%
- Usable High+Medium: 100.0%

### Endpoints

- getAllOddsForEvent: 3 (100.0%)

### Quality tiers

- HIGH: 2 (66.67%)
- MEDIUM_CURRENT_ONLY: 1 (33.33%)

### Data status

- EXACT_BETTING_ODDS_WITH_OPENING: 2 (66.67%)
- EXACT_CURRENT_ODDS_ONLY: 1 (33.33%)

### Movement status

- REAL_OPENING_CURRENT_AVAILABLE: 2 (66.67%)
- OPENING_EQUALS_CURRENT: 1 (33.33%)

### Value status

- NO_VALUE: 2 (66.67%)
- VALUE_STRONG: 1 (33.33%)

### Numeric stats

- CorQ market weight: `{'count': 3, 'avg': 0.2133, 'min': 0.12, 'max': 0.3}`
- Value delta pp: `{'count': 3, 'avg': -0.6, 'min': -10.07, 'max': 8.08}`
- Expected value pct: `{'count': 3, 'avg': -5.2833, 'min': -20.5, 'max': 8.84}`

## cloq

Rows: 1

### Coverage

- High MarQ: 0.0%
- Medium current-only: 100.0%
- Thin fallback: 0.0%
- No/unknown MarQ: 0.0%
- Usable High+Medium: 100.0%

### Endpoints

- getAllOddsForEvent: 1 (100.0%)

### Quality tiers

- MEDIUM_CURRENT_ONLY: 1 (100.0%)

### Data status

- EXACT_CURRENT_ODDS_ONLY: 1 (100.0%)

### Movement status

- OPENING_EQUALS_CURRENT: 1 (100.0%)

### Value status

- VALUE_STRONG: 1 (100.0%)

### Numeric stats

- CorQ market weight: `{'count': 1, 'avg': 0.12, 'min': 0.12, 'max': 0.12}`
- Value delta pp: `{'count': 1, 'avg': 8.08, 'min': 8.08, 'max': 8.08}`
- Expected value pct: `{'count': 1, 'avg': 8.84, 'min': 8.84, 'max': 8.84}`

## Notes

- HIGH should represent exact TennisApi odds with real opening/current movement data.
- MEDIUM_CURRENT_ONLY is usable but should not carry full 30% MarQ influence.
- THIN_FALLBACK should remain close to zero influence and should be investigated if it grows.
- NO_MARQ/NO_TIER rows indicate missing audit fields or missing market data.
