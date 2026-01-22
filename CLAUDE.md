# CLAUDE.md

> Project conventions and coding standards for AI coding assistants.

## Project Overview

**FAF Map AI** - A toolset for training and running AI models that generate maps for Supreme Commander: Forged Alliance (via Forged Alliance Forever).

**Tech Stack:**
- **Python 3.11+**: ML/AI pipeline, data processing, CLI tools
- **Java 17+**: Neroxis Map Generator integration, SCMap file I/O
- **Docker**: Development environment, deployment
- **PyTorch**: Model training and inference

## Architecture Principles

### 1. Separation of Concerns
```
src/
├── python/           # All Python code
│   ├── cli/          # Command-line interfaces
│   ├── data/         # Data loading, preprocessing
│   ├── models/       # Model definitions
│   ├── training/     # Training loops, configs
│   └── utils/        # Shared utilities
├── java/             # All Java code (if needed beyond Neroxis)
└── scripts/          # Shell scripts for automation
```

### 2. Dependency Direction
- CLI depends on training/models
- Training depends on models and data
- Models depend on nothing (pure definitions)
- Data depends on utils only
- Utils depend on nothing internal

### 3. Configuration Over Code
- All hyperparameters in config files (YAML/JSON)
- No magic numbers in source code
- Environment-specific config via environment variables

## Python Standards

### Style
- **Formatter**: `black` (line length 100)
- **Linter**: `ruff`
- **Type hints**: Required on all public functions
- **Docstrings**: Google style, required on all public functions

### Example Function
```python
def load_heightmap(path: Path, normalize: bool = True) -> np.ndarray:
    """Load a heightmap from an SCMap file.

    Args:
        path: Path to the .scmap file.
        normalize: If True, scale values to [0, 1] range.

    Returns:
        2D numpy array of height values.

    Raises:
        FileNotFoundError: If the scmap file doesn't exist.
        ValueError: If the file is not a valid SCMap.
    """
    # Implementation
```

### Imports
```python
# Standard library (alphabetical)
import os
from pathlib import Path
from typing import Optional

# Third-party (alphabetical)
import numpy as np
import torch
from torch import nn

# Local (alphabetical, explicit)
from faf.data.loader import MapDataset
from faf.utils.logging import get_logger
```

### Error Handling
```python
# DO: Specific exceptions with context
raise ValueError(f"Invalid map size {size}. Expected one of {VALID_SIZES}")

# DON'T: Bare exceptions or generic messages
raise Exception("Error")
```

### Testing
- **Framework**: `pytest`
- **Location**: `tests/` mirroring `src/` structure
- **Naming**: `test_<module>.py`, functions `test_<behavior>()`
- **Coverage**: Minimum 80% for new code

```python
# tests/python/data/test_loader.py
def test_load_heightmap_returns_correct_shape():
    """Heightmap should match map dimensions + 1."""
    result = load_heightmap(FIXTURE_PATH / "test_10km.scmap")
    assert result.shape == (513, 513)

def test_load_heightmap_raises_on_missing_file():
    """Should raise FileNotFoundError for missing files."""
    with pytest.raises(FileNotFoundError):
        load_heightmap(Path("/nonexistent.scmap"))
```

## Java Standards

### Style
- **Formatter**: Google Java Format
- **Build**: Gradle (Kotlin DSL)
- **Target**: Java 17 LTS

### Naming
- Classes: `PascalCase`
- Methods/variables: `camelCase`
- Constants: `SCREAMING_SNAKE_CASE`
- Packages: `lowercase`

### Null Safety
```java
// DO: Use Optional for nullable returns
public Optional<SCMap> loadMap(Path path) { ... }

// DO: Validate inputs early
public void processMap(SCMap map) {
    Objects.requireNonNull(map, "map must not be null");
    // ...
}

// DON'T: Return null
public SCMap loadMap(Path path) { return null; }  // Bad
```

## Git Conventions

### Branch Names
```
feature/XXX-short-description
bugfix/XXX-short-description
```

### Commit Messages
```
{feat|fix}(XXX): Short description (50 chars max)

- Detailed point 1
- Detailed point 2

Refs: #issue-number (if applicable)
```

### PR Requirements
- All tests pass
- No linter errors
- Ticket acceptance criteria met
- Self-review completed

## Docker Standards

### Dockerfile
- Use specific version tags, never `latest`
- Order commands from least to most frequently changed
- Combine RUN commands to reduce layers
- Use multi-stage builds for production

```dockerfile
# DO
FROM eclipse-temurin:17-jdk-jammy AS builder
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# DON'T
FROM eclipse-temurin:latest
RUN apt-get update
RUN apt-get install -y build-essential
RUN apt-get install -y curl
```

## File Naming

| Type | Convention | Example |
|------|------------|---------|
| Python modules | `snake_case.py` | `map_loader.py` |
| Python classes | `PascalCase` | `class MapDataset` |
| Java files | `PascalCase.java` | `SCMapExporter.java` |
| Config files | `kebab-case.yaml` | `training-config.yaml` |
| Scripts | `kebab-case.sh` | `smoke-test.sh` |
| Tickets | `NNN-kebab-case.md` | `001-docker-setup.md` |

## Documentation

### Required Documentation
- `README.md`: Project overview, quickstart, usage
- `CLAUDE.md`: This file (coding standards)
- `tickets/README.md`: Ticket format specification
- Docstrings on all public APIs

### Markdown Style
- One sentence per line (easier diffs)
- Code blocks with language specifier
- Relative links for internal docs

## Security

### Secrets
- Never commit secrets, tokens, or credentials
- Use environment variables for sensitive config
- Add sensitive patterns to `.gitignore`

### Dependencies
- Pin exact versions in requirements/build files
- Review dependencies before adding
- Prefer well-maintained, widely-used packages

## Performance

### Python
- Profile before optimizing
- Use NumPy vectorization over Python loops
- Lazy loading for large datasets
- Generator functions for memory efficiency

### General
- Document performance-critical sections
- Include benchmarks in PR if performance-relevant

## AI Assistant Guidelines

### When Implementing Tickets
1. Read the full ticket before starting
2. Check existing code for patterns to follow
3. Write tests alongside implementation
4. Run all tests before committing
5. Update relevant documentation

### When Uncertain
- State assumptions explicitly in PR description
- Prefer conservative, working solutions over clever ones
- Add TODO comments for known limitations

### Code Review Checklist
- [ ] Acceptance criteria met
- [ ] Tests added/updated
- [ ] No regressions in existing tests
- [ ] Follows conventions in this file
- [ ] No hardcoded values that should be config
- [ ] Error messages are actionable
- [ ] No security issues introduced