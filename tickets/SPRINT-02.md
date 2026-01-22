# Sprint 2: Training Data Pipeline

## Goal
Build the infrastructure to bulk-download maps from the FAF vault and preprocess them into ML-ready datasets. By the end of this sprint, we should have a local dataset of extracted heightmaps and metadata ready for model training experiments.

## Success Criteria
```bash
# Bulk download maps from FAF vault
docker-compose run --rm faf bulk-download --limit 100 --output-dir /data/maps

# Preprocess downloaded maps into training dataset
docker-compose run --rm faf preprocess /data/maps --output /data/dataset

# Dataset structure ready for training
ls /data/dataset/
# heightmaps/     <- numpy arrays (.npy)
# metadata.json   <- map info, sizes, labels
# splits.json     <- train/val/test splits
```

## Prerequisites
- Sprint 1 complete and merged to main
- Docker environment functional
- SCMap parser working
- Map download utility working

## Tickets

| ID | Title | Priority | Dependencies | Status |
|----|-------|----------|--------------|--------|
| 005 | FAF API Map Discovery | P0 | Sprint 1 | NOT STARTED |
| 006 | Bulk Map Downloader | P0 | 005 | NOT STARTED |
| 007 | Extended SCMap Parser | P1 | Sprint 1 | NOT STARTED |
| 008 | Dataset Preprocessor | P0 | 006, 007 | NOT STARTED |
| 009 | Data Validation & Stats | P1 | 008 | NOT STARTED |

## Execution Order
```
005 (API Discovery)
    │
    └── 006 (Bulk Download) ──┐
                              ├── 008 (Preprocessor) ── 009 (Validation)
007 (Extended Parser) ────────┘
```

## Architecture Overview
```
┌─────────────────────────────────────────────────────────────────┐
│                      CLI (extended)                              │
│  faf bulk-download | faf preprocess | faf dataset-info          │
└──────────┬──────────────────────────────────────────────────────┘
           │
┌──────────▼──────────────────────────────────────────────────────┐
│                    Data Pipeline                                 │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────────┐  │
│  │ FAF API     │  │ Bulk         │  │ Dataset                │  │
│  │ Discovery   │→ │ Downloader   │→ │ Preprocessor           │  │
│  │             │  │ (parallel)   │  │ (heightmap extraction) │  │
│  └─────────────┘  └──────────────┘  └────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
           │
┌──────────▼──────────────────────────────────────────────────────┐
│                    Output Dataset                                │
│  /data/dataset/                                                  │
│  ├── heightmaps/          # Normalized numpy arrays              │
│  │   ├── map_001.npy      # Shape: (H, W), dtype: float32       │
│  │   └── ...                                                     │
│  ├── metadata.json        # Map info, sizes, player counts      │
│  └── splits.json          # train/val/test assignments          │
└─────────────────────────────────────────────────────────────────┘
```

## Non-Goals for This Sprint
- Texture extraction (heightmaps only)
- Model training
- Data augmentation
- Cloud storage integration
- Distributed processing

## Data Quality Targets
- Minimum 1,000 successfully parsed maps
- Heightmap normalization to [0, 1] range
- Metadata includes: map_name, size, player_count, version
- 80/10/10 train/val/test split
- Reproducible splits via seed

## Notes for Claude Code
- Respect FAF API rate limits (add delays between requests)
- Implement checkpointing for bulk downloads (resume on failure)
- Log failed maps for debugging, don't halt entire pipeline
- Use multiprocessing for I/O-bound downloads
- Validate heightmap dimensions match expected sizes