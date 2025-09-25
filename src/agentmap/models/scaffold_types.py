"""
Shared types and data structures for scaffolding services.

This module contains common data structures used by both IndentedTemplateComposer
and GraphScaffoldService to avoid circular import dependencies.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, NamedTuple, Optional

if TYPE_CHECKING:
    from agentmap.models.graph_bundle import GraphBundle


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
    """Configuration options for scaffolding operations.

    Args:
        graph_name: Optional name for the graph being scaffolded
        output_path: Directory path where agent files will be generated
        function_path: Directory path where function files will be generated
        overwrite_existing: Whether to overwrite existing agent files
        force_rescaffold: Whether to force rescaffold all custom agents (not just missing ones).
                         When True, all custom agents will be regenerated regardless of existing files.
                         Requires overwrite_existing=True for safety.
    """

    graph_name: Optional[str] = None
    output_path: Optional[Path] = None
    function_path: Optional[Path] = None
    overwrite_existing: bool = False
    force_rescaffold: bool = False


@dataclass
class ScaffoldResult:
    """Result of scaffolding operations."""

    scaffolded_count: int
    created_files: List[Path] = field(default_factory=list)
    skipped_files: List[Path] = field(default_factory=list)
    service_stats: Dict[str, int] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    updated_bundle: Optional["GraphBundle"] = None
