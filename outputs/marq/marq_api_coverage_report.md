# MarQ API Coverage Report

Generated UTC: 2026-08-19T05:38:13.678901+00:00
Model: 2026-08-04-marq-coverage-report-v1

## all_audit

Rows: 32

### Coverage

- High MarQ: 56.25%
- Medium current-only: 43.75%
- Thin fallback: 0.0%
- No/unknown MarQ: 0.0%
- Usable High+Medium: 100.0%

### Endpoints

- getAllOddsForEvent: 32 (100.0%)

### Quality tiers

- HIGH: 18 (56.25%)
- MEDIUM_CURRENT_ONLY: 14 (43.75%)

### Data status

- EXACT_BETTING_ODDS_WITH_OPENING: 18 (56.25%)
- EXACT_CURRENT_ODDS_ONLY: 14 (43.75%)

### Movement status

- REAL_OPENING_CURRENT_AVAILABLE: 18 (56.25%)
- OPENING_EQUALS_CURRENT: 14 (43.75%)

### Value status

- NO_VALUE: 16 (50.0%)
- VALUE_STRONG: 15 (46.88%)
- VALUE_PLAYABLE: 1 (3.12%)

### Numeric stats

- CorQ market weight: `{'count': 32, 'avg': 0.1987, 'min': 0.12, 'max': 0.3}`
- Value delta pp: `{'count': 32, 'avg': 0.0, 'min': -24.33, 'max': 24.33}`
- Expected value pct: `{'count': 32, 'avg': 15.6359, 'min': -28.68, 'max': 361.4}`

## corq_top7

Rows: 5

### Coverage

- High MarQ: 60.0%
- Medium current-only: 40.0%
- Thin fallback: 0.0%
- No/unknown MarQ: 0.0%
- Usable High+Medium: 100.0%

### Endpoints

- getAllOddsForEvent: 5 (100.0%)

### Quality tiers

- HIGH: 3 (60.0%)
- MEDIUM_CURRENT_ONLY: 2 (40.0%)

### Data status

- EXACT_BETTING_ODDS_WITH_OPENING: 3 (60.0%)
- EXACT_CURRENT_ODDS_ONLY: 2 (40.0%)

### Movement status

- REAL_OPENING_CURRENT_AVAILABLE: 3 (60.0%)
- OPENING_EQUALS_CURRENT: 2 (40.0%)

### Value status

- NO_VALUE: 4 (80.0%)
- VALUE_PLAYABLE: 1 (20.0%)

### Numeric stats

- CorQ market weight: `{'count': 5, 'avg': 0.196, 'min': 0.12, 'max': 0.3}`
- Value delta pp: `{'count': 5, 'avg': -5.296, 'min': -10.77, 'max': 2.72}`
- Expected value pct: `{'count': 5, 'avg': -12.784, 'min': -20.64, 'max': -1.14}`

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
- Value delta pp: `{'count': 2, 'avg': 7.975, 'min': 7.25, 'max': 8.7}`
- Expected value pct: `{'count': 2, 'avg': 10.455, 'min': 7.78, 'max': 13.13}`

## Notes

- HIGH should represent exact TennisApi odds with real opening/current movement data.
- MEDIUM_CURRENT_ONLY is usable but should not carry full 30% MarQ influence.
- THIN_FALLBACK should remain close to zero influence and should be investigated if it grows.
- NO_MARQ/NO_TIER rows indicate missing audit fields or missing market data.
