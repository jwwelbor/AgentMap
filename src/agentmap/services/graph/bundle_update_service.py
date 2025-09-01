"""
BundleUpdateService for AgentMap.

Service responsible for updating cached bundles with current declaration mappings
after scaffolding or when declarations change.
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from agentmap.models.graph_bundle import GraphBundle
from agentmap.services.custom_agent_declaration_manager import (
    CustomAgentDeclarationManager,
)
from agentmap.services.declaration_registry_service import DeclarationRegistryService
from agentmap.services.file_path_service import FilePathService
from agentmap.services.graph.graph_bundle_service import GraphBundleService
from agentmap.services.logging_service import LoggingService


class BundleUpdateService:
    """
    Service for updating bundles with current declaration mappings.

    Bridges the gap between scaffolded YAML declarations and cached bundles,
    ensuring bundles have proper agent_mappings for instantiation.
    """

    def __init__(
        self,
        declaration_registry_service: DeclarationRegistryService,
        custom_agent_declaration_manager: CustomAgentDeclarationManager,
        graph_bundle_service: GraphBundleService,
        file_path_service: FilePathService,
        logging_service: LoggingService,
    ):
        """
        Initialize with required services.

        Args:
            declaration_registry_service: Service for accessing declarations
            custom_agent_declaration_manager: Service for custom agent declarations
            graph_bundle_service: Service for bundle persistence
            file_path_service: Service for centralized secure path handling
            logging_service: Service for logging
        """
        self.declaration_registry = declaration_registry_service
        self.custom_agent_declaration_manager = custom_agent_declaration_manager
        self.graph_bundle_service = graph_bundle_service
        self.file_path_service = file_path_service
        self.logger = logging_service.get_class_logger(self)

        self.logger.info("[BundleUpdateService] Initialized")

    def update_bundle_from_declarations(
        self, bundle: GraphBundle, persist: bool = True
    ) -> GraphBundle:
        """
        Update a bundle with current declaration mappings.

        Updates bundle's agent_mappings and service requirements
        based on current state of declaration registry.

        Args:
            bundle: Bundle to update
            persist: Whether to save updated bundle to cache

        Returns:
            Updated bundle with current mappings
        """
        self.logger.info(
            f"[BundleUpdateService] Updating bundle '{bundle.graph_name}' "
            f"with current declarations"
        )

        update_summary = {
            "newly_resolved": [],
            "updated_mappings": [],
            "removed_mappings": [],
            "new_services": set(),
        }

        # Initialize sets if None
        if bundle.agent_mappings is None:
            bundle.agent_mappings = {}
        if bundle.custom_agents is None:
            bundle.custom_agents = set()
        if bundle.missing_declarations is None:
            bundle.missing_declarations = set()

        # Step 1: Update missing declarations
        if bundle.missing_declarations:
            self._update_missing_declarations(bundle, update_summary)

        # Step 2: Verify existing mappings
        self._verify_existing_mappings(bundle, update_summary)

        # Step 3: Update service requirements
        if update_summary["newly_resolved"]:
            self._update_service_requirements(bundle, update_summary)

        # Step 4: Add troubleshooting timestamp
        bundle.last_updated = datetime.now().isoformat()

        # Step 5: Persist if requested and changed
        if self._has_changes(update_summary) and persist:
            self._persist_updated_bundle(bundle)

        # Step 6: Log summary
        self._log_update_summary(bundle, update_summary)

        return bundle

    def _update_missing_declarations(
        self, bundle: GraphBundle, summary: Dict[str, Any]
    ) -> None:
        """Update bundle with newly available declarations."""

        custom_agent_declarations = (
            self.custom_agent_declaration_manager.load_declarations().get("agents", {})
            or {}
        )
        for agent_type in list(bundle.missing_declarations):
            decl = self.declaration_registry.get_agent_declaration(
                agent_type
            ) or custom_agent_declarations.get(agent_type)

            if decl:
                class_path = (
                    isinstance(decl, dict) and decl.get("class_path") or decl.class_path
                )
                # Found declaration - update bundle
                bundle.agent_mappings[agent_type] = class_path
                bundle.custom_agents.add(agent_type)
                bundle.missing_declarations.remove(agent_type)
                summary["newly_resolved"].append(agent_type)

                self.logger.debug(
                    f"[BundleUpdateService] Resolved missing agent "
                    f"'{agent_type}' -> {class_path}"
                )

    def _verify_existing_mappings(
        self, bundle: GraphBundle, summary: Dict[str, Any]
    ) -> None:
        """Verify existing mappings are still current."""

        custom_agent_declarations = (
            self.custom_agent_declaration_manager.load_declarations().get("agents", {})
            or {}
        )
        for agent_type, class_path in list(bundle.agent_mappings.items()):
            decl = self.declaration_registry.get_agent_declaration(
                agent_type
            ) or custom_agent_declarations.get(agent_type)

            if not decl:
                # Declaration no longer exists - handle in the elif below
                decl_class_path = None
            else:
                decl_class_path = (
                    isinstance(decl, dict) and decl.get("class_path") or decl.class_path
                )

            if decl and decl_class_path and decl_class_path != class_path:
                # Declaration changed - update mapping
                old_path = class_path
                bundle.agent_mappings[agent_type] = decl_class_path
                summary["updated_mappings"].append(
                    (agent_type, old_path, decl_class_path)
                )
                self.logger.info(
                    f"[BundleUpdateService] Updated mapping for '{agent_type}': "
                    f"{old_path} -> {decl_class_path}"
                )

            elif not decl and agent_type in bundle.custom_agents:
                # Custom agent no longer exists - mark as missing
                bundle.missing_declarations.add(agent_type)
                del bundle.agent_mappings[agent_type]
                bundle.custom_agents.discard(agent_type)
                summary["removed_mappings"].append(agent_type)
                self.logger.warning(
                    f"[BundleUpdateService] Agent '{agent_type}' no longer "
                    f"in declarations, marking as missing"
                )

    def _update_service_requirements(
        self, bundle: GraphBundle, summary: Dict[str, Any]
    ) -> None:
        """Update service requirements for newly resolved agents."""
        new_requirements = self.declaration_registry.resolve_agent_requirements(
            set(summary["newly_resolved"])
        )

        if new_requirements["services"]:
            # Add new service requirements
            bundle.required_services.update(new_requirements["services"])
            summary["new_services"] = new_requirements["services"]

            # Recalculate load order
            bundle.service_load_order = self.declaration_registry.calculate_load_order(
                bundle.required_services
            )

            self.logger.debug(
                f"[BundleUpdateService] Added {len(new_requirements['services'])} "
                f"new service requirements"
            )

    def _persist_updated_bundle(self, bundle: GraphBundle) -> None:
        """Save updated bundle back to cache."""
        try:
            # Use FilePathService for centralized path calculation
            bundle_path = self.file_path_service.get_bundle_path(
                csv_hash=bundle.csv_hash, graph_name=bundle.graph_name
            )

            result = self.graph_bundle_service.save_bundle(bundle, bundle_path)
            if result.success:
                self.logger.info(
                    f"[BundleUpdateService] Saved updated bundle to {bundle_path.name}"
                )
            else:
                self.logger.error(
                    f"[BundleUpdateService] Failed to save bundle: {result.error}"
                )
        except Exception as e:
            self.logger.error(f"[BundleUpdateService] Error persisting bundle: {e}")

    def _has_changes(self, summary: Dict[str, Any]) -> bool:
        """Check if any changes were made."""
        return bool(
            summary["newly_resolved"]
            or summary["updated_mappings"]
            or summary["removed_mappings"]
            or summary["new_services"]
        )

    def _log_update_summary(self, bundle: GraphBundle, summary: Dict[str, Any]) -> None:
        """Log a summary of the update."""
        if summary["newly_resolved"]:
            self.logger.info(
                f"[BundleUpdateService] ✅ Resolved {len(summary['newly_resolved'])} "
                f"agents: {', '.join(summary['newly_resolved'])}"
            )

        if summary["updated_mappings"]:
            self.logger.info(
                f"[BundleUpdateService] 🔄 Updated {len(summary['updated_mappings'])} "
                f"mappings"
            )

        if summary["removed_mappings"]:
            self.logger.warning(
                f"[BundleUpdateService] ⚠️ Removed {len(summary['removed_mappings'])} "
                f"obsolete mappings: {', '.join(summary['removed_mappings'])}"
            )

        if bundle.missing_declarations:
            self.logger.warning(
                f"[BundleUpdateService] ⚠️ Still missing {len(bundle.missing_declarations)} "
                f"declarations: {', '.join(bundle.missing_declarations)}"
            )

        total_mapped = len(bundle.agent_mappings) if bundle.agent_mappings else 0
        self.logger.info(
            f"[BundleUpdateService] Bundle now has {total_mapped} agent mappings"
        )

    def get_update_summary(self, bundle: GraphBundle) -> Dict[str, Any]:
        """
        Get a summary of what would be updated for a bundle.

        Args:
            bundle: Bundle to analyze

        Returns:
            Dictionary with update preview information
        """
        preview = {
            "bundle_name": bundle.graph_name,
            "current_mappings": (
                len(bundle.agent_mappings) if bundle.agent_mappings else 0
            ),
            "missing_declarations": (
                list(bundle.missing_declarations) if bundle.missing_declarations else []
            ),
            "would_resolve": [],
            "would_update": [],
            "would_remove": [],
        }

        # Check what would be resolved
        if bundle.missing_declarations:
            for agent_type in bundle.missing_declarations:
                decl = self.declaration_registry.get_agent_declaration(agent_type)
                if decl and decl.class_path:
                    preview["would_resolve"].append(agent_type)

        # Check what would be updated
        if bundle.agent_mappings:
            for agent_type, class_path in bundle.agent_mappings.items():
                decl = self.declaration_registry.get_agent_declaration(agent_type)
                if decl and decl.class_path != class_path:
                    preview["would_update"].append(agent_type)
                elif not decl:
                    preview["would_remove"].append(agent_type)

        return preview
