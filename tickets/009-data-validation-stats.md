# TICKET-009: Data Validation & Statistics

## Status
NOT STARTED

## Priority
P1-High

## Description
Implement validation checks and statistical analysis for the preprocessed dataset. This ensures data quality before training and provides insights into dataset composition that inform model design decisions.

## Acceptance Criteria
- [ ] `src/python/faf/preprocessing/validate.py` exists with `DatasetValidator` class
- [ ] `src/python/faf/preprocessing/stats.py` exists with `DatasetStats` class
- [ ] Validates heightmap values are in [0, 1] range
- [ ] Validates heightmap dimensions match metadata
- [ ] Validates splits are disjoint and cover all samples
- [ ] Generates dataset statistics: size distribution, terrain types, player counts
- [ ] CLI command: `faf dataset-info /data/dataset`
- [ ] CLI command: `faf dataset-validate /data/dataset`
- [ ] Validation outputs machine-readable JSON report
- [ ] Stats outputs human-readable summary and optional JSON
- [ ] Unit tests for validation and stats logic
- [ ] Code passes `black` and `ruff` checks

## Technical Context

### Validation Checks

**Heightmap Validation:**
```python
def validate_heightmap(path: Path, expected_shape: tuple[int, int]) -> list[str]:
    """
    Returns list of error messages, empty if valid.
    """
    errors = []
    try:
        hm = np.load(path)
        if hm.dtype != np.float32:
            errors.append(f"Wrong dtype: {hm.dtype}, expected float32")
        if hm.shape != expected_shape:
            errors.append(f"Wrong shape: {hm.shape}, expected {expected_shape}")
        if hm.min() < 0 or hm.max() > 1:
            errors.append(f"Values out of range: [{hm.min()}, {hm.max()}]")
    except Exception as e:
        errors.append(f"Failed to load: {e}")
    return errors
```

**Split Validation:**
```python
def validate_splits(splits: dict, all_samples: set[str]) -> list[str]:
    """
    Validates train/val/test splits.
    """
    errors = []
    train = set(splits["train"])
    val = set(splits["val"])
    test = set(splits["test"])
    
    # Check disjoint
    if train & val:
        errors.append(f"Train/val overlap: {train & val}")
    if train & test:
        errors.append(f"Train/test overlap: {train & test}")
    if val & test:
        errors.append(f"Val/test overlap: {val & test}")
    
    # Check coverage
    split_union = train | val | test
    if split_union != all_samples:
        missing = all_samples - split_union
        extra = split_union - all_samples
        if missing:
            errors.append(f"Samples not in any split: {missing}")
        if extra:
            errors.append(f"Unknown samples in splits: {extra}")
    
    return errors
```

### Validation Report Format
```json
{
  "valid": false,
  "timestamp": "2025-01-22T10:00:00Z",
  "dataset_path": "/data/dataset",
  "total_samples": 1000,
  "valid_samples": 998,
  "invalid_samples": 2,
  "errors": [
    {
      "sample_id": "broken_map_v0001",
      "errors": ["Values out of range: [-0.1, 1.2]"]
    },
    {
      "sample_id": "corrupted_map_v0001", 
      "errors": ["Failed to load: file truncated"]
    }
  ],
  "split_errors": []
}
```

### Statistics Output

**Human-readable (stdout):**
```
Dataset Statistics: /data/dataset
================================

Samples: 1,000 total
  Train: 800 (80.0%)
  Val:   100 (10.0%)
  Test:  100 (10.0%)

Map Sizes:
  5km (256):   150 (15.0%)
  10km (512):  600 (60.0%)
  20km (1024): 250 (25.0%)

Player Counts:
  2 players:  100 (10.0%)
  4 players:  200 (20.0%)
  6 players:  150 (15.0%)
  8 players:  400 (40.0%)
  10+ players: 150 (15.0%)

Terrain Types:
  temperate:  450 (45.0%)
  desert:     200 (20.0%)
  tundra:     150 (15.0%)
  tropical:   100 (10.0%)
  lava:        50 (5.0%)
  unknown:     50 (5.0%)

Heightmap Stats:
  Mean elevation: 0.342
  Std elevation:  0.187
  Min across all: 0.000
  Max across all: 1.000

Water:
  Maps with water: 750 (75.0%)
  Maps without:    250 (25.0%)
```

**JSON format (--json flag):**
```json
{
  "total_samples": 1000,
  "splits": {"train": 800, "val": 100, "test": 100},
  "map_sizes": {"256": 150, "512": 600, "1024": 250},
  "player_counts": {"2": 100, "4": 200, ...},
  "terrain_types": {"temperate": 450, ...},
  "heightmap_stats": {"mean": 0.342, "std": 0.187, ...},
  "water": {"with_water": 750, "without_water": 250}
}
```

### CLI Interface
```bash
# Validate dataset
faf dataset-validate /data/dataset
# Exit code 0 if valid, 1 if errors

# Validate with JSON output
faf dataset-validate /data/dataset --json > validation_report.json

# Show statistics
faf dataset-info /data/dataset

# Statistics as JSON
faf dataset-info /data/dataset --json > stats.json
```

### Directory Structure After Completion
```
src/
└── python/
    └── faf/
        └── preprocessing/
            ├── __init__.py
            ├── dataset.py       # From TICKET-008
            ├── normalize.py     # From TICKET-008
            ├── validate.py      # NEW
            └── stats.py         # NEW
tests/
└── python/
    └── preprocessing/
        ├── test_dataset.py
        ├── test_validate.py     # NEW
        └── test_stats.py        # NEW
```

## Out of Scope
- Visualization (histograms, sample images)
- Automated data cleaning/repair
- Outlier detection and removal
- Cross-validation fold generation
- Dataset comparison tools

## Testing Requirements

### Unit Tests
```bash
docker-compose run --rm dev pytest tests/python/preprocessing/test_validate.py tests/python/preprocessing/test_stats.py -v
```

Expected test cases:
- `test_validate_heightmap_valid`
- `test_validate_heightmap_wrong_dtype`
- `test_validate_heightmap_out_of_range`
- `test_validate_splits_valid`
- `test_validate_splits_overlap`
- `test_validate_splits_missing_samples`
- `test_stats_map_size_distribution`
- `test_stats_terrain_distribution`
- `test_stats_heightmap_statistics`

### Integration Test
```bash
docker-compose run --rm dev pytest tests/python/preprocessing/test_validate_integration.py -v -m integration
```

### Manual Verification
```bash
# Validate the dataset
docker-compose run --rm faf dataset-validate /data/dataset
echo "Exit code: $?"

# Get statistics
docker-compose run --rm faf dataset-info /data/dataset
```

## Dependencies
- TICKET-008: Dataset preprocessor creates the dataset to validate

## References
- NumPy statistics: https://numpy.org/doc/stable/reference/routines.statistics.html