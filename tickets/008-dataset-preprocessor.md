# TICKET-008: Dataset Preprocessor

## Status
PENDING REVIEW

## Claude Code Working Area
- [x] Read ticket and understand requirements
- [x] Create preprocessing module structure
- [x] Implement normalize.py with heightmap normalization
- [x] Implement dataset.py with DatasetBuilder class
- [x] Add preprocess CLI command to main.py
- [x] Add unit tests for normalization and split logic (64 new tests, 192 total)
- [x] Run black and ruff checks
- [x] Self-review and update status

## Priority
P0-Critical

## Description
Implement a preprocessing pipeline that transforms downloaded FAF maps into an ML-ready dataset. The preprocessor extracts heightmaps, normalizes them, collects metadata, and creates train/val/test splits.

## Acceptance Criteria
- [x] `src/python/faf/preprocessing/dataset.py` exists with `DatasetBuilder` class
- [x] Extracts heightmaps as normalized float32 numpy arrays
- [x] Saves heightmaps to `heightmaps/` directory as `.npy` files
- [x] Generates `metadata.json` with map info for each sample
- [x] Generates `splits.json` with reproducible train/val/test assignments
- [x] CLI command: `faf preprocess INPUT_DIR --output OUTPUT_DIR`
- [x] Handles corrupted/unparseable maps gracefully (log and skip)
- [x] Supports filtering by map size during preprocessing
- [x] Progress bar showing preprocessing status
- [x] Unit tests for normalization and split logic (23 dataset + 17 normalize + 13 CLI + 11 misc = 64 new tests)
- [x] Code passes `black` and `ruff` checks

## Technical Context

### Preprocessing Pipeline
```
Input: /data/maps/
├── map_a.v0001/
│   └── map_a.scmap
├── map_b.v0001/
│   └── map_b.scmap
└── ...

                    ┌─────────────────┐
                    │  DatasetBuilder │
                    └────────┬────────┘
                             │
        ┌────────────────────┼────────────────────┐
        ▼                    ▼                    ▼
   Parse .scmap      Extract heightmap     Collect metadata
        │                    │                    │
        │            Normalize [0, 1]             │
        │                    │                    │
        │             Save as .npy                │
        └────────────────────┼────────────────────┘
                             │
                             ▼
                      Create splits

Output: /data/dataset/
├── heightmaps/
│   ├── map_a_v0001.npy      # float32, shape (H, W)
│   ├── map_b_v0001.npy
│   └── ...
├── metadata.json
└── splits.json
```

### Heightmap Normalization
```python
def normalize_heightmap(raw: np.ndarray) -> np.ndarray:
    """
    Normalize uint16 heightmap to float32 [0, 1] range.
    
    Args:
        raw: uint16 array from SCMap parser
        
    Returns:
        float32 array in [0, 1] range
    """
    return raw.astype(np.float32) / 65535.0
```

### Output File Formats

**metadata.json:**
```json
{
  "version": "1.0",
  "created_at": "2025-01-22T10:00:00Z",
  "total_samples": 1000,
  "samples": {
    "map_a_v0001": {
      "original_name": "Map A",
      "map_size": 512,
      "map_size_km": 10,
      "player_count": 8,
      "terrain_type": "temperate",
      "has_water": true,
      "heightmap_shape": [513, 513],
      "heightmap_file": "heightmaps/map_a_v0001.npy"
    },
    ...
  }
}
```

**splits.json:**
```json
{
  "version": "1.0",
  "seed": 42,
  "ratios": {"train": 0.8, "val": 0.1, "test": 0.1},
  "train": ["map_a_v0001", "map_c_v0001", ...],
  "val": ["map_b_v0001", ...],
  "test": ["map_d_v0001", ...]
}
```

### CLI Interface
```bash
# Basic preprocessing
faf preprocess /data/maps --output /data/dataset

# Filter by size
faf preprocess /data/maps --output /data/dataset --min-size 512

# Custom split ratios
faf preprocess /data/maps --output /data/dataset --split 0.7,0.15,0.15

# Reproducible splits
faf preprocess /data/maps --output /data/dataset --seed 42
```

### Directory Structure After Completion
```
src/
└── python/
    └── faf/
        ├── preprocessing/
        │   ├── __init__.py
        │   ├── dataset.py      # DatasetBuilder
        │   └── normalize.py    # Normalization functions
        └── ...
tests/
└── python/
    └── preprocessing/
        ├── test_dataset.py
        └── test_normalize.py
```

### Error Handling
- Corrupted .scmap files: Log warning, skip, continue
- Missing .scmap in directory: Log warning, skip
- Disk full: Raise clear exception with space required
- Track success/failure counts in summary

## Out of Scope
- Data augmentation (rotation, flipping)
- Resizing heightmaps to uniform dimensions
- Stratum mask preprocessing
- Texture preprocessing
- TFRecord/HDF5 output formats

## Testing Requirements

### Unit Tests
```bash
docker-compose run --rm dev pytest tests/python/preprocessing/ -v
```

Expected test cases:
- `test_normalize_heightmap_range`
- `test_normalize_heightmap_dtype`
- `test_build_dataset_creates_heightmaps`
- `test_build_dataset_creates_metadata`
- `test_build_dataset_creates_splits`
- `test_build_dataset_splits_are_disjoint`
- `test_build_dataset_skips_corrupted`
- `test_build_dataset_reproducible_with_seed`

### Integration Test
```bash
docker-compose run --rm dev pytest tests/python/preprocessing/test_dataset_integration.py -v -m integration
```

### Manual Verification
```bash
# Preprocess downloaded maps
docker-compose run --rm faf preprocess /data/maps --output /data/dataset --seed 42

# Verify output structure
docker-compose run --rm dev python -c "
import json
import numpy as np
from pathlib import Path

dataset_dir = Path('/data/dataset')

# Check metadata
with open(dataset_dir / 'metadata.json') as f:
    meta = json.load(f)
print(f'Total samples: {meta[\"total_samples\"]}')

# Check splits
with open(dataset_dir / 'splits.json') as f:
    splits = json.load(f)
print(f'Train: {len(splits[\"train\"])}, Val: {len(splits[\"val\"])}, Test: {len(splits[\"test\"])}')

# Load a heightmap
sample_id = list(meta['samples'].keys())[0]
hm = np.load(dataset_dir / 'heightmaps' / f'{sample_id}.npy')
print(f'Heightmap shape: {hm.shape}, dtype: {hm.dtype}, range: [{hm.min():.3f}, {hm.max():.3f}]')
"
```

## Dependencies
- TICKET-006: Bulk downloader provides input maps
- TICKET-007: Extended parser provides rich metadata

## References
- NumPy save/load: https://numpy.org/doc/stable/reference/generated/numpy.save.html
- scikit-learn train_test_split: https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.train_test_split.html