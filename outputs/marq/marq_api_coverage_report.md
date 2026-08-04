# MarQ API Coverage Report

Generated UTC: 2026-08-04T15:19:01.375718+00:00
Model: 2026-08-04-marq-coverage-report-v1

## all_audit

Rows: 112

### Coverage

- High MarQ: 60.71%
- Medium current-only: 39.29%
- Thin fallback: 0.0%
- No/unknown MarQ: 0.0%
- Usable High+Medium: 100.0%

### Endpoints

- getAllOddsForEvent: 112 (100.0%)

### Quality tiers

- HIGH: 68 (60.71%)
- MEDIUM_CURRENT_ONLY: 44 (39.29%)

### Data status

- EXACT_BETTING_ODDS_WITH_OPENING: 68 (60.71%)
- EXACT_CURRENT_ODDS_ONLY: 44 (39.29%)

### Movement status

- REAL_OPENING_CURRENT_AVAILABLE: 68 (60.71%)
- OPENING_EQUALS_CURRENT: 44 (39.29%)

### Value status

- NO_VALUE: 55 (49.11%)
- VALUE_STRONG: 39 (34.82%)
- VALUE_PLAYABLE: 18 (16.07%)

### Numeric stats

- CorQ market weight: `{'count': 112, 'avg': 0.2046, 'min': 0.1, 'max': 0.3}`
- Value delta pp: `{'count': 112, 'avg': 0.0, 'min': -26.92, 'max': 26.92}`
- Expected value pct: `{'count': 112, 'avg': 4.1536, 'min': -37.73, 'max': 233.4}`

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
- VALUE_PLAYABLE: 1 (14.29%)

### Numeric stats

- CorQ market weight: `{'count': 7, 'avg': 0.2257, 'min': 0.12, 'max': 0.3}`
- Value delta pp: `{'count': 7, 'avg': -1.0129, 'min': -8.46, 'max': 3.67}`
- Expected value pct: `{'count': 7, 'avg': -5.8529, 'min': -12.64, 'max': 0.99}`

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
- Value delta pp: `{'count': 1, 'avg': 4.75, 'min': 4.75, 'max': 4.75}`
- Expected value pct: `{'count': 1, 'avg': 4.57, 'min': 4.57, 'max': 4.57}`

## Notes

- HIGH should represent exact TennisApi odds with real opening/current movement data.
- MEDIUM_CURRENT_ONLY is usable but should not carry full 30% MarQ influence.
- THIN_FALLBACK should remain close to zero influence and should be investigated if it grows.
- NO_MARQ/NO_TIER rows indicate missing audit fields or missing market data.
