"""
Business Constraint Extractor
==============================

Extracts business constraints and rules from code and comments.
"""

import json
import logging
import re
from typing import Any

from ariadne_core.models.types import ConstraintEntry, ConstraintType, SymbolData
from ariadne_llm import LLMClient, LLMConfig

from .prompts import CONSTRAINT_EXTRACTION_PROMPT

logger = logging.getLogger(__name__)


class BusinessConstraintExtractor:
    """Extracts business constraints from code.

    Identifies:
    - Validation constraints from annotations and asserts
    - Business rules from logic patterns
    - Invariants from code structure
    """

    # Patterns for explicit constraint extraction
    ASSERT_PATTERN = re.compile(r'assert\s+(.+?)\s*:\s*["\'](.+?)["\']')
    VALIDATION_ANNOTATIONS = [
        "@NotNull",
        "@NotEmpty",
        "@NotBlank",
        "@Min(",
        "@Max(",
        "@Size(",
        "@Pattern(",
        "@Email",
        "@Positive",
        "@Negative",
    ]

    # Patterns for implicit constraint detection
    CONSTRAINT_CHECKS = [
        (r"if\s*\(\s*(.+?)\s*[<>=]+\s*0\s*\)", "边界值检查"),
        (r"if\s*\(\s*(.+?)\s*==\s*null\s*\)", "空值检查"),
        (r"throw new IllegalArgumentException\((.+?)\)", "非法参数异常"),
        (r"throw new IllegalStateException\((.+?)\)", "非法状态异常"),
    ]

    def __init__(self, config: LLMConfig | None = None) -> None:
        """Initialize constraint extractor with LLM client.

        Args:
            config: Optional LLMConfig (uses env if not provided)
        """
        if config is None:
            config = LLMConfig.from_env()

        self.llm_client = LLMClient(config)

    def extract_from_method(
        self,
        method: SymbolData,
        source_code: str,
        class_name: str = "",
    ) -> list[ConstraintEntry]:
        """Extract constraints from a method.

        Args:
            method: Method symbol data
            source_code: Method source code
            class_name: Optional class name for context

        Returns:
            List of constraint entries
        """
        constraints: list[ConstraintEntry] = []

        # Extract explicit constraints from annotations
        constraints.extend(self._extract_from_annotations(method, class_name))

        # Extract explicit constraints from asserts
        constraints.extend(self._extract_from_asserts(method, source_code, class_name))

        # Extract implicit constraints using LLM
        implicit = self._extract_implicit_constraints(method, source_code, class_name)
        constraints.extend(implicit)

        return constraints

    def _extract_from_annotations(
        self,
        method: SymbolData,
        class_name: str,
    ) -> list[ConstraintEntry]:
        """Extract validation constraints from annotations.

        Args:
            method: Method symbol data
            class_name: Class name for context

        Returns:
            List of constraint entries
        """
        constraints: list[ConstraintEntry] = []

        for annotation in method.annotations:
            # Check for validation annotations
            for valid_ann in self.VALIDATION_ANNOTATIONS:
                if annotation.startswith(valid_ann):
                    name = f"{method.name}_{valid_ann.replace('@', '')}"
                    description = f"参数验证: {annotation}"

                    # Determine constraint type
                    if valid_ann in ["@NotNull", "@NotEmpty", "@NotBlank"]:
                        ctype = ConstraintType.VALIDATION
                    else:
                        ctype = ConstraintType.VALIDATION

                    constraints.append(
                        ConstraintEntry(
                            name=name,
                            description=description,
                            source_fqn=method.fqn,
                            constraint_type=ctype,
                        )
                    )

        return constraints

    def _extract_from_asserts(
        self,
        method: SymbolData,
        source_code: str,
        class_name: str,
    ) -> list[ConstraintEntry]:
        """Extract constraints from assert statements.

        Args:
            method: Method symbol data
            source_code: Method source code
            class_name: Class name for context

        Returns:
            List of constraint entries
        """
        constraints: list[ConstraintEntry] = []

        for match in self.ASSERT_PATTERN.finditer(source_code):
            condition = match.group(1).strip()
            message = match.group(2)

            constraints.append(
                ConstraintEntry(
                    name=f"{method.name}_assert_{len(constraints)}",
                    description=message or f"断言: {condition}",
                    source_fqn=method.fqn,
                    constraint_type=ConstraintType.BUSINESS_RULE,
                )
            )

        return constraints

    def _extract_implicit_constraints(
        self,
        method: SymbolData,
        source_code: str,
        class_name: str,
    ) -> list[ConstraintEntry]:
        """Extract implicit constraints using LLM.

        Args:
            method: Method symbol data
            source_code: Method source code
            class_name: Class name for context

        Returns:
            List of constraint entries
        """
        prompt = CONSTRAINT_EXTRACTION_PROMPT.format(
            source_code=source_code[:2000],  # Limit to 2000 chars for LLM
            class_name=class_name,
            method_name=method.name,
        )

        try:
            result = self.llm_client.generate_structured_response(prompt)
            constraint_list = result.get("constraints", [])

            constraints: list[ConstraintEntry] = []
            for i, c in enumerate(constraint_list):
                name = c.get("name", f"{method.name}_constraint_{i}")
                description = c.get("description", "")
                type_str = c.get("type", "business_rule")

                # Map string to ConstraintType
                if type_str == "validation":
                    ctype = ConstraintType.VALIDATION
                elif type_str == "invariant":
                    ctype = ConstraintType.INVARIANT
                else:
                    ctype = ConstraintType.BUSINESS_RULE

                constraints.append(
                    ConstraintEntry(
                        name=name,
                        description=description,
                        source_fqn=method.fqn,
                        constraint_type=ctype,
                    )
                )

            return constraints
        except Exception as e:
            logger.error(f"Failed to extract implicit constraints from {method.name}: {e}")
            return []

    def extract_from_comments(
        self,
        comments: list[tuple[int, str]],
        context_fqn: str,
    ) -> list[ConstraintEntry]:
        """Extract constraints from code comments.

        Args:
            comments: List of (line_number, comment_text) tuples
            context_fqn: Context symbol FQN

        Returns:
            List of constraint entries
        """
        constraints: list[ConstraintEntry] = []

        # Patterns for constraint descriptions in comments
        constraint_patterns = [
            r"(必须|不能|不可|禁止|限制|要求|约束|规则)",
            r"(should not|must not|required|mandatory)",
        ]

        for line_no, comment in comments:
            # Check if comment contains constraint language
            for pattern in constraint_patterns:
                if re.search(pattern, comment, re.IGNORECASE):
                    constraints.append(
                        ConstraintEntry(
                            name=f"constraint_line_{line_no}",
                            description=comment.strip(),
                            source_fqn=context_fqn,
                            source_line=line_no,
                            constraint_type=ConstraintType.BUSINESS_RULE,
                        )
                    )
                    break

        return constraints

    def close(self) -> None:
        """Close the LLM client."""
        self.llm_client.close()
