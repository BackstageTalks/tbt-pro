# MarQ API Coverage Report

Generated UTC: 2026-08-21T04:25:32.574476+00:00
Model: 2026-08-04-marq-coverage-report-v1

## all_audit

Rows: 8

### Coverage

- High MarQ: 100.0%
- Medium current-only: 0.0%
- Thin fallback: 0.0%
- No/unknown MarQ: 0.0%
- Usable High+Medium: 100.0%

### Endpoints

- getAllOddsForEvent: 8 (100.0%)

### Quality tiers

- HIGH: 8 (100.0%)

### Data status

- EXACT_BETTING_ODDS_WITH_OPENING: 8 (100.0%)

### Movement status

- REAL_OPENING_CURRENT_AVAILABLE: 8 (100.0%)

### Value status

- NO_VALUE: 4 (50.0%)
- VALUE_STRONG: 4 (50.0%)

### Numeric stats

- CorQ market weight: `{'count': 8, 'avg': 0.26, 'min': 0.22, 'max': 0.3}`
- Value delta pp: `{'count': 8, 'avg': 0.0, 'min': -7.82, 'max': 7.82}`
- Expected value pct: `{'count': 8, 'avg': -4.145, 'min': -19.34, 'max': 10.38}`

## corq_top7

Rows: 2

### Coverage

- High MarQ: 100.0%
- Medium current-only: 0.0%
- Thin fallback: 0.0%
- No/unknown MarQ: 0.0%
- Usable High+Medium: 100.0%

### Endpoints

- getAllOddsForEvent: 2 (100.0%)

### Quality tiers

- HIGH: 2 (100.0%)

### Data status

- EXACT_BETTING_ODDS_WITH_OPENING: 2 (100.0%)

### Movement status

- REAL_OPENING_CURRENT_AVAILABLE: 2 (100.0%)

### Value status

- NO_VALUE: 2 (100.0%)

### Numeric stats

- CorQ market weight: `{'count': 2, 'avg': 0.3, 'min': 0.3, 'max': 0.3}`
- Value delta pp: `{'count': 2, 'avg': -3.94, 'min': -4.55, 'max': -3.33}`
- Expected value pct: `{'count': 2, 'avg': -11.175, 'min': -12.06, 'max': -10.29}`

## cloq

Rows: 2

### Coverage

- High MarQ: 100.0%
- Medium current-only: 0.0%
- Thin fallback: 0.0%
- No/unknown MarQ: 0.0%
- Usable High+Medium: 100.0%

### Endpoints

- getAllOddsForEvent: 2 (100.0%)

### Quality tiers

- HIGH: 2 (100.0%)

### Data status

- EXACT_BETTING_ODDS_WITH_OPENING: 2 (100.0%)

### Movement status

- REAL_OPENING_CURRENT_AVAILABLE: 2 (100.0%)

### Value status

- VALUE_STRONG: 2 (100.0%)

### Numeric stats

- CorQ market weight: `{'count': 2, 'avg': 0.3, 'min': 0.3, 'max': 0.3}`
- Value delta pp: `{'count': 2, 'avg': 6.0, 'min': 4.18, 'max': 7.82}`
- Expected value pct: `{'count': 2, 'avg': 6.235, 'min': 2.09, 'max': 10.38}`

## Notes

- HIGH should represent exact TennisApi odds with real opening/current movement data.
- MEDIUM_CURRENT_ONLY is usable but should not carry full 30% MarQ influence.
- THIN_FALLBACK should remain close to zero influence and should be investigated if it grows.
- NO_MARQ/NO_TIER rows indicate missing audit fields or missing market data.
