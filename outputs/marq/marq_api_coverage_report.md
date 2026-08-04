# MarQ API Coverage Report

Generated UTC: 2026-08-04T11:19:50.059866+00:00
Model: 2026-08-04-marq-coverage-report-v1

## all_audit

Rows: 114

### Coverage

- High MarQ: 0.0%
- Medium current-only: 0.0%
- Thin fallback: 100.0%
- No/unknown MarQ: 0.0%
- Usable High+Medium: 0.0%

### Endpoints

- NO_ENDPOINT: 114 (100.0%)

### Quality tiers

- THIN_FALLBACK: 114 (100.0%)

### Data status

- NO_DATA_STATUS: 114 (100.0%)

### Movement status

- NO_MOVEMENT_STATUS: 114 (100.0%)

### Value status

- NO_VALUE: 57 (50.0%)
- VALUE_STRONG: 41 (35.96%)
- VALUE_PLAYABLE: 16 (14.04%)

### Numeric stats

- CorQ market weight: `{'count': 114, 'avg': 0.03, 'min': 0.03, 'max': 0.03}`
- Value delta pp: `{'count': 114, 'avg': 0.0, 'min': -28.7, 'max': 28.7}`
- Expected value pct: `{'count': 114, 'avg': 4.0096, 'min': -39.77, 'max': 233.4}`

## corq_top7

Rows: 7

### Coverage

- High MarQ: 0.0%
- Medium current-only: 0.0%
- Thin fallback: 100.0%
- No/unknown MarQ: 0.0%
- Usable High+Medium: 0.0%

### Endpoints

- NO_ENDPOINT: 7 (100.0%)

### Quality tiers

- THIN_FALLBACK: 7 (100.0%)

### Data status

- NO_DATA_STATUS: 7 (100.0%)

### Movement status

- NO_MOVEMENT_STATUS: 7 (100.0%)

### Value status

- VALUE_STRONG: 4 (57.14%)
- VALUE_PLAYABLE: 3 (42.86%)

### Numeric stats

- CorQ market weight: `{'count': 7, 'avg': 0.03, 'min': 0.03, 'max': 0.03}`
- Value delta pp: `{'count': 7, 'avg': 4.2971, 'min': 1.12, 'max': 10.56}`
- Expected value pct: `{'count': 7, 'avg': 2.4029, 'min': -3.07, 'max': 17.1}`

## cloq

Rows: 4

### Coverage

- High MarQ: 0.0%
- Medium current-only: 0.0%
- Thin fallback: 100.0%
- No/unknown MarQ: 0.0%
- Usable High+Medium: 0.0%

### Endpoints

- NO_ENDPOINT: 4 (100.0%)

### Quality tiers

- THIN_FALLBACK: 4 (100.0%)

### Data status

- NO_DATA_STATUS: 4 (100.0%)

### Movement status

- NO_MOVEMENT_STATUS: 4 (100.0%)

### Value status

- VALUE_STRONG: 4 (100.0%)

### Numeric stats

- CorQ market weight: `{'count': 4, 'avg': 0.03, 'min': 0.03, 'max': 0.03}`
- Value delta pp: `{'count': 4, 'avg': 6.9, 'min': 4.75, 'max': 10.56}`
- Expected value pct: `{'count': 4, 'avg': 7.4575, 'min': 4.01, 'max': 17.1}`

## Notes

- HIGH should represent exact TennisApi odds with real opening/current movement data.
- MEDIUM_CURRENT_ONLY is usable but should not carry full 30% MarQ influence.
- THIN_FALLBACK should remain close to zero influence and should be investigated if it grows.
- NO_MARQ/NO_TIER rows indicate missing audit fields or missing market data.
