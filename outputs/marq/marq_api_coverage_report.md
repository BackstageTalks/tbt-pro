# MarQ API Coverage Report

Generated UTC: 2026-08-31T06:58:08.085039+00:00
Model: 2026-08-04-marq-coverage-report-v1

## all_audit

Rows: 114

### Coverage

- High MarQ: 77.19%
- Medium current-only: 22.81%
- Thin fallback: 0.0%
- No/unknown MarQ: 0.0%
- Usable High+Medium: 100.0%

### Endpoints

- getAllOddsForEvent: 114 (100.0%)

### Quality tiers

- HIGH: 88 (77.19%)
- MEDIUM_CURRENT_ONLY: 26 (22.81%)

### Data status

- EXACT_BETTING_ODDS_WITH_OPENING: 88 (77.19%)
- EXACT_CURRENT_ODDS_ONLY: 26 (22.81%)

### Movement status

- REAL_OPENING_CURRENT_AVAILABLE: 88 (77.19%)
- OPENING_EQUALS_CURRENT: 26 (22.81%)

### Value status

- NO_VALUE: 57 (50.0%)
- VALUE_STRONG: 54 (47.37%)
- VALUE_PLAYABLE: 3 (2.63%)

### Numeric stats

- CorQ market weight: `{'count': 114, 'avg': 0.2281, 'min': 0.12, 'max': 0.3}`
- Value delta pp: `{'count': 114, 'avg': 0.4021, 'min': -33.68, 'max': 33.68}`
- Expected value pct: `{'count': 114, 'avg': 25.8601, 'min': -42.97, 'max': 260.7}`

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

- NO_VALUE: 7 (100.0%)

### Numeric stats

- CorQ market weight: `{'count': 7, 'avg': 0.2657, 'min': 0.22, 'max': 0.3}`
- Value delta pp: `{'count': 7, 'avg': -6.8343, 'min': -11.37, 'max': 0.03}`
- Expected value pct: `{'count': 7, 'avg': -14.9514, 'min': -21.61, 'max': -4.91}`

## cloq

Rows: 3

### Coverage

- High MarQ: 100.0%
- Medium current-only: 0.0%
- Thin fallback: 0.0%
- No/unknown MarQ: 0.0%
- Usable High+Medium: 100.0%

### Endpoints

- getAllOddsForEvent: 3 (100.0%)

### Quality tiers

- HIGH: 3 (100.0%)

### Data status

- EXACT_BETTING_ODDS_WITH_OPENING: 3 (100.0%)

### Movement status

- REAL_OPENING_CURRENT_AVAILABLE: 3 (100.0%)

### Value status

- VALUE_PLAYABLE: 1 (33.33%)
- VALUE_STRONG: 1 (33.33%)
- NO_VALUE: 1 (33.33%)

### Numeric stats

- CorQ market weight: `{'count': 3, 'avg': 0.2733, 'min': 0.22, 'max': 0.3}`
- Value delta pp: `{'count': 3, 'avg': 3.2033, 'min': -0.63, 'max': 7.39}`
- Expected value pct: `{'count': 3, 'avg': 0.9933, 'min': -6.4, 'max': 9.52}`

## Notes

- HIGH should represent exact TennisApi odds with real opening/current movement data.
- MEDIUM_CURRENT_ONLY is usable but should not carry full 30% MarQ influence.
- THIN_FALLBACK should remain close to zero influence and should be investigated if it grows.
- NO_MARQ/NO_TIER rows indicate missing audit fields or missing market data.
