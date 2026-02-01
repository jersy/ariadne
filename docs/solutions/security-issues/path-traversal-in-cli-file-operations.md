---
category: security
module: cli
symptoms:
  - Arbitrary file access via CLI
  - Path traversal vulnerability
  - No validation of file paths
tags:
  - security
  - path-traversal
  - cli
  - file-operations
---

# Path Traversal Vulnerability in CLI File Operations

## Problem

The CLI's `_cmd_summarize()` accepted file paths without validation, allowing access to files outside the project root through path traversal attacks (e.g., `../../../etc/passwd`).

## Detection

```python
# ariadne_cli/main.py (before)
def _cmd_summarize(args: argparse.Namespace) -> None:
    file_path = Path(args.file)  # No validation!
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    # Vulnerable to ../../../etc/passwd
```

## Solution

### 1. Add Path Validation Helper

Create a validation function that ensures paths are within project root:

```python
# ariadne_cli/main.py
def validate_project_path(file_path: str, project_root: Path) -> Path | None:
    """
    Validate that a path is within the project root.

    Returns None if:
    - Path is outside project root (ValueError from relative_to)
    - Path does not exist

    Args:
        file_path: User-provided file path
        project_root: Root directory of the project

    Returns:
        Resolved absolute Path if valid, None otherwise
    """
    try:
        resolved_path = Path(file_path).resolve()
        # Raises ValueError if path is outside project_root
        resolved_path.relative_to(project_root)

        if not resolved_path.exists():
            logger.warning(f"Path does not exist: {file_path}")
            return None

        return resolved_path
    except ValueError:
        logger.warning(f"Path outside project root: {file_path}")
        return None
```

### 2. Update CLI Command to Use Validation

```python
def _cmd_summarize(args: argparse.Namespace) -> None:
    # Get project root from config
    project_root = Path(args.project).resolve()

    # Validate file path
    validated_path = validate_project_path(args.file, project_root)
    if not validated_path:
        logger.error("Invalid file path")
        return

    # Use validated path
    file_path = validated_path
```

### 3. Add Logging

Import logging module for security-relevant events:

```python
import logging

logger = logging.getLogger(__name__)
```

## Why This Matters

- **Prevents unauthorized access**: Users can only access files within the project
- **Security boundary**: Project root defines the security boundary
- **Audit trail**: Logging provides record of blocked attempts

## Testing

```python
import pytest
from pathlib import Path

def test_validate_project_path_blocks_traversal():
    project_root = Path("/safe/project")
    assert validate_project_path("../../../etc/passwd", project_root) is None

def test_validate_project_path_allows_valid():
    project_root = Path("/safe/project")
    assert validate_project_path("src/main.py", project_root) == project_root / "src/main.py"
```

## Files Changed

- `ariadne_cli/main.py` - Added `validate_project_path()`, updated `_cmd_summarize()`, added logging import

## Related

- Todo #003: Path traversal vulnerability
- CWE-22: Improper Limitation of a Pathname to a Restricted Directory ('Path Traversal')
- Security: File system access boundaries
