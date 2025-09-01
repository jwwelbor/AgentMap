from agentmap.exceptions.base_exceptions import AgentMapException


class GraphBuildingError(AgentMapException):
    """Base class for graph building related exceptions."""


class InvalidEdgeDefinitionError(GraphBuildingError):
    """Raised when a graph edge is defined incorrectly in the CSV."""


class BundleLoadError(AgentMapException):
    """Raised when a bundle fails to load."""
