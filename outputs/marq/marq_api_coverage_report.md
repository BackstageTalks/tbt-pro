# MarQ API Coverage Report

Generated UTC: 2026-08-06T04:41:12.669443+00:00
Model: 2026-08-04-marq-coverage-report-v1

## all_audit

Rows: 54

### Coverage

- High MarQ: 70.37%
- Medium current-only: 29.63%
- Thin fallback: 0.0%
- No/unknown MarQ: 0.0%
- Usable High+Medium: 100.0%

### Endpoints

- getAllOddsForEvent: 54 (100.0%)

### Quality tiers

- HIGH: 38 (70.37%)
- MEDIUM_CURRENT_ONLY: 16 (29.63%)

### Data status

- EXACT_BETTING_ODDS_WITH_OPENING: 38 (70.37%)
- EXACT_CURRENT_ODDS_ONLY: 16 (29.63%)

### Movement status

- REAL_OPENING_CURRENT_AVAILABLE: 38 (70.37%)
- OPENING_EQUALS_CURRENT: 16 (29.63%)

### Value status

- NO_VALUE: 28 (51.85%)
- VALUE_STRONG: 24 (44.44%)
- VALUE_PLAYABLE: 2 (3.7%)

### Numeric stats

- CorQ market weight: `{'count': 54, 'avg': 0.2185, 'min': 0.12, 'max': 0.3}`
- Value delta pp: `{'count': 54, 'avg': 0.0, 'min': -26.19, 'max': 26.19}`
- Expected value pct: `{'count': 54, 'avg': 10.0285, 'min': -37.5, 'max': 250.1}`

## corq_top7

Rows: 7

### Coverage

- High MarQ: 85.71%
- Medium current-only: 14.29%
- Thin fallback: 0.0%
- No/unknown MarQ: 0.0%
- Usable High+Medium: 100.0%

### Endpoints

- getAllOddsForEvent: 7 (100.0%)

### Quality tiers

- HIGH: 6 (85.71%)
- MEDIUM_CURRENT_ONLY: 1 (14.29%)

### Data status

- EXACT_BETTING_ODDS_WITH_OPENING: 6 (85.71%)
- EXACT_CURRENT_ODDS_ONLY: 1 (14.29%)

### Movement status

- REAL_OPENING_CURRENT_AVAILABLE: 6 (85.71%)
- OPENING_EQUALS_CURRENT: 1 (14.29%)

### Value status

- VALUE_STRONG: 4 (57.14%)
- NO_VALUE: 2 (28.57%)
- VALUE_PLAYABLE: 1 (14.29%)

### Numeric stats

- CorQ market weight: `{'count': 7, 'avg': 0.2743, 'min': 0.12, 'max': 0.3}`
- Value delta pp: `{'count': 7, 'avg': 4.0286, 'min': -1.43, 'max': 9.71}`
- Expected value pct: `{'count': 7, 'avg': 2.4029, 'min': -6.62, 'max': 15.25}`

## cloq

Rows: 1

### Coverage

- High MarQ: 100.0%
- Medium current-only: 0.0%
- Thin fallback: 0.0%
- No/unknown MarQ: 0.0%
- Usable High+Medium: 100.0%

### Endpoints

- getAllOddsForEvent: 1 (100.0%)

### Quality tiers

- HIGH: 1 (100.0%)

### Data status

- EXACT_BETTING_ODDS_WITH_OPENING: 1 (100.0%)

### Movement status

- REAL_OPENING_CURRENT_AVAILABLE: 1 (100.0%)

### Value status

- VALUE_STRONG: 1 (100.0%)

### Numeric stats

- CorQ market weight: `{'count': 1, 'avg': 0.3, 'min': 0.3, 'max': 0.3}`
- Value delta pp: `{'count': 1, 'avg': 5.71, 'min': 5.71, 'max': 5.71}`
- Expected value pct: `{'count': 1, 'avg': 4.73, 'min': 4.73, 'max': 4.73}`

## Notes

- HIGH should represent exact TennisApi odds with real opening/current movement data.
- MEDIUM_CURRENT_ONLY is usable but should not carry full 30% MarQ influence.
- THIN_FALLBACK should remain close to zero influence and should be investigated if it grows.
- NO_MARQ/NO_TIER rows indicate missing audit fields or missing market data.
