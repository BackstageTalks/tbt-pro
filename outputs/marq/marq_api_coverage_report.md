# MarQ API Coverage Report

Generated UTC: 2026-08-15T07:52:00.013368+00:00
Model: 2026-08-04-marq-coverage-report-v1

## all_audit

Rows: 64

### Coverage

- High MarQ: 71.88%
- Medium current-only: 28.12%
- Thin fallback: 0.0%
- No/unknown MarQ: 0.0%
- Usable High+Medium: 100.0%

### Endpoints

- getAllOddsForEvent: 64 (100.0%)

### Quality tiers

- HIGH: 46 (71.88%)
- MEDIUM_CURRENT_ONLY: 18 (28.12%)

### Data status

- EXACT_BETTING_ODDS_WITH_OPENING: 46 (71.88%)
- EXACT_CURRENT_ODDS_ONLY: 18 (28.12%)

### Movement status

- REAL_OPENING_CURRENT_AVAILABLE: 46 (71.88%)
- OPENING_EQUALS_CURRENT: 18 (28.12%)

### Value status

- NO_VALUE: 34 (53.12%)
- VALUE_STRONG: 26 (40.62%)
- VALUE_PLAYABLE: 4 (6.25%)

### Numeric stats

- CorQ market weight: `{'count': 64, 'avg': 0.2206, 'min': 0.12, 'max': 0.3}`
- Value delta pp: `{'count': 64, 'avg': 0.0, 'min': -26.85, 'max': 26.85}`
- Expected value pct: `{'count': 64, 'avg': 3.8914, 'min': -35.27, 'max': 237.32}`

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

- VALUE_STRONG: 6 (85.71%)
- VALUE_PLAYABLE: 1 (14.29%)

### Numeric stats

- CorQ market weight: `{'count': 7, 'avg': 0.2657, 'min': 0.22, 'max': 0.3}`
- Value delta pp: `{'count': 7, 'avg': 8.2343, 'min': 2.25, 'max': 19.02}`
- Expected value pct: `{'count': 7, 'avg': 11.1943, 'min': -1.31, 'max': 39.87}`

## cloq

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

- VALUE_STRONG: 2 (66.67%)
- NO_VALUE: 1 (33.33%)

### Numeric stats

- CorQ market weight: `{'count': 3, 'avg': 0.24, 'min': 0.12, 'max': 0.3}`
- Value delta pp: `{'count': 3, 'avg': 6.62, 'min': -0.17, 'max': 10.91}`
- Expected value pct: `{'count': 3, 'avg': 7.99, 'min': -5.57, 'max': 16.56}`

## Notes

- HIGH should represent exact TennisApi odds with real opening/current movement data.
- MEDIUM_CURRENT_ONLY is usable but should not carry full 30% MarQ influence.
- THIN_FALLBACK should remain close to zero influence and should be investigated if it grows.
- NO_MARQ/NO_TIER rows indicate missing audit fields or missing market data.
