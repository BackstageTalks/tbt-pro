# MarQ API Coverage Report

Generated UTC: 2026-08-04T13:32:55.585002+00:00
Model: 2026-08-04-marq-coverage-report-v1

## all_audit

Rows: 112

### Coverage

- High MarQ: 64.29%
- Medium current-only: 35.71%
- Thin fallback: 0.0%
- No/unknown MarQ: 0.0%
- Usable High+Medium: 100.0%

### Endpoints

- getAllOddsForEvent: 112 (100.0%)

### Quality tiers

- HIGH: 72 (64.29%)
- MEDIUM_CURRENT_ONLY: 40 (35.71%)

### Data status

- EXACT_BETTING_ODDS_WITH_OPENING: 72 (64.29%)
- EXACT_CURRENT_ODDS_ONLY: 40 (35.71%)

### Movement status

- REAL_OPENING_CURRENT_AVAILABLE: 72 (64.29%)
- OPENING_EQUALS_CURRENT: 40 (35.71%)

### Value status

- NO_VALUE: 56 (50.0%)
- VALUE_STRONG: 39 (34.82%)
- VALUE_PLAYABLE: 17 (15.18%)

### Numeric stats

- CorQ market weight: `{'count': 112, 'avg': 0.2096, 'min': 0.1, 'max': 0.3}`
- Value delta pp: `{'count': 112, 'avg': 0.0, 'min': -45.49, 'max': 45.49}`
- Expected value pct: `{'count': 112, 'avg': 5.4779, 'min': -40.33, 'max': 233.4}`

## corq_top7

Rows: 7

### Coverage

- High MarQ: 57.14%
- Medium current-only: 42.86%
- Thin fallback: 0.0%
- No/unknown MarQ: 0.0%
- Usable High+Medium: 100.0%

### Endpoints

- getAllOddsForEvent: 7 (100.0%)

### Quality tiers

- HIGH: 4 (57.14%)
- MEDIUM_CURRENT_ONLY: 3 (42.86%)

### Data status

- EXACT_BETTING_ODDS_WITH_OPENING: 4 (57.14%)
- EXACT_CURRENT_ODDS_ONLY: 3 (42.86%)

### Movement status

- REAL_OPENING_CURRENT_AVAILABLE: 4 (57.14%)
- OPENING_EQUALS_CURRENT: 3 (42.86%)

### Value status

- VALUE_PLAYABLE: 4 (57.14%)
- VALUE_STRONG: 3 (42.86%)

### Numeric stats

- CorQ market weight: `{'count': 7, 'avg': 0.2114, 'min': 0.12, 'max': 0.3}`
- Value delta pp: `{'count': 7, 'avg': 3.53, 'min': 1.14, 'max': 10.59}`
- Expected value pct: `{'count': 7, 'avg': 1.4386, 'min': -3.07, 'max': 17.1}`

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
