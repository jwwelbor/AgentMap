# services/graph/bundle_validator.py

import hashlib
from typing import Any, Dict

from agentmap.models.node import Node
from agentmap.services.logging_service import LoggingService


class BundleValidator:
    """Handles validation metadata generation (Phase 3).

    This class is responsible for generating validation metadata used for
    integrity checks and compatibility verification.
    """

    def __init__(self, logging_service: LoggingService):
        """Initialize the bundle validator.

        Args:
            logging_service: Service for logging operations
        """
        self.logger = logging_service.get_class_logger(self)

    def generate_validation_metadata(self, nodes: Dict[str, Node]) -> Dict[str, Any]:
        """Generate validation metadata for integrity checks.

        Args:
            nodes: Dictionary of node name to Node objects

        Returns:
            Dictionary containing validation metadata
        """
        try:
            # Generate per-node hashes for validation
            node_hashes = {}
            for name, node in nodes.items():
                node_str = f"{node.name}:{node.agent_type}:{len(node.edges)}"
                node_hashes[name] = hashlib.md5(node_str.encode()).hexdigest()[:8]

            validation_data = {
                "node_hashes": node_hashes,
                "compatibility_version": "1.0",
                "framework_version": self.get_framework_version(),
                "validation_rules": [
                    "unique_node_names",
                    "valid_edge_targets",
                    "required_fields_present",
                ],
            }

            self.logger.debug(
                f"Generated validation metadata for {len(node_hashes)} nodes"
            )
            return validation_data

        except Exception as e:
            self.logger.warning(
                f"Failed to generate validation metadata: {e}. Using minimal validation."
            )
            return {
                "node_hashes": {},
                "compatibility_version": "1.0",
                "framework_version": "unknown",
                "validation_rules": [],
            }

    def get_framework_version(self) -> str:
        """Get the AgentMap framework version.

        Returns:
            Framework version string
        """
        try:
            # This would typically read from package metadata
            return "2.0.0"  # Placeholder version
        except Exception:
            return "unknown"
