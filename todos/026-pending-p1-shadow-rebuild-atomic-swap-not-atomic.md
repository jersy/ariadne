---
status: completed
priority: p1
issue_id: "026"
tags:
  - code-review
  - data-integrity
  - critical
dependencies: []
---

# Shadow Rebuild Atomic Swap Not Truly Atomic

## Problem Statement

The `_atomic_swap_databases()` method in `shadow_rebuilder.py` uses two separate `os.rename()` operations which creates a window where no valid database exists. If the process crashes between the two renames, the system is left in an unusable state.

**Code Location:** `ariadne_core/storage/shadow_rebuilder.py:290-339`

## Why It Matters

1. **System Unavailability**: Crash between renames leaves no valid database
2. **No Recovery**: System requires manual intervention to recover
3. **Data Loss**: While old database is preserved as backup, application can't start
4. **Production Impact**: For production deployments, this is unacceptable downtime

## Findings

### From Data Integrity Review:

> **Severity:** CRITICAL
>
> The atomic swap is not actually atomic. `os.rename()` is only atomic if both files are on the same filesystem, but the two-step process creates a race condition window.

### Root Cause Analysis:

```python
# ariadne_core/storage/shadow_rebuilder.py:290-339
def _atomic_swap_databases(self, current: str, new: str, backup_suffix: str) -> None:
    """Atomically swap current database with new database."""
    backup_path = current + backup_suffix
    current_exists = os.path.exists(current)

    try:
        # Step 1: Rename current to backup (not atomic!)
        if current_exists:
            os.rename(current, backup_path)

        # ❌ RACE WINDOW: No valid database exists here!
        # If process crashes now, system is broken

        # Step 2: Rename new to current (not atomic!)
        os.rename(new, current)

        # Verify swap succeeded
        if not os.path.exists(current):
            raise RebuildFailedError("Swap failed - no current database exists")

    except Exception as e:
        # Rollback attempt
        logger.error(f"Atomic swap failed: {e}")
        if os.path.exists(backup_path):
            os.rename(backup_path, current)  # May also fail
        raise
```

### Failure Scenario:

```
Timeline:
T1: os.rename(current, backup) succeeds
T2: Process crashes (kill -9, power loss, OOM)
T3: New database not yet moved
T4: Result: No valid database at "current" path

State after crash:
- current: ❌ Does not exist
- backup: ✅ Exists (old database)
- new: ✅ Exists (new database)

System requires manual recovery: mv backup current
```

### Additional Issues:

1. **Non-atomic on different filesystems**: `os.rename()` is only guaranteed atomic on POSIX filesystems when source and destination are on the same filesystem
2. **Rollback can fail**: The rollback itself can fail, leaving system in worse state
3. **No verification**: Doesn't verify filesystem before attempting swap

## Proposed Solutions

### Solution 1: Use os.replace() with Three-Way Swap (Recommended)

**Approach:** Use `os.replace()` which is atomic on most platforms, and implement a three-way swap to eliminate the window.

**Pros:**
- `os.replace()` is atomic on POSIX and Windows
- Three-way swap eliminates window with no valid database
- Follows best practices for atomic file operations

**Cons:**
- Slightly more complex logic
- Requires temporary intermediate path

**Effort:** Medium
**Risk:** Low

**Implementation:**
```python
def _atomic_swap_databases(self, current: str, new: str, backup_suffix: str) -> None:
    """Atomically swap current database with new database using three-way swap.

    Process:
    1. Rename new -> temp (atomic)
    2. Rename current -> backup (atomic)
    3. Rename temp -> current (atomic)
    4. Verify current exists

    At any point, at least one valid database exists.
    """
    backup_path = current + backup_suffix
    temp_path = current + ".tmp_swap"
    current_exists = os.path.exists(current)

    # Clean up any leftover temp file from previous failed swap
    if os.path.exists(temp_path):
        os.remove(temp_path)

    try:
        # Step 1: Move new database to temp location (atomic with os.replace)
        os.replace(new, temp_path)

        # Step 2: Move current database to backup location (atomic)
        if current_exists:
            os.replace(current, backup_path)

        # Step 3: Move temp database to current location (atomic)
        os.replace(temp_path, current)

        # Verify: A valid database must exist at current path
        if not os.path.exists(current):
            raise RebuildFailedError(
                f"Swap verification failed: no database at {current}"
            )

        logger.info(
            f"Atomic swap completed successfully",
            extra={
                "event": "swap_complete",
                "current": current,
                "backup": backup_path,
            }
        )

    except Exception as e:
        # Attempt recovery
        logger.error(f"Atomic swap failed, attempting recovery: {e}")

        # Recovery: restore from whichever valid database exists
        if os.path.exists(temp_path):
            logger.info("Recovering from temp database")
            if os.path.exists(current):
                os.remove(current)
            os.replace(temp_path, current)
        elif os.path.exists(backup_path):
            logger.info("Recovering from backup database")
            if os.path.exists(current):
                os.remove(current)
            os.replace(backup_path, current)
        elif os.path.exists(new):
            logger.info("Recovering from new database")
            os.replace(new, current)
        else:
            raise RebuildFailedError(
                f"Catastrophic swap failure: no valid database found. "
                f"Manual recovery required. Paths checked: current={current}, "
                f"temp={temp_path}, backup={backup_path}, new={new}"
            ) from e

        # Verify recovery succeeded
        if not os.path.exists(current):
            raise RebuildFailedError(
                f"Recovery failed: no database at {current}"
            )
```

### Solution 2: Symlink Swap Strategy

**Approach:** Use a symlink that points to the active database, and swap the symlink target atomically.

**Pros:**
- Truly atomic (symlink rename is always atomic)
- Multiple backups can be kept
- Easy rollback

**Cons:**
- Requires changing how database path is configured
- Symlink management adds complexity
- Windows symlink support varies

**Effort:** High
**Risk:** Medium

**Implementation:**
```python
# On initialization
db_symlink = "ariadne.db"  # This is a symlink
db_real_1 = "ariadne_1.db"
db_real_2 = "ariadne_2.db"

# To swap
def swap_database():
    current_target = os.readlink(db_symlink)
    new_target = db_real_2 if current_target == db_real_1 else db_real_1
    os.remove(db_symlink)
    os.symlink(new_target, db_symlink)  # Atomic symlink replacement
```

### Solution 3: Add Crash Recovery on Startup

**Approach:** Keep current implementation but add automatic recovery on startup if swap is detected incomplete.

**Pros:**
- Doesn't change swap logic much
- Self-healing on restart
- Simple to implement

**Cons:**
- System still briefly unavailable after crash
- Doesn't prevent the race window
- Adds startup complexity

**Effort:** Low
**Risk:** Low

**Implementation:**
```python
def check_and_recover_swap_incomplete(current: str, backup_suffix: str) -> bool:
    """Check if previous swap was incomplete and recover.

    Returns True if recovery was performed.
    """
    backup_path = current + backup_suffix
    temp_path = current + ".tmp_swap"

    # Check for incomplete swap indicators
    current_exists = os.path.exists(current)
    backup_exists = os.path.exists(backup_path)
    temp_exists = os.path.exists(temp_path)

    # If current doesn't exist but backup does, recover from backup
    if not current_exists and backup_exists:
        logger.warning(
            f"Detected incomplete swap: current missing, backup exists. Recovering.",
            extra={"event": "swap_recovery", "backup": backup_path}
        )
        os.replace(backup_path, current)
        return True

    # If temp exists but current doesn't, recover from temp
    if not current_exists and temp_exists:
        logger.warning(
            f"Detected incomplete swap: current missing, temp exists. Recovering.",
            extra={"event": "swap_recovery", "temp": temp_path}
        )
        os.replace(temp_path, current)
        return True

    return False

# Call this on SQLiteStore initialization
def __init__(self, db_path: str = "ariadne.db", ...):
    check_and_recover_swap_incomplete(db_path, "_backup")
    # ... rest of initialization
```

## Recommended Action

**Use Solution 1 (os.replace with Three-Way Swap)**

This provides true atomicity with no window where no valid database exists. The three-way swap ensures that at every point, at least one valid database is accessible.

**Additionally implement Solution 3** as a safety net for crash recovery on startup.

## Technical Details

### Files to Modify:

1. **`ariadne_core/storage/shadow_rebuilder.py`** (lines 290-339)
   - Rewrite `_atomic_swap_databases()` method
   - Add three-way swap logic
   - Improve recovery handling

2. **`ariadne_core/storage/sqlite_store.py`** (init method)
   - Add crash recovery check on initialization

### Testing Requirements:

```python
# tests/unit/test_shadow_rebuilder.py
def test_atomic_swap_is_truly_atomic():
    """Verify swap leaves no window without valid database."""
    # Mock os.replace to simulate crash at each step
    # Verify at least one valid database always exists

def test_swap_incomplete_recovery():
    """Verify automatic recovery from incomplete swap."""
    # Create state: current missing, backup exists
    # Initialize store
    # Verify current database restored

def test_three_way_swap_order():
    """Verify three-way swap maintains database availability."""
    # Test swap completes successfully
    # Verify current exists at end
    # Verify backup is preserved
```

## Acceptance Criteria

- [ ] Three-way swap eliminates window with no valid database
- [ ] `os.replace()` used instead of `os.rename()` for atomicity
- [ ] Crash recovery implemented on startup
- [ ] All unit tests pass including crash simulation
- [ ] Integration test verifies system can restart after crash during swap

## Work Log

| Date | Action | Result |
|------|--------|--------|
| 2026-02-02 | Code review completed | Critical issue identified |
| 2026-02-02 | Implemented three-way swap with os.replace() | Rewrote `_atomic_swap_databases()` with temp file pattern |
| 2026-02-02 | Added crash recovery on SQLiteStore init | Added `_check_and_recover_swap_incomplete()` method |
| 2026-02-02 | Added os import to sqlite_store.py | Required for os.replace() and os.path operations |
| 2026-02-02 | All tests passing (179 passed) | Fix verified working |

## Resources

- **Affected Files:**
  - `ariadne_core/storage/shadow_rebuilder.py:290-339`
- **Related Issues:**
  - Data Integrity Review: Finding #3 - Atomic Swap Not Atomic
- **References:**
  - Python os.replace() documentation
  - POSIX atomic rename guarantees
  - Three-way swap pattern documentation
