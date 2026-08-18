# MarQ API Coverage Report

Generated UTC: 2026-08-18T05:57:20.239018+00:00
Model: 2026-08-04-marq-coverage-report-v1

## all_audit

Rows: 32

### Coverage

- High MarQ: 81.25%
- Medium current-only: 18.75%
- Thin fallback: 0.0%
- No/unknown MarQ: 0.0%
- Usable High+Medium: 100.0%

### Endpoints

- getAllOddsForEvent: 32 (100.0%)

### Quality tiers

- HIGH: 26 (81.25%)
- MEDIUM_CURRENT_ONLY: 6 (18.75%)

### Data status

- EXACT_BETTING_ODDS_WITH_OPENING: 26 (81.25%)
- EXACT_CURRENT_ODDS_ONLY: 6 (18.75%)

### Movement status

- REAL_OPENING_CURRENT_AVAILABLE: 26 (81.25%)
- OPENING_EQUALS_CURRENT: 6 (18.75%)

### Value status

- NO_VALUE: 16 (50.0%)
- VALUE_STRONG: 14 (43.75%)
- VALUE_PLAYABLE: 2 (6.25%)

### Numeric stats

- CorQ market weight: `{'count': 32, 'avg': 0.2337, 'min': 0.12, 'max': 0.3}`
- Value delta pp: `{'count': 32, 'avg': 0.0016, 'min': -21.6, 'max': 21.6}`
- Expected value pct: `{'count': 32, 'avg': 13.4275, 'min': -27.49, 'max': 190.07}`

## corq_top7

Rows: 4

### Coverage

- High MarQ: 75.0%
- Medium current-only: 25.0%
- Thin fallback: 0.0%
- No/unknown MarQ: 0.0%
- Usable High+Medium: 100.0%

### Endpoints

- getAllOddsForEvent: 4 (100.0%)

### Quality tiers

- HIGH: 3 (75.0%)
- MEDIUM_CURRENT_ONLY: 1 (25.0%)

### Data status

- EXACT_BETTING_ODDS_WITH_OPENING: 3 (75.0%)
- EXACT_CURRENT_ODDS_ONLY: 1 (25.0%)

### Movement status

- REAL_OPENING_CURRENT_AVAILABLE: 3 (75.0%)
- OPENING_EQUALS_CURRENT: 1 (25.0%)

### Value status

- VALUE_STRONG: 2 (50.0%)
- NO_VALUE: 2 (50.0%)

### Numeric stats

- CorQ market weight: `{'count': 4, 'avg': 0.215, 'min': 0.12, 'max': 0.3}`
- Value delta pp: `{'count': 4, 'avg': 2.0425, 'min': -4.02, 'max': 9.06}`
- Expected value pct: `{'count': 4, 'avg': -0.2775, 'min': -11.24, 'max': 14.86}`

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

- VALUE_STRONG: 2 (66.67%)
- VALUE_PLAYABLE: 1 (33.33%)

### Numeric stats

- CorQ market weight: `{'count': 3, 'avg': 0.18, 'min': 0.12, 'max': 0.3}`
- Value delta pp: `{'count': 3, 'avg': 4.89, 'min': 2.4, 'max': 6.38}`
- Expected value pct: `{'count': 3, 'avg': 3.4267, 'min': -0.95, 'max': 5.89}`

## Notes

- HIGH should represent exact TennisApi odds with real opening/current movement data.
- MEDIUM_CURRENT_ONLY is usable but should not carry full 30% MarQ influence.
- THIN_FALLBACK should remain close to zero influence and should be investigated if it grows.
- NO_MARQ/NO_TIER rows indicate missing audit fields or missing market data.
