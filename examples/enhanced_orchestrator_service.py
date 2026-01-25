"""
Enhanced OrchestratorService with NLP library integration.

This example shows how to integrate spaCy, sentence-transformers, and fuzzywuzzy
for improved matching capabilities in the orchestrator service.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple
import json

from agentmap.services.logging_service import LoggingService
from agentmap.services.prompt_manager_service import PromptManagerService
from agentmap.services.protocols import LLMServiceProtocol

# Optional NLP imports (graceful degradation if not available)
try:
    import spacy
    SPACY_AVAILABLE = True
    try:
        nlp = spacy.load("en_core_web_sm")
    except OSError:
        SPACY_AVAILABLE = False
except ImportError:
    SPACY_AVAILABLE = False

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
    try:
        semantic_model = SentenceTransformer('all-MiniLM-L6-v2')
    except Exception:
        SENTENCE_TRANSFORMERS_AVAILABLE = False
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False

try:
    from fuzzywuzzy import fuzz
    FUZZYWUZZY_AVAILABLE = True
except ImportError:
    FUZZYWUZZY_AVAILABLE = False


class EnhancedOrchestratorService:
    """
    Enhanced orchestrator service with NLP library integration.
    
    Provides multiple levels of matching:
    1. Exact keyword matching (fastest)
    2. Fuzzy keyword matching (handles typos)
    3. Semantic similarity matching (understands meaning)
    4. LLM-based matching (most intelligent, slowest)
    """

    def __init__(
        self,
        prompt_manager_service: PromptManagerService,
        logging_service: LoggingService,
        llm_service: Optional[LLMServiceProtocol] = None,
    ):
        """Initialize enhanced orchestrator service."""
        self.prompt_manager = prompt_manager_service
        self.logger = logging_service.get_class_logger(self)
        self.llm_service = llm_service
        
        # Log available NLP capabilities
        capabilities = []
        if SPACY_AVAILABLE:
            capabilities.append("spaCy (advanced keyword extraction)")
        if SENTENCE_TRANSFORMERS_AVAILABLE:
            capabilities.append("sentence-transformers (semantic similarity)")
        if FUZZYWUZZY_AVAILABLE:
            capabilities.append("fuzzywuzzy (fuzzy matching)")
        
        if capabilities:
            self.logger.info(f"[EnhancedOrchestratorService] Available NLP: {', '.join(capabilities)}")
        else:
            self.logger.info("[EnhancedOrchestratorService] No additional NLP libraries available, using basic matching")

    def select_best_node(
        self,
        input_text: str,
        available_nodes: Dict[str, Dict[str, Any]],
        strategy: str = "enhanced_tiered",
        confidence_threshold: float = 0.8,
        semantic_threshold: float = 0.7,
        fuzzy_threshold: float = 0.6,
        **kwargs
    ) -> str:
        """
        Enhanced node selection with multiple NLP strategies.
        
        Args:
            input_text: User input text
            available_nodes: Available nodes with metadata
            strategy: Matching strategy ("enhanced_tiered", "semantic", "fuzzy", "basic")
            confidence_threshold: Threshold for basic algorithm matching
            semantic_threshold: Threshold for semantic similarity
            fuzzy_threshold: Threshold for fuzzy matching
        """
        self.logger.debug(f"Enhanced node selection for: '{input_text}'")
        
        if not available_nodes:
            return kwargs.get("default_target", "No nodes available")

        if len(available_nodes) == 1:
            return next(iter(available_nodes.keys()))

        if strategy == "enhanced_tiered":
            return self._enhanced_tiered_matching(
                input_text, available_nodes, confidence_threshold, 
                semantic_threshold, fuzzy_threshold, kwargs
            )
        elif strategy == "semantic" and SENTENCE_TRANSFORMERS_AVAILABLE:
            return self._semantic_matching(input_text, available_nodes, semantic_threshold)
        elif strategy == "fuzzy" and FUZZYWUZZY_AVAILABLE:
            return self._fuzzy_matching(input_text, available_nodes, fuzzy_threshold)
        else:
            # Fallback to basic matching
            return self._basic_algorithm_match(input_text, available_nodes)[0]

    def _enhanced_tiered_matching(
        self,
        input_text: str,
        available_nodes: Dict[str, Dict[str, Any]],
        confidence_threshold: float,
        semantic_threshold: float,
        fuzzy_threshold: float,
        context: Dict[str, Any]
    ) -> str:
        """Enhanced tiered matching with multiple NLP approaches."""
        
        # Level 1: Basic keyword matching (fastest)
        node, confidence = self._basic_algorithm_match(input_text, available_nodes)
        if confidence >= confidence_threshold:
            self.logger.info(f"Basic matching selected '{node}' with confidence {confidence:.2f}")
            return node

        # Level 2: Enhanced keyword extraction with spaCy
        if SPACY_AVAILABLE:
            node, confidence = self._spacy_enhanced_matching(input_text, available_nodes)
            if confidence >= confidence_threshold:
                self.logger.info(f"spaCy matching selected '{node}' with confidence {confidence:.2f}")
                return node

        # Level 3: Fuzzy string matching (handles typos)
        if FUZZYWUZZY_AVAILABLE:
            node, confidence = self._fuzzy_matching_internal(input_text, available_nodes)
            if confidence >= fuzzy_threshold:
                self.logger.info(f"Fuzzy matching selected '{node}' with confidence {confidence:.2f}")
                return node

        # Level 4: Semantic similarity matching
        if SENTENCE_TRANSFORMERS_AVAILABLE:
            node, confidence = self._semantic_matching_internal(input_text, available_nodes)
            if confidence >= semantic_threshold:
                self.logger.info(f"Semantic matching selected '{node}' with confidence {confidence:.2f}")
                return node

        # Level 5: LLM-based matching (fallback)
        if self.llm_service:
            self.logger.info("All NLP methods below threshold, using LLM matching")
            return self._llm_match(input_text, available_nodes, {}, context)
        
        # Final fallback
        self.logger.warning("All matching methods failed, using first available node")
        return next(iter(available_nodes.keys()))

    def _spacy_enhanced_matching(
        self, input_text: str, available_nodes: Dict[str, Dict[str, Any]]
    ) -> Tuple[str, float]:
        """Enhanced keyword matching using spaCy for better text processing."""
        if not SPACY_AVAILABLE:
            return self._basic_algorithm_match(input_text, available_nodes)

        # Extract enhanced keywords from input
        doc = nlp(input_text)
        input_keywords = set()
        
        # Extract meaningful tokens
        for token in doc:
            if (token.pos_ in ['NOUN', 'VERB', 'ADJ'] and 
                not token.is_stop and 
                len(token.text) > 2):
                input_keywords.add(token.lemma_.lower())
        
        # Extract named entities
        for ent in doc.ents:
            input_keywords.add(ent.text.lower())

        if not input_keywords:
            return self._basic_algorithm_match(input_text, available_nodes)

        best_match = None
        best_score = 0.0

        for node_name, node_info in available_nodes.items():
            if not isinstance(node_info, dict):
                continue

            # Get enhanced keywords for node
            node_keywords = set(self._extract_enhanced_keywords(node_info))
            
            if node_keywords:
                # Calculate overlap
                overlap = len(input_keywords.intersection(node_keywords))
                score = overlap / len(input_keywords.union(node_keywords))
                
                if score > best_score:
                    best_score = score
                    best_match = node_name

        return best_match or next(iter(available_nodes)), best_score

    def _extract_enhanced_keywords(self, node_info: Dict[str, Any]) -> List[str]:
        """Extract enhanced keywords using spaCy if available."""
        if not SPACY_AVAILABLE:
            return self.parse_node_keywords(node_info)

        keywords = set()
        
        # Get basic keywords first
        basic_keywords = self.parse_node_keywords(node_info)
        keywords.update(basic_keywords)
        
        # Process text fields with spaCy
        text_fields = [
            node_info.get("description", ""),
            node_info.get("prompt", ""),
            node_info.get("intent", ""),
        ]
        
        for text in text_fields:
            if text:
                doc = nlp(text)
                for token in doc:
                    if (token.pos_ in ['NOUN', 'VERB', 'ADJ'] and 
                        not token.is_stop and 
                        len(token.text) > 2):
                        keywords.add(token.lemma_.lower())
                
                # Add entities
                for ent in doc.ents:
                    keywords.add(ent.text.lower())

        return list(keywords)

    def _fuzzy_matching_internal(
        self, input_text: str, available_nodes: Dict[str, Dict[str, Any]]
    ) -> Tuple[str, float]:
        """Internal fuzzy matching with confidence score."""
        if not FUZZYWUZZY_AVAILABLE:
            return self._basic_algorithm_match(input_text, available_nodes)

        best_match = None
        best_score = 0.0

        for node_name, node_info in available_nodes.items():
            if not isinstance(node_info, dict):
                continue

            keywords = self.parse_node_keywords(node_info)
            node_score = 0.0
            
            for keyword in keywords:
                # Use partial ratio for substring matching
                score = fuzz.partial_ratio(keyword.lower(), input_text.lower()) / 100.0
                node_score = max(node_score, score)
            
            if node_score > best_score:
                best_score = node_score
                best_match = node_name

        return best_match or next(iter(available_nodes)), best_score

    def _semantic_matching_internal(
        self, input_text: str, available_nodes: Dict[str, Dict[str, Any]]
    ) -> Tuple[str, float]:
        """Internal semantic similarity matching."""
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            return self._basic_algorithm_match(input_text, available_nodes)

        try:
            # Prepare node descriptions
            node_names = []
            descriptions = []
            
            for node_name, node_info in available_nodes.items():
                if isinstance(node_info, dict):
                    node_names.append(node_name)
                    # Combine available text
                    desc_parts = [
                        node_info.get("description", ""),
                        node_info.get("prompt", ""),
                        node_info.get("intent", ""),
                        " ".join(self.parse_node_keywords(node_info))
                    ]
                    descriptions.append(" ".join(filter(None, desc_parts)))

            if not descriptions:
                return next(iter(available_nodes)), 0.0

            # Calculate semantic similarity
            input_embedding = semantic_model.encode([input_text])
            node_embeddings = semantic_model.encode(descriptions)
            
            similarities = semantic_model.similarity(input_embedding, node_embeddings)[0]
            
            # Find best match
            best_idx = similarities.argmax()
            best_score = float(similarities[best_idx])
            best_node = node_names[best_idx]
            
            return best_node, best_score

        except Exception as e:
            self.logger.warning(f"Semantic matching failed: {e}")
            return self._basic_algorithm_match(input_text, available_nodes)

    def _semantic_matching(
        self, input_text: str, available_nodes: Dict[str, Dict[str, Any]], threshold: float
    ) -> str:
        """Public semantic matching method."""
        node, confidence = self._semantic_matching_internal(input_text, available_nodes)
        return node

    def _fuzzy_matching(
        self, input_text: str, available_nodes: Dict[str, Dict[str, Any]], threshold: float
    ) -> str:
        """Public fuzzy matching method."""
        node, confidence = self._fuzzy_matching_internal(input_text, available_nodes)
        return node

    def _basic_algorithm_match(
        self, input_text: str, available_nodes: Dict[str, Dict[str, Any]]
    ) -> Tuple[str, float]:
        """Basic algorithm matching (from original implementation)."""
        input_lower = input_text.lower()

        # Check for exact node name match
        for node_name in available_nodes:
            if node_name.lower() in input_lower:
                return node_name, 1.0

        # Keyword matching
        best_match = None
        best_score = 0.0

        for node_name, node_info in available_nodes.items():
            if not isinstance(node_info, dict):
                continue

            keywords = self.parse_node_keywords(node_info)
            if keywords:
                matches = sum(1 for kw in keywords if kw in input_lower)
                score = matches / len(keywords) if keywords else 0.0
                
                if score > best_score:
                    best_score = score
                    best_match = node_name

        return best_match or next(iter(available_nodes)), best_score

    def parse_node_keywords(self, node_info: Dict[str, Any]) -> List[str]:
        """Parse keywords from node information (from original implementation)."""
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
            text_keywords = combined_text.lower().replace(",", " ").replace(";", " ").split()
            keywords.extend(text_keywords)

        # Remove duplicates and filter out short/common words
        unique_keywords = list(set(keyword.strip() for keyword in keywords if keyword.strip()))
        filtered_keywords = [kw for kw in unique_keywords if len(kw) > 2 and kw not in ["the", "and", "for", "with"]]

        return filtered_keywords

    def _llm_match(self, input_text: str, available_nodes: Dict[str, Dict[str, Any]], 
                   llm_config: Dict[str, Any], context: Dict[str, Any]) -> str:
        """LLM-based matching (from original implementation)."""
        # Implementation would be the same as in the original OrchestratorService
        # This is a placeholder for the existing LLM matching logic
        return next(iter(available_nodes))

    def get_service_info(self) -> Dict[str, Any]:
        """Get information about available NLP capabilities."""
        return {
            "service": "EnhancedOrchestratorService",
            "nlp_capabilities": {
                "spacy_available": SPACY_AVAILABLE,
                "sentence_transformers_available": SENTENCE_TRANSFORMERS_AVAILABLE,
                "fuzzywuzzy_available": FUZZYWUZZY_AVAILABLE,
            },
            "supported_strategies": [
                "enhanced_tiered", "semantic", "fuzzy", "basic", "llm"
            ],
            "matching_levels": [
                "1. Basic keyword matching",
                "2. Enhanced keyword extraction (spaCy)",
                "3. Fuzzy string matching",
                "4. Semantic similarity",
                "5. LLM-based matching"
            ]
        }
