# MarQ API Coverage Report

Generated UTC: 2026-08-08T07:54:13.076120+00:00
Model: 2026-08-04-marq-coverage-report-v1

## all_audit

Rows: 26

### Coverage

- High MarQ: 76.92%
- Medium current-only: 23.08%
- Thin fallback: 0.0%
- No/unknown MarQ: 0.0%
- Usable High+Medium: 100.0%

### Endpoints

- getAllOddsForEvent: 26 (100.0%)

### Quality tiers

- HIGH: 20 (76.92%)
- MEDIUM_CURRENT_ONLY: 6 (23.08%)

### Data status

- EXACT_BETTING_ODDS_WITH_OPENING: 20 (76.92%)
- EXACT_CURRENT_ODDS_ONLY: 6 (23.08%)

### Movement status

- REAL_OPENING_CURRENT_AVAILABLE: 20 (76.92%)
- OPENING_EQUALS_CURRENT: 6 (23.08%)

### Value status

- NO_VALUE: 14 (53.85%)
- VALUE_STRONG: 10 (38.46%)
- VALUE_PLAYABLE: 2 (7.69%)

### Numeric stats

- CorQ market weight: `{'count': 26, 'avg': 0.2277, 'min': 0.12, 'max': 0.3}`
- Value delta pp: `{'count': 26, 'avg': 0.0, 'min': -16.18, 'max': 16.18}`
- Expected value pct: `{'count': 26, 'avg': 0.1427, 'min': -27.2, 'max': 44.0}`

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

- CorQ market weight: `{'count': 4, 'avg': 0.195, 'min': 0.12, 'max': 0.22}`
- Value delta pp: `{'count': 4, 'avg': -5.7175, 'min': -9.87, 'max': 0.68}`
- Expected value pct: `{'count': 4, 'avg': -13.7425, 'min': -19.8, 'max': -3.6}`

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
