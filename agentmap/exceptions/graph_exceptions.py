class GraphBuildingError(Exception):
    """Base class for graph building related exceptions."""
    pass

class InvalidEdgeDefinitionError(GraphBuildingError):
    """Raised when a graph edge is defined incorrectly in the CSV."""
    pass