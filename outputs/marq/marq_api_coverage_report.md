# MarQ API Coverage Report

Generated UTC: 2026-08-11T08:47:36.188383+00:00
Model: 2026-08-04-marq-coverage-report-v1

## all_audit

Rows: 100

### Coverage

- High MarQ: 2.0%
- Medium current-only: 98.0%
- Thin fallback: 0.0%
- No/unknown MarQ: 0.0%
- Usable High+Medium: 100.0%

### Endpoints

- getAllOddsForEvent: 100 (100.0%)

### Quality tiers

- MEDIUM_CURRENT_ONLY: 98 (98.0%)
- HIGH: 2 (2.0%)

### Data status

- EXACT_CURRENT_ODDS_ONLY: 98 (98.0%)
- EXACT_BETTING_ODDS_WITH_OPENING: 2 (2.0%)

### Movement status

- OPENING_EQUALS_CURRENT: 98 (98.0%)
- REAL_OPENING_CURRENT_AVAILABLE: 2 (2.0%)

### Value status

- NO_VALUE: 53 (53.0%)
- VALUE_STRONG: 39 (39.0%)
- VALUE_PLAYABLE: 8 (8.0%)

### Numeric stats

- CorQ market weight: `{'count': 100, 'avg': 0.1208, 'min': 0.1, 'max': 0.3}`
- Value delta pp: `{'count': 100, 'avg': -0.0128, 'min': -35.8, 'max': 35.8}`
- Expected value pct: `{'count': 100, 'avg': 2.4349, 'min': -44.89, 'max': 227.6}`

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

- VALUE_STRONG: 7 (100.0%)

### Numeric stats

- CorQ market weight: `{'count': 7, 'avg': 0.1457, 'min': 0.12, 'max': 0.3}`
- Value delta pp: `{'count': 7, 'avg': 10.7829, 'min': 6.62, 'max': 13.98}`
- Expected value pct: `{'count': 7, 'avg': 13.5543, 'min': 3.33, 'max': 24.76}`

## cloq

Rows: 8

### Coverage

- High MarQ: 12.5%
- Medium current-only: 87.5%
- Thin fallback: 0.0%
- No/unknown MarQ: 0.0%
- Usable High+Medium: 100.0%

### Endpoints

- getAllOddsForEvent: 8 (100.0%)

### Quality tiers

- MEDIUM_CURRENT_ONLY: 7 (87.5%)
- HIGH: 1 (12.5%)

### Data status

- EXACT_CURRENT_ODDS_ONLY: 7 (87.5%)
- EXACT_BETTING_ODDS_WITH_OPENING: 1 (12.5%)

### Movement status

- OPENING_EQUALS_CURRENT: 7 (87.5%)
- REAL_OPENING_CURRENT_AVAILABLE: 1 (12.5%)

### Value status

- VALUE_STRONG: 7 (87.5%)
- NO_VALUE: 1 (12.5%)

### Numeric stats

- CorQ market weight: `{'count': 8, 'avg': 0.1425, 'min': 0.12, 'max': 0.3}`
- Value delta pp: `{'count': 8, 'avg': 8.7137, 'min': 0.19, 'max': 13.56}`
- Expected value pct: `{'count': 8, 'avg': 11.1288, 'min': -7.01, 'max': 24.76}`

## Notes

- HIGH should represent exact TennisApi odds with real opening/current movement data.
- MEDIUM_CURRENT_ONLY is usable but should not carry full 30% MarQ influence.
- THIN_FALLBACK should remain close to zero influence and should be investigated if it grows.
- NO_MARQ/NO_TIER rows indicate missing audit fields or missing market data.
