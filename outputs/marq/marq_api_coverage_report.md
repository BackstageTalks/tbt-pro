# MarQ API Coverage Report

Generated UTC: 2026-08-26T04:28:08.943671+00:00
Model: 2026-08-04-marq-coverage-report-v1

## all_audit

Rows: 160

### Coverage

- High MarQ: 5.0%
- Medium current-only: 55.0%
- Thin fallback: 0.0%
- No/unknown MarQ: 40.0%
- Usable High+Medium: 60.0%

### Endpoints

- getAllOddsForEvent: 96 (60.0%)
- NO_ENDPOINT: 64 (40.0%)

### Quality tiers

- MEDIUM_CURRENT_ONLY: 88 (55.0%)
- NO_MARQ: 64 (40.0%)
- HIGH: 8 (5.0%)

### Data status

- EXACT_CURRENT_ODDS_ONLY: 88 (55.0%)
- NO_DATA_STATUS: 64 (40.0%)
- EXACT_BETTING_ODDS_WITH_OPENING: 8 (5.0%)

### Movement status

- OPENING_EQUALS_CURRENT: 88 (55.0%)
- NO_MOVEMENT_STATUS: 64 (40.0%)
- REAL_OPENING_CURRENT_AVAILABLE: 8 (5.0%)

### Value status

- VALUE_UNKNOWN: 64 (40.0%)
- NO_VALUE: 49 (30.63%)
- VALUE_STRONG: 40 (25.0%)
- VALUE_PLAYABLE: 7 (4.38%)

### Numeric stats

- CorQ market weight: `{'count': 160, 'avg': 0.0783, 'min': 0.0, 'max': 0.3}`
- Value delta pp: `{'count': 96, 'avg': 0.0, 'min': -37.39, 'max': 37.39}`
- Expected value pct: `{'count': 96, 'avg': 6.2086, 'min': -45.8, 'max': 311.23}`

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

- NO_VALUE: 6 (85.71%)
- VALUE_PLAYABLE: 1 (14.29%)

### Numeric stats

- CorQ market weight: `{'count': 7, 'avg': 0.1457, 'min': 0.12, 'max': 0.3}`
- Value delta pp: `{'count': 7, 'avg': -3.5071, 'min': -7.29, 'max': 1.99}`
- Expected value pct: `{'count': 7, 'avg': -11.1043, 'min': -17.43, 'max': -1.74}`

## cloq

Rows: 10

### Coverage

- High MarQ: 10.0%
- Medium current-only: 90.0%
- Thin fallback: 0.0%
- No/unknown MarQ: 0.0%
- Usable High+Medium: 100.0%

### Endpoints

- getAllOddsForEvent: 10 (100.0%)

### Quality tiers

- MEDIUM_CURRENT_ONLY: 9 (90.0%)
- HIGH: 1 (10.0%)

### Data status

- EXACT_CURRENT_ODDS_ONLY: 9 (90.0%)
- EXACT_BETTING_ODDS_WITH_OPENING: 1 (10.0%)

### Movement status

- OPENING_EQUALS_CURRENT: 9 (90.0%)
- REAL_OPENING_CURRENT_AVAILABLE: 1 (10.0%)

### Value status

- VALUE_STRONG: 6 (60.0%)
- NO_VALUE: 3 (30.0%)
- VALUE_PLAYABLE: 1 (10.0%)

### Numeric stats

- CorQ market weight: `{'count': 10, 'avg': 0.136, 'min': 0.1, 'max': 0.3}`
- Value delta pp: `{'count': 10, 'avg': 4.153, 'min': -1.96, 'max': 12.72}`
- Expected value pct: `{'count': 10, 'avg': 1.125, 'min': -9.7, 'max': 21.14}`

## Notes

- HIGH should represent exact TennisApi odds with real opening/current movement data.
- MEDIUM_CURRENT_ONLY is usable but should not carry full 30% MarQ influence.
- THIN_FALLBACK should remain close to zero influence and should be investigated if it grows.
- NO_MARQ/NO_TIER rows indicate missing audit fields or missing market data.
