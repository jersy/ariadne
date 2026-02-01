"""HTTP client for the ASM Analysis Service (Java bytecode analyzer)."""

from __future__ import annotations

import httpx
from typing import Any


class ASMClient:
    """Client for the Java ASM Analysis Service.

    The ASM service analyzes .class files and returns symbol information
    and call relationships.
    """

    def __init__(self, service_url: str = "http://localhost:8766", timeout: float = 60.0):
        self.service_url = service_url.rstrip("/")
        self.timeout = timeout
        self._client = httpx.Client(timeout=timeout)

    def health_check(self) -> dict[str, Any]:
        """Check if the ASM service is running."""
        resp = self._client.get(f"{self.service_url}/health")
        resp.raise_for_status()
        return resp.json()

    def index_class_file(self, class_file_path: str) -> dict[str, Any]:
        """Index a single .class file to extract symbols.

        Args:
            class_file_path: Absolute path to the .class file.

        Returns:
            Dict with class_fqn, is_entity, symbols list, etc.
        """
        resp = self._client.post(
            f"{self.service_url}/index",
            json={"classFile": class_file_path},
        )
        resp.raise_for_status()
        return resp.json()

    def analyze_classes(
        self,
        class_files: list[str],
        domains: list[str] | None = None,
    ) -> dict[str, Any]:
        """Analyze multiple .class files for call relationships.

        Args:
            class_files: List of absolute paths to .class files.
            domains: Optional domain filter (e.g. ["com.example"]).

        Returns:
            Dict with classes, nodes, edges, etc.
        """
        payload: dict[str, Any] = {
            "classFiles": class_files,
            "enhanced": True,
            "springAnalysis": True,
            "includeAttributes": True,
        }
        if domains:
            payload["domains"] = domains

        resp = self._client.post(
            f"{self.service_url}/analyze",
            json=payload,
            timeout=600.0,
        )
        resp.raise_for_status()
        return resp.json()

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()

    def __enter__(self) -> ASMClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
