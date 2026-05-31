from agentmap.exceptions.base_exceptions import AgentMapException


class GraphBuildingError(AgentMapException):
    """Base class for graph building related exceptions."""


class InvalidEdgeDefinitionError(GraphBuildingError):
    """Raised when a graph edge is defined incorrectly in the CSV."""


class BundleLoadError(AgentMapException):
    """Raised when a bundle fails to load."""


class MissingServiceDeclarationError(GraphBuildingError):
    """Raised when a graph requires a service that is not declared/registered.

    This is a wiring ("compiler") error: a declared agent requires a service
    that exists in neither the builtin nor the host declaration namespace. It
    is enforced at the run/execute gate, not at assembly, so that scaffold and
    other repair flows can still assemble an incomplete bundle.
    """
