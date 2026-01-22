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

### Development Environment Contents

The development container includes:

- **Java 17** (Eclipse Temurin) - For Neroxis Map Generator compatibility
- **Python 3.11** - For ML/AI development
- **Gradle 8.x** - Build system for Java projects
- **PyTorch** (CPU) - Deep learning framework
- **NumPy** - Numerical computing
- **Pillow** - Image processing

## Project Structure

```
/
├── Dockerfile              # Development environment definition
├── docker-compose.yml      # Container orchestration
├── README.md               # This file
├── CLAUDE.md               # Coding standards and conventions
├── scripts/
│   └── smoke-test.sh       # Environment verification script
└── tickets/
    ├── README.md           # Ticket format specification
    └── *.md                # Individual tickets
```

## License

See LICENSE file for details.
