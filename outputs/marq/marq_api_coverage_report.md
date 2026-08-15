# MarQ API Coverage Report

Generated UTC: 2026-08-15T11:33:55.605457+00:00
Model: 2026-08-04-marq-coverage-report-v1

## all_audit

Rows: 64

### Coverage

- High MarQ: 81.25%
- Medium current-only: 18.75%
- Thin fallback: 0.0%
- No/unknown MarQ: 0.0%
- Usable High+Medium: 100.0%

### Endpoints

- getAllOddsForEvent: 64 (100.0%)

### Quality tiers

- HIGH: 52 (81.25%)
- MEDIUM_CURRENT_ONLY: 12 (18.75%)

### Data status

- EXACT_BETTING_ODDS_WITH_OPENING: 52 (81.25%)
- EXACT_CURRENT_ODDS_ONLY: 12 (18.75%)

### Movement status

- REAL_OPENING_CURRENT_AVAILABLE: 52 (81.25%)
- OPENING_EQUALS_CURRENT: 12 (18.75%)

### Value status

- NO_VALUE: 33 (51.56%)
- VALUE_STRONG: 26 (40.62%)
- VALUE_PLAYABLE: 4 (6.25%)
- VALUE_NEUTRAL: 1 (1.56%)

### Numeric stats

- CorQ market weight: `{'count': 64, 'avg': 0.2337, 'min': 0.12, 'max': 0.3}`
- Value delta pp: `{'count': 64, 'avg': 0.0, 'min': -27.9, 'max': 27.9}`
- Expected value pct: `{'count': 64, 'avg': 4.96, 'min': -35.27, 'max': 274.8}`

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
- VALUE_NEUTRAL: 1 (14.29%)

### Numeric stats

- CorQ market weight: `{'count': 7, 'avg': 0.2257, 'min': 0.12, 'max': 0.3}`
- Value delta pp: `{'count': 7, 'avg': -0.2871, 'min': -3.6, 'max': 3.96}`
- Expected value pct: `{'count': 7, 'avg': -4.98, 'min': -9.59, 'max': 1.46}`

## cloq

Rows: 9

### Coverage

- High MarQ: 88.89%
- Medium current-only: 11.11%
- Thin fallback: 0.0%
- No/unknown MarQ: 0.0%
- Usable High+Medium: 100.0%

### Endpoints

- getAllOddsForEvent: 9 (100.0%)

### Quality tiers

- HIGH: 8 (88.89%)
- MEDIUM_CURRENT_ONLY: 1 (11.11%)

### Data status

- EXACT_BETTING_ODDS_WITH_OPENING: 8 (88.89%)
- EXACT_CURRENT_ODDS_ONLY: 1 (11.11%)

### Movement status

- REAL_OPENING_CURRENT_AVAILABLE: 8 (88.89%)
- OPENING_EQUALS_CURRENT: 1 (11.11%)

### Value status

- VALUE_STRONG: 8 (88.89%)
- NO_VALUE: 1 (11.11%)

### Numeric stats

- CorQ market weight: `{'count': 9, 'avg': 0.2622, 'min': 0.12, 'max': 0.3}`
- Value delta pp: `{'count': 9, 'avg': 9.0178, 'min': -0.17, 'max': 19.02}`
- Expected value pct: `{'count': 9, 'avg': 12.7667, 'min': -5.57, 'max': 39.87}`

## Notes

- HIGH should represent exact TennisApi odds with real opening/current movement data.
- MEDIUM_CURRENT_ONLY is usable but should not carry full 30% MarQ influence.
- THIN_FALLBACK should remain close to zero influence and should be investigated if it grows.
- NO_MARQ/NO_TIER rows indicate missing audit fields or missing market data.
