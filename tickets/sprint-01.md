# Sprint 1: Foundation

## Goal
Establish a functional Docker-based development environment where a user can run CLI commands to download FAF maps and parse their .scmap files for data extraction.

## Success Criteria
```bash
# This workflow should work end-to-end:
docker-compose run --rm faf fetch https://content.faforever.com/maps/theta_passage_5.v0001.zip --output-dir /data/maps

# Expected output:
# Downloading theta_passage_5.v0001.zip...
# Extracting...
# Parsing theta_passage_5.scmap...
#
# Map: theta_passage_5
# Version: 60 (Forged Alliance)
# Size: 256x256 (5km)
# Heightmap: 257x257
# Water Elevation: 25.0
```

## Tickets

| ID | Title | Priority | Dependencies | Status |
|----|-------|----------|--------------|--------|
| 001 | Docker Environment Setup | P0 | - | NOT STARTED |
| 002 | SCMap Binary Parser | P0 | 001 | NOT STARTED |
| 003 | Map Download Utility | P0 | 001 | NOT STARTED |
| 004 | CLI Integration | P1 | 002, 003 | NOT STARTED |

## Execution Order
1. **TICKET-001** - Must be first, provides dev environment
2. **TICKET-002** and **TICKET-003** - Can be done in parallel after 001
3. **TICKET-004** - Requires both 002 and 003 complete

## Architecture Overview
```
┌─────────────────────────────────────────────────────────┐
│                    Docker Container                      │
│  ┌─────────────────────────────────────────────────┐   │
│  │                  CLI (click)                      │   │
│  │  faf download | faf parse | faf info | faf fetch │   │
│  └──────────┬────────────────────┬──────────────────┘   │
│             │                    │                       │
│  ┌──────────▼──────────┐  ┌─────▼─────────────┐        │
│  │   MapDownloader     │  │   SCMapParser     │        │
│  │   - HTTP client     │  │   - Binary reader │        │
│  │   - Zip extraction  │  │   - Heightmap     │        │
│  │   - Validation      │  │   - Metadata      │        │
│  └─────────────────────┘  └───────────────────┘        │
│                                                          │
│  Python 3.11 | NumPy | Requests | Click                 │
└─────────────────────────────────────────────────────────┘
```

## Non-Goals for This Sprint
- GPU/CUDA support
- ML model training
- Map generation
- Java/Neroxis integration
- FAF API authentication
- Caching layer

## Notes for Claude Code
- Read `CLAUDE.md` first for coding standards
- Each ticket is self-contained with full context
- Run tests after each implementation
- Commit with ticket reference: `[TICKET-XXX] description`
- Ask for clarification via PR comments if requirements are ambiguous