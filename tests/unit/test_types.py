"""Unit tests for data types."""

import json

import pytest

from ariadne_core.models.types import EdgeData, RelationKind, SymbolData, SymbolKind


class TestSymbolData:
    def test_to_row_basic(self):
        symbol = SymbolData(
            fqn="com.example.User",
            kind=SymbolKind.CLASS,
            name="User",
        )
        row = symbol.to_row()

        assert row[0] == "com.example.User"
        assert row[1] == "class"
        assert row[2] == "User"
        assert row[3] is None  # file_path
        assert row[4] is None  # line_number

    def test_to_row_full(self):
        symbol = SymbolData(
            fqn="com.example.User.getName",
            kind=SymbolKind.METHOD,
            name="getName",
            file_path="/path/to/User.java",
            line_number=42,
            modifiers=["public"],
            signature="()Ljava/lang/String;",
            parent_fqn="com.example.User",
            annotations=["@Override"],
        )
        row = symbol.to_row()

        assert row[0] == "com.example.User.getName"
        assert row[1] == "method"
        assert row[2] == "getName"
        assert row[3] == "/path/to/User.java"
        assert row[4] == 42
        assert json.loads(row[5]) == ["public"]
        assert row[6] == "()Ljava/lang/String;"
        assert row[7] == "com.example.User"
        assert json.loads(row[8]) == ["@Override"]


class TestEdgeData:
    def test_to_row_basic(self):
        edge = EdgeData(
            from_fqn="A",
            to_fqn="B",
            relation=RelationKind.CALLS,
        )
        row = edge.to_row()

        assert row[0] == "A"
        assert row[1] == "B"
        assert row[2] == "calls"
        assert row[3] is None

    def test_to_row_with_metadata(self):
        edge = EdgeData(
            from_fqn="A",
            to_fqn="B",
            relation=RelationKind.INHERITS,
            metadata={"kind": "extends"},
        )
        row = edge.to_row()

        assert row[2] == "inherits"
        assert json.loads(row[3]) == {"kind": "extends"}


class TestSymbolKind:
    def test_enum_values(self):
        assert SymbolKind.CLASS.value == "class"
        assert SymbolKind.INTERFACE.value == "interface"
        assert SymbolKind.METHOD.value == "method"
        assert SymbolKind.FIELD.value == "field"


class TestRelationKind:
    def test_enum_values(self):
        assert RelationKind.CALLS.value == "calls"
        assert RelationKind.INHERITS.value == "inherits"
        assert RelationKind.IMPLEMENTS.value == "implements"
        assert RelationKind.INSTANTIATES.value == "instantiates"
        assert RelationKind.INJECTS.value == "injects"
        assert RelationKind.MEMBER_OF.value == "member_of"
