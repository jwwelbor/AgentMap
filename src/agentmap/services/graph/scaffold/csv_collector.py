"""
CSV collection utilities for scaffolding.

This module provides functionality for collecting agent and function
information from CSV graph definition files.
"""

import csv
from pathlib import Path
from typing import Any, Dict, Optional

from agentmap.services.agent.agent_registry_service import AgentRegistryService
from agentmap.services.function_resolution_service import FunctionResolutionService
from agentmap.services.logging_service import LoggingService


class CSVCollector:
    """
    Collects agent and function information from CSV files.

    This class provides methods to parse CSV graph definition files
    and extract structured information for scaffolding purposes.
    """

    def __init__(
        self,
        agent_registry: AgentRegistryService,
        function_service: FunctionResolutionService,
        logging_service: LoggingService,
    ):
        """
        Initialize the CSVCollector.

        Args:
            agent_registry: Service for checking agent registration
            function_service: Service for function resolution and extraction
            logging_service: Logging service instance
        """
        self.agent_registry = agent_registry
        self.function_service = function_service
        self.logger = logging_service.get_class_logger(self)

    def collect_agent_info(
        self, csv_path: Path, graph_name: Optional[str] = None
    ) -> Dict[str, Dict[str, Any]]:
        """
        Collect information about agents from the CSV file.

        Args:
            csv_path: Path to the CSV file
            graph_name: Optional graph name to filter by

        Returns:
            Dictionary mapping agent types to their information
        """
        agent_info: Dict[str, Dict[str, Any]] = {}

        with open(csv_path) as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Skip rows that don't match our graph filter
                if graph_name and row.get("GraphName", "").strip() != graph_name:
                    continue

                # Collect agent information
                agent_type = row.get("AgentType", "").strip()

                # Check agent registry to see if agent is already registered
                # If agent is already in registry (builtin or custom), don't scaffold it
                if agent_type and not self.agent_registry.has_agent(agent_type):
                    self.logger.debug(
                        f"[CSVCollector] Found unregistered agent type '{agent_type}' - will scaffold"
                    )
                    node_name = row.get("Node", "").strip()
                    context = row.get("Context", "").strip()
                    prompt = row.get("Prompt", "").strip()
                    input_fields = [
                        x.strip()
                        for x in row.get("Input_Fields", "").split("|")
                        if x.strip()
                    ]
                    output_field = row.get("Output_Field", "").strip()
                    description = row.get("Description", "").strip()

                    if agent_type not in agent_info:
                        agent_info[agent_type] = {
                            "agent_type": agent_type,
                            "node_name": node_name,
                            "context": context,
                            "prompt": prompt,
                            "input_fields": input_fields,
                            "output_field": output_field,
                            "description": description,
                        }
                elif agent_type:
                    # Agent is already registered, skip scaffolding
                    self.logger.debug(
                        f"[CSVCollector] Skipping registered agent type '{agent_type}' - already available"
                    )

        return agent_info

    def collect_function_info(
        self, csv_path: Path, graph_name: Optional[str] = None
    ) -> Dict[str, Dict[str, Any]]:
        """
        Collect information about functions from the CSV file.

        Args:
            csv_path: Path to the CSV file
            graph_name: Optional graph name to filter by

        Returns:
            Dictionary mapping function names to their information
        """
        func_info: Dict[str, Dict[str, Any]] = {}

        with open(csv_path) as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Skip rows that don't match our graph filter
                if graph_name and row.get("GraphName", "").strip() != graph_name:
                    continue

                # Collect function information
                for col in ["Edge", "Success_Next", "Failure_Next"]:
                    func = self.function_service.extract_func_ref(row.get(col, ""))
                    if func:
                        node_name = row.get("Node", "").strip()
                        context = row.get("Context", "").strip()
                        input_fields = [
                            x.strip()
                            for x in row.get("Input_Fields", "").split("|")
                            if x.strip()
                        ]
                        output_field = row.get("Output_Field", "").strip()
                        success_next = row.get("Success_Next", "").strip()
                        failure_next = row.get("Failure_Next", "").strip()
                        description = row.get("Description", "").strip()

                        if func not in func_info:
                            func_info[func] = {
                                "node_name": node_name,
                                "context": context,
                                "input_fields": input_fields,
                                "output_field": output_field,
                                "success_next": success_next,
                                "failure_next": failure_next,
                                "description": description,
                            }

        return func_info
