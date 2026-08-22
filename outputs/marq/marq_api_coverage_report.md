# MarQ API Coverage Report

Generated UTC: 2026-08-22T15:18:49.854541+00:00
Model: 2026-08-04-marq-coverage-report-v1

## all_audit

Rows: 40

### Coverage

- High MarQ: 25.0%
- Medium current-only: 75.0%
- Thin fallback: 0.0%
- No/unknown MarQ: 0.0%
- Usable High+Medium: 100.0%

### Endpoints

- getAllOddsForEvent: 40 (100.0%)

### Quality tiers

- MEDIUM_CURRENT_ONLY: 30 (75.0%)
- HIGH: 10 (25.0%)

### Data status

- EXACT_CURRENT_ODDS_ONLY: 30 (75.0%)
- EXACT_BETTING_ODDS_WITH_OPENING: 10 (25.0%)

### Movement status

- OPENING_EQUALS_CURRENT: 30 (75.0%)
- REAL_OPENING_CURRENT_AVAILABLE: 10 (25.0%)

### Value status

- NO_VALUE: 21 (52.5%)
- VALUE_STRONG: 17 (42.5%)
- VALUE_PLAYABLE: 2 (5.0%)

### Numeric stats

- CorQ market weight: `{'count': 40, 'avg': 0.148, 'min': 0.1, 'max': 0.3}`
- Value delta pp: `{'count': 40, 'avg': 0.0, 'min': -43.67, 'max': 43.67}`
- Expected value pct: `{'count': 40, 'avg': 37.8725, 'min': -48.09, 'max': 739.12}`

## corq_top7

Rows: 7

### Coverage

- High MarQ: 14.29%
- Medium current-only: 85.71%
- Thin fallback: 0.0%
- No/unknown MarQ: 0.0%
- Usable High+Medium: 100.0%

### Endpoints

- getAllOddsForEvent: 7 (100.0%)

### Quality tiers

- MEDIUM_CURRENT_ONLY: 6 (85.71%)
- HIGH: 1 (14.29%)

### Data status

- EXACT_CURRENT_ODDS_ONLY: 6 (85.71%)
- EXACT_BETTING_ODDS_WITH_OPENING: 1 (14.29%)

### Movement status

- OPENING_EQUALS_CURRENT: 6 (85.71%)
- REAL_OPENING_CURRENT_AVAILABLE: 1 (14.29%)

### Value status

- NO_VALUE: 5 (71.43%)
- VALUE_STRONG: 1 (14.29%)
- VALUE_PLAYABLE: 1 (14.29%)

### Numeric stats

- CorQ market weight: `{'count': 7, 'avg': 0.1286, 'min': 0.1, 'max': 0.22}`
- Value delta pp: `{'count': 7, 'avg': -1.5729, 'min': -14.57, 'max': 13.44}`
- Expected value pct: `{'count': 7, 'avg': -6.9829, 'min': -24.95, 'max': 25.09}`

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
- Value delta pp: `{'count': 1, 'avg': 8.7, 'min': 8.7, 'max': 8.7}`
- Expected value pct: `{'count': 1, 'avg': 7.61, 'min': 7.61, 'max': 7.61}`

## Notes

- HIGH should represent exact TennisApi odds with real opening/current movement data.
- MEDIUM_CURRENT_ONLY is usable but should not carry full 30% MarQ influence.
- THIN_FALLBACK should remain close to zero influence and should be investigated if it grows.
- NO_MARQ/NO_TIER rows indicate missing audit fields or missing market data.
