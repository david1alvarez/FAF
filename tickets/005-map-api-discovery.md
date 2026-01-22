# TICKET-005: FAF API Map Discovery

## Status
COMPLETE

## Claude Code Working Area
- [x] Read ticket and Sprint 2 documentation
- [x] Create api module with FAFApiClient class
- [x] Implement list_maps with pagination
- [x] Implement filtering (size, player_count, ranked)
- [x] Implement rate limiting and exponential backoff
- [x] Create unit tests (mocked API) - 17 tests
- [x] Create integration tests (skip when API requires auth)
- [x] Run black and ruff checks
- [x] Run tests and verify (77 passed, 5 skipped)
- [x] Self-review and update status

## Notes
**API Authentication Required**: The FAF API now requires OAuth authentication (returns 403 Forbidden).
Integration tests are skipped when the API is inaccessible. See TODO-002 for tracking this issue.

## Priority
P0-Critical

## Description
Implement a client for the FAF API to discover and list maps available in the vault. This enables bulk downloading by providing map URLs, metadata, and filtering capabilities.

## Acceptance Criteria
- [x] `src/python/faf/api/client.py` exists with `FAFApiClient` class
- [x] Can query `/data/map` endpoint with pagination
- [x] Can filter maps by: size, player count, ranked status
- [x] Returns `MapListResult` with map metadata and download URLs
- [x] Handles API rate limiting gracefully (exponential backoff)
- [x] Handles API errors with meaningful exceptions
- [x] Unit tests with mocked API responses
- [x] Integration test that queries real API (skipped when auth required)
- [x] Code passes `black` and `ruff` checks

## Technical Context

### FAF API Endpoints
Base URL: `https://api.faforever.com`

**List Maps:**
```
GET /data/map?page[size]=100&page[number]=1
```

**Filter Examples:**
```
# Maps for 8 players
GET /data/map?filter[playerCount]==8

# Maps at least 10km
GET /data/map?filter[mapSize]=ge=512

# Ranked maps only
GET /data/map?filter[ranked]==true
```

**Response Structure:**
```json
{
  "data": [
    {
      "type": "map",
      "id": "12345",
      "attributes": {
        "displayName": "Seton's Clutch",
        "mapSize": 1024,
        "playerCount": 8,
        "ranked": true,
        "downloadUrl": "https://content.faforever.com/maps/setons_clutch.v0001.zip"
      }
    }
  ],
  "meta": {
    "page": {
      "totalRecords": 15000,
      "totalPages": 150
    }
  }
}
```

### Data Classes
```python
@dataclass
class MapMetadata:
    id: str
    display_name: str
    map_size: int              # 256, 512, 1024
    player_count: int
    ranked: bool
    download_url: str
    version: str | None

@dataclass  
class MapListResult:
    maps: list[MapMetadata]
    total_records: int
    total_pages: int
    current_page: int
```

### Rate Limiting
FAF API may rate limit aggressive clients. Implement:
- Minimum 100ms delay between requests
- Exponential backoff on 429 responses
- Configurable rate limit parameter

### Directory Structure After Completion
```
src/
└── python/
    └── faf/
        ├── __init__.py
        ├── api/
        │   ├── __init__.py
        │   └── client.py
        ├── cli/
        ├── downloader/
        └── parser/
tests/
└── python/
    └── api/
        ├── test_client.py
        └── test_client_integration.py
```

## Out of Scope
- Authentication (not required for public vault)
- Map upload/modification
- User data queries
- Replay data queries
- Caching responses locally

## Testing Requirements

### Unit Tests
```bash
docker-compose run --rm dev pytest tests/python/api/test_client.py -v
```

Expected test cases:
- `test_list_maps_returns_maplistresult`
- `test_list_maps_paginates_correctly`
- `test_list_maps_applies_size_filter`
- `test_list_maps_applies_player_filter`
- `test_list_maps_handles_429_with_backoff`
- `test_list_maps_raises_on_api_error`

### Integration Test
```bash
docker-compose run --rm dev pytest tests/python/api/test_client_integration.py -v -m integration
```

### Manual Verification
```bash
docker-compose run --rm dev python -c "
from faf.api.client import FAFApiClient

client = FAFApiClient()
result = client.list_maps(page_size=10, page=1)
print(f'Total maps in vault: {result.total_records}')
for m in result.maps[:3]:
    print(f'  - {m.display_name} ({m.map_size}px, {m.player_count}p)')
"
```

## Dependencies
- Sprint 1 complete (Docker environment)

## References
- FAF API: https://api.faforever.com
- JSON:API spec: https://jsonapi.org/format/