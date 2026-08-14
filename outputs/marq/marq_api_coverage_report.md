# MarQ API Coverage Report

Generated UTC: 2026-08-14T04:25:08.351173+00:00
Model: 2026-08-04-marq-coverage-report-v1

## all_audit

Rows: 80

### Coverage

- High MarQ: 42.5%
- Medium current-only: 57.5%
- Thin fallback: 0.0%
- No/unknown MarQ: 0.0%
- Usable High+Medium: 100.0%

### Endpoints

- getAllOddsForEvent: 80 (100.0%)

### Quality tiers

- MEDIUM_CURRENT_ONLY: 46 (57.5%)
- HIGH: 34 (42.5%)

### Data status

- EXACT_CURRENT_ODDS_ONLY: 46 (57.5%)
- EXACT_BETTING_ODDS_WITH_OPENING: 34 (42.5%)

### Movement status

- OPENING_EQUALS_CURRENT: 46 (57.5%)
- REAL_OPENING_CURRENT_AVAILABLE: 34 (42.5%)

### Value status

- NO_VALUE: 40 (50.0%)
- VALUE_STRONG: 32 (40.0%)
- VALUE_PLAYABLE: 6 (7.5%)
- VALUE_UNKNOWN: 2 (2.5%)

### Numeric stats

- CorQ market weight: `{'count': 80, 'avg': 0.1795, 'min': 0.12, 'max': 0.3}`
- Value delta pp: `{'count': 78, 'avg': 0.0331, 'min': -22.93, 'max': 22.93}`
- Expected value pct: `{'count': 78, 'avg': -0.0071, 'min': -35.77, 'max': 68.8}`

## corq_top7

Rows: 7

### Coverage

- High MarQ: 42.86%
- Medium current-only: 57.14%
- Thin fallback: 0.0%
- No/unknown MarQ: 0.0%
- Usable High+Medium: 100.0%

### Endpoints

- getAllOddsForEvent: 7 (100.0%)

### Quality tiers

- MEDIUM_CURRENT_ONLY: 4 (57.14%)
- HIGH: 3 (42.86%)

### Data status

- EXACT_CURRENT_ODDS_ONLY: 4 (57.14%)
- EXACT_BETTING_ODDS_WITH_OPENING: 3 (42.86%)

### Movement status

- OPENING_EQUALS_CURRENT: 4 (57.14%)
- REAL_OPENING_CURRENT_AVAILABLE: 3 (42.86%)

### Value status

- VALUE_STRONG: 7 (100.0%)

### Numeric stats

- CorQ market weight: `{'count': 7, 'avg': 0.1743, 'min': 0.12, 'max': 0.3}`
- Value delta pp: `{'count': 7, 'avg': 9.5114, 'min': 6.39, 'max': 15.19}`
- Expected value pct: `{'count': 7, 'avg': 12.8229, 'min': 5.11, 'max': 25.12}`

## cloq

Rows: 5

### Coverage

- High MarQ: 40.0%
- Medium current-only: 60.0%
- Thin fallback: 0.0%
- No/unknown MarQ: 0.0%
- Usable High+Medium: 100.0%

### Endpoints

- getAllOddsForEvent: 5 (100.0%)

### Quality tiers

- MEDIUM_CURRENT_ONLY: 3 (60.0%)
- HIGH: 2 (40.0%)

### Data status

- EXACT_CURRENT_ODDS_ONLY: 3 (60.0%)
- EXACT_BETTING_ODDS_WITH_OPENING: 2 (40.0%)

### Movement status

- OPENING_EQUALS_CURRENT: 3 (60.0%)
- REAL_OPENING_CURRENT_AVAILABLE: 2 (40.0%)

### Value status

- VALUE_STRONG: 4 (80.0%)
- VALUE_PLAYABLE: 1 (20.0%)

### Numeric stats

- CorQ market weight: `{'count': 5, 'avg': 0.176, 'min': 0.12, 'max': 0.3}`
- Value delta pp: `{'count': 5, 'avg': 8.99, 'min': 1.98, 'max': 16.0}`
- Expected value pct: `{'count': 5, 'avg': 13.866, 'min': -1.7, 'max': 32.68}`

## Notes

- HIGH should represent exact TennisApi odds with real opening/current movement data.
- MEDIUM_CURRENT_ONLY is usable but should not carry full 30% MarQ influence.
- THIN_FALLBACK should remain close to zero influence and should be investigated if it grows.
- NO_MARQ/NO_TIER rows indicate missing audit fields or missing market data.
