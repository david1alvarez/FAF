# TICKET-004: CLI Tool Integration

## Status
COMPLETE

## Claude Code Working Area
- [x] Read ticket and explore codebase
- [x] Create CLI module with Click-based commands
- [x] Implement download, parse, info, fetch commands
- [x] Update pyproject.toml with entry point
- [x] Update Dockerfile to install click and requests
- [x] Update docker-compose.yml with faf service
- [x] Update README.md with CLI usage examples
- [x] Create unit tests (19 tests)
- [x] Run black and ruff checks
- [x] Run tests and verify (60 total tests passing)
- [x] Self-review and update status

## Priority
P1-High

## Description
Create a command-line interface that exposes the map download and parsing functionality. Users should be able to run simple commands via docker-compose to fetch maps and extract data from them.

## Acceptance Criteria
- [x] `src/python/faf/cli/main.py` exists with CLI entry point
- [x] CLI uses `click` library for argument parsing
- [x] Command `faf download <url> [--output-dir DIR]` downloads and extracts a map
- [x] Command `faf parse <scmap_path> [--output FORMAT]` parses an .scmap file
- [x] Command `faf info <scmap_path>` prints map metadata summary
- [x] Command `faf fetch <url> [--output-dir DIR]` downloads AND parses (convenience)
- [x] All commands have `--help` documentation
- [x] Exit codes: 0 for success, 1 for user error, 2 for system error
- [x] Errors print human-readable messages to stderr
- [x] `pyproject.toml` configured with `[project.scripts]` entry point
- [x] `docker-compose.yml` updated with convenient command aliases
- [x] README.md updated with CLI usage examples
- [x] Tests for CLI argument parsing and error handling

## Technical Context

### CLI Structure
```
faf <command> [options] [arguments]

Commands:
  download   Download a map from URL
  parse      Parse a local .scmap file
  info       Display map information
  fetch      Download and parse in one step
```

### Command Specifications

#### `faf download`
```bash
faf download <url> [--output-dir DIR]

# Example:
faf download https://content.faforever.com/maps/theta_passage_5.v0001.zip
# Output: Downloaded to ./maps/theta_passage_5.v0001/

faf download https://content.faforever.com/maps/theta_passage_5.v0001.zip --output-dir /data
# Output: Downloaded to /data/theta_passage_5.v0001/
```

#### `faf parse`
```bash
faf parse <scmap_path> [--output FORMAT] [--output-file PATH]

# Formats: json (default), numpy
# Example:
faf parse ./maps/theta_passage_5.v0001/theta_passage_5.scmap
# Output: JSON to stdout

faf parse ./maps/theta_passage_5.scmap --output numpy --output-file heightmap.npy
# Output: Saves heightmap as .npy file
```

#### `faf info`
```bash
faf info <scmap_path>

# Example output:
# Map: theta_passage_5
# Version: 60 (Forged Alliance)
# Size: 256x256 (5km)
# Heightmap: 257x257
# Water Elevation: 25.0
# Textures: 4 stratum layers
```

#### `faf fetch`
```bash
faf fetch <url> [--output-dir DIR]

# Downloads map, parses it, prints info
# Equivalent to: download + info
```

### Docker Compose Integration
```yaml
services:
  dev:
    # ... existing config ...
    entrypoint: ["python", "-m", "faf.cli.main"]
    
  # Alternative: keep dev as bash, add specific commands
  faf:
    build: .
    volumes:
      - .:/workspace
      - ./data:/data
    entrypoint: ["python", "-m", "faf.cli.main"]
```

Usage:
```bash
# Interactive development
docker-compose run --rm dev bash

# Direct CLI commands
docker-compose run --rm faf download <url>
docker-compose run --rm faf parse /data/maps/test.scmap
```

### pyproject.toml Entry Point
```toml
[project.scripts]
faf = "faf.cli.main:cli"
```

### Directory Structure After Completion
```
src/
└── python/
    └── faf/
        ├── __init__.py
        ├── cli/
        │   ├── __init__.py
        │   └── main.py
        ├── parser/
        │   └── scmap.py
        └── downloader/
            └── maps.py
tests/
└── python/
    └── cli/
        └── test_main.py
pyproject.toml          # Updated with entry point
docker-compose.yml      # Updated with faf service
README.md               # Updated with usage examples
```

## Out of Scope
- Interactive/TUI mode
- Shell completion scripts
- Configuration file support
- Verbose/debug logging flags (use LOGLEVEL env var)
- Batch processing multiple maps

## Testing Requirements

### Unit Tests
```bash
docker-compose run --rm dev pytest tests/python/cli/test_main.py -v
```

Expected test cases:
- `test_download_command_calls_downloader`
- `test_parse_command_calls_parser`
- `test_info_command_prints_summary`
- `test_invalid_url_exits_with_code_1`
- `test_missing_file_exits_with_code_1`
- `test_help_flag_shows_usage`

### End-to-End Test
```bash
# Full workflow test
docker-compose run --rm faf fetch https://content.faforever.com/maps/theta_passage_5.v0001.zip --output-dir /data/maps
# Should print map info summary
# Exit code should be 0

# Verify files exist
docker-compose run --rm dev ls -la /data/maps/theta_passage_5.v0001/
```

## Dependencies
- TICKET-001: Docker environment
- TICKET-002: SCMap parser
- TICKET-003: Map downloader

## References
- Click documentation: https://click.palletsprojects.com/
- Python packaging scripts: https://packaging.python.org/en/latest/specifications/entry-points/