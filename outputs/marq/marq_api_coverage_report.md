# MarQ API Coverage Report

Generated UTC: 2026-08-06T14:47:35.741228+00:00
Model: 2026-08-04-marq-coverage-report-v1

## all_audit

Rows: 54

### Coverage

- High MarQ: 81.48%
- Medium current-only: 18.52%
- Thin fallback: 0.0%
- No/unknown MarQ: 0.0%
- Usable High+Medium: 100.0%

### Endpoints

- getAllOddsForEvent: 54 (100.0%)

### Quality tiers

- HIGH: 44 (81.48%)
- MEDIUM_CURRENT_ONLY: 10 (18.52%)

### Data status

- EXACT_BETTING_ODDS_WITH_OPENING: 44 (81.48%)
- EXACT_CURRENT_ODDS_ONLY: 10 (18.52%)

### Movement status

- REAL_OPENING_CURRENT_AVAILABLE: 44 (81.48%)
- OPENING_EQUALS_CURRENT: 10 (18.52%)

### Value status

- VALUE_STRONG: 26 (48.15%)
- NO_VALUE: 26 (48.15%)
- VALUE_PLAYABLE: 2 (3.7%)

### Numeric stats

- CorQ market weight: `{'count': 54, 'avg': 0.2341, 'min': 0.12, 'max': 0.3}`
- Value delta pp: `{'count': 54, 'avg': 0.0, 'min': -26.19, 'max': 26.19}`
- Expected value pct: `{'count': 54, 'avg': 10.2987, 'min': -37.5, 'max': 250.1}`

## corq_top7

Rows: 4

### Coverage

- High MarQ: 100.0%
- Medium current-only: 0.0%
- Thin fallback: 0.0%
- No/unknown MarQ: 0.0%
- Usable High+Medium: 100.0%

### Endpoints

- getAllOddsForEvent: 4 (100.0%)

### Quality tiers

- HIGH: 4 (100.0%)

### Data status

- EXACT_BETTING_ODDS_WITH_OPENING: 4 (100.0%)

### Movement status

- REAL_OPENING_CURRENT_AVAILABLE: 4 (100.0%)

### Value status

- VALUE_STRONG: 4 (100.0%)

### Numeric stats

- CorQ market weight: `{'count': 4, 'avg': 0.3, 'min': 0.3, 'max': 0.3}`
- Value delta pp: `{'count': 4, 'avg': 7.89, 'min': 5.71, 'max': 11.76}`
- Expected value pct: `{'count': 4, 'avg': 10.485, 'min': 4.73, 'max': 20.8}`

## cloq

Rows: 4

### Coverage

- High MarQ: 100.0%
- Medium current-only: 0.0%
- Thin fallback: 0.0%
- No/unknown MarQ: 0.0%
- Usable High+Medium: 100.0%

### Endpoints

- getAllOddsForEvent: 4 (100.0%)

### Quality tiers

- HIGH: 4 (100.0%)

### Data status

- EXACT_BETTING_ODDS_WITH_OPENING: 4 (100.0%)

### Movement status

- REAL_OPENING_CURRENT_AVAILABLE: 4 (100.0%)

### Value status

- VALUE_STRONG: 4 (100.0%)

### Numeric stats

- CorQ market weight: `{'count': 4, 'avg': 0.3, 'min': 0.3, 'max': 0.3}`
- Value delta pp: `{'count': 4, 'avg': 7.89, 'min': 5.71, 'max': 11.76}`
- Expected value pct: `{'count': 4, 'avg': 10.485, 'min': 4.73, 'max': 20.8}`

## Notes

- HIGH should represent exact TennisApi odds with real opening/current movement data.
- MEDIUM_CURRENT_ONLY is usable but should not carry full 30% MarQ influence.
- THIN_FALLBACK should remain close to zero influence and should be investigated if it grows.
- NO_MARQ/NO_TIER rows indicate missing audit fields or missing market data.
