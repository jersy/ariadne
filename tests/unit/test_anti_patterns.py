"""Unit tests for AntiPatternDetector."""

import tempfile
from pathlib import Path

import pytest

from ariadne_analyzer.l2_architecture.anti_patterns import AntiPatternDetector
from ariadne_core.models.types import (
    EdgeData,
    RelationKind,
    Severity,
    SymbolData,
    SymbolKind,
)
from ariadne_core.storage.sqlite_store import SQLiteStore


@pytest.fixture
def store():
    """Create a temporary SQLite store for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    store = SQLiteStore(db_path, init=True)
    yield store
    store.close()
    Path(db_path).unlink(missing_ok=True)


@pytest.fixture
def detector(store: SQLiteStore):
    return AntiPatternDetector(store)


class TestControllerDaoRule:
    def test_detect_controller_directly_calls_mapper(self, store: SQLiteStore, detector: AntiPatternDetector):
        # Setup: Controller class with method that calls Mapper directly
        store.insert_symbols([
            SymbolData(
                fqn="com.example.UserController",
                kind=SymbolKind.CLASS,
                name="UserController",
                annotations=["@RestController"],
            ),
            SymbolData(
                fqn="com.example.UserController.getUser(Long)",
                kind=SymbolKind.METHOD,
                name="getUser",
                parent_fqn="com.example.UserController",
            ),
            SymbolData(
                fqn="com.example.mapper.UserMapper",
                kind=SymbolKind.CLASS,
                name="UserMapper",
            ),
            SymbolData(
                fqn="com.example.mapper.UserMapper.selectById(Long)",
                kind=SymbolKind.METHOD,
                name="selectById",
                parent_fqn="com.example.mapper.UserMapper",
            ),
        ])
        store.insert_edges([
            EdgeData(
                from_fqn="com.example.UserController.getUser(Long)",
                to_fqn="com.example.mapper.UserMapper.selectById(Long)",
                relation=RelationKind.CALLS,
            ),
        ])

        patterns = detector.detect_all()

        assert len(patterns) == 1
        assert patterns[0].rule_id == "controller-dao"
        assert patterns[0].severity == Severity.ERROR
        assert "com.example.UserController.getUser(Long)" in patterns[0].from_fqn
        assert "UserMapper" in patterns[0].to_fqn

    def test_detect_controller_calls_dao(self, store: SQLiteStore, detector: AntiPatternDetector):
        store.insert_symbols([
            SymbolData(
                fqn="com.example.OrderController",
                kind=SymbolKind.CLASS,
                name="OrderController",
                annotations=["@Controller"],
            ),
            SymbolData(
                fqn="com.example.OrderController.list()",
                kind=SymbolKind.METHOD,
                name="list",
                parent_fqn="com.example.OrderController",
            ),
            SymbolData(
                fqn="com.example.dao.OrderDao.findAll()",
                kind=SymbolKind.METHOD,
                name="findAll",
                parent_fqn="com.example.dao.OrderDao",
            ),
        ])
        store.insert_edges([
            EdgeData(
                from_fqn="com.example.OrderController.list()",
                to_fqn="com.example.dao.OrderDao.findAll()",
                relation=RelationKind.CALLS,
            ),
        ])

        patterns = detector.detect_all()

        assert len(patterns) == 1
        assert patterns[0].rule_id == "controller-dao"

    def test_detect_controller_calls_repository(self, store: SQLiteStore, detector: AntiPatternDetector):
        store.insert_symbols([
            SymbolData(
                fqn="com.example.ProductController",
                kind=SymbolKind.CLASS,
                name="ProductController",
                annotations=["@RestController"],
            ),
            SymbolData(
                fqn="com.example.ProductController.get(Long)",
                kind=SymbolKind.METHOD,
                name="get",
                parent_fqn="com.example.ProductController",
            ),
            SymbolData(
                fqn="com.example.repository.ProductRepository.findById(Long)",
                kind=SymbolKind.METHOD,
                name="findById",
                parent_fqn="com.example.repository.ProductRepository",
            ),
        ])
        store.insert_edges([
            EdgeData(
                from_fqn="com.example.ProductController.get(Long)",
                to_fqn="com.example.repository.ProductRepository.findById(Long)",
                relation=RelationKind.CALLS,
            ),
        ])

        patterns = detector.detect_all()

        assert len(patterns) == 1

    def test_no_violation_controller_calls_service(self, store: SQLiteStore, detector: AntiPatternDetector):
        store.insert_symbols([
            SymbolData(
                fqn="com.example.UserController",
                kind=SymbolKind.CLASS,
                name="UserController",
                annotations=["@RestController"],
            ),
            SymbolData(
                fqn="com.example.UserController.getUser(Long)",
                kind=SymbolKind.METHOD,
                name="getUser",
                parent_fqn="com.example.UserController",
            ),
            SymbolData(
                fqn="com.example.service.UserService.findById(Long)",
                kind=SymbolKind.METHOD,
                name="findById",
                parent_fqn="com.example.service.UserService",
            ),
        ])
        store.insert_edges([
            EdgeData(
                from_fqn="com.example.UserController.getUser(Long)",
                to_fqn="com.example.service.UserService.findById(Long)",
                relation=RelationKind.CALLS,
            ),
        ])

        patterns = detector.detect_all()

        assert len(patterns) == 0

    def test_no_violation_service_calls_mapper(self, store: SQLiteStore, detector: AntiPatternDetector):
        # Service calling Mapper is OK
        store.insert_symbols([
            SymbolData(
                fqn="com.example.service.UserService",
                kind=SymbolKind.CLASS,
                name="UserService",
                annotations=["@Service"],
            ),
            SymbolData(
                fqn="com.example.service.UserService.getUser(Long)",
                kind=SymbolKind.METHOD,
                name="getUser",
                parent_fqn="com.example.service.UserService",
            ),
            SymbolData(
                fqn="com.example.mapper.UserMapper.selectById(Long)",
                kind=SymbolKind.METHOD,
                name="selectById",
                parent_fqn="com.example.mapper.UserMapper",
            ),
        ])
        store.insert_edges([
            EdgeData(
                from_fqn="com.example.service.UserService.getUser(Long)",
                to_fqn="com.example.mapper.UserMapper.selectById(Long)",
                relation=RelationKind.CALLS,
            ),
        ])

        patterns = detector.detect_all()

        assert len(patterns) == 0

    def test_controller_by_name_convention(self, store: SQLiteStore, detector: AntiPatternDetector):
        # Controller identified by name even without annotation
        store.insert_symbols([
            SymbolData(
                fqn="com.example.ApiController",
                kind=SymbolKind.CLASS,
                name="ApiController",
            ),
            SymbolData(
                fqn="com.example.ApiController.handle()",
                kind=SymbolKind.METHOD,
                name="handle",
                parent_fqn="com.example.ApiController",
            ),
            SymbolData(
                fqn="com.example.DataMapper.query()",
                kind=SymbolKind.METHOD,
                name="query",
                parent_fqn="com.example.DataMapper",
            ),
        ])
        store.insert_edges([
            EdgeData(
                from_fqn="com.example.ApiController.handle()",
                to_fqn="com.example.DataMapper.query()",
                relation=RelationKind.CALLS,
            ),
        ])

        patterns = detector.detect_all()

        assert len(patterns) == 1

    def test_exclude_base_mapper(self, store: SQLiteStore, detector: AntiPatternDetector):
        # BaseMapper should be excluded
        store.insert_symbols([
            SymbolData(
                fqn="com.example.TestController",
                kind=SymbolKind.CLASS,
                name="TestController",
                annotations=["@RestController"],
            ),
            SymbolData(
                fqn="com.example.TestController.test()",
                kind=SymbolKind.METHOD,
                name="test",
                parent_fqn="com.example.TestController",
            ),
            SymbolData(
                fqn="com.baomidou.mybatisplus.core.mapper.BaseMapper.selectById(Long)",
                kind=SymbolKind.METHOD,
                name="selectById",
                parent_fqn="com.baomidou.mybatisplus.core.mapper.BaseMapper",
            ),
        ])
        store.insert_edges([
            EdgeData(
                from_fqn="com.example.TestController.test()",
                to_fqn="com.baomidou.mybatisplus.core.mapper.BaseMapper.selectById(Long)",
                relation=RelationKind.CALLS,
            ),
        ])

        patterns = detector.detect_all()

        assert len(patterns) == 0


class TestDetectorMethods:
    def test_detect_by_rule(self, store: SQLiteStore, detector: AntiPatternDetector):
        store.insert_symbols([
            SymbolData(
                fqn="com.example.UserController",
                kind=SymbolKind.CLASS,
                name="UserController",
                annotations=["@RestController"],
            ),
            SymbolData(
                fqn="com.example.UserController.get()",
                kind=SymbolKind.METHOD,
                name="get",
                parent_fqn="com.example.UserController",
            ),
            SymbolData(
                fqn="com.example.UserMapper.select()",
                kind=SymbolKind.METHOD,
                name="select",
                parent_fqn="com.example.UserMapper",
            ),
        ])
        store.insert_edges([
            EdgeData(
                from_fqn="com.example.UserController.get()",
                to_fqn="com.example.UserMapper.select()",
                relation=RelationKind.CALLS,
            ),
        ])

        patterns = detector.detect_by_rule("controller-dao")

        assert len(patterns) == 1
        assert patterns[0].rule_id == "controller-dao"

    def test_detect_by_unknown_rule(self, detector: AntiPatternDetector):
        with pytest.raises(ValueError, match="Unknown rule"):
            detector.detect_by_rule("nonexistent-rule")

    def test_list_rules(self, detector: AntiPatternDetector):
        rules = detector.list_rules()

        assert len(rules) >= 1
        rule_ids = {r["rule_id"] for r in rules}
        assert "controller-dao" in rule_ids

        # Check rule structure
        for rule in rules:
            assert "rule_id" in rule
            assert "severity" in rule
            assert "description" in rule


class TestEmptyStore:
    def test_detect_with_no_data(self, detector: AntiPatternDetector):
        patterns = detector.detect_all()
        assert len(patterns) == 0

    def test_detect_with_no_controllers(self, store: SQLiteStore, detector: AntiPatternDetector):
        # Only services, no controllers
        store.insert_symbols([
            SymbolData(
                fqn="com.example.UserService",
                kind=SymbolKind.CLASS,
                name="UserService",
                annotations=["@Service"],
            ),
        ])

        patterns = detector.detect_all()
        assert len(patterns) == 0
