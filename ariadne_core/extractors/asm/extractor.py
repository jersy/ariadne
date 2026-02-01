"""Main extractor for Java projects using ASM bytecode analysis."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any

from ariadne_core.extractors.asm.client import ASMClient
from ariadne_core.models.types import EdgeData, ExtractionResult, RelationKind, SymbolData, SymbolKind
from ariadne_core.storage.sqlite_store import SQLiteStore

# 外部库前缀 - 这些包不会被索引到调用边中
EXTERNAL_PREFIXES = (
    "java.", "javax.", "jdk.", "sun.", "com.sun.",
    "org.w3c.", "org.xml.", "org.omg.", "org.ietf.",
    "org.slf4j.", "org.apache.", "org.springframework.",
    "com.fasterxml.", "com.google.", "org.hibernate.",
)


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
        self._source_index: dict[str, Path] | None = None

    def extract_project(
        self,
        project_root: str,
        domains: list[str] | None = None,
        limit: int | None = None,
    ) -> ExtractionResult:
        """Extract symbols and relationships from a Java project."""
        project_path = Path(project_root).resolve()
        if not project_path.exists():
            return ExtractionResult(success=False, errors=[f"Project not found: {project_root}"])

        print(f"[Ariadne] Extracting project: {project_path}")
        if domains:
            print(f"[Ariadne] Domain filter: {', '.join(domains)}")

        class_dirs = self._find_class_dirs(project_path)
        if not class_dirs:
            return ExtractionResult(
                success=False,
                errors=["No compiled classes found. Please build the project first."],
            )

        print(f"[Ariadne] Found {len(class_dirs)} module(s)")

        # 构建源文件索引（一次性扫描）
        self._source_index = self._build_source_index(project_path)
        print(f"[Ariadne] Source index: {len(self._source_index)} files")

        total_symbols = 0
        total_edges = 0
        errors: list[str] = []

        for classes_dir, module_name in class_dirs:
            result = self._process_module(
                classes_dir, module_name, project_path, domains, limit
            )
            if result["error"]:
                errors.append(result["error"])
            else:
                total_symbols += result["symbols"]
                total_edges += result["edges"]

        print(f"[Ariadne] Extraction complete: {total_symbols} symbols, {total_edges} edges")

        return ExtractionResult(
            success=len(errors) == 0,
            stats={
                "total_symbols": total_symbols,
                "total_edges": total_edges,
                "modules": len(class_dirs),
            },
            errors=errors,
        )

    def _process_module(
        self,
        classes_dir: Path,
        module_name: str,
        project_path: Path,
        domains: list[str] | None,
        limit: int | None,
    ) -> dict[str, Any]:
        """处理单个模块的提取。"""
        print(f"[Ariadne] Processing module: {module_name}")

        # 检查是否需要重新提取（使用 stat-based hash）
        if not self._needs_reindex(module_name, classes_dir):
            print(f"[Ariadne]   -> Skipped (unchanged)")
            return {"symbols": 0, "edges": 0, "error": None}

        class_files = self._find_class_files(classes_dir, limit)
        if not class_files:
            print(f"[Ariadne]   -> No class files found")
            return {"symbols": 0, "edges": 0, "error": None}

        print(f"[Ariadne]   -> Analyzing {len(class_files)} class files...")

        try:
            result = self.asm_client.analyze_classes(
                class_files=[str(f) for f in class_files],
                domains=domains,
            )

            if not result.get("success"):
                return {"symbols": 0, "edges": 0, "error": f"ASM analysis failed for {module_name}"}

            classes = result.get("classes", [])
            symbols, edges = self._process_classes(classes, project_path)

            # 直接存储，不累积到内存
            self.store.insert_symbols(symbols)
            self.store.insert_edges(edges)

            # 更新 hash
            content_hash = self._compute_hash(classes_dir)
            self.store.set_metadata(f"hash:{module_name}", content_hash)

            print(f"[Ariadne]   -> {len(symbols)} symbols, {len(edges)} edges")
            return {"symbols": len(symbols), "edges": len(edges), "error": None}

        except Exception as e:
            print(f"[Ariadne]   -> ERROR: {e}")
            return {"symbols": 0, "edges": 0, "error": f"Error processing {module_name}: {e}"}

    def _build_source_index(self, project_path: Path) -> dict[str, Path]:
        """一次性构建源文件索引，避免 N+1 查找。"""
        index: dict[str, Path] = {}
        for src_dir in ["src/main/java", "src/java", "src"]:
            src_path = project_path / src_dir
            if src_path.exists():
                for java_file in src_path.rglob("*.java"):
                    # 将路径转换为 FQN key: src/main/java/com/example/Foo.java -> com.example.Foo
                    try:
                        relative = java_file.relative_to(src_path)
                        fqn_key = str(relative.with_suffix("")).replace(os.sep, ".")
                        index[fqn_key] = java_file
                    except ValueError:
                        continue
        return index

    def _find_source_file(self, class_fqn: str) -> Path | None:
        """从索引中查找源文件（O(1) 查找）。"""
        if self._source_index is None:
            return None
        # 处理内部类：com.example.Outer$Inner -> com.example.Outer
        base_fqn = class_fqn.split("$")[0]
        return self._source_index.get(base_fqn)

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
        """Check if a module needs re-indexing based on stat hash."""
        current_hash = self._compute_hash(classes_dir)
        stored_hash = self.store.get_metadata(f"hash:{module_name}")
        return current_hash != stored_hash

    def _compute_hash(self, classes_dir: Path) -> str:
        """使用 stat (mtime + size) 计算 hash，避免读取文件内容。"""
        hasher = hashlib.sha256()
        class_files = sorted(classes_dir.rglob("*.class"))
        for class_file in class_files:
            stat = class_file.stat()
            # 使用文件名 + mtime + size 作为 hash 输入
            hasher.update(class_file.name.encode("utf-8"))
            hasher.update(str(stat.st_mtime_ns).encode("utf-8"))
            hasher.update(str(stat.st_size).encode("utf-8"))
        return hasher.hexdigest()

    def _process_classes(
        self,
        classes: list[dict[str, Any]],
        project_path: Path,
    ) -> tuple[list[SymbolData], list[EdgeData]]:
        """Process ASM analysis results into SymbolData and EdgeData."""
        symbols: list[SymbolData] = []
        edges: list[EdgeData] = []

        for class_data in classes:
            class_fqn = class_data["fqn"]
            class_name = class_fqn.rsplit(".", 1)[-1]

            # 使用索引查找源文件 (O(1))
            source_path = self._find_source_file(class_fqn)

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
                    if to_fqn and not to_fqn.startswith(EXTERNAL_PREFIXES):
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
