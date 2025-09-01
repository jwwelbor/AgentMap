"""
OrchestratorService for AgentMap.

Service that provides node selection and orchestration business logic.
Extracted from OrchestratorAgent following Domain Model Principles where
models are data containers and services contain business logic.
"""

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from agentmap.services.features_registry_service import FeaturesRegistryService
from agentmap.services.llm_service import LLMService
from agentmap.services.logging_service import LoggingService
from agentmap.services.prompt_manager_service import PromptManagerService
from agentmap.services.protocols import (
    LLMServiceProtocol,
)


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
        keywords = []

        # Extract from standard fields
        text_fields = [
            node_info.get("description", ""),
            node_info.get("prompt", ""),
            node_info.get("intent", ""),
            node_info.get("name", ""),
        ]

        # Extract from context if available
        context = node_info.get("context", {})
        if isinstance(context, dict):
            # Look for keywords field in context
            if "keywords" in context:
                keywords_field = context["keywords"]
                if isinstance(keywords_field, str):
                    keywords.extend(keywords_field.split(","))
                elif isinstance(keywords_field, list):
                    keywords.extend(keywords_field)

            # Extract from other context text fields
            context_text_fields = [
                context.get("description", ""),
                context.get("intent", ""),
                context.get("purpose", ""),
            ]
            text_fields.extend(context_text_fields)

        # Clean and combine all text
        combined_text = " ".join(field for field in text_fields if field)
        if combined_text:
            # Split on common delimiters and clean
            text_keywords = (
                combined_text.lower().replace(",", " ").replace(";", " ").split()
            )
            keywords.extend(text_keywords)

        # Remove duplicates and filter out short/common words
        unique_keywords = list(
            set(keyword.strip() for keyword in keywords if keyword.strip())
        )
        filtered_keywords = [
            kw
            for kw in unique_keywords
            if len(kw) > 2 and kw not in ["the", "and", "for", "with"]
        ]

        self.logger.debug(f"Parsed keywords: {filtered_keywords}")
        return filtered_keywords

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
        if not self._nlp_capabilities or not self._nlp_capabilities.get(
            "fuzzywuzzy_available", False
        ):
            return 0.0, []

        try:
            from fuzzywuzzy import fuzz

            input_lower = input_text.lower()
            matched_keywords = []
            total_score = 0.0

            for keyword in keywords:
                # Check both partial and token sort ratios for better matching
                partial_ratio = fuzz.partial_ratio(keyword, input_lower)
                token_ratio = fuzz.token_sort_ratio(keyword, input_lower)
                best_ratio = max(partial_ratio, token_ratio)

                if best_ratio >= threshold:
                    matched_keywords.append(keyword)
                    total_score += best_ratio / 100.0  # Normalize to 0-1

            # Calculate average match score
            match_score = total_score / len(keywords) if keywords else 0.0

            self.logger.debug(
                f"Fuzzy matching found {len(matched_keywords)} matches with score {match_score:.2f}"
            )
            return match_score, matched_keywords

        except Exception as e:
            self.logger.debug(f"Fuzzy matching error: {e}")
            return 0.0, []

    def _spacy_enhanced_keywords(self, node_info: Dict[str, Any]) -> List[str]:
        """
        Extract enhanced keywords using spaCy NLP processing if available.

        Args:
            node_info: Node information dictionary

        Returns:
            List of enhanced keywords extracted using spaCy
        """
        if not self._nlp_capabilities or not self._nlp_capabilities.get(
            "spacy_available", False
        ):
            return []

        try:
            import spacy

            # Load the English model
            nlp = spacy.load("en_core_web_sm")

            # Combine text fields for processing
            text_fields = [
                node_info.get("description", ""),
                node_info.get("prompt", ""),
                node_info.get("intent", ""),
            ]

            # Include context text if available
            context = node_info.get("context", {})
            if isinstance(context, dict):
                text_fields.extend(
                    [
                        context.get("description", ""),
                        context.get("intent", ""),
                        context.get("purpose", ""),
                    ]
                )

            combined_text = " ".join(field for field in text_fields if field)

            if not combined_text:
                return []

            # Process with spaCy
            doc = nlp(combined_text)

            enhanced_keywords = []

            # Extract lemmatized tokens (root forms of words)
            for token in doc:
                if (
                    not token.is_stop  # Not a stop word
                    and not token.is_punct  # Not punctuation
                    and not token.is_space  # Not whitespace
                    and len(token.text) > 2  # Reasonable length
                    and token.pos_
                    in ["NOUN", "VERB", "ADJ"]  # Meaningful parts of speech
                ):
                    enhanced_keywords.append(token.lemma_.lower())

            # Extract named entities
            for ent in doc.ents:
                if ent.label_ in ["ORG", "PRODUCT", "EVENT", "WORK_OF_ART"]:
                    enhanced_keywords.append(ent.text.lower())

            # Remove duplicates and filter
            unique_keywords = list(set(enhanced_keywords))

            self.logger.debug(
                f"spaCy extracted {len(unique_keywords)} enhanced keywords"
            )
            return unique_keywords

        except Exception as e:
            self.logger.debug(f"spaCy processing error: {e}")
            return []

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
        input_lower = input_text.lower()
        matching_level = "unknown"

        # Level 1: Exact node name matching
        for node_name in available_nodes:
            if node_name.lower() in input_lower:
                matching_level = "exact_name"
                self.logger.debug(f"Level 1 (exact name) match: {node_name}")
                return node_name, 1.0

        # Level 2: Basic keyword matching (existing logic)
        best_match, best_score = self._basic_keyword_match(input_text, available_nodes)
        if best_score > 0.3:  # Good basic match threshold
            matching_level = "basic_keyword"
            self.logger.debug(
                f"Level 2 (basic keyword) match: {best_match} (score: {best_score:.2f})"
            )
            return best_match, best_score

        # Level 3: Fuzzy keyword matching (if available)
        if self._nlp_capabilities and self._nlp_capabilities.get(
            "fuzzywuzzy_available", False
        ):
            fuzzy_match, fuzzy_score = self._fuzzy_algorithm_match(
                input_text, available_nodes
            )
            if fuzzy_score > 0.2:  # Lower threshold for fuzzy matching
                matching_level = "fuzzy_keyword"
                self.logger.debug(
                    f"Level 3 (fuzzy keyword) match: {fuzzy_match} (score: {fuzzy_score:.2f})"
                )
                return fuzzy_match, fuzzy_score + 0.1  # Slight boost for fuzzy match

        # Level 4: spaCy enhanced keyword extraction (if available)
        if self._nlp_capabilities and self._nlp_capabilities.get(
            "spacy_available", False
        ):
            spacy_match, spacy_score = self._spacy_algorithm_match(
                input_text, available_nodes
            )
            if spacy_score > 0.15:  # Even lower threshold for advanced NLP
                matching_level = "spacy_enhanced"
                self.logger.debug(
                    f"Level 4 (spaCy enhanced) match: {spacy_match} (score: {spacy_score:.2f})"
                )
                return spacy_match, spacy_score + 0.2  # Higher boost for advanced match

        # Fallback: Use basic match result or first available node
        fallback_node = best_match or next(iter(available_nodes))
        matching_level = "fallback"
        self.logger.debug(f"Fallback match: {fallback_node} (score: {best_score:.2f})")
        return fallback_node, best_score

    def _basic_keyword_match(
        self, input_text: str, available_nodes: Dict[str, Dict[str, Any]]
    ) -> Tuple[str, float]:
        """Basic keyword matching using parsed keywords (Level 2)."""
        input_lower = input_text.lower()
        best_match = None
        best_score = 0.0

        for node_name, node_info in available_nodes.items():
            # Skip invalid node formats gracefully
            if not isinstance(node_info, dict):
                continue

            # Get keywords for this node
            keywords = self.parse_node_keywords(node_info)

            if keywords:
                # Calculate match score based on keyword overlap
                matches = sum(1 for kw in keywords if kw in input_lower)
                score = matches / len(keywords) if keywords else 0.0

                # Boost score for exact phrase matches
                combined_text = " ".join(
                    [
                        node_info.get("description", ""),
                        node_info.get("prompt", ""),
                        node_info.get("intent", ""),
                    ]
                ).lower()

                # Check for multi-word phrase matches
                input_words = input_lower.split()
                if len(input_words) > 1:
                    for i in range(len(input_words) - 1):
                        phrase = " ".join(input_words[i : i + 2])
                        if phrase in combined_text:
                            score += 0.3  # Boost for phrase match

                if score > best_score:
                    best_score = score
                    best_match = node_name

        return best_match or next(iter(available_nodes)), best_score

    def _fuzzy_algorithm_match(
        self, input_text: str, available_nodes: Dict[str, Dict[str, Any]]
    ) -> Tuple[str, float]:
        """Fuzzy keyword matching using fuzzywuzzy (Level 3)."""
        best_match = None
        best_score = 0.0

        for node_name, node_info in available_nodes.items():
            if not isinstance(node_info, dict):
                continue

            # Get basic keywords
            keywords = self.parse_node_keywords(node_info)
            if not keywords:
                continue

            # Apply fuzzy matching
            fuzzy_score, matched_keywords = self._fuzzy_keyword_match(
                input_text, keywords, threshold=70  # Lower threshold for Level 3
            )

            if fuzzy_score > best_score:
                best_score = fuzzy_score
                best_match = node_name

        return best_match or next(iter(available_nodes)), best_score

    def _spacy_algorithm_match(
        self, input_text: str, available_nodes: Dict[str, Dict[str, Any]]
    ) -> Tuple[str, float]:
        """spaCy enhanced keyword matching (Level 4)."""
        try:
            import spacy

            nlp = spacy.load("en_core_web_sm")

            # Process input text with spaCy
            input_doc = nlp(input_text.lower())
            input_keywords = [
                token.lemma_.lower()
                for token in input_doc
                if not token.is_stop and not token.is_punct and len(token.text) > 2
            ]

            if not input_keywords:
                return next(iter(available_nodes)), 0.0

            best_match = None
            best_score = 0.0

            for node_name, node_info in available_nodes.items():
                if not isinstance(node_info, dict):
                    continue

                # Get enhanced keywords using spaCy
                enhanced_keywords = self._spacy_enhanced_keywords(node_info)
                if not enhanced_keywords:
                    continue

                # Calculate semantic similarity
                matches = sum(1 for kw in enhanced_keywords if kw in input_keywords)
                if enhanced_keywords:
                    score = matches / len(enhanced_keywords)

                    # Boost for lemma matches (root word forms)
                    lemma_matches = 0
                    for input_kw in input_keywords:
                        for node_kw in enhanced_keywords:
                            if input_kw == node_kw:  # Exact lemma match
                                lemma_matches += 1

                    if enhanced_keywords:
                        lemma_score = lemma_matches / len(enhanced_keywords)
                        score = max(score, lemma_score * 0.8)  # Weight lemma matches

                    if score > best_score:
                        best_score = score
                        best_match = node_name

            return best_match or next(iter(available_nodes)), best_score

        except Exception as e:
            self.logger.debug(f"spaCy algorithm match error: {e}")
            return next(iter(available_nodes)), 0.0

    def _llm_match(
        self,
        input_text: str,
        available_nodes: Dict[str, Dict[str, Any]],
        llm_config: Optional[Dict[str, Any]],
        context: Optional[Dict[str, Any]],
    ) -> str:
        """Use LLM Service to match input to the best node."""
        if not self.llm_service:
            raise ValueError(
                "LLM service not configured but required for LLM matching strategy"
            )

        # Format nodes for prompt using PromptManagerService
        nodes_text = self._format_node_descriptions(available_nodes)

        # Get additional context if provided
        additional_context = ""
        if context and "routing_context" in context and context["routing_context"]:
            additional_context = f"\n\nAdditional context: {context['routing_context']}"

        # Use PromptManagerService to format the prompt
        template_variables = {
            "nodes_text": nodes_text,
            "input_text": input_text,
            "additional_context": additional_context,
        }

        # Use the existing orchestrator template
        formatted_prompt = self.prompt_manager.format_prompt(
            "file:orchestrator/intent_matching_v1.txt", template_variables
        )

        # Add additional context if available
        if additional_context:
            formatted_prompt += additional_context

        # Build messages for LLM call
        messages = [{"role": "user", "content": formatted_prompt}]

        # Get LLM configuration
        llm_config = llm_config or {}
        provider = llm_config.get("provider", "openai")
        temperature = llm_config.get("temperature", 0.2)

        # Call LLM service
        llm_response = self.llm_service.call_llm(
            provider=provider, messages=messages, temperature=temperature
        )

        # Extract selected node from response
        return self._extract_node_from_response(llm_response, available_nodes)

    def _format_node_descriptions(self, nodes: Dict[str, Dict[str, Any]]) -> str:
        """Format node descriptions for template substitution."""
        if not nodes:
            return "No nodes available"

        descriptions = []
        for node_name, node_info in nodes.items():
            # Skip invalid node formats gracefully
            if not isinstance(node_info, dict):
                descriptions.append(f"- Node: {node_name}\n  Status: Invalid format")
                continue

            description = node_info.get("description", "")
            prompt = node_info.get("prompt", "")
            node_type = node_info.get("type", "")

            # Include keywords if available
            keywords = self.parse_node_keywords(node_info)
            keywords_text = (
                f" (Keywords: {', '.join(keywords[:5])})" if keywords else ""
            )

            descriptions.append(
                f"- Node: {node_name}\n"
                f"  Description: {description}\n"
                f"  Prompt: {prompt}\n"
                f"  Type: {node_type}{keywords_text}"
            )

        return "\n".join(descriptions)

    def _extract_node_from_response(
        self, llm_response: str, available_nodes: Dict[str, Dict[str, Any]]
    ) -> str:
        """Extract the selected node from LLM response."""
        # Try to parse JSON response first
        try:
            if isinstance(llm_response, str) and llm_response.strip().startswith("{"):
                parsed = json.loads(llm_response.strip())
                if "selectedNode" in parsed:
                    selected = parsed["selectedNode"]
                    if selected in available_nodes:
                        return selected
        except json.JSONDecodeError:
            pass

        # Fallback: look for exact node name in response
        llm_response_str = str(llm_response).strip()

        # First try exact match
        if llm_response_str in available_nodes:
            return llm_response_str

        # Then try substring matching (but prioritize longer matches)
        matches = []
        for node_name in available_nodes.keys():
            if node_name in llm_response_str:
                matches.append(node_name)

        if matches:
            # Return the longest match (most specific)
            return max(matches, key=len)

        # Last resort: return first available
        self.logger.warning(
            "Couldn't extract node from LLM response. Using first available."
        )
        return next(iter(available_nodes.keys()))

    def _apply_node_filter(
        self, nodes: Dict[str, Dict[str, Any]], node_filter: str
    ) -> Dict[str, Dict[str, Any]]:
        """Apply node filtering based on filter criteria."""
        if not nodes or node_filter == "all":
            return nodes

        if "|" in node_filter:
            # Specific node names filter: "node1|node2|node3"
            node_names = [name.strip() for name in node_filter.split("|")]
            return {name: info for name, info in nodes.items() if name in node_names}
        elif node_filter.startswith("nodeType:"):
            # Node type filter: "nodeType:agent"
            type_filter = node_filter.split(":", 1)[1].strip()
            return {
                name: info
                for name, info in nodes.items()
                if info.get("type", "").lower() == type_filter.lower()
            }

        return nodes

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
