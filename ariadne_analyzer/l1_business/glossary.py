"""
Domain Glossary Extractor
==========================

Extracts domain vocabulary from code and maps code terms to business meanings.
"""

import json
import logging
import re
from typing import Any

from ariadne_core.models.types import GlossaryEntry, SymbolData, SymbolKind
from ariadne_llm import LLMClient, LLMConfig

from .prompts import GLOSSARY_TERM_PROMPT

logger = logging.getLogger(__name__)


class DomainGlossaryExtractor:
    """Extracts domain vocabulary from code.

    Identifies:
    - Core domain concepts from class names
    - Business operations from method names
    - Attributes from field names
    - Business states from enum values
    """

    # Patterns for identifying domain-relevant symbols
    DOMAIN_CLASS_PATTERNS = [
        r".*(Entity|DTO|VO|Model)$",  # Data model classes
        r".*(Service|Repository|Controller)$",  # Layer classes
        r".*(Manager|Handler|Processor)$",  # Processing classes
    ]

    GETTER_SETTER_PATTERNS = [
        r"^(get|set|is)[A-Z].*$",
        r"^(has|contains|equals|hashCode|toString)$",
    ]

    def __init__(self, config: LLMConfig | None = None) -> None:
        """Initialize glossary extractor with LLM client.

        Args:
            config: Optional LLMConfig (uses env if not provided)
        """
        if config is None:
            config = LLMConfig.from_env()

        self.llm_client = LLMClient(config)

    def extract_terms_from_class(
        self,
        class_data: SymbolData,
        methods: list[SymbolData] | None = None,
        fields: list[SymbolData] | None = None,
    ) -> list[GlossaryEntry]:
        """Extract domain terms from a class.

        Args:
            class_data: Class symbol data
            methods: Optional list of method symbols in the class
            fields: Optional list of field symbols in the class

        Returns:
            List of glossary entries
        """
        entries: list[GlossaryEntry] = []

        # Extract class name as term
        class_term = self._extract_class_term(class_data.name)
        if class_term:
            entry = self._generate_business_meaning(
                term=class_term,
                context={
                    "class_name": class_data.name,
                    "method_name": "",
                    "comment": "",
                },
                source_fqn=class_data.fqn,
            )
            if entry:
                entries.append(entry)

        # Extract method names as terms
        if methods:
            for method in methods:
                if self._is_domain_relevant_method(method):
                    method_term = self._extract_method_term(method.name)
                    if method_term:
                        entry = self._generate_business_meaning(
                            term=method_term,
                            context={
                                "class_name": class_data.name,
                                "method_name": method.name,
                                "comment": "",
                            },
                            source_fqn=method.fqn,
                        )
                        if entry:
                            entries.append(entry)

        # Extract field names as terms
        if fields:
            for field in fields:
                field_term = self._extract_field_term(field.name)
                if field_term:
                    entry = self._generate_business_meaning(
                        term=field_term,
                        context={
                            "class_name": class_data.name,
                            "method_name": "",
                            "comment": "",
                        },
                        source_fqn=field.fqn,
                    )
                    if entry:
                        entries.append(entry)

        return entries

    def build_glossary(
        self,
        symbols: list[SymbolData],
        symbol_map: dict[str, SymbolData] | None = None,
    ) -> list[GlossaryEntry]:
        """Build complete glossary from all symbols.

        Args:
            symbols: List of all symbols
            symbol_map: Optional map from FQN to symbol data

        Returns:
            List of all glossary entries
        """
        all_entries: list[GlossaryEntry] = []
        symbol_map = symbol_map or {}

        # Group symbols by class
        classes = [s for s in symbols if s.kind in (SymbolKind.CLASS, SymbolKind.INTERFACE)]

        for cls in classes:
            # Get methods and fields for this class
            methods = [s for s in symbols if s.parent_fqn == cls.fqn and s.kind == SymbolKind.METHOD]
            fields = [s for s in symbols if s.parent_fqn == cls.fqn and s.kind == SymbolKind.FIELD]

            entries = self.extract_terms_from_class(cls, methods, fields)
            all_entries.extend(entries)

        # Remove duplicates (by code_term)
        seen_terms: set[str] = set()
        unique_entries: list[GlossaryEntry] = []
        for entry in all_entries:
            if entry.code_term not in seen_terms:
                seen_terms.add(entry.code_term)
                unique_entries.append(entry)

        return unique_entries

    def _extract_class_term(self, class_name: str) -> str | None:
        """Extract domain term from class name.

        Args:
            class_name: Class name

        Returns:
            Extracted term or None if not domain-relevant
        """
        # Skip generic test/mock classes
        if class_name.startswith("Test") or class_name.startswith("Mock"):
            return None

        # Remove common suffixes
        base_name = class_name
        for suffix in ["Entity", "DTO", "VO", "Model", "Service", "Repository", "Controller", "Manager", "Handler", "Processor"]:
            if base_name.endswith(suffix):
                base_name = base_name[: -len(suffix)]
                break

        # Skip if too short after removing suffix
        if len(base_name) < 3:
            return None

        return base_name

    def _extract_method_term(self, method_name: str) -> str | None:
        """Extract domain term from method name.

        Args:
            method_name: Method name

        Returns:
            Extracted term or None if not domain-relevant
        """
        # Skip getters/setters and common methods
        for pattern in self.GETTER_SETTER_PATTERNS:
            if re.match(pattern, method_name):
                return None

        # Convert camelCase to space-separated words
        term = re.sub(r"([A-Z])", r" \1", method_name).strip().lower()

        # Skip if too short
        if len(term) < 3:
            return None

        return term

    def _extract_field_term(self, field_name: str) -> str | None:
        """Extract domain term from field name.

        Args:
            field_name: Field name

        Returns:
            Extracted term or None if not domain-relevant
        """
        # Skip common technical fields
        if field_name.startswith(("_", "serial")):
            return None

        # Convert camelCase to space-separated words
        term = re.sub(r"([A-Z])", r" \1", field_name).strip().lower()

        # Skip if too short
        if len(term) < 3:
            return None

        return term

    def _is_domain_relevant_method(self, method: SymbolData) -> bool:
        """Check if a method is domain-relevant (not just technical).

        Args:
            method: Method symbol data

        Returns:
            True if method should be included in glossary
        """
        name = method.name

        # Skip getters/setters
        for pattern in self.GETTER_SETTER_PATTERNS:
            if re.match(pattern, name):
                return False

        # Include methods with business-related verbs
        business_verbs = ["create", "update", "delete", "save", "find", "validate", "process", "calculate", "generate"]
        return any(name.startswith(verb) or verb in name.lower() for verb in business_verbs)

    def _generate_business_meaning(
        self,
        term: str,
        context: dict[str, str],
        source_fqn: str,
    ) -> GlossaryEntry | None:
        """Generate business meaning for a term using LLM.

        Args:
            term: Code term
            context: Context (class_name, method_name, comment)
            source_fqn: Source symbol FQN

        Returns:
            GlossaryEntry or None if generation failed
        """
        prompt = GLOSSARY_TERM_PROMPT.format(
            term=term,
            class_name=context.get("class_name", ""),
            method_name=context.get("method_name", ""),
            comment=context.get("comment", ""),
        )

        try:
            result = self.llm_client.generate_structured_response(prompt)
            business_meaning = result.get("business_meaning", "")
            synonyms = result.get("synonyms", [])

            if not business_meaning:
                return None

            return GlossaryEntry(
                code_term=term,
                business_meaning=business_meaning,
                synonyms=synonyms,
                source_fqn=source_fqn,
            )
        except Exception as e:
            logger.error(f"Failed to generate business meaning for {term}: {e}")
            return None

    def close(self) -> None:
        """Close the LLM client."""
        self.llm_client.close()
