# TICKET-001: Docker Development Environment Setup

## Status
NOT STARTED

## Priority
P0-Critical

## Description
Create a Docker-based development environment that supports all technologies required for this project: Java (for Neroxis Map Generator compatibility), Python (for ML/AI development), and common build tools. The container must be OS-agnostic and runnable via a simple CLI command.

## Acceptance Criteria
- [ ] `Dockerfile` exists at repository root
- [ ] `docker-compose.yml` exists at repository root for easy orchestration
- [ ] Container includes Java 17+ (LTS, required for modern Neroxis builds)
- [ ] Container includes Python 3.11+
- [ ] Container includes Gradle 8.x
- [ ] Container includes common Python ML dependencies: numpy, torch, pillow
- [ ] Container can be built with `docker-compose build`
- [ ] Container can be run interactively with `docker-compose run --rm dev bash`
- [ ] Working directory is mounted at `/workspace` inside container
- [ ] A simple smoke test script exists and passes: `scripts/smoke-test.sh`
- [ ] README.md in repo root is updated with "Getting Started" instructions

## Technical Context

### Neroxis Map Generator Requirements
- Source: https://github.com/FAForever/Neroxis-Map-Generator
- Build system: Gradle (Kotlin DSL)
- Language: Java (originally Java 8, modern versions use 17+)
- Key dependencies: Lombok, JUnit 5

### Python ML Stack (anticipated)
- PyTorch for model training
- NumPy for numerical operations
- Pillow for image I/O (heightmaps are image data)
- Future: diffusers, transformers (not required in this ticket)

### Directory Structure After Completion
```
/
├── Dockerfile
├── docker-compose.yml
├── README.md (updated)
├── scripts/
│   └── smoke-test.sh
└── tickets/
    ├── README.md
    └── 001-docker-environment-setup.md
```

## Out of Scope
- GPU/CUDA support (future ticket)
- CI/CD pipeline setup
- Cloning or building Neroxis source (future ticket)
- Python virtual environments inside container (container IS the isolated env)
- IDE-specific configurations

## Testing Requirements

### Build Test
```bash
docker-compose build
# Expected: Builds successfully with no errors
```

### Smoke Test
```bash
docker-compose run --rm dev bash /workspace/scripts/smoke-test.sh
```

Expected output:
```
[OK] Java version: 17.x.x or higher
[OK] Python version: 3.11.x or higher
[OK] Gradle version: 8.x.x
[OK] PyTorch installed
[OK] NumPy installed
[OK] Pillow installed
[OK] Workspace mounted at /workspace
```

### Interactive Test
```bash
docker-compose run --rm dev bash
# Should drop into bash shell inside container
# pwd should show /workspace
# ls should show repo contents
```

## References
- Neroxis Map Generator: https://github.com/FAForever/Neroxis-Map-Generator
- Docker Compose specification: https://docs.docker.com/compose/compose-file/
- Eclipse Temurin (Java) Docker images: https://hub.docker.com/_/eclipse-temurin