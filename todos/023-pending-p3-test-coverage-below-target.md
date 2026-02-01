---
status: pending
priority: p3
issue_id: "023"
tags:
  - code-review
  - testing
  - quality
dependencies: []
---

# Test Coverage Below 80% Target

## Problem Statement

The plan specifies **> 80% test coverage** as a target, but current coverage is approximately **31%**. This is a significant gap that affects code quality confidence and refactoring safety.

**Plan Target:**
```yaml
# From plan: "测试策略"
测试覆盖率目标：> 80%
```

**Current State:**
```bash
# Current metrics
Production code: ~9,100 lines
Test code: ~2,800 lines
Coverage: ~31%
```

**Gap:** 49 percentage points below target

## Why It Matters

1. **Quality Confidence**: Low coverage means untested code paths
2. **Refactoring Risk**: Can't safely refactor without test coverage
3. **Regression Prevention**: Untested code is prone to bugs
4. **NFR Validation**: Performance targets need benchmark tests
5. **Professional Standards**: 80% is industry standard for critical systems

## Findings

### From Code Quality Review:

> **Severity:** MEDIUM
>
> Test coverage gap is significant. ~31% test ratio is below the 80% target stated in the plan.

### From Implementation Review:

> **Observation:** E2E tests mentioned in plan (Spring PetClinic) but not implemented.

### Missing Test Categories:

| Category | Plan Status | Actual Status | Gap |
|----------|-------------|---------------|-----|
| Unit tests | Per component | Partial | Medium |
| Integration tests | Spring PetClinic | 1 project | Medium |
| E2E tests | HTTP API | Partial | Low |
| Performance tests | pytest-benchmark | Missing | High |
| LLM integration tests | Mock only | Mock only | Medium |
| ChromaDB integration | Not mentioned | Missing | Medium |

### Coverage by Module (estimated):

| Module | Coverage | Notes |
|--------|----------|-------|
| `ariadne_core/storage/` | ~60% | SQLite operations tested |
| `ariadne_core/extractors/` | ~40% | ASM client partially mocked |
| `ariadne_analyzer/l1_business/` | ~30% | LLM calls mocked |
| `ariadne_analyzer/l2_architecture/` | ~40% | Call chain tested |
| `ariadne_analyzer/l3_implementation/` | ~20% | Impact analyzer undertested |
| `ariadne_api/routes/` | ~50% | API endpoints tested |
| `ariadne_llm/` | ~25% | LLM client mostly mocked |

## Proposed Solutions

### Solution 1: Incremental Coverage Improvement (Recommended)

**Approach:** Set monthly coverage targets with focused test writing.

**Pros:**
- Manageable increments
- Prioritizes high-risk code
- Measurable progress

**Cons:**
- Takes time to reach 80%
- Requires sustained effort

**Effort:** Medium (ongoing)
**Risk:** Low

**Implementation Plan:**
```
Month 1: 31% → 45% (+14%)
  - Add unit tests for impact_analyzer.py
  - Add integration tests for L2 layer
  - Add performance benchmarks

Month 2: 45% → 60% (+15%)
  - Add unit tests for L1 business layer
  - Add ChromaDB integration tests
  - Add ASM client integration tests

Month 3: 60% → 75% (+15%)
  - Add E2E API tests
  - Add edge case tests
  - Add property-based tests

Month 4: 75% → 80% (+5%)
  - Fill remaining gaps
  - Add regression tests
  - Stabilize at 80%
```

### Solution 2: Test-Driven Development Going Forward

**Approach:** Require test coverage for all new code.

**Pros:**
- Prevents coverage regression
- Better code quality
- Easier to maintain

**Cons:**
- Doesn't fix existing code
- Slows initial development

**Effort:** Low (policy change)
**Risk:** Low

**Policy:**
```yaml
# CLAUDE.md addition
## Code Review Guidelines

### Test Coverage Requirements

All new code must include:
- Unit tests for public functions
- Integration tests for external service interactions
- API tests for new endpoints

Minimum coverage for new modules: 80%
```

### Solution 3: Coverage Gates in CI/CD

**Approach:** Block merges if coverage drops below threshold.

**Pros:**
- Enforces coverage requirement
- Prevents regression
- Automated enforcement

**Cons:**
- May block legitimate changes
- Requires CI/CD setup

**Effort:** Medium
**Risk:** Low

**GitHub Action:**
```yaml
# .github/workflows/test.yml
name: Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Install dependencies
        run: uv pip install -e ".[dev]"
      - name: Run tests with coverage
        run: |
          pytest --cov=ariadne --cov-report=xml \
                 --cov-report=term-missing \
                 --cov-fail-under=70
      - name: Check coverage threshold
        run: |
          coverage=$(coverage report | grep TOTAL | awk '{print $4}' | sed 's/%//')
          if [ $coverage -lt 70 ]; then
            echo "Coverage $coverage% below 70% threshold"
            exit 1
          fi
```

## Recommended Action

**Use Solution 1 (Incremental Improvement) + Solution 3 (CI Gates)**

Combine gradual improvement with automated enforcement to reach and maintain 80% coverage.

## Technical Details

### Priority Testing Areas (by risk):

1. **HIGH RISK** (untested critical code):
   - `ariadne_analyzer/l3_implementation/impact_analyzer.py`
   - `ariadne_core/storage/sqlite_store.py` (dual-write paths)
   - `ariadne_api/routes/rebuild.py` (data loss risk)

2. **MEDIUM RISK** (partial coverage):
   - `ariadne_analyzer/l1_business/summarizer.py`
   - `ariadne_core/extractors/asm/client.py`
   - `ariadne_api/routes/impact.py`

3. **LOW RISK** (well-tested or simple):
   - `ariadne_api/schemas/` (Pydantic handles most)
   - `ariadne_core/models/types.py` (dataclasses)

### Test Infrastructure Needed:

```python
# tests/conftest.py (shared fixtures)
import pytest
import tempfile
from pathlib import Path

@pytest.fixture
def temp_db():
    """Temporary database for testing"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    yield db_path
    Path(db_path).unlink(missing_ok=True)

@pytest.fixture
def mock_store(temp_db):
    """Mock SQLite store with test data"""
    from ariadne_core.storage import SQLiteStore
    store = SQLiteStore(temp_db, init=True)
    # Load test fixtures
    _load_test_fixtures(store)
    yield store
    store.close()

@pytest.fixture
def mock_llm_client():
    """Mock LLM client for testing"""
    from unittest.mock import Mock
    mock = Mock()
    mock.generate_summary.return_value = "Test summary"
    mock.embed_text.return_value = [0.1, 0.2, 0.3]
    return mock

@pytest.fixture
def sample_java_project():
    """Sample Java project for integration tests"""
    return Path(__file__).parent / "fixtures" / "sample-java-project"
```

### Missing Test Categories:

**Performance Tests:**
```python
# tests/benchmarks/test_query_performance.py
import pytest

@pytest.mark.benchmark(group="graph-queries")
def test_call_chain_performance(benchmark, store):
    """Call chain query should be < 500ms"""

    def query_call_chain():
        tracer = CallChainTracer(store)
        return tracer.trace_from_entry("com.example.Controller")

    result = benchmark(query_call_chain)
    assert result.duration_ms < 500
```

**Integration Tests:**
```python
# tests/integration/test_spring_project.py
def test_spring_petclinic_extraction():
    """Test extraction on real Spring project"""

    project_path = Path(__file__).parent / "fixtures" / "spring-petclinic"

    # Extract symbols
    extractor = ASMExtractor(asm_url="http://localhost:8766")
    symbols = extractor.extract_project(project_path)

    # Verify extraction
    assert len(symbols) > 100
    assert any(s.name == "OwnerController" for s in symbols)

    # Verify Spring components detected
    controllers = [s for s in symbols if "@RestController" in s.annotations]
    assert len(controllers) > 0
```

**Property-Based Tests:**
```python
# tests/properties/test_graph_properties.py
from hypothesis import given, strategies as st
import hypothesis

@given(st.lists(st.text(min_size=1, alphabet='abc'), min_size=1, max_size=100))
def test_graph_traversal_no_duplicates(fqns):
    """Graph traversal should not return duplicate nodes"""

    # Create test graph
    store = create_test_store()
    for fqn in fqns:
        store.insert_symbol(SymbolData(fqn=fqn, kind="class", name=fqn))

    # Trace from entry point
    tracer = CallChainTracer(store)
    result = tracer.trace_from_entry(fqns[0])

    # Verify no duplicates
    assert len(result.nodes) == len(set(n.fqn for n in result.nodes))
```

### Files to Create:

1. **`tests/benchmarks/`** - NEW: Performance tests
2. **`tests/integration/test_spring_projects.py`** - NEW: Real project tests
3. **`tests/properties/`** - NEW: Property-based tests
4. **`tests/fixtures/spring-petclinic/`** - NEW: Test fixture

### Files to Modify:

1. **`tests/conftest.py`** - Add shared fixtures
2. **`.github/workflows/test.yml`** - Add coverage gate (NEW)
3. **`pytest.ini`** - Add coverage configuration

### pytest.ini Configuration:

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_functions = test_*
python_classes = Test*

[coverage:run]
source = ariadne
omit =
    */tests/*
    */__pycache__/*
    */migrations/*

[coverage:report]
precision = 2
show_missing = True
skip_covered = False

[coverage:html]
directory = htmlcov
```

## Acceptance Criteria

- [ ] Coverage increased to 45% (Month 1 target)
- [ ] Performance benchmarks added for critical paths
- [ ] Integration tests for Spring PetClinic
- [ ] Property-based tests for graph traversals
- [ ] CI/CD coverage gate implemented (70% threshold)
- [ ] Coverage report published with each build
- [ ] Test documentation updated
- [ ] Coverage tracking dashboard (optional)

## Work Log

| Date | Action | Result |
|------|--------|--------|
| 2026-02-02 | Plan review completed | Test coverage gap identified |
| | | |

## Resources

- **Affected Files**:
  - `tests/` (all test files)
  - `.github/workflows/test.yml` (NEW)
  - `pytest.ini` (modify or create)
- **Plan Reference**: "测试策略" section
- **Related Issues**:
  - Code Quality Review: Coverage gap
- **Tools**:
  - pytest: https://docs.pytest.org/
  - pytest-cov: https://pytest-cov.readthedocs.io/
  - pytest-benchmark: https://pytest-benchmark.readthedocs.io/
  - Hypothesis: https://hypothesis.readthedocs.io/
