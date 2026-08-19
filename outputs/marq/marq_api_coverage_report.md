# MarQ API Coverage Report

Generated UTC: 2026-08-19T13:26:49.806614+00:00
Model: 2026-08-04-marq-coverage-report-v1

## all_audit

Rows: 32

### Coverage

- High MarQ: 62.5%
- Medium current-only: 37.5%
- Thin fallback: 0.0%
- No/unknown MarQ: 0.0%
- Usable High+Medium: 100.0%

### Endpoints

- getAllOddsForEvent: 32 (100.0%)

### Quality tiers

- HIGH: 20 (62.5%)
- MEDIUM_CURRENT_ONLY: 12 (37.5%)

### Data status

- EXACT_BETTING_ODDS_WITH_OPENING: 20 (62.5%)
- EXACT_CURRENT_ODDS_ONLY: 12 (37.5%)

### Movement status

- REAL_OPENING_CURRENT_AVAILABLE: 20 (62.5%)
- OPENING_EQUALS_CURRENT: 12 (37.5%)

### Value status

- NO_VALUE: 15 (46.88%)
- VALUE_STRONG: 15 (46.88%)
- VALUE_PLAYABLE: 2 (6.25%)

### Numeric stats

- CorQ market weight: `{'count': 32, 'avg': 0.2075, 'min': 0.12, 'max': 0.3}`
- Value delta pp: `{'count': 32, 'avg': -0.4159, 'min': -30.87, 'max': 24.33}`
- Expected value pct: `{'count': 32, 'avg': 16.8869, 'min': -35.42, 'max': 361.4}`

## corq_top7

Rows: 4

### Coverage

- High MarQ: 75.0%
- Medium current-only: 25.0%
- Thin fallback: 0.0%
- No/unknown MarQ: 0.0%
- Usable High+Medium: 100.0%

### Endpoints

- getAllOddsForEvent: 4 (100.0%)

### Quality tiers

- HIGH: 3 (75.0%)
- MEDIUM_CURRENT_ONLY: 1 (25.0%)

### Data status

- EXACT_BETTING_ODDS_WITH_OPENING: 3 (75.0%)
- EXACT_CURRENT_ODDS_ONLY: 1 (25.0%)

### Movement status

- REAL_OPENING_CURRENT_AVAILABLE: 3 (75.0%)
- OPENING_EQUALS_CURRENT: 1 (25.0%)

### Value status

- NO_VALUE: 3 (75.0%)
- VALUE_PLAYABLE: 1 (25.0%)

### Numeric stats

- CorQ market weight: `{'count': 4, 'avg': 0.215, 'min': 0.12, 'max': 0.3}`
- Value delta pp: `{'count': 4, 'avg': -6.335, 'min': -15.84, 'max': 2.72}`
- Expected value pct: `{'count': 4, 'avg': -14.685, 'min': -28.3, 'max': -1.14}`

## cloq

Rows: 2

### Coverage

- High MarQ: 50.0%
- Medium current-only: 50.0%
- Thin fallback: 0.0%
- No/unknown MarQ: 0.0%
- Usable High+Medium: 100.0%

### Endpoints

- getAllOddsForEvent: 2 (100.0%)

### Quality tiers

- HIGH: 1 (50.0%)
- MEDIUM_CURRENT_ONLY: 1 (50.0%)

### Data status

- EXACT_BETTING_ODDS_WITH_OPENING: 1 (50.0%)
- EXACT_CURRENT_ODDS_ONLY: 1 (50.0%)

### Movement status

- REAL_OPENING_CURRENT_AVAILABLE: 1 (50.0%)
- OPENING_EQUALS_CURRENT: 1 (50.0%)

### Value status

- VALUE_STRONG: 2 (100.0%)

### Numeric stats

- CorQ market weight: `{'count': 2, 'avg': 0.17, 'min': 0.12, 'max': 0.22}`
- Value delta pp: `{'count': 2, 'avg': 6.04, 'min': 4.94, 'max': 7.14}`
- Expected value pct: `{'count': 2, 'avg': 6.74, 'min': 3.63, 'max': 9.85}`

## Notes

- HIGH should represent exact TennisApi odds with real opening/current movement data.
- MEDIUM_CURRENT_ONLY is usable but should not carry full 30% MarQ influence.
- THIN_FALLBACK should remain close to zero influence and should be investigated if it grows.
- NO_MARQ/NO_TIER rows indicate missing audit fields or missing market data.
