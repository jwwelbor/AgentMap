from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class GraphBundle:
    graph: Any
    node_registry: Dict[str, Any]
    version_hash: Optional[str] = None
