# services/graph_bundle_service.py

import hashlib
import logging
import pickle
from pathlib import Path
from typing import Optional

from agentmap.models.graph_bundle import GraphBundle


class GraphBundleService:
    def __init__(self, logger: logging.Logger):
        if not logger:
            raise ValueError("Logger is required for GraphBundleService.")
        self.logger = logger

    def create_bundle(
        self,
        graph: any,
        node_registry: dict,
        csv_content: Optional[str] = None,
        version_hash: Optional[str] = None,
    ) -> GraphBundle:
        """Create a new GraphBundle, optionally computing a version hash."""
        if not version_hash and csv_content:
            version_hash = self._generate_hash(csv_content)
        return GraphBundle(
            graph=graph, node_registry=node_registry, version_hash=version_hash
        )

    def save_bundle(self, bundle: GraphBundle, path: Path) -> None:
        """Persist the bundle to disk as a pickle file."""
        data = {
            "graph": bundle.graph,
            "node_registry": bundle.node_registry,
            "version_hash": bundle.version_hash,
        }
        with path.open("wb") as f:
            pickle.dump(data, f)
        self.logger.debug(
            f"Saved GraphBundle to {path} with version hash {bundle.version_hash}"
        )

    def load_bundle(self, path: Path) -> Optional[GraphBundle]:
        """Load a GraphBundle from a file."""
        try:
            with path.open("rb") as f:
                data = pickle.load(f)

            return GraphBundle(
                graph=data["graph"],
                node_registry=data["node_registry"],
                version_hash=data["version_hash"],
            )
        except Exception as e:
            self.logger.error(f"Failed to load GraphBundle from {path}: {e}")
            return None

    def verify_csv(self, bundle: GraphBundle, csv_content: str) -> bool:
        """Check if CSV content hash matches bundle version hash."""
        if not bundle.version_hash:
            return False
        current_hash = self._generate_hash(csv_content)
        return bundle.version_hash == current_hash

    @staticmethod
    def _generate_hash(content: str) -> str:
        return hashlib.md5(content.encode("utf-8")).hexdigest()
