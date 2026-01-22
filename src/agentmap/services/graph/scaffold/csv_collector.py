"""CSV collection utilities for scaffolding."""

import csv
from pathlib import Path
from typing import Any, Dict, Optional

from agentmap.services.agent.agent_registry_service import AgentRegistryService
from agentmap.services.function_resolution_service import FunctionResolutionService
from agentmap.services.logging_service import LoggingService


class CSVCollector:
    """Collects agent and function information from CSV files."""

    def __init__(
        self,
        agent_registry: AgentRegistryService,
        function_service: FunctionResolutionService,
        logging_service: LoggingService,
    ):
        self.agent_registry = agent_registry
        self.function_service = function_service
        self.logger = logging_service.get_class_logger(self)

    def collect_agent_info(
        self, csv_path: Path, graph_name: Optional[str] = None
    ) -> Dict[str, Dict[str, Any]]:
        """Collect information about agents from the CSV file."""
        agent_info: Dict[str, Dict[str, Any]] = {}

        with open(csv_path) as f:
            reader = csv.DictReader(f)
            for row in reader:
                if graph_name and row.get("GraphName", "").strip() != graph_name:
                    continue

                agent_type = row.get("AgentType", "").strip()

                if agent_type and not self.agent_registry.has_agent(agent_type):
                    if agent_type not in agent_info:
                        agent_info[agent_type] = {
                            "agent_type": agent_type,
                            "node_name": row.get("Node", "").strip(),
                            "context": row.get("Context", "").strip(),
                            "prompt": row.get("Prompt", "").strip(),
                            "input_fields": [
                                x.strip()
                                for x in row.get("Input_Fields", "").split("|")
                                if x.strip()
                            ],
                            "output_field": row.get("Output_Field", "").strip(),
                            "description": row.get("Description", "").strip(),
                        }

        return agent_info

    def collect_function_info(
        self, csv_path: Path, graph_name: Optional[str] = None
    ) -> Dict[str, Dict[str, Any]]:
        """Collect information about functions from the CSV file."""
        func_info: Dict[str, Dict[str, Any]] = {}

        with open(csv_path) as f:
            reader = csv.DictReader(f)
            for row in reader:
                if graph_name and row.get("GraphName", "").strip() != graph_name:
                    continue

                for col in ["Edge", "Success_Next", "Failure_Next"]:
                    func = self.function_service.extract_func_ref(row.get(col, ""))
                    if func and func not in func_info:
                        func_info[func] = {
                            "node_name": row.get("Node", "").strip(),
                            "context": row.get("Context", "").strip(),
                            "input_fields": [
                                x.strip()
                                for x in row.get("Input_Fields", "").split("|")
                                if x.strip()
                            ],
                            "output_field": row.get("Output_Field", "").strip(),
                            "success_next": row.get("Success_Next", "").strip(),
                            "failure_next": row.get("Failure_Next", "").strip(),
                            "description": row.get("Description", "").strip(),
                        }

        return func_info
