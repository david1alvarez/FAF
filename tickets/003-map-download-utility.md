# TICKET-003: Map Download Utility

## Status
NOT STARTED

## Priority
P0-Critical

## Description
Implement a Python utility to download maps from the FAF content server. Given a map URL or map name, the utility will download the zip archive, extract it, and return the path to the extracted map directory containing the .scmap file.

## Acceptance Criteria
- [ ] `src/python/faf/downloader/maps.py` exists with `MapDownloader` class
- [ ] Can download map by direct URL: `https://content.faforever.com/maps/mapname.zip`
- [ ] Can download map by name using FAF API to resolve URL
- [ ] Extracts downloaded zip to specified output directory
- [ ] Returns `MapInfo` dataclass with paths to key files (.scmap, _scenario.lua, etc.)
- [ ] Handles HTTP errors gracefully with meaningful exceptions
- [ ] Implements retry logic (3 attempts with exponential backoff)
- [ ] Validates downloaded zip contains expected map structure
- [ ] Unit tests exist in `tests/python/downloader/test_maps.py`
- [ ] Integration test exists that downloads a real (small) map
- [ ] Code passes `black` and `ruff` checks
- [ ] All public functions have type hints and docstrings

## Technical Context

### FAF Content Server
Maps are hosted at: `https://content.faforever.com/maps/{filename}`

Example URLs:
- `https://content.faforever.com/maps/seton's_clutch.v0001.zip`
- `https://content.faforever.com/maps/astro_crater_battles_4x4.v0005.zip`

### FAF API for Map Lookup
To resolve map name → download URL:
```
GET https://api.faforever.com/data/map?filter[displayName]==Seton's%20Clutch
```

Response includes `downloadUrl` field.

For this ticket, we'll support both:
1. Direct URL download (primary)
2. Map name lookup via API (convenience)

### Expected Map Zip Structure
```
mapname.v0001.zip
└── mapname.v0001/
    ├── mapname.scmap           # Binary terrain data
    ├── mapname_scenario.lua    # Map metadata
    ├── mapname_save.lua        # Markers, props
    ├── mapname_script.lua      # Custom scripts
    └── env/                    # Optional custom textures
```

### Data Classes
```python
@dataclass
class MapInfo:
    name: str                    # Map display name
    version: str                 # e.g., "v0001"
    root_dir: Path               # Extracted directory path
    scmap_path: Path             # Path to .scmap file
    scenario_path: Path          # Path to _scenario.lua
    save_path: Path              # Path to _save.lua
    script_path: Path            # Path to _script.lua
```

### Directory Structure After Completion
```
src/
└── python/
    └── faf/
        ├── __init__.py
        ├── parser/
        │   └── scmap.py         # From TICKET-002
        └── downloader/
            ├── __init__.py
            └── maps.py
tests/
└── python/
    └── downloader/
        ├── test_maps.py
        └── test_maps_integration.py  # Marked with @pytest.mark.integration
```

## Out of Scope
- Caching downloaded maps (future ticket)
- Bulk download functionality
- Map vault browsing/search
- Downloading mod files
- Progress callbacks/streaming progress

## Testing Requirements

### Unit Tests (mocked HTTP)
```bash
docker-compose run --rm dev pytest tests/python/downloader/test_maps.py -v
```

Expected test cases:
- `test_download_from_url_extracts_zip`
- `test_download_returns_correct_mapinfo`
- `test_download_raises_on_404`
- `test_download_raises_on_invalid_zip`
- `test_download_retries_on_transient_error`
- `test_download_validates_map_structure`

### Integration Test (real network)
```bash
docker-compose run --rm dev pytest tests/python/downloader/test_maps_integration.py -v -m integration
```

Uses a small, stable map that's unlikely to be removed from FAF vault.

### Manual Verification
```bash
docker-compose run --rm dev python -c "
from faf.downloader.maps import MapDownloader
from pathlib import Path

downloader = MapDownloader()
info = downloader.download(
    'https://content.faforever.com/maps/theta_passage_5.v0001.zip',
    output_dir=Path('/tmp/maps')
)
print(f'Downloaded: {info.name}')
print(f'SCMAP path: {info.scmap_path}')
print(f'Exists: {info.scmap_path.exists()}')
"
```

## Dependencies
- TICKET-001: Docker environment must be complete

## References
- FAF API documentation: https://api.faforever.com
- FAF content server: https://content.faforever.com
- requests library: https://docs.python-requests.org/