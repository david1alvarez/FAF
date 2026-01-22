# FAF Map AI

Scripts and utilities focused on supporting the Forged Alliance Forever community mod for the classic RTS game, Supreme Commander: Forged Alliance.

## Getting Started

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) installed and running
- [Docker Compose](https://docs.docker.com/compose/install/) (included with Docker Desktop)

### Building the Development Environment

Build the Docker container:

```bash
docker compose build
```

### Running the Development Environment

Start an interactive shell:

```bash
docker compose run --rm dev bash
```

This drops you into a bash shell at `/workspace` with the repository mounted.

### Verifying the Installation

Run the smoke test to verify all dependencies are installed correctly:

```bash
docker compose run --rm dev bash /workspace/scripts/smoke-test.sh
```

Expected output:

```
=== FAF Map AI Smoke Test ===

[OK] Java version: openjdk version "17.x.x" ...
[OK] Python version: Python 3.11.x
[OK] Gradle version: Gradle 8.x
[OK] PyTorch installed: x.x.x
[OK] NumPy installed: x.x.x
[OK] Pillow installed: x.x.x
[OK] Workspace mounted at /workspace

=== Results ===
Passed: 7
Failed: 0

All checks passed!
```

## CLI Usage

The FAF CLI provides commands for downloading and parsing Supreme Commander maps.

### Download a Map

Download a map from the FAF content server:

```bash
docker compose run --rm faf download https://content.faforever.com/maps/theta_passage_5.v0001.zip
```

With custom output directory:

```bash
docker compose run --rm faf download https://content.faforever.com/maps/theta_passage_5.v0001.zip --output-dir /data/maps
```

### Parse a Map File

Parse a local .scmap file and output JSON:

```bash
docker compose run --rm faf parse /data/maps/theta_passage_5.v0001/theta_passage_5.scmap
```

Save heightmap as NumPy array:

```bash
docker compose run --rm faf parse /data/maps/theta_passage_5.v0001/theta_passage_5.scmap --output numpy --output-file /data/heightmap.npy
```

### Display Map Information

Show a summary of map metadata:

```bash
docker compose run --rm faf info /data/maps/theta_passage_5.v0001/theta_passage_5.scmap
```

Example output:

```
Map: theta_passage_5
Version: 60
Size: 256x256 (5km)
Heightmap: 257x257
Heightmap Scale: 0.0078125
Water Elevation: 25.0
Textures: 4 stratum layers
```

### Fetch (Download + Info)

Download a map and immediately display its information:

```bash
docker compose run --rm faf fetch https://content.faforever.com/maps/theta_passage_5.v0001.zip --output-dir /data/maps
```

### Getting Help

View available commands:

```bash
docker compose run --rm faf --help
```

View help for a specific command:

```bash
docker compose run --rm faf download --help
```

## Development Environment Contents

The development container includes:

- **Java 17** (Eclipse Temurin) - For Neroxis Map Generator compatibility
- **Python 3.11** - For ML/AI development
- **Gradle 8.x** - Build system for Java projects
- **PyTorch** (CPU) - Deep learning framework
- **NumPy** - Numerical computing
- **Pillow** - Image processing
- **Click** - CLI framework
- **Requests** - HTTP library

## Project Structure

```
/
├── Dockerfile              # Development environment definition
├── docker-compose.yml      # Container orchestration
├── pyproject.toml          # Python project configuration
├── README.md               # This file
├── CLAUDE.md               # Coding standards and conventions
├── src/
│   └── python/
│       └── faf/
│           ├── cli/        # Command-line interface
│           ├── downloader/ # Map download utilities
│           └── parser/     # SCMap file parser
├── tests/
│   └── python/             # Python unit tests
├── scripts/
│   └── smoke-test.sh       # Environment verification script
└── tickets/
    ├── README.md           # Ticket format specification
    └── *.md                # Individual tickets
```

## Running Tests

Run all tests:

```bash
docker compose run --rm dev bash -c "PYTHONPATH=src/python pytest tests/python/ -v"
```

Run specific test file:

```bash
docker compose run --rm dev bash -c "PYTHONPATH=src/python pytest tests/python/cli/test_main.py -v"
```

## Debugging

### "Command not found" errors

If you see errors like `pytest: command not found` or similar, the Docker image may be outdated.
Rebuild it with:

```bash
docker compose build --no-cache
```

### Stale containers

If changes to `docker-compose.yml` or `Dockerfile` aren't taking effect, remove old containers:

```bash
docker compose down
docker compose build --no-cache
```

## License

See LICENSE file for details.
