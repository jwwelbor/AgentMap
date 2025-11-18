"""
OrchestratorService for AgentMap.

Service that provides node selection and orchestration business logic.
Extracted from OrchestratorAgent following Domain Model Principles where
models are data containers and services contain business logic.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from agentmap.services.features_registry_service import FeaturesRegistryService
from agentmap.services.llm_service import LLMService
from agentmap.services.logging_service import LoggingService
from agentmap.services.prompt_manager_service import PromptManagerService

# Import from extracted modules
from agentmap.services.orchestrator_algorithm_matching import AlgorithmMatcher
from agentmap.services.orchestrator_llm_matching import LLMMatcher
from agentmap.services.orchestrator_node_filtering import NodeFilter


class OrchestratorService:
    """
    Service for orchestrating node selection using various matching strategies.

    Handles:
    - Algorithm-based keyword matching
    - LLM-based intelligent matching
    - Tiered strategy with confidence thresholds
    - Node filtering and scoring
    - Keyword parsing from CSV context data
    """

    def __init__(
        self,
        prompt_manager_service: PromptManagerService,
        logging_service: LoggingService,
        llm_service: LLMService,
        features_registry_service: FeaturesRegistryService,
    ):
        """Initialize service with dependency injection."""
        self.prompt_manager = prompt_manager_service
        self.logger = logging_service.get_class_logger(self)
        self.llm_service = llm_service
        self.features_registry = features_registry_service

        # Cache NLP capabilities for performance
        self._nlp_capabilities = None
        if self.features_registry:
            self._nlp_capabilities = self.features_registry.get_nlp_capabilities()
            self.logger.debug(
                f"[OrchestratorService] NLP capabilities: {self._nlp_capabilities}"
            )

        # Initialize matchers with extracted modules
        self._algorithm_matcher = AlgorithmMatcher(
            logger=self.logger,
            nlp_capabilities=self._nlp_capabilities
        )

        self._llm_matcher = LLMMatcher(
            logger=self.logger,
            prompt_manager=self.prompt_manager,
            llm_service=self.llm_service,
            keyword_parser=self._algorithm_matcher.parse_node_keywords
        )

        self.logger.info("[OrchestratorService] Initialized")

    def select_best_node(
        self,
        input_text: str,
        available_nodes: Dict[str, Dict[str, Any]],
        strategy: str = "tiered",
        confidence_threshold: float = 0.8,
        node_filter: str = "all",
        llm_config: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Select the best matching node for the given input using specified strategy.

        Args:
            input_text: User input text for matching
            available_nodes: Dictionary of available nodes with metadata
            strategy: Matching strategy ("algorithm", "llm", "tiered")
            confidence_threshold: Confidence threshold for tiered strategy
            node_filter: Node filtering criteria
            llm_config: LLM configuration (provider, temperature, etc.)
            context: Additional context for matching

        Returns:
            Name of the selected node
        """
        self.logger.debug(f"Selecting node for input: '{input_text}'")
        self.logger.debug(
            f"Strategy: {strategy}, Available nodes: {list(available_nodes.keys())}"
        )

        if not available_nodes:
            error_msg = "No nodes available"
            self.logger.error(f"{error_msg} - cannot perform orchestration")
            return context.get("default_target", error_msg) if context else error_msg

        # Apply filtering based on node_filter criteria
        filtered_nodes = self._apply_node_filter(available_nodes, node_filter)
        self.logger.debug(
            f"Available nodes after filtering: {list(filtered_nodes.keys())}"
        )

        if not filtered_nodes:
            default_target = context.get("default_target", "") if context else ""
            self.logger.warning(
                f"No nodes available after filtering. Using default: {default_target}"
            )
            return default_target

        # Handle single node case
        if len(filtered_nodes) == 1:
            node_name = next(iter(filtered_nodes.keys()))
            self.logger.debug(
                f"Only one node available, selecting '{node_name}' without matching"
            )
            return node_name

        # Select node based on matching strategy
        selected_node = self._match_intent(
            input_text,
            filtered_nodes,
            strategy,
            confidence_threshold,
            llm_config,
            context,
        )
        self.logger.info(f"Selected node: '{selected_node}'")
        return selected_node

    def parse_node_keywords(self, node_info: Dict[str, Any]) -> List[str]:
        """
        Parse keywords from node information for efficient matching.

        Args:
            node_info: Node information dictionary

        Returns:
            List of keywords extracted from description, context, and other fields
        """
        return self._algorithm_matcher.parse_node_keywords(node_info)

    def _fuzzy_keyword_match(
        self, input_text: str, keywords: List[str], threshold: int = 80
    ) -> Tuple[float, List[str]]:
        """
        Perform fuzzy keyword matching using fuzzywuzzy if available.

        Args:
            input_text: User input text
            keywords: List of keywords to match against
            threshold: Fuzzy matching threshold (0-100)

        Returns:
            Tuple of (match_score, matched_keywords)
        """
        return self._algorithm_matcher.fuzzy_keyword_match(input_text, keywords, threshold)

    def _spacy_enhanced_keywords(self, node_info: Dict[str, Any]) -> List[str]:
        """
        Extract enhanced keywords using spaCy NLP processing if available.

        Args:
            node_info: Node information dictionary

        Returns:
            List of enhanced keywords extracted using spaCy
        """
        return self._algorithm_matcher.spacy_enhanced_keywords(node_info)

    def _match_intent(
        self,
        input_text: str,
        available_nodes: Dict[str, Dict[str, Any]],
        strategy: str,
        confidence_threshold: float,
        llm_config: Optional[Dict[str, Any]],
        context: Optional[Dict[str, Any]],
    ) -> str:
        """Match input to the best node using the configured strategy."""
        if strategy == "algorithm":
            self.logger.info(
                f"Using algorithm-based orchestration for request: {input_text}"
            )
            node, confidence = self._algorithm_match(input_text, available_nodes)

            # Log warning if no good match found
            if confidence < 0.1:  # Very low confidence indicates no specific match
                self.logger.warning(
                    f"No specific match found for request '{input_text}', using fallback node '{node}'"
                )

            self.logger.debug(
                f"Algorithm matching selected '{node}' with confidence {confidence:.2f}"
            )
            return node

        elif strategy == "llm":
            self.logger.info(f"Using LLM-based orchestration for request: {input_text}")
            return self._llm_match(input_text, available_nodes, llm_config, context)

        else:  # "tiered" - default approach
            node, confidence = self._algorithm_match(input_text, available_nodes)
            if confidence >= confidence_threshold:
                self.logger.info(
                    f"Algorithm match confidence {confidence:.2f} exceeds threshold. Using '{node}'"
                )
                return node
            self.logger.info(
                f"Algorithm match confidence {confidence:.2f} below threshold. Using LLM."
            )
            return self._llm_match(input_text, available_nodes, llm_config, context)

    def _algorithm_match(
        self, input_text: str, available_nodes: Dict[str, Dict[str, Any]]
    ) -> Tuple[str, float]:
        """Enhanced algorithmic matching with 4-level fallback detection."""
        return self._algorithm_matcher.algorithm_match(input_text, available_nodes)

    def _basic_keyword_match(
        self, input_text: str, available_nodes: Dict[str, Dict[str, Any]]
    ) -> Tuple[str, float]:
        """Basic keyword matching using parsed keywords (Level 2)."""
        return self._algorithm_matcher.basic_keyword_match(input_text, available_nodes)

    def _fuzzy_algorithm_match(
        self, input_text: str, available_nodes: Dict[str, Dict[str, Any]]
    ) -> Tuple[str, float]:
        """Fuzzy keyword matching using fuzzywuzzy (Level 3)."""
        return self._algorithm_matcher.fuzzy_algorithm_match(input_text, available_nodes)

    def _spacy_algorithm_match(
        self, input_text: str, available_nodes: Dict[str, Dict[str, Any]]
    ) -> Tuple[str, float]:
        """spaCy enhanced keyword matching (Level 4)."""
        return self._algorithm_matcher.spacy_algorithm_match(input_text, available_nodes)

    def _llm_match(
        self,
        input_text: str,
        available_nodes: Dict[str, Dict[str, Any]],
        llm_config: Optional[Dict[str, Any]],
        context: Optional[Dict[str, Any]],
    ) -> str:
        """Use LLM Service to match input to the best node."""
        return self._llm_matcher.llm_match(input_text, available_nodes, llm_config, context)

    def _format_node_descriptions(self, nodes: Dict[str, Dict[str, Any]]) -> str:
        """Format node descriptions for template substitution."""
        return self._llm_matcher._format_node_descriptions(nodes)

    def _extract_node_from_response(
        self, llm_response: str, available_nodes: Dict[str, Dict[str, Any]]
    ) -> str:
        """Extract the selected node from LLM response."""
        return self._llm_matcher._extract_node_from_response(llm_response, available_nodes)

    def _apply_node_filter(
        self, nodes: Dict[str, Dict[str, Any]], node_filter: str
    ) -> Dict[str, Dict[str, Any]]:
        """Apply node filtering based on filter criteria."""
        return NodeFilter.apply_node_filter(nodes, node_filter)

    def get_service_info(self) -> Dict[str, Any]:
        """
        Get information about the orchestrator service for debugging.

        Returns:
            Dictionary with service status and configuration info
        """
        info = {
            "service": "OrchestratorService",
            "prompt_manager_available": self.prompt_manager is not None,
            "llm_service_configured": self.llm_service is not None,
            "features_registry_configured": self.features_registry is not None,
            "supported_strategies": ["algorithm", "llm", "tiered"],
            "supported_filters": ["all", "nodeType:type", "node1|node2|..."],
            "template_file": "file:orchestrator/intent_matching_v1.txt",
            "matching_levels": [
                "Level 1: Exact node name matching",
                "Level 2: Basic keyword matching",
                "Level 3: Fuzzy keyword matching (if fuzzywuzzy available)",
                "Level 4: spaCy enhanced matching (if spaCy available)",
            ],
        }

        # Add NLP capabilities if available
        if self._nlp_capabilities:
            info["nlp_capabilities"] = self._nlp_capabilities
        else:
            info["nlp_capabilities"] = {
                "fuzzywuzzy_available": False,
                "spacy_available": False,
                "enhanced_matching": False,
            }

        return info
