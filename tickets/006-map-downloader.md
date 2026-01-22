# TICKET-006: Bulk Map Downloader

## Status
NOT STARTED

## Priority
P0-Critical

## Description
Extend the map download utility to support bulk downloading of maps from the FAF vault. The downloader should handle parallel downloads, checkpointing for resume capability, and graceful error handling for failed downloads.

## Acceptance Criteria
- [ ] `src/python/faf/downloader/bulk.py` exists with `BulkDownloader` class
- [ ] Supports parallel downloads with configurable concurrency (default: 4)
- [ ] Implements checkpointing: saves progress to `checkpoint.json`
- [ ] Resumes from checkpoint if interrupted
- [ ] Logs failed downloads to `failures.json` without halting
- [ ] CLI command: `faf bulk-download --limit N --output-dir DIR`
- [ ] Supports filtering via API filters (size, player count)
- [ ] Progress reporting to stdout (maps downloaded / total)
- [ ] Unit tests for download logic and checkpointing
- [ ] Integration test with small batch (5 maps)
- [ ] Code passes `black` and `ruff` checks

## Technical Context

### Bulk Download Flow
```
1. Query FAF API for map list (paginated)
2. Load checkpoint if exists (skip already downloaded)
3. Download maps in parallel (ThreadPoolExecutor)
4. For each successful download:
   - Extract zip
   - Verify .scmap exists
   - Update checkpoint
5. For each failed download:
   - Log to failures.json
   - Continue with remaining maps
6. Print summary on completion
```

### Checkpointing
```json
// checkpoint.json
{
  "completed": ["map_id_1", "map_id_2", ...],
  "in_progress": [],
  "timestamp": "2025-01-22T10:30:00Z",
  "filters": {"map_size": ">=512", "player_count": 8}
}
```

### Failure Logging
```json
// failures.json
[
  {
    "map_id": "12345",
    "map_name": "Broken Map",
    "url": "https://content.faforever.com/maps/broken.zip",
    "error": "HTTP 404: Not Found",
    "timestamp": "2025-01-22T10:31:00Z"
  }
]
```

### CLI Interface
```bash
# Download 100 maps
faf bulk-download --limit 100 --output-dir /data/maps

# Download with filters
faf bulk-download --limit 500 --min-size 512 --players 8 --output-dir /data/maps

# Resume interrupted download
faf bulk-download --resume --output-dir /data/maps

# Parallel downloads
faf bulk-download --limit 100 --concurrency 8 --output-dir /data/maps
```

### Directory Structure After Completion
```
src/
└── python/
    └── faf/
        ├── downloader/
        │   ├── __init__.py
        │   ├── maps.py        # From TICKET-003
        │   └── bulk.py        # NEW
        └── ...

/data/maps/                    # Output directory
├── checkpoint.json
├── failures.json
├── setons_clutch.v0001/
│   ├── setons_clutch.scmap
│   └── ...
├── theta_passage_5.v0001/
│   └── ...
└── ...
```

### Concurrency Considerations
- Use `ThreadPoolExecutor` for I/O-bound downloads
- Limit concurrency to avoid overwhelming FAF servers
- Add small delay between starting new downloads (100ms)
- Thread-safe checkpoint updates (use file locking or queue)

## Out of Scope
- Distributed downloading across machines
- Cloud storage output (S3, GCS)
- Incremental sync (only download new maps)
- Bandwidth throttling
- Download verification via checksums

## Testing Requirements

### Unit Tests
```bash
docker-compose run --rm dev pytest tests/python/downloader/test_bulk.py -v
```

Expected test cases:
- `test_bulk_download_creates_checkpoint`
- `test_bulk_download_resumes_from_checkpoint`
- `test_bulk_download_logs_failures`
- `test_bulk_download_respects_limit`
- `test_bulk_download_respects_concurrency`
- `test_bulk_download_applies_filters`

### Integration Test
```bash
docker-compose run --rm dev pytest tests/python/downloader/test_bulk_integration.py -v -m integration
```

Downloads 5 real maps and verifies extraction.

### Manual Verification
```bash
# Download small batch
docker-compose run --rm faf bulk-download --limit 10 --output-dir /data/maps

# Check results
docker-compose run --rm dev bash -c "ls /data/maps | wc -l"
# Expected: 10 directories

# Check checkpoint
docker-compose run --rm dev cat /data/maps/checkpoint.json
```

## Dependencies
- TICKET-005: FAF API client for map discovery
- TICKET-003: Single map downloader (reuse extraction logic)

## References
- ThreadPoolExecutor: https://docs.python.org/3/library/concurrent.futures.html
- File locking: https://docs.python.org/3/library/fcntl.html