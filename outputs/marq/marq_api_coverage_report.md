# MarQ API Coverage Report

Generated UTC: 2026-08-27T21:14:53.458135+00:00
Model: 2026-08-04-marq-coverage-report-v1

## all_audit

Rows: 86

### Coverage

- High MarQ: 18.6%
- Medium current-only: 81.4%
- Thin fallback: 0.0%
- No/unknown MarQ: 0.0%
- Usable High+Medium: 100.0%

### Endpoints

- getAllOddsForEvent: 86 (100.0%)

### Quality tiers

- MEDIUM_CURRENT_ONLY: 70 (81.4%)
- HIGH: 16 (18.6%)

### Data status

- EXACT_CURRENT_ODDS_ONLY: 70 (81.4%)
- EXACT_BETTING_ODDS_WITH_OPENING: 16 (18.6%)

### Movement status

- OPENING_EQUALS_CURRENT: 70 (81.4%)
- REAL_OPENING_CURRENT_AVAILABLE: 16 (18.6%)

### Value status

- NO_VALUE: 43 (50.0%)
- VALUE_STRONG: 40 (46.51%)
- VALUE_PLAYABLE: 3 (3.49%)

### Numeric stats

- CorQ market weight: `{'count': 86, 'avg': 0.1456, 'min': 0.1, 'max': 0.3}`
- Value delta pp: `{'count': 86, 'avg': 0.0, 'min': -36.84, 'max': 36.84}`
- Expected value pct: `{'count': 86, 'avg': 7.3426, 'min': -41.88, 'max': 770.45}`

## corq_top7

Rows: 7

### Coverage

- High MarQ: 28.57%
- Medium current-only: 71.43%
- Thin fallback: 0.0%
- No/unknown MarQ: 0.0%
- Usable High+Medium: 100.0%

### Endpoints

- getAllOddsForEvent: 7 (100.0%)

### Quality tiers

- MEDIUM_CURRENT_ONLY: 5 (71.43%)
- HIGH: 2 (28.57%)

### Data status

- EXACT_CURRENT_ODDS_ONLY: 5 (71.43%)
- EXACT_BETTING_ODDS_WITH_OPENING: 2 (28.57%)

### Movement status

- OPENING_EQUALS_CURRENT: 5 (71.43%)
- REAL_OPENING_CURRENT_AVAILABLE: 2 (28.57%)

### Value status

- NO_VALUE: 4 (57.14%)
- VALUE_STRONG: 3 (42.86%)

### Numeric stats

- CorQ market weight: `{'count': 7, 'avg': 0.16, 'min': 0.12, 'max': 0.3}`
- Value delta pp: `{'count': 7, 'avg': -1.1486, 'min': -10.06, 'max': 10.47}`
- Expected value pct: `{'count': 7, 'avg': -6.46, 'min': -19.44, 'max': 16.08}`

## cloq

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

- VALUE_STRONG: 6 (85.71%)
- NO_VALUE: 1 (14.29%)

### Numeric stats

- CorQ market weight: `{'count': 7, 'avg': 0.1457, 'min': 0.12, 'max': 0.3}`
- Value delta pp: `{'count': 7, 'avg': 5.5943, 'min': -1.99, 'max': 10.43}`
- Expected value pct: `{'count': 7, 'avg': 3.3814, 'min': -10.75, 'max': 14.83}`

## Notes

- HIGH should represent exact TennisApi odds with real opening/current movement data.
- MEDIUM_CURRENT_ONLY is usable but should not carry full 30% MarQ influence.
- THIN_FALLBACK should remain close to zero influence and should be investigated if it grows.
- NO_MARQ/NO_TIER rows indicate missing audit fields or missing market data.
