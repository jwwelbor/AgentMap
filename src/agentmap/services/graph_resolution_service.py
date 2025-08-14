"""
GraphResolutionService for determining graph execution strategies.

Extracted from GraphRunnerService to follow Single Responsibility Principle.
"""

from pathlib import Path
from typing import Any, Dict, Optional

from agentmap.services.config.app_config_service import AppConfigService
from agentmap.services.graph_bundle_service import GraphBundleService
from agentmap.services.graph_definition_service import GraphDefinitionService
from agentmap.services.logging_service import LoggingService


class GraphResolutionService:
    """Service for resolving graph execution strategies."""

    def __init__(
        self,
        graph_bundle_service: GraphBundleService,
        graph_definition_service: GraphDefinitionService,
        app_config_service: AppConfigService,
        logging_service: LoggingService,
    ):
        """Initialize GraphResolutionService with dependencies."""
        self.graph_bundle_service = graph_bundle_service
        self.graph_definition_service = graph_definition_service
        self.config = app_config_service
        self.logger = logging_service.get_class_logger(self)

        self.logger.debug("[GraphResolutionService] Initialized")

    def resolve_graph_for_execution(
        self, graph_name: str, csv_path: Optional[Path] = None
    ) -> Dict[str, Any]:
        """
        Resolve graph execution strategy.

        Returns:
            Dict with type ("bundle"/"definition") and corresponding data
        """
        self.logger.debug(f"Resolving graph: {graph_name}")

        if csv_path is None:
            csv_path = self.config.get_csv_path()

        # Check if bundle-based flow is enabled
        bypass_bundling = self.config.get_value("bypass_bundling", False)

        if bypass_bundling:
            # Try cached bundle first
            bundle_path = self.find_metadata_bundle(graph_name)
            if bundle_path:
                bundle = self.graph_bundle_service.load_bundle(bundle_path)
                if bundle and self.validate_bundle_against_csv(bundle, csv_path):
                    self.logger.debug(f"Using cached bundle: {bundle_path}")
                    return {"type": "bundle", "bundle": bundle}

            # Create new bundle
            bundle = self.create_and_cache_bundle(graph_name, csv_path)
            if bundle:
                self.logger.info(f"Created new bundle: {graph_name}")
                return {"type": "bundle", "bundle": bundle}

        # Fallback to definition execution
        self.logger.debug(f"Using definition execution: {graph_name}")
        graph_def = self._load_graph_definition(csv_path, graph_name)
        return {"type": "definition", "graph_def": graph_def}

    def find_metadata_bundle(self, graph_name: str) -> Optional[Path]:
        """Find metadata bundle if it exists."""
        bundle_path = self.config.get_metadata_bundles_path() / f"{graph_name}.json"
        return bundle_path if bundle_path.exists() else None

    def validate_bundle_against_csv(self, bundle: Any, csv_path: Path) -> bool:
        """Validate if bundle is still valid against CSV content."""
        try:
            csv_content = csv_path.read_text(encoding="utf-8")
            return self.graph_bundle_service.validate_bundle(bundle, csv_content)
        except Exception as e:
            self.logger.warning(f"Bundle validation failed: {e}")
            return False

    def create_and_cache_bundle(self, graph_name: str, csv_path: Path) -> Optional[Any]:
        """Create and cache a new metadata bundle."""
        self.logger.debug(f"Creating bundle: {graph_name}")

        try:
            # Parse CSV into GraphSpec first
            csv_content = csv_path.read_text(encoding="utf-8")
            csv_hash = self.graph_bundle_service._generate_hash(csv_content)
            
            # Get GraphSpec from CSV using the CSV parser
            graph_spec = self.graph_definition_service.csv_parser.parse_csv_to_graph_spec(csv_path)
            
            # Create bundle using the correct method
            bundle = self.graph_bundle_service.create_metadata_bundle_from_spec(
                graph_spec, graph_name, csv_hash
            )

            # Save bundle
            bundle_path = self.config.get_metadata_bundles_path() / f"{graph_name}.json"
            bundle_path.parent.mkdir(parents=True, exist_ok=True)
            self.graph_bundle_service.save_bundle(bundle, bundle_path)

            self.logger.info(f"✅ Created bundle: {graph_name}")
            return bundle

        except Exception as e:
            self.logger.error(f"Bundle creation failed for {graph_name}: {e}")
            return None

    def _load_graph_definition(self, csv_path: Path, graph_name: Optional[str]) -> Any:
        """Load graph definition for fallback execution."""
        if graph_name:
            return self.graph_definition_service.build_from_csv(csv_path, graph_name)
        
        # Load first available graph
        all_graphs = self.graph_definition_service.build_all_from_csv(csv_path)
        if not all_graphs:
            raise ValueError(f"No graphs found in CSV file: {csv_path}")
        
        graph_name = next(iter(all_graphs))
        self.logger.debug(f"Using first graph: {graph_name}")
        return all_graphs[graph_name]
