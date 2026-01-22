# TICKET-006: Bulk Map Downloader

## Status
NOT STARTED

## Priority
P0-Critical

## Description
Extend the map download utility to support bulk downloading of maps from the FAF vault. The downloader should handle parallel downloads, checkpointing for resume capability, and graceful error handling for failed downloads.

**Note:** Due to FAF API requiring OAuth authentication (see TODO-002), this ticket includes a static URL fallback mechanism. This fallback should be removed once TICKET-010 (OAuth implementation) is complete.

## Acceptance Criteria
- [ ] `src/python/faf/downloader/bulk.py` exists with `BulkDownloader` class
- [ ] Supports parallel downloads with configurable concurrency (default: 4)
- [ ] Implements checkpointing: saves progress to `checkpoint.json`
- [ ] Resumes from checkpoint if interrupted
- [ ] Logs failed downloads to `failures.json` without halting
- [ ] CLI command: `faf bulk-download --limit N --output-dir DIR`
- [ ] Supports filtering via API filters (size, player count) - when API auth available
- [ ] **Supports `--from-file FILE` flag to read URLs from static file**
- [ ] **Ships with `data/seed_map_urls.txt` containing 200+ curated map URLs**
- [ ] Progress reporting to stdout (maps downloaded / total)
- [ ] Unit tests for download logic and checkpointing
- [ ] Integration test with small batch (5 maps)
- [ ] Code passes `black` and `ruff` checks

## Technical Context

### Bulk Download Flow
```
1. Determine map source:
   a. If --from-file provided: Read URLs from file
   b. Else if API auth available: Query FAF API (paginated)
   c. Else: Fall back to data/seed_map_urls.txt with warning
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

### Static URL Fallback (Temporary)
Until TICKET-010 (OAuth) is implemented, provide a curated seed list:

```
# data/seed_map_urls.txt
# Curated list of FAF map URLs for bulk download
# This file is a temporary fallback until OAuth is implemented (TICKET-010)
# Format: one URL per line, comments start with #

https://content.faforever.com/maps/setons_clutch.v0003.zip
https://content.faforever.com/maps/theta_passage_5.v0001.zip
https://content.faforever.com/maps/dual_gap_adaptive.v0012.zip
# ... 200+ maps covering various sizes and player counts
```

**Seed List Curation Criteria:**
- Include maps of all sizes: 5km, 10km, 20km, 40km
- Include various player counts: 2, 4, 6, 8, 10+
- Prioritize ranked/popular maps
- Exclude maps known to have parsing issues
- Target ~250 maps for initial ML experimentation

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
# Download from static seed list (default fallback)
faf bulk-download --limit 100 --output-dir /data/maps

# Download from custom URL file
faf bulk-download --from-file my_urls.txt --output-dir /data/maps

# Download with API filters (requires OAuth - TICKET-010)
faf bulk-download --limit 500 --min-size 512 --players 8 --output-dir /data/maps

# Resume interrupted download
faf bulk-download --resume --output-dir /data/maps

# Parallel downloads
faf bulk-download --limit 100 --concurrency 8 --output-dir /data/maps

# Explicitly use seed file (same as default when API unavailable)
faf bulk-download --from-file data/seed_map_urls.txt --limit 50 --output-dir /data/maps
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

data/
└── seed_map_urls.txt          # Curated fallback URLs (until TICKET-010)

/data/maps/                    # Output directory (runtime)
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
- `test_bulk_download_reads_from_file`
- `test_bulk_download_skips_comments_in_url_file`
- `test_bulk_download_falls_back_to_seed_file`

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
- TICKET-005: FAF API client for map discovery (when auth available)
- TICKET-003: Single map downloader (reuse extraction logic)

## Future Work
- TICKET-010: FAF OAuth implementation will enable API-based discovery
- Once TICKET-010 is complete, remove `data/seed_map_urls.txt` fallback

## References
- ThreadPoolExecutor: https://docs.python.org/3/library/concurrent.futures.html
- File locking: https://docs.python.org/3/library/fcntl.html
- FAF Content Server: https://content.faforever.com/maps/