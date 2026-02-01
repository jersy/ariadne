"""Tests for layer detection utility."""

import pytest

from ariadne_core.utils.layer import (
    determine_layer,
    determine_layer_or_unknown,
    get_layer_priority,
    is_controller,
    is_repository,
    is_service,
)


@pytest.fixture
def sample_symbol():
    """Create a sample symbol for testing."""
    return {
        "fqn": "com.example.Service.method",
        "kind": "method",
        "name": "method",
        "file_path": "/test/Service.java",
        "line_number": 10,
        "annotations": [],
    }


class TestDetermineLayer:
    """Tests for determine_layer function."""

    def test_controller_layer_detection(self, sample_symbol):
        """Test that Controller annotations are detected."""
        sample_symbol["annotations"] = "Controller"
        assert determine_layer(sample_symbol) == "controller"

    def test_rest_controller_layer_detection(self, sample_symbol):
        """Test that RestController annotations are detected."""
        sample_symbol["annotations"] = "RestController"
        assert determine_layer(sample_symbol) == "controller"

    def test_service_layer_detection(self, sample_symbol):
        """Test that Service annotations are detected."""
        sample_symbol["annotations"] = "Service"
        assert determine_layer(sample_symbol) == "service"

    def test_repository_layer_detection(self, sample_symbol):
        """Test that Repository annotations are detected."""
        sample_symbol["annotations"] = "Repository"
        assert determine_layer(sample_symbol) == "repository"

    def test_no_annotations_returns_domain_for_class(self, sample_symbol):
        """Test that classes without annotations return 'domain'."""
        sample_symbol["kind"] = "class"
        sample_symbol["annotations"] = []
        assert determine_layer(sample_symbol) == "domain"

    def test_no_annotations_returns_none_for_non_class(self, sample_symbol):
        """Test that non-classes without annotations return None."""
        sample_symbol["kind"] = "method"
        sample_symbol["annotations"] = []
        assert determine_layer(sample_symbol) is None

    def test_list_annotations(self, sample_symbol):
        """Test that list annotations are handled."""
        sample_symbol["annotations"] = ["Service", "Transactional"]
        assert determine_layer(sample_symbol) == "service"

    def test_comma_separated_annotations(self, sample_symbol):
        """Test that comma-separated annotations are handled."""
        sample_symbol["annotations"] = "Service,Transactional"
        assert determine_layer(sample_symbol) == "service"


class TestDetermineLayerOrUnknown:
    """Tests for determine_layer_or_unknown function."""

    def test_returns_unknown_for_no_layer(self, sample_symbol):
        """Test that 'unknown' is returned instead of None."""
        sample_symbol["kind"] = "method"
        sample_symbol["annotations"] = []
        assert determine_layer_or_unknown(sample_symbol) == "unknown"

    def test_returns_layer_for_known_layers(self, sample_symbol):
        """Test that actual layers are returned correctly."""
        sample_symbol["annotations"] = "Controller"
        assert determine_layer_or_unknown(sample_symbol) == "controller"


class TestHelperFunctions:
    """Tests for layer detection helper functions."""

    def test_is_controller(self, sample_symbol):
        """Test is_controller helper."""
        sample_symbol["annotations"] = "Controller"
        assert is_controller(sample_symbol) is True
        sample_symbol["annotations"] = "Service"
        assert is_controller(sample_symbol) is False

    def test_is_service(self, sample_symbol):
        """Test is_service helper."""
        sample_symbol["annotations"] = "Service"
        assert is_service(sample_symbol) is True
        sample_symbol["annotations"] = "Repository"
        assert is_service(sample_symbol) is False

    def test_is_repository(self, sample_symbol):
        """Test is_repository helper."""
        sample_symbol["annotations"] = "Repository"
        assert is_repository(sample_symbol) is True
        sample_symbol["annotations"] = "Service"
        assert is_repository(sample_symbol) is False


class TestGetLayerPriority:
    """Tests for get_layer_priority function."""

    def test_controller_has_highest_priority(self):
        """Test that controller has the highest priority (0)."""
        assert get_layer_priority("controller") == 0

    def test_service_has_second_priority(self):
        """Test that service has the second priority (1)."""
        assert get_layer_priority("service") == 1

    def test_repository_has_third_priority(self):
        """Test that repository has the third priority (2)."""
        assert get_layer_priority("repository") == 2

    def test_domain_has_fourth_priority(self):
        """Test that domain has the fourth priority (3)."""
        assert get_layer_priority("domain") == 3

    def test_unknown_has_lowest_priority(self):
        """Test that unknown has the lowest priority (4)."""
        assert get_layer_priority("unknown") == 4
        assert get_layer_priority(None) == 4
