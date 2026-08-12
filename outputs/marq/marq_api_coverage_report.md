# MarQ API Coverage Report

Generated UTC: 2026-08-12T10:21:34.462369+00:00
Model: 2026-08-04-marq-coverage-report-v1

## all_audit

Rows: 64

### Coverage

- High MarQ: 9.38%
- Medium current-only: 87.5%
- Thin fallback: 0.0%
- No/unknown MarQ: 3.12%
- Usable High+Medium: 96.88%

### Endpoints

- getAllOddsForEvent: 62 (96.88%)
- NO_ENDPOINT: 2 (3.12%)

### Quality tiers

- MEDIUM_CURRENT_ONLY: 56 (87.5%)
- HIGH: 6 (9.38%)
- NO_MARQ: 2 (3.12%)

### Data status

- EXACT_CURRENT_ODDS_ONLY: 56 (87.5%)
- EXACT_BETTING_ODDS_WITH_OPENING: 6 (9.38%)
- NO_DATA_STATUS: 2 (3.12%)

### Movement status

- OPENING_EQUALS_CURRENT: 56 (87.5%)
- REAL_OPENING_CURRENT_AVAILABLE: 6 (9.38%)
- NO_MOVEMENT_STATUS: 2 (3.12%)

### Value status

- NO_VALUE: 34 (53.12%)
- VALUE_STRONG: 25 (39.06%)
- VALUE_PLAYABLE: 3 (4.69%)
- VALUE_UNKNOWN: 2 (3.12%)

### Numeric stats

- CorQ market weight: `{'count': 64, 'avg': 0.1288, 'min': 0.0, 'max': 0.3}`
- Value delta pp: `{'count': 62, 'avg': -1.0026, 'min': -45.17, 'max': 17.49}`
- Expected value pct: `{'count': 62, 'avg': -3.2084, 'min': -36.43, 'max': 79.55}`

## corq_top7

Rows: 7

### Coverage

- High MarQ: 0.0%
- Medium current-only: 100.0%
- Thin fallback: 0.0%
- No/unknown MarQ: 0.0%
- Usable High+Medium: 100.0%

### Endpoints

- getAllOddsForEvent: 7 (100.0%)

### Quality tiers

- MEDIUM_CURRENT_ONLY: 7 (100.0%)

### Data status

- EXACT_CURRENT_ODDS_ONLY: 7 (100.0%)

### Movement status

- OPENING_EQUALS_CURRENT: 7 (100.0%)

### Value status

- VALUE_STRONG: 6 (85.71%)
- VALUE_PLAYABLE: 1 (14.29%)

### Numeric stats

- CorQ market weight: `{'count': 7, 'avg': 0.12, 'min': 0.12, 'max': 0.12}`
- Value delta pp: `{'count': 7, 'avg': 9.28, 'min': 0.6, 'max': 13.98}`
- Expected value pct: `{'count': 7, 'avg': 9.1386, 'min': -6.38, 'max': 18.34}`

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

- VALUE_STRONG: 7 (70.0%)
- NO_VALUE: 3 (30.0%)

### Numeric stats

- CorQ market weight: `{'count': 10, 'avg': 0.138, 'min': 0.12, 'max': 0.3}`
- Value delta pp: `{'count': 10, 'avg': 6.573, 'min': -1.86, 'max': 13.05}`
- Expected value pct: `{'count': 10, 'avg': 5.899, 'min': -10.53, 'max': 19.26}`

## Notes

- HIGH should represent exact TennisApi odds with real opening/current movement data.
- MEDIUM_CURRENT_ONLY is usable but should not carry full 30% MarQ influence.
- THIN_FALLBACK should remain close to zero influence and should be investigated if it grows.
- NO_MARQ/NO_TIER rows indicate missing audit fields or missing market data.
