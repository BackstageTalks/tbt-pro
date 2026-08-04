# MarQ API Coverage Report

Generated UTC: 2026-08-04T11:50:53.263013+00:00
Model: 2026-08-04-marq-coverage-report-v1

## all_audit

Rows: 114

### Coverage

- High MarQ: 8.77%
- Medium current-only: 91.23%
- Thin fallback: 0.0%
- No/unknown MarQ: 0.0%
- Usable High+Medium: 100.0%

### Endpoints

- getMatchWinningOdds: 100 (87.72%)
- getAllOddsForEvent: 14 (12.28%)

### Quality tiers

- MEDIUM_CURRENT_ONLY: 104 (91.23%)
- HIGH: 10 (8.77%)

### Data status

- EXACT_CURRENT_ODDS_ONLY: 104 (91.23%)
- EXACT_BETTING_ODDS_WITH_OPENING: 10 (8.77%)

### Movement status

- CURRENT_ONLY_NO_REAL_OPENING: 100 (87.72%)
- REAL_OPENING_CURRENT_AVAILABLE: 10 (8.77%)
- OPENING_EQUALS_CURRENT: 4 (3.51%)

### Value status

- NO_VALUE: 55 (48.25%)
- VALUE_STRONG: 41 (35.96%)
- VALUE_PLAYABLE: 16 (14.04%)
- VALUE_NEUTRAL: 2 (1.75%)

### Numeric stats

- CorQ market weight: `{'count': 114, 'avg': 0.1316, 'min': 0.1, 'max': 0.3}`
- Value delta pp: `{'count': 114, 'avg': 0.0, 'min': -40.87, 'max': 40.87}`
- Expected value pct: `{'count': 114, 'avg': 9.6648, 'min': -46.3, 'max': 609.5}`

## corq_top7

Rows: 7

### Coverage

- High MarQ: 0.0%
- Medium current-only: 100.0%
- Thin fallback: 0.0%
- No/unknown MarQ: 0.0%
- Usable High+Medium: 100.0%

### Endpoints

- getMatchWinningOdds: 7 (100.0%)

### Quality tiers

- MEDIUM_CURRENT_ONLY: 7 (100.0%)

### Data status

- EXACT_CURRENT_ODDS_ONLY: 7 (100.0%)

### Movement status

- CURRENT_ONLY_NO_REAL_OPENING: 7 (100.0%)

### Value status

- VALUE_PLAYABLE: 3 (42.86%)
- VALUE_STRONG: 3 (42.86%)
- VALUE_NEUTRAL: 1 (14.29%)

### Numeric stats

- CorQ market weight: `{'count': 7, 'avg': 0.12, 'min': 0.12, 'max': 0.12}`
- Value delta pp: `{'count': 7, 'avg': 2.9814, 'min': -2.37, 'max': 10.59}`
- Expected value pct: `{'count': 7, 'avg': 1.4386, 'min': -3.07, 'max': 17.1}`

## cloq

Rows: 2

### Coverage

- High MarQ: 0.0%
- Medium current-only: 100.0%
- Thin fallback: 0.0%
- No/unknown MarQ: 0.0%
- Usable High+Medium: 100.0%

### Endpoints

- getMatchWinningOdds: 2 (100.0%)

### Quality tiers

- MEDIUM_CURRENT_ONLY: 2 (100.0%)

### Data status

- EXACT_CURRENT_ODDS_ONLY: 2 (100.0%)

### Movement status

- CURRENT_ONLY_NO_REAL_OPENING: 2 (100.0%)

### Value status

- VALUE_STRONG: 2 (100.0%)

### Numeric stats

- CorQ market weight: `{'count': 2, 'avg': 0.12, 'min': 0.12, 'max': 0.12}`
- Value delta pp: `{'count': 2, 'avg': 5.09, 'min': 4.75, 'max': 5.43}`
- Expected value pct: `{'count': 2, 'avg': 4.29, 'min': 4.01, 'max': 4.57}`

## Notes

- HIGH should represent exact TennisApi odds with real opening/current movement data.
- MEDIUM_CURRENT_ONLY is usable but should not carry full 30% MarQ influence.
- THIN_FALLBACK should remain close to zero influence and should be investigated if it grows.
- NO_MARQ/NO_TIER rows indicate missing audit fields or missing market data.
