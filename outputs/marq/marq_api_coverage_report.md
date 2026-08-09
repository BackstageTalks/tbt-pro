# MarQ API Coverage Report

Generated UTC: 2026-08-09T06:29:35.882204+00:00
Model: 2026-08-04-marq-coverage-report-v1

## all_audit

Rows: 16

### Coverage

- High MarQ: 100.0%
- Medium current-only: 0.0%
- Thin fallback: 0.0%
- No/unknown MarQ: 0.0%
- Usable High+Medium: 100.0%

### Endpoints

- getAllOddsForEvent: 16 (100.0%)

### Quality tiers

- HIGH: 16 (100.0%)

### Data status

- EXACT_BETTING_ODDS_WITH_OPENING: 16 (100.0%)

### Movement status

- REAL_OPENING_CURRENT_AVAILABLE: 16 (100.0%)

### Value status

- NO_VALUE: 9 (56.25%)
- VALUE_STRONG: 7 (43.75%)

### Numeric stats

- CorQ market weight: `{'count': 16, 'avg': 0.26, 'min': 0.22, 'max': 0.3}`
- Value delta pp: `{'count': 16, 'avg': 0.0, 'min': -15.95, 'max': 15.95}`
- Expected value pct: `{'count': 16, 'avg': 3.9519, 'min': -23.76, 'max': 82.16}`

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

- VALUE_STRONG: 1 (50.0%)
- NO_VALUE: 1 (50.0%)

### Numeric stats

- CorQ market weight: `{'count': 2, 'avg': 0.26, 'min': 0.22, 'max': 0.3}`
- Value delta pp: `{'count': 2, 'avg': -1.0, 'min': -7.89, 'max': 5.89}`
- Expected value pct: `{'count': 2, 'avg': -4.535, 'min': -15.59, 'max': 6.52}`

## cloq

Rows: 0

### Coverage

- High MarQ: 0.0%
- Medium current-only: 0.0%
- Thin fallback: 0.0%
- No/unknown MarQ: 0.0%
- Usable High+Medium: 0.0%

### Endpoints

No data.

### Quality tiers

No data.

### Data status

No data.

### Movement status

No data.

### Value status

No data.

### Numeric stats

- CorQ market weight: `{'count': 0, 'avg': None, 'min': None, 'max': None}`
- Value delta pp: `{'count': 0, 'avg': None, 'min': None, 'max': None}`
- Expected value pct: `{'count': 0, 'avg': None, 'min': None, 'max': None}`

## Notes

- HIGH should represent exact TennisApi odds with real opening/current movement data.
- MEDIUM_CURRENT_ONLY is usable but should not carry full 30% MarQ influence.
- THIN_FALLBACK should remain close to zero influence and should be investigated if it grows.
- NO_MARQ/NO_TIER rows indicate missing audit fields or missing market data.
