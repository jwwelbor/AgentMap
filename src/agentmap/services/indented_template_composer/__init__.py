"""
IndentedTemplateComposer for AgentMap.

Service that provides template composition with proper indentation handling.
This module has been refactored into smaller, focused components while maintaining
100% backwards compatibility with the original API.

Architecture:
- TemplateLoader: Template loading and caching
- CodeGenerator: Code snippet generation
- AgentTemplateComposer: Agent template composition
- FunctionTemplateComposer: Function template composition
- IndentedTemplateComposer: Main orchestrator (delegates to above)

Public API (Backwards Compatible):
- IndentedTemplateComposer: Main service class
- SectionSpec: Template section specification
- INDENT_LEVELS: Standard Python indentation levels
"""

from .composer import INDENT_LEVELS, IndentedTemplateComposer, SectionSpec

# Re-export for backwards compatibility
__all__ = [
    "IndentedTemplateComposer",
    "SectionSpec",
    "INDENT_LEVELS",
]
