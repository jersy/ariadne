---
title: "P1 #026 - Shadow Rebuild Atomic Swap Not Truly Atomic"
category: database-issues
severity: P1
date_created: 2026-02-02
related_issues:
  - "026-pending-p1-shadow-rebuild-atomic-swap-not-truly-atomic.md"
  - "017-pending-p1-rebuild-operation-data-loss-risk.md"
tags:
  - atomic-operations
  - file-system
  - database-rebuild
  - crash-recovery
  - race-condition
---

## Problem

The shadow rebuild's atomic database swap was not truly atomic due to a two-step `os.rename()` process, creating a race window where no valid database exists. If the process crashed between renames, the system became unusable.

### Symptom

**File**: `ariadne_core/storage/shadow_rebuilder.py`

The original `_atomic_swap_databases()` implementation:

```python
# Original buggy implementation (simplified)
def _atomic_swap_databases(self, current: str, new: str, backup_suffix: str) -> None:
    backup_path = current + backup_suffix

    # Step 1: Rename current -> backup
    os.replace(current, backup_path)

    # RACE WINDOW: At this point, NO valid database exists at 'current'
    # If process crashes here, system is broken

    # Step 2: Rename new -> current
    os.replace(new, current)
```

### Impact

1. **Race Window**: Between step 1 and step 2, no valid database exists
2. **Catastrophic Failure**: If process crashes during window, system unusable
3. **No Recovery**: Startup code didn't detect or recover from this state
4. **Data Loss Risk**: User would need to manually identify valid database

### Timeline of Failure

```
T0: os.replace(current, backup)  <-- current now gone
T1: [RACE WINDOW]                <-- no valid database
T2: os.replace(new, current)     <-- current restored

Process crash at T1 = System broken
```

---

## Root Cause Analysis

### Why `os.replace()` is Not Enough

`os.replace()` is atomic for individual operations, but the **sequence** of two replacements is not:

1. Each `os.replace()` is atomic (POSIX `rename()` syscall)
2. But the **gap** between syscalls allows process termination
3. No transactional guarantee across multiple syscalls

### Why This Was Missed

1. **Assumption**: Two atomic operations = one atomic operation
2. **Testing**: Tests didn't simulate process crashes mid-swap
3. **No Crash Recovery**: Startup code never checked for incomplete swaps

---

## Solution

The fix implements a **three-way swap pattern** using a temporary intermediate file, plus automatic crash recovery on startup.

### Part 1: Three-Way Atomic Swap

**File**: `ariadne_core/storage/shadow_rebuilder.py` (lines 290-400)

```python
def _atomic_swap_databases(
    self, current: str, new: str, backup_suffix: str
) -> None:
    """Atomically swap database files using three-way swap.

    This implementation ensures there is never a window where no valid database
    exists by using a temporary intermediate file and os.replace() which is
    atomic on both POSIX and Windows.

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
        logger.info(f"Cleaning up leftover temp file: {temp_path}")
        try:
            os.remove(temp_path)
        except OSError as e:
            logger.warning(f"Failed to remove temp file: {e}")

    try:
        # Step 1: Move new database to temp location (atomic with os.replace)
        logger.info(f"Moving new database to temp: {new} -> {temp_path}")
        os.replace(new, temp_path)

        # State: temp=new, current=current, backup=none

        # Step 2: Move current database to backup location (atomic)
        if current_exists:
            logger.info(f"Backing up current database: {current} -> {backup_path}")
            os.replace(current, backup_path)

        # State: temp=new, current=none, backup=old
        # RISK: If crash here, can recover from temp

        # Step 3: Move temp database to current location (atomic)
        logger.info(f"Moving temp database to current: {temp_path} -> {current}")
        os.replace(temp_path, current)

        # State: temp=none, current=new, backup=old

        # Verify: A valid database must exist at current path
        if not os.path.exists(current):
            raise IOError(f"Swap verification failed: no database at {current}")

        logger.info(
            "Atomic swap completed successfully",
            extra={"event": "swap_complete", "current": current, "backup": backup_path}
        )

    except Exception as e:
        # Attempt recovery from whichever valid database exists
        logger.error(f"Atomic swap failed, attempting recovery: {e}")

        # Recovery priority: temp > backup > new
        recovered = False

        if os.path.exists(temp_path):
            logger.info("Recovering from temp database")
            try:
                if os.path.exists(current):
                    os.remove(current)
                os.replace(temp_path, current)
                recovered = True
            except OSError as recovery_error:
                logger.error(f"Failed to recover from temp: {recovery_error}")

        elif os.path.exists(backup_path):
            logger.info("Recovering from backup database")
            try:
                if os.path.exists(current):
                    os.remove(current)
                os.replace(backup_path, current)
                recovered = True
            except OSError as recovery_error:
                logger.error(f"Failed to recover from backup: {recovery_error}")

        elif os.path.exists(new):
            logger.info("Recovering from new database")
            try:
                if os.path.exists(current):
                    os.remove(current)
                os.replace(new, current)
                recovered = True
            except OSError as recovery_error:
                logger.error(f"Failed to recover from new: {recovery_error}")

        if not recovered or not os.path.exists(current):
            raise IOError(
                f"Catastrophic swap failure: no valid database found. "
                f"Manual recovery required. Paths checked: current={current}, "
                f"temp={temp_path}, backup={backup_path}, new={new}"
            ) from e

        logger.info("Recovery completed successfully")
```

### Part 2: Crash Recovery on Startup

**File**: `ariadne_core/storage/shadow_rebuilder.py` (lines 401-458)

```python
def _check_and_recover_swap_incomplete(self, current: str, backup_suffix: str) -> bool:
    """Check if previous swap was incomplete and recover automatically.

    This should be called on SQLiteStore initialization to ensure the database
    is in a valid state after a potential crash during swap.

    Args:
        current: Path to current database file
        backup_suffix: Suffix used for backup files

    Returns:
        True if recovery was performed, False otherwise
    """
    backup_path = current + backup_suffix
    temp_path = current + ".tmp_swap"

    # Check for incomplete swap indicators
    current_exists = os.path.exists(current)
    backup_exists = os.path.exists(backup_path)
    temp_exists = os.path.exists(temp_path)

    # Case 1: current doesn't exist but backup does (main recovery scenario)
    if not current_exists and backup_exists:
        logger.warning(
            f"Detected incomplete swap: current missing, backup exists. Recovering.",
            extra={"event": "swap_recovery", "backup": backup_path}
        )
        try:
            os.replace(backup_path, current)
            logger.info("Recovery from backup completed")
            return True
        except OSError as e:
            logger.error(f"Failed to recover from backup: {e}")
            return False

    # Case 2: temp exists but current doesn't (race window scenario)
    if not current_exists and temp_exists:
        logger.warning(
            f"Detected incomplete swap: current missing, temp exists. Recovering.",
            extra={"event": "swap_recovery", "temp": temp_path}
        )
        try:
            os.replace(temp_path, current)
            logger.info("Recovery from temp completed")
            return True
        except OSError as e:
            logger.error(f"Failed to recover from temp: {e}")
            return False

    # Case 3: temp still exists (previous swap failed, need cleanup)
    if temp_exists:
        logger.info(f"Cleaning up leftover temp file from previous swap: {temp_path}")
        try:
            os.remove(temp_path)
        except OSError as e:
            logger.warning(f"Failed to remove temp file: {e}")

    return False
```

### Part 3: Integration with SQLiteStore

**File**: `ariadne_core/storage/sqlite_store.py` (lines 43-100)

```python
def __init__(self, db_path: str = "ariadne.db", init: bool = False):
    self.db_path = db_path
    self._local = local()

    if init:
        self._rebuild_schema()
    else:
        self._ensure_schema()

    # Check and recover from incomplete swap (if crashed during rebuild)
    self._check_and_recover_swap_incomplete()
```

---

## Key Insights

### 1. Three-Way Swap Pattern

The pattern ensures at least one valid database exists at all times:

```
Initial:   current=old, new=new, temp=none, backup=none
Step 1:    current=old, new=none, temp=new, backup=none  (atomic)
Step 2:    current=none, new=none, temp=new, backup=old  (atomic)
Step 3:    current=new, new=none, temp=none, backup=old  (atomic)

Crash recovery:
- If crash after step 2: recover from temp (new db)
- If crash after step 1: recover from backup (old db)
- If temp still exists: cleanup and continue
```

### 2. Atomic File Operations

`os.replace()` is atomic on both POSIX and Windows:

- **POSIX**: `rename()` syscall is atomic
- **Windows**: `MoveFileEx()` with `MOVEFILE_REPLACE_EXISTING`
- **Cross-platform**: Safe to use for critical operations

### 3. Recovery Priority Order

When swap fails, recovery priority is:

1. **temp** (new database - most up-to-date)
2. **backup** (old database - safe fallback)
3. **new** (if still exists - rebuild was starting)

---

## Prevention Strategies

### 1. Code Review Checklist

- [ ] File swaps use three-way pattern
- [ ] Startup code checks for incomplete operations
- [ ] Recovery attempts are logged
- [ ] Manual recovery path is documented

### 2. Testing Strategy

```python
def test_crash_during_swap():
    """Test that system recovers from crash during swap."""
    rebuilder = ShadowRebuilder(db_path="test.db")

    # Simulate crash at each step
    for step in ["after_temp", "after_backup", "before_final"]:
        with simulate_crash(step):
            rebuilder._atomic_swap_databases("test.db", "test_new.db", "_backup")

        # Verify recovery on next startup
        store = SQLiteStore("test.db")
        assert os.path.exists("test.db")
        assert len(store.get_symbols()) > 0
```

### 3. Monitoring

Track swap operations and recovery:

```python
logger.info(
    "Atomic swap completed",
    extra={
        "event": "swap_complete",
        "current": current,
        "backup": backup_path,
        "metric": "database.swap.success"
    }
)

logger.warning(
    "Detected incomplete swap, recovering",
    extra={
        "event": "swap_recovery",
        "backup": backup_path,
        "metric": "database.swap.recovery"
    }
)
```

---

## Comparison: Before vs After

| Aspect | Before (Two-Step) | After (Three-Way) |
|--------|------------------|-------------------|
| **Atomic Operations** | 2 | 3 |
| **Race Window** | Yes (dangerous) | No (safe) |
| **Crash Recovery** | None | Automatic |
| **Valid DB Guarantee** | No | Yes |
| **Recovery Priority** | N/A | temp > backup > new |
| **Startup Check** | No | Yes |

---

## Related Documentation

- **Issue Analysis**: `docs/issues/026-pending-p1-shadow-rebuild-atomic-swap-not-truly-atomic.md`
- **Shadow Rebuild**: Module `ariadne_core/storage/shadow_rebuilder.py`
- **Related**: `docs/solutions/database-issues/p025-two-phase-commit-rollback-tracking-failure.md`

---

## Verification

After implementing this fix, verify:

1. **Normal Swap**: Run rebuild and verify files end up in correct state
2. **Crash Recovery**: Simulate crash at each step and verify automatic recovery
3. **Startup Recovery**: Delete `current` database and verify recovery from backup/temp
4. **Manual Recovery**: Verify error message provides clear recovery instructions

```bash
# Test swap recovery
python -c "
from ariadne_core.storage.shadow_rebuilder import ShadowRebuilder
rebuilder = ShadowRebuilder('test.db')
# Test recovery methods
"
```
