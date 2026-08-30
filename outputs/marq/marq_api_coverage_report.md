# MarQ API Coverage Report

Generated UTC: 2026-08-30T12:54:56.769903+00:00
Model: 2026-08-04-marq-coverage-report-v1

## all_audit

Rows: 80

### Coverage

- High MarQ: 80.0%
- Medium current-only: 20.0%
- Thin fallback: 0.0%
- No/unknown MarQ: 0.0%
- Usable High+Medium: 100.0%

### Endpoints

- getAllOddsForEvent: 80 (100.0%)

### Quality tiers

- HIGH: 64 (80.0%)
- MEDIUM_CURRENT_ONLY: 16 (20.0%)

### Data status

- EXACT_BETTING_ODDS_WITH_OPENING: 64 (80.0%)
- EXACT_CURRENT_ODDS_ONLY: 16 (20.0%)

### Movement status

- REAL_OPENING_CURRENT_AVAILABLE: 64 (80.0%)
- OPENING_EQUALS_CURRENT: 16 (20.0%)

### Value status

- NO_VALUE: 42 (52.5%)
- VALUE_STRONG: 33 (41.25%)
- VALUE_PLAYABLE: 5 (6.25%)

### Numeric stats

- CorQ market weight: `{'count': 80, 'avg': 0.232, 'min': 0.12, 'max': 0.3}`
- Value delta pp: `{'count': 80, 'avg': 0.0, 'min': -33.68, 'max': 33.68}`
- Expected value pct: `{'count': 80, 'avg': 20.2896, 'min': -42.97, 'max': 270.26}`

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

- NO_VALUE: 5 (71.43%)
- VALUE_PLAYABLE: 1 (14.29%)
- VALUE_STRONG: 1 (14.29%)

### Numeric stats

- CorQ market weight: `{'count': 7, 'avg': 0.1743, 'min': 0.12, 'max': 0.3}`
- Value delta pp: `{'count': 7, 'avg': -2.6943, 'min': -8.83, 'max': 14.6}`
- Expected value pct: `{'count': 7, 'avg': -6.9443, 'min': -16.91, 'max': 31.42}`

## cloq

Rows: 10

### Coverage

- High MarQ: 90.0%
- Medium current-only: 10.0%
- Thin fallback: 0.0%
- No/unknown MarQ: 0.0%
- Usable High+Medium: 100.0%

### Endpoints

- getAllOddsForEvent: 10 (100.0%)

### Quality tiers

- HIGH: 9 (90.0%)
- MEDIUM_CURRENT_ONLY: 1 (10.0%)

### Data status

- EXACT_BETTING_ODDS_WITH_OPENING: 9 (90.0%)
- EXACT_CURRENT_ODDS_ONLY: 1 (10.0%)

### Movement status

- REAL_OPENING_CURRENT_AVAILABLE: 9 (90.0%)
- OPENING_EQUALS_CURRENT: 1 (10.0%)

### Value status

- VALUE_STRONG: 5 (50.0%)
- VALUE_PLAYABLE: 3 (30.0%)
- NO_VALUE: 2 (20.0%)

### Numeric stats

- CorQ market weight: `{'count': 10, 'avg': 0.242, 'min': 0.12, 'max': 0.3}`
- Value delta pp: `{'count': 10, 'avg': 4.487, 'min': -1.87, 'max': 13.53}`
- Expected value pct: `{'count': 10, 'avg': 4.192, 'min': -8.63, 'max': 26.18}`

## Notes

- HIGH should represent exact TennisApi odds with real opening/current movement data.
- MEDIUM_CURRENT_ONLY is usable but should not carry full 30% MarQ influence.
- THIN_FALLBACK should remain close to zero influence and should be investigated if it grows.
- NO_MARQ/NO_TIER rows indicate missing audit fields or missing market data.
