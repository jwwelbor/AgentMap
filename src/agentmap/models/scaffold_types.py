"""
Shared types and data structures for scaffolding services.

This module contains common data structures used by both IndentedTemplateComposer
and GraphScaffoldService to avoid circular import dependencies.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional


@dataclass
class ServiceAttribute:
    """Represents a service attribute to be added to an agent."""

    name: str
    type_hint: str
    documentation: str


class ServiceRequirements(NamedTuple):
    """Container for parsed service requirements."""

    services: List[str]
    protocols: List[str]
    imports: List[str]
    attributes: List[ServiceAttribute]
    usage_examples: Dict[str, str]


@dataclass
class ScaffoldOptions:
    """Configuration options for scaffolding operations."""

    graph_name: Optional[str] = None
    output_path: Optional[Path] = None
    function_path: Optional[Path] = None
    overwrite_existing: bool = False


@dataclass
class ScaffoldResult:
    """Result of scaffolding operations."""

    scaffolded_count: int
    created_files: List[Path] = field(default_factory=list)
    skipped_files: List[Path] = field(default_factory=list)
    service_stats: Dict[str, int] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
