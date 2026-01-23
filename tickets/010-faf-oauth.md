# TICKET-010: FAF OAuth Implementation

## Status
TESTING AND REVISIONS

## Claude Code Working Area
- [x] Read ticket and understand requirements
- [x] Implement auth.py with FAFAuthClient class
- [x] Update FAFApiClient to support authentication
- [x] Add unit tests with mocked OAuth responses (29 tests)
- [x] Add CLI flags for credentials (--auth-config, env vars, --no-auth)
- [x] Run black and ruff checks
- [ ] Integration tests (pending credentials)
- [ ] Remove seed file fallback (pending credentials verification - see TODO-012)
- [ ] Self-review and update status

## Priority
P2-Medium

## Description
Implement OAuth2 authentication for the FAF API to enable dynamic map discovery. The FAF API now requires authentication (see TODO-002), blocking programmatic access to map listings. This ticket restores full API functionality and removes the need for the static URL fallback in TICKET-006.

## Acceptance Criteria
- [x] `src/python/faf/api/auth.py` exists with `FAFAuthClient` class
- [x] Supports OAuth2 client credentials flow
- [x] Securely stores/retrieves tokens (environment variables or config file)
- [x] Automatically refreshes expired tokens
- [x] `FAFApiClient` updated to use authentication when credentials available
- [x] CLI commands support `--auth-config` flag for credentials file
- [ ] Documentation for obtaining FAF API credentials
- [ ] **Remove `data/seed_map_urls.txt` static fallback from TICKET-006** (TODO-012)
- [ ] **Update `bulk-download` command to use API by default** (TODO-012)
- [ ] Integration tests pass with authenticated requests (pending credentials)
- [x] Unit tests with mocked OAuth responses
- [x] Code passes `black` and `ruff` checks

## Technical Context

### FAF OAuth2 Flow
FAF uses standard OAuth2. Based on FAF ecosystem patterns:

```
1. Register application with FAF (manual, one-time)
2. Obtain client_id and client_secret
3. Request access token:
   POST https://hydra.faforever.com/oauth2/token
   Content-Type: application/x-www-form-urlencoded
   
   grant_type=client_credentials
   &client_id=YOUR_CLIENT_ID
   &client_secret=YOUR_CLIENT_SECRET
   &scope=public_profile

4. Use token in API requests:
   GET https://api.faforever.com/data/map
   Authorization: Bearer ACCESS_TOKEN

5. Refresh token before expiry (typically 1 hour)
```

### Credential Storage Options

**Option 1: Environment Variables (Recommended for CI/containers)**
```bash
export FAF_CLIENT_ID="your_client_id"
export FAF_CLIENT_SECRET="your_client_secret"
```

**Option 2: Config File (Recommended for local development)**
```yaml
# ~/.faf/credentials.yaml (chmod 600)
client_id: "your_client_id"
client_secret: "your_client_secret"
```

**Option 3: CLI Flags (For one-off use)**
```bash
faf bulk-download --client-id XXX --client-secret YYY --output-dir /data/maps
```

### Data Classes
```python
@dataclass
class FAFCredentials:
    client_id: str
    client_secret: str

@dataclass
class FAFToken:
    access_token: str
    token_type: str
    expires_at: datetime
    scope: str
    
    @property
    def is_expired(self) -> bool:
        return datetime.utcnow() >= self.expires_at - timedelta(minutes=5)
```

### Updated FAFApiClient
```python
class FAFApiClient:
    def __init__(
        self,
        auth_client: FAFAuthClient | None = None,
        # ... existing params
    ):
        self.auth_client = auth_client
    
    def _get_headers(self) -> dict[str, str]:
        headers = {**DEFAULT_HEADERS}
        if self.auth_client:
            token = self.auth_client.get_valid_token()
            headers["Authorization"] = f"Bearer {token.access_token}"
        return headers
```

### CLI Integration
```bash
# Use environment variables (automatic)
export FAF_CLIENT_ID="xxx"
export FAF_CLIENT_SECRET="yyy"
faf bulk-download --limit 100 --output-dir /data/maps

# Use config file
faf bulk-download --auth-config ~/.faf/credentials.yaml --output-dir /data/maps

# Without auth (falls back to seed file with warning - until this ticket removes it)
faf bulk-download --no-auth --output-dir /data/maps
```

### Directory Structure After Completion
```
src/
└── python/
    └── faf/
        ├── api/
        │   ├── __init__.py
        │   ├── client.py      # Updated with auth support
        │   └── auth.py        # NEW: OAuth implementation
        └── ...
docs/
└── faf-api-setup.md           # NEW: How to obtain credentials
```

### Cleanup Tasks
Upon completion, remove the temporary fallback:
1. Delete `data/seed_map_urls.txt`
2. Remove `--from-file` fallback logic that auto-uses seed file
3. Update CLI help text to remove fallback mentions
4. Update TICKET-006 status/notes

## Out of Scope
- User-based OAuth flows (authorization code grant)
- Token persistence across container restarts (use env vars)
- GUI for credential management
- Multiple account support
- FAF account registration automation

## Testing Requirements

### Unit Tests
```bash
docker-compose run --rm dev pytest tests/python/api/test_auth.py -v
```

Expected test cases:
- `test_auth_client_requests_token`
- `test_auth_client_refreshes_expired_token`
- `test_auth_client_reads_env_credentials`
- `test_auth_client_reads_file_credentials`
- `test_auth_client_raises_on_invalid_credentials`
- `test_api_client_uses_auth_header`
- `test_api_client_works_without_auth`

### Integration Test
```bash
# Requires real credentials (skip in CI without secrets)
docker-compose run --rm dev pytest tests/python/api/test_auth_integration.py -v -m integration
```

### Manual Verification
```bash
# Set credentials
export FAF_CLIENT_ID="your_id"
export FAF_CLIENT_SECRET="your_secret"

# Verify authenticated API access
docker-compose run --rm dev python -c "
from faf.api.client import FAFApiClient
from faf.api.auth import FAFAuthClient

auth = FAFAuthClient.from_environment()
client = FAFApiClient(auth_client=auth)
result = client.list_maps(page_size=5)
print(f'Authenticated! Found {result.total_records} maps')
for m in result.maps:
    print(f'  - {m.display_name}')
"

# Verify bulk download works without seed file
docker-compose run --rm faf bulk-download --limit 10 --output-dir /data/maps
```

## Dependencies
- TICKET-005: FAF API client (base implementation)
- TICKET-006: Bulk downloader (remove fallback upon completion)

## Research Required
Before implementation, investigate:
1. FAF developer portal / app registration process
2. Exact OAuth endpoints (hydra.faforever.com vs other)
3. Required scopes for map vault access
4. Rate limits for authenticated requests
5. Community contact for API access questions

## References
- FAF API: https://api.faforever.com
- FAF GitHub (for OAuth patterns): https://github.com/FAForever
- OAuth2 Client Credentials: https://oauth.net/2/grant-types/client-credentials/
- Python requests-oauthlib: https://requests-oauthlib.readthedocs.io/

## Claude Code Working Area
### Implementation Notes
**Completed:**
- `FAFAuthClient` class with OAuth2 client credentials flow
- Token caching with 5-minute expiry buffer for automatic refresh
- Three credential sources: config file, environment variables, direct credentials
- Helper functions: `get_credentials_from_environment()`, `has_credentials_in_environment()`
- `FAFApiClient` integration via optional `auth_client` parameter
- CLI flags: `--auth-config`, `--no-auth` for bulk-download command
- 29 unit tests for auth module (all passing)
- All 261 tests pass, black and ruff checks pass

**Pending (requires credentials):**
- Integration tests with real FAF API
- Switch bulk-download from seed file to API (TODO-012)
- Remove seed file fallback after verification
- Documentation for obtaining FAF API credentials