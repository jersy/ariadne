"""Main extractor for Java projects using ASM bytecode analysis."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from ariadne_core.extractors.asm.client import ASMClient
from ariadne_core.models.types import EdgeData, ExtractionResult, RelationKind, SymbolData, SymbolKind
from ariadne_core.storage.sqlite_store import SQLiteStore


class Extractor:
    """Extracts symbols and call relationships from Java projects.

    Uses the ASM Analysis Service for bytecode analysis and stores
    results in SQLite.
    """

    def __init__(
        self,
        db_path: str = "ariadne.db",
        service_url: str = "http://localhost:8766",
        init: bool = False,
    ):
        self.db_path = db_path
        self.store = SQLiteStore(db_path, init=init)
        self.asm_client = ASMClient(service_url)

    def extract_project(
        self,
        project_root: str,
        domains: list[str] | None = None,
        limit: int | None = None,
    ) -> ExtractionResult:
        """Extract symbols and relationships from a Java project.

        Args:
            project_root: Path to the project root directory.
            domains: Optional filter for Java package domains (e.g., ["com.example"]).
            limit: Optional limit on class files per module (for testing).

        Returns:
            ExtractionResult with stats and any errors.
        """
        project_path = Path(project_root).resolve()
        if not project_path.exists():
            return ExtractionResult(success=False, errors=[f"Project not found: {project_root}"])

        print(f"[Ariadne] Extracting project: {project_path}")
        if domains:
            print(f"[Ariadne] Domain filter: {', '.join(domains)}")

        # Find class directories (Maven or Gradle)
        class_dirs = self._find_class_dirs(project_path)
        if not class_dirs:
            return ExtractionResult(
                success=False,
                errors=["No compiled classes found. Please build the project first."],
            )

        print(f"[Ariadne] Found {len(class_dirs)} module(s)")

        total_symbols = 0
        total_edges = 0
        all_symbols: list[SymbolData] = []
        all_edges: list[EdgeData] = []
        errors: list[str] = []

        for classes_dir, module_name in class_dirs:
            print(f"[Ariadne] Processing module: {module_name}")

            # Check if module needs re-extraction
            if not self._needs_reindex(module_name, classes_dir):
                print(f"[Ariadne]   -> Skipped (unchanged)")
                continue

            # Find class files
            class_files = self._find_class_files(classes_dir, limit)
            if not class_files:
                print(f"[Ariadne]   -> No class files found")
                continue

            print(f"[Ariadne]   -> Analyzing {len(class_files)} class files...")

            try:
                # Call ASM service
                result = self.asm_client.analyze_classes(
                    class_files=[str(f) for f in class_files],
                    domains=domains,
                )

                if not result.get("success"):
                    errors.append(f"ASM analysis failed for {module_name}")
                    continue

                # Process classes
                classes = result.get("classes", [])
                symbols, edges = self._process_classes(classes, module_name, project_path)
                all_symbols.extend(symbols)
                all_edges.extend(edges)

                # Store incrementally
                self.store.insert_symbols(symbols)
                self.store.insert_edges(edges)

                # Update metadata hash
                content_hash = self._compute_hash(classes_dir)
                self.store.set_metadata(f"hash:{module_name}", content_hash)

                print(f"[Ariadne]   -> {len(symbols)} symbols, {len(edges)} edges")
                total_symbols += len(symbols)
                total_edges += len(edges)

            except Exception as e:
                errors.append(f"Error processing {module_name}: {e}")
                print(f"[Ariadne]   -> ERROR: {e}")

        print(f"[Ariadne] Extraction complete: {total_symbols} symbols, {total_edges} edges")

        return ExtractionResult(
            success=len(errors) == 0,
            symbols=all_symbols,
            edges=all_edges,
            stats={
                "total_symbols": total_symbols,
                "total_edges": total_edges,
                "modules": len(class_dirs),
            },
            errors=errors,
        )

    def _find_class_dirs(self, project_path: Path) -> list[tuple[Path, str]]:
        """Find compiled class directories in the project."""
        class_dirs = []

        # Maven: target/classes
        for target_classes in project_path.rglob("target/classes"):
            if target_classes.is_dir():
                module_path = target_classes.parent.parent
                module_name = module_path.name
                class_dirs.append((target_classes, module_name))

        # Gradle: build/classes/java/main
        for build_classes in project_path.rglob("build/classes/java/main"):
            if build_classes.is_dir():
                module_path = build_classes.parent.parent.parent.parent
                module_name = module_path.name
                class_dirs.append((build_classes, module_name))

        return class_dirs

    def _find_class_files(self, classes_dir: Path, limit: int | None = None) -> list[Path]:
        """Find .class files in a directory."""
        class_files = list(classes_dir.rglob("*.class"))
        if limit:
            return class_files[:limit]
        return class_files

    def _needs_reindex(self, module_name: str, classes_dir: Path) -> bool:
        """Check if a module needs re-indexing based on content hash."""
        current_hash = self._compute_hash(classes_dir)
        stored_hash = self.store.get_metadata(f"hash:{module_name}")
        return current_hash != stored_hash

    def _compute_hash(self, classes_dir: Path) -> str:
        """Compute SHA256 hash of all .class files."""
        hasher = hashlib.sha256()
        class_files = sorted(classes_dir.rglob("*.class"))
        for class_file in class_files:
            hasher.update(class_file.name.encode("utf-8"))
            hasher.update(class_file.read_bytes())
        return hasher.hexdigest()

    def _process_classes(
        self,
        classes: list[dict[str, Any]],
        module_name: str,
        project_path: Path,
    ) -> tuple[list[SymbolData], list[EdgeData]]:
        """Process ASM analysis results into SymbolData and EdgeData."""
        symbols: list[SymbolData] = []
        edges: list[EdgeData] = []

        for class_data in classes:
            class_fqn = class_data["fqn"]
            class_name = class_fqn.rsplit(".", 1)[-1]

            # Determine source file path
            source_path = self._find_source_file(class_fqn, project_path)

            # Create class symbol
            class_symbol = SymbolData(
                fqn=class_fqn,
                kind=SymbolKind.CLASS if class_data.get("type") != "interface" else SymbolKind.INTERFACE,
                name=class_name,
                file_path=str(source_path) if source_path else None,
                line_number=class_data.get("line"),
                modifiers=class_data.get("modifiers", []),
                annotations=class_data.get("annotations", []),
            )
            symbols.append(class_symbol)

            # Process inheritance
            for inheritance in class_data.get("inheritance", []):
                parent_fqn = inheritance.get("fqn") if isinstance(inheritance, dict) else inheritance
                inherit_kind = inheritance.get("kind", "extends") if isinstance(inheritance, dict) else "extends"
                relation = RelationKind.INHERITS if inherit_kind == "extends" else RelationKind.IMPLEMENTS
                edges.append(EdgeData(from_fqn=class_fqn, to_fqn=parent_fqn, relation=relation))

            # Process methods
            for method in class_data.get("methods", []):
                method_fqn = method["fqn"]
                method_name = method_fqn.rsplit(".", 1)[-1]
                if "(" in method_name:
                    method_name = method_name.split("(")[0]

                method_symbol = SymbolData(
                    fqn=method_fqn,
                    kind=SymbolKind.METHOD,
                    name=method_name,
                    file_path=str(source_path) if source_path else None,
                    line_number=method.get("line"),
                    modifiers=method.get("modifiers", []),
                    signature=method.get("signature"),
                    parent_fqn=class_fqn,
                    annotations=method.get("annotations", []),
                )
                symbols.append(method_symbol)

                # Process calls
                for call in method.get("calls", []):
                    to_fqn = call.get("toFqn")
                    if to_fqn and not self._is_external(to_fqn):
                        edges.append(EdgeData(
                            from_fqn=method_fqn,
                            to_fqn=to_fqn,
                            relation=RelationKind.CALLS,
                            metadata={"line": call.get("line"), "kind": call.get("kind")},
                        ))

            # Process fields
            for field in class_data.get("fields", []):
                field_name = field.get("name")
                field_type = field.get("type")
                if field_name:
                    field_fqn = f"{class_fqn}.{field_name}"
                    field_symbol = SymbolData(
                        fqn=field_fqn,
                        kind=SymbolKind.FIELD,
                        name=field_name,
                        file_path=str(source_path) if source_path else None,
                        modifiers=field.get("modifiers", []),
                        signature=field_type,
                        parent_fqn=class_fqn,
                        annotations=field.get("annotations", []),
                    )
                    symbols.append(field_symbol)

        return symbols, edges

    def _find_source_file(self, class_fqn: str, project_path: Path) -> Path | None:
        """Try to find the source file for a class FQN."""
        relative_path = class_fqn.replace(".", "/") + ".java"
        # Check common source locations
        for src_dir in ["src/main/java", "src/java", "src"]:
            source_file = project_path / src_dir / relative_path
            if source_file.exists():
                return source_file
        return None

    def _is_external(self, fqn: str) -> bool:
        """Check if a FQN belongs to an external library."""
        external_prefixes = [
            "java.", "javax.", "jdk.", "sun.", "com.sun.",
            "org.w3c.", "org.xml.", "org.omg.", "org.ietf.",
            "org.slf4j.", "org.apache.", "org.springframework.",
            "com.fasterxml.", "com.google.", "org.hibernate.",
        ]
        return any(fqn.startswith(prefix) for prefix in external_prefixes)

    def close(self) -> None:
        """Close resources."""
        self.store.close()
        self.asm_client.close()

    def __enter__(self) -> Extractor:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()


def extract_project(project_root: str, output: str = "ariadne.db") -> None:
    """Convenience function for CLI usage."""
    with Extractor(db_path=output, init=True) as extractor:
        result = extractor.extract_project(project_root)
        if result.success:
            print(f"[Ariadne] Saved to {output}")
            print(f"[Ariadne] Stats: {result.stats}")
        else:
            print("[Ariadne] Extraction failed:")
            for error in result.errors:
                print(f"  - {error}")
