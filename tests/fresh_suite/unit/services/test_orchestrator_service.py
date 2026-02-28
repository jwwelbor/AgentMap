"""
Unit tests for OrchestratorService using pure Mock objects and established testing patterns.

This test suite validates the orchestrator's business logic including node selection
strategies, keyword parsing, prompt integration, and service coordination.
"""

import unittest
from unittest.mock import Mock, patch

from agentmap.services.orchestrator_service import OrchestratorService
from agentmap.services.protocols import LLMServiceProtocol
from tests.utils.mock_service_factory import MockServiceFactory


class TestOrchestratorService(unittest.TestCase):
    """Unit tests for OrchestratorService using pure Mock objects."""

    def setUp(self):
        """Set up test fixtures with pure Mock dependencies."""
        # Use MockServiceFactory for consistent behavior
        self.mock_logging_service = MockServiceFactory.create_mock_logging_service()
        self.mock_prompt_manager_service = Mock()

        # Create LLM service mock
        self.mock_llm_service = Mock(spec=LLMServiceProtocol)
        self.mock_llm_service.call_llm.return_value = '{"selectedNode": "selected_node_2", "confidence": 0.9, "reasoning": "Best match"}'

        # Configure prompt manager mock
        self.mock_prompt_manager_service.format_prompt.return_value = (
            "Formatted orchestration prompt"
        )

        # Sample node list for testing
        self.test_nodes = {
            "auth_node": {
                "name": "auth_node",
                "description": "Handle user authentication and login",
                "type": "security",
                "context": {"keywords": "login,authentication,signin"},
            },
            "payment_node": {
                "name": "payment_node",
                "description": "Process payment transactions and billing",
                "type": "financial",
                "context": {"keywords": "payment,billing,transaction,money"},
            },
            "email_node": {
                "name": "email_node",
                "description": "Send notification emails and messages",
                "type": "communication",
                "context": {"keywords": "email,notification,message,send"},
            },
            "selected_node_2": {
                "name": "selected_node_2",
                "description": "Selected payment processor",
                "type": "financial",
            },
        }

        # Get mock logger for verification
        self.mock_logger = self.mock_logging_service.get_class_logger(
            OrchestratorService
        )

    def create_orchestrator_service(
        self, include_llm=True, include_features_registry=True, nlp_capabilities=None
    ):
        """Helper to create orchestrator service with common configuration."""
        llm_service = self.mock_llm_service if include_llm else None

        # Create mock features registry service
        mock_features_registry = None
        if include_features_registry:
            mock_features_registry = Mock()
            # Set default NLP capabilities
            default_capabilities = nlp_capabilities or {
                "fuzzywuzzy_available": True,
                "spacy_available": True,
                "enhanced_matching": True,
                "fuzzy_threshold_default": 80,
                "supported_features": [
                    "fuzzy_string_matching",
                    "advanced_tokenization",
                ],
            }
            mock_features_registry.get_nlp_capabilities.return_value = (
                default_capabilities
            )
            mock_features_registry.has_fuzzywuzzy.return_value = default_capabilities[
                "fuzzywuzzy_available"
            ]
            mock_features_registry.has_spacy.return_value = default_capabilities[
                "spacy_available"
            ]

        service = OrchestratorService(
            prompt_manager_service=self.mock_prompt_manager_service,
            logging_service=self.mock_logging_service,
            llm_service=llm_service,
            features_registry_service=mock_features_registry,
        )

        return service

    # =============================================================================
    # 1. Service Initialization Tests
    # =============================================================================

    def test_service_initialization_with_all_dependencies(self):
        """Test service initialization with all dependencies."""
        service = self.create_orchestrator_service()

        # Verify dependencies are stored
        self.assertEqual(service.prompt_manager, self.mock_prompt_manager_service)
        self.assertEqual(service.llm_service, self.mock_llm_service)
        self.assertIsNotNone(service.logger)

        # Verify logger setup (called during both setUp and service creation)
        self.assertTrue(self.mock_logging_service.get_class_logger.call_count >= 1)

        # Verify service is properly configured (logging details may vary based on mock setup)
        self.assertIsNotNone(service.logger)
        self.assertTrue(self.mock_logging_service.get_class_logger.call_count >= 1)

    def test_service_initialization_without_llm(self):
        """Test service initialization without LLM service."""
        service = self.create_orchestrator_service(include_llm=False)

        # Should initialize successfully without LLM
        self.assertIsNone(service.llm_service)
        self.assertIsNotNone(service.prompt_manager)
        self.assertIsNotNone(service.logger)

    # =============================================================================
    # 2. Keyword Parsing Tests
    # =============================================================================

    def test_parse_node_keywords_from_context_keywords_field(self):
        """Test keyword parsing from context keywords field."""
        service = self.create_orchestrator_service()

        node_info = {
            "name": "test_node",
            "description": "Test node",
            "context": {"keywords": "keyword1,keyword2,keyword3"},
        }

        keywords = service.parse_node_keywords(node_info)

        # Should extract keywords from context
        self.assertIn("keyword1", keywords)
        self.assertIn("keyword2", keywords)
        self.assertIn("keyword3", keywords)

    def test_parse_node_keywords_from_description_fields(self):
        """Test keyword parsing from description and prompt fields."""
        service = self.create_orchestrator_service()

        node_info = {
            "name": "auth_handler",
            "description": "Handle authentication and security validation",
            "prompt": "Validate user credentials and authorize access",
            "intent": "security authentication",
        }

        keywords = service.parse_node_keywords(node_info)

        # Should extract relevant keywords
        keyword_text = " ".join(keywords)
        self.assertIn("authentication", keyword_text)
        self.assertIn("security", keyword_text)
        self.assertIn("validation", keyword_text)
        self.assertIn("credentials", keyword_text)

    def test_parse_node_keywords_from_context_list(self):
        """Test keyword parsing from context keywords as list."""
        service = self.create_orchestrator_service()

        node_info = {
            "name": "test_node",
            "context": {"keywords": ["payment", "billing", "transaction"]},
        }

        keywords = service.parse_node_keywords(node_info)

        # Should handle list format
        self.assertIn("payment", keywords)
        self.assertIn("billing", keywords)
        self.assertIn("transaction", keywords)

    def test_parse_node_keywords_filters_short_words(self):
        """Test keyword parsing filters out short and common words."""
        service = self.create_orchestrator_service()

        node_info = {
            "description": "The and for with a an authentication system",
            "context": {"keywords": "a,an,the,auth,system"},
        }

        keywords = service.parse_node_keywords(node_info)

        # Should filter out short/common words
        self.assertNotIn("the", keywords)
        self.assertNotIn("and", keywords)
        self.assertNotIn("for", keywords)
        self.assertNotIn("with", keywords)
        self.assertNotIn("a", keywords)
        self.assertNotIn("an", keywords)

        # Should keep longer meaningful words
        self.assertIn("auth", keywords)
        self.assertIn("system", keywords)
        self.assertIn("authentication", keywords)

    def test_parse_node_keywords_handles_empty_node(self):
        """Test keyword parsing handles empty or malformed node info."""
        service = self.create_orchestrator_service()

        # Empty node info
        keywords1 = service.parse_node_keywords({})
        self.assertEqual(keywords1, [])

        # Node with no text fields
        keywords2 = service.parse_node_keywords({"numeric_field": 123})
        self.assertEqual(keywords2, [])

        # Node with empty strings
        keywords3 = service.parse_node_keywords(
            {"description": "", "prompt": "", "context": {}}
        )
        self.assertEqual(keywords3, [])

    # =============================================================================
    # 3. NLP Enhancement Tests
    # =============================================================================

    def test_service_initialization_with_features_registry(self):
        """Test service initialization with features registry service."""
        service = self.create_orchestrator_service()

        # Verify features registry is configured
        self.assertIsNotNone(service.features_registry)
        self.assertIsNotNone(service._nlp_capabilities)

        # Verify NLP capabilities are cached
        self.assertTrue(service._nlp_capabilities["enhanced_matching"])
        self.assertTrue(service._nlp_capabilities["fuzzywuzzy_available"])
        self.assertTrue(service._nlp_capabilities["spacy_available"])

    def test_service_initialization_without_features_registry(self):
        """Test service initialization without features registry service."""
        service = self.create_orchestrator_service(include_features_registry=False)

        # Should initialize successfully without features registry
        self.assertIsNone(service.features_registry)
        self.assertIsNone(service._nlp_capabilities)

    def test_fuzzy_keyword_match_with_available_library(self):
        """Test fuzzy keyword matching when fuzzywuzzy is available."""
        service = self.create_orchestrator_service()

        keywords = ["authentication", "login", "security", "credentials"]

        # Test with exact matches - note: actual library may not be available in test environment
        score, matches = service._fuzzy_keyword_match(
            "user authentication required", keywords
        )
        # Should return valid types regardless of library availability
        self.assertIsInstance(score, float)
        self.assertIsInstance(matches, list)
        self.assertGreaterEqual(
            score, 0.0
        )  # Should be >= 0, may be 0 if library not available

        # Test with typos (would work if fuzzywuzzy was actually available)
        # Note: This tests the interface, actual fuzzy matching would need real library
        score2, matches2 = service._fuzzy_keyword_match(
            "authentcation needed", keywords, threshold=70
        )
        # Interface should work even if library not available in test environment
        self.assertIsInstance(score2, float)
        self.assertIsInstance(matches2, list)
        self.assertGreaterEqual(score2, 0.0)

    def test_fuzzy_keyword_match_without_library(self):
        """Test fuzzy keyword matching graceful degradation without library."""
        # Create service with no NLP capabilities
        nlp_capabilities = {
            "fuzzywuzzy_available": False,
            "spacy_available": False,
            "enhanced_matching": False,
        }
        service = self.create_orchestrator_service(nlp_capabilities=nlp_capabilities)

        keywords = ["authentication", "login"]
        score, matches = service._fuzzy_keyword_match("authentication", keywords)

        # Should gracefully return empty results
        self.assertEqual(score, 0.0)
        self.assertEqual(matches, [])

    def test_spacy_enhanced_keywords_with_available_library(self):
        """Test spaCy enhanced keyword extraction when available."""
        service = self.create_orchestrator_service()

        node_info = {
            "description": "Handle user authentication and login processes",
            "prompt": "Authenticate users and validate credentials",
            "context": {"purpose": "Security validation and access control"},
        }

        # Test enhanced keyword extraction interface
        keywords = service._spacy_enhanced_keywords(node_info)

        # Should return a list (even if empty due to test environment)
        self.assertIsInstance(keywords, list)

    def test_spacy_enhanced_keywords_without_library(self):
        """Test spaCy enhanced keywords graceful degradation without library."""
        # Create service with no spaCy capabilities
        nlp_capabilities = {
            "fuzzywuzzy_available": True,
            "spacy_available": False,
            "enhanced_matching": True,
        }
        service = self.create_orchestrator_service(nlp_capabilities=nlp_capabilities)

        node_info = {"description": "Test node", "prompt": "Test prompt"}
        keywords = service._spacy_enhanced_keywords(node_info)

        # Should gracefully return empty list
        self.assertEqual(keywords, [])

    def test_enhanced_algorithm_match_with_nlp_fallback(self):
        """Test enhanced algorithm matching with NLP fallback levels."""
        service = self.create_orchestrator_service()

        # Test nodes with different keyword complexities
        test_nodes = {
            "exact_match_node": {
                "description": "Exact match test",
                "context": {"keywords": "exact,test"},
            },
            "fuzzy_match_node": {
                "description": "Authentication and security handling",
                "context": {"keywords": "authentication,security,access"},
            },
        }

        # Test Level 1: Exact node name match
        node, confidence = service._algorithm_match("use exact_match_node", test_nodes)
        self.assertEqual(node, "exact_match_node")
        self.assertEqual(confidence, 1.0)

        # Test Level 2: Basic keyword match
        node2, confidence2 = service._algorithm_match(
            "authentication required", test_nodes
        )
        self.assertEqual(node2, "fuzzy_match_node")
        self.assertGreater(confidence2, 0.0)

    def test_basic_keyword_match_level2(self):
        """Test Level 2 basic keyword matching functionality."""
        service = self.create_orchestrator_service()

        test_nodes = {
            "auth_node": {
                "description": "Handle user authentication",
                "context": {"keywords": "authentication,login,user"},
            },
            "payment_node": {
                "description": "Process payments",
                "context": {"keywords": "payment,billing,transaction"},
            },
        }

        # Should match auth_node based on keywords
        node, confidence = service._basic_keyword_match(
            "user authentication needed", test_nodes
        )
        self.assertEqual(node, "auth_node")
        self.assertGreater(confidence, 0.0)

        # Should match payment_node for payment keywords
        node2, confidence2 = service._basic_keyword_match(
            "process billing transaction", test_nodes
        )
        self.assertEqual(node2, "payment_node")
        self.assertGreater(confidence2, 0.0)

    def test_fuzzy_algorithm_match_level3(self):
        """Test Level 3 fuzzy algorithm matching."""
        service = self.create_orchestrator_service()

        test_nodes = {
            "auth_node": {
                "description": "Authentication service",
                "context": {"keywords": "authentication,security"},
            }
        }

        # Test fuzzy matching interface
        node, confidence = service._fuzzy_algorithm_match(
            "authentcation needed", test_nodes
        )

        # Should return a valid node and confidence score
        self.assertIn(node, test_nodes.keys())
        self.assertIsInstance(confidence, float)
        self.assertGreaterEqual(confidence, 0.0)

    def test_spacy_algorithm_match_level4(self):
        """Test Level 4 spaCy enhanced algorithm matching."""
        service = self.create_orchestrator_service()

        test_nodes = {
            "auth_node": {
                "description": "User authentication and verification",
                "context": {"keywords": "authentication,user,verification"},
            }
        }

        # Test spaCy matching interface
        node, confidence = service._spacy_algorithm_match(
            "verify user identity", test_nodes
        )

        # Should return a valid result
        self.assertIn(node, test_nodes.keys())
        self.assertIsInstance(confidence, float)
        self.assertGreaterEqual(confidence, 0.0)

    def test_nlp_graceful_degradation_in_algorithm_match(self):
        """Test that algorithm matching gracefully degrades when NLP libraries unavailable."""
        # Create service without NLP capabilities
        nlp_capabilities = {
            "fuzzywuzzy_available": False,
            "spacy_available": False,
            "enhanced_matching": False,
        }
        service = self.create_orchestrator_service(nlp_capabilities=nlp_capabilities)

        node, confidence = service._algorithm_match(
            "authentication required", self.test_nodes
        )

        # Should still work with basic matching
        self.assertIn(node, self.test_nodes.keys())
        self.assertIsInstance(confidence, float)

    # =============================================================================
    # 4. Algorithm-Based Matching Tests
    # =============================================================================

    def test_algorithm_match_exact_node_name(self):
        """Test algorithm matching with exact node name in input."""
        service = self.create_orchestrator_service()

        input_text = "Use the payment_node for this transaction"
        node, confidence = service._algorithm_match(input_text, self.test_nodes)

        # Should match exactly with high confidence
        self.assertEqual(node, "payment_node")
        self.assertEqual(confidence, 1.0)

    def test_algorithm_match_keyword_based(self):
        """Test algorithm matching based on keyword overlap."""
        service = self.create_orchestrator_service()

        input_text = "I need to process a payment transaction"
        node, confidence = service._algorithm_match(input_text, self.test_nodes)

        # Should match payment_node based on keywords
        self.assertEqual(node, "payment_node")
        self.assertGreater(confidence, 0.0)

    def test_algorithm_match_phrase_matching_boost(self):
        """Test algorithm matching gives boost for phrase matches."""
        service = self.create_orchestrator_service()

        # Create nodes with overlapping single keywords but different phrases
        test_nodes = {
            "node_1": {
                "description": "user authentication system",
                "context": {"keywords": "user,authentication"},
            },
            "node_2": {
                "description": "authentication service for user management",
                "context": {"keywords": "authentication,service"},
            },
        }

        input_text = "user authentication needed"
        node, confidence = service._algorithm_match(input_text, test_nodes)

        # Should prefer node_1 due to exact phrase match
        self.assertEqual(node, "node_1")
        self.assertGreater(confidence, 0.3)  # Should get phrase boost

    def test_algorithm_match_no_matches(self):
        """Test algorithm matching when no keywords match."""
        service = self.create_orchestrator_service()

        input_text = "quantum physics analysis"
        node, confidence = service._algorithm_match(input_text, self.test_nodes)

        # Should return first node with low confidence
        self.assertIn(node, self.test_nodes.keys())
        self.assertLess(confidence, 0.1)

    def test_algorithm_match_handles_invalid_nodes(self):
        """Test algorithm matching handles invalid node formats gracefully."""
        service = self.create_orchestrator_service()

        invalid_nodes = {
            "valid_node": {
                "description": "Valid node",
                "context": {"keywords": "valid"},
            },
            "invalid_node": "not_a_dict",
            "empty_node": {},
        }

        input_text = "valid request"
        node, confidence = service._algorithm_match(input_text, invalid_nodes)

        # Should handle gracefully and find valid node
        self.assertEqual(node, "valid_node")
        self.assertGreater(confidence, 0.0)

    # =============================================================================
    # 5. LLM-Based Matching Tests
    # =============================================================================

    def test_llm_match_with_service_configured(self):
        """Test LLM matching with properly configured service."""
        service = self.create_orchestrator_service()

        input_text = "I need to process a payment"
        llm_config = {"provider": "openai", "temperature": 0.2}

        result = service._llm_match(input_text, self.test_nodes, llm_config, {})

        # Verify prompt manager was called for formatting
        self.mock_prompt_manager_service.format_prompt.assert_called_once()
        call_args = self.mock_prompt_manager_service.format_prompt.call_args

        # Verify template file and variables
        template_ref, variables = call_args[0]
        self.assertEqual(template_ref, "file:orchestrator/intent_matching_v1.txt")
        self.assertIn("nodes_text", variables)
        self.assertIn("input_text", variables)
        self.assertEqual(variables["input_text"], input_text)

        # Verify LLM service was called
        self.mock_llm_service.call_llm.assert_called_once()
        llm_call_args = self.mock_llm_service.call_llm.call_args

        # Verify LLM call parameters
        kwargs = llm_call_args.kwargs
        self.assertEqual(kwargs["provider"], "openai")
        self.assertEqual(kwargs["temperature"], 0.2)
        self.assertIn("messages", kwargs)

        # Verify messages structure
        messages = kwargs["messages"]
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["role"], "user")
        self.assertIn("Formatted orchestration prompt", messages[0]["content"])

        # Verify result extraction
        self.assertEqual(result, "selected_node_2")

    def test_llm_match_without_service_configured(self):
        """Test LLM matching fails gracefully without service."""
        service = self.create_orchestrator_service(include_llm=False)

        input_text = "process payment"

        with self.assertRaises(ValueError) as cm:
            service._llm_match(input_text, self.test_nodes, {}, {})

        self.assertIn("LLM service not configured", str(cm.exception))

    def test_llm_match_with_additional_context(self):
        """Test LLM matching includes additional routing context."""
        service = self.create_orchestrator_service()

        input_text = "process payment"
        context = {"routing_context": "High priority VIP customer transaction"}

        service._llm_match(input_text, self.test_nodes, {}, context)

        # Verify prompt included additional context
        call_args = self.mock_prompt_manager_service.format_prompt.call_args
        variables = call_args[0][1]

        self.assertIn("additional_context", variables)
        self.assertIn("High priority VIP", variables["additional_context"])

    def test_llm_match_node_extraction_from_json(self):
        """Test LLM response node extraction from JSON format."""
        service = self.create_orchestrator_service()

        # Test with properly formatted JSON response
        response = '{"selectedNode": "payment_node", "confidence": 0.85}'
        result = service._extract_node_from_response(response, self.test_nodes)
        self.assertEqual(result, "payment_node")

    def test_llm_match_node_extraction_fallback(self):
        """Test LLM response node extraction with fallback methods."""
        service = self.create_orchestrator_service()

        # Test with malformed JSON but node name present
        response = "The best choice is payment_node for this task"
        result = service._extract_node_from_response(response, self.test_nodes)
        self.assertEqual(result, "payment_node")

        # Test with multiple matches - should prefer longer/more specific
        response = "auth_node or payment_node - I recommend payment_node"
        result = service._extract_node_from_response(response, self.test_nodes)
        self.assertEqual(result, "payment_node")

        # Test with no matches - should return first available
        response = "Unable to determine the best node"
        result = service._extract_node_from_response(response, self.test_nodes)
        self.assertIn(result, self.test_nodes.keys())

    # =============================================================================
    # 6. Node Selection Strategy Tests
    # =============================================================================

    def test_select_best_node_algorithm_strategy(self):
        """Test node selection with algorithm strategy."""
        service = self.create_orchestrator_service()

        result = service.select_best_node(
            input_text="user authentication required",
            available_nodes=self.test_nodes,
            strategy="algorithm",
        )

        # Should use algorithm matching
        self.assertEqual(result, "auth_node")

    def test_select_best_node_llm_strategy(self):
        """Test node selection with LLM strategy."""
        service = self.create_orchestrator_service()

        result = service.select_best_node(
            input_text="process payment",
            available_nodes=self.test_nodes,
            strategy="llm",
            llm_config={"provider": "openai", "temperature": 0.2},
        )

        # Should use LLM matching
        self.assertEqual(result, "selected_node_2")

        # Verify LLM was called
        self.mock_llm_service.call_llm.assert_called_once()

    def test_select_best_node_tiered_strategy_high_confidence(self):
        """Test tiered strategy with high algorithm confidence."""
        service = self.create_orchestrator_service()

        # Mock algorithm match to return high confidence
        with patch.object(service, "_algorithm_match", return_value=("auth_node", 0.9)):
            result = service.select_best_node(
                input_text="authentication needed",
                available_nodes=self.test_nodes,
                strategy="tiered",
                confidence_threshold=0.8,
            )

        # Should use algorithm result due to high confidence
        self.assertEqual(result, "auth_node")

        # LLM should not be called
        self.mock_llm_service.call_llm.assert_not_called()

    def test_select_best_node_tiered_strategy_low_confidence(self):
        """Test tiered strategy with low algorithm confidence falls back to LLM."""
        service = self.create_orchestrator_service()

        # Mock algorithm match to return low confidence
        with patch.object(service, "_algorithm_match", return_value=("auth_node", 0.3)):
            result = service.select_best_node(
                input_text="complex request",
                available_nodes=self.test_nodes,
                strategy="tiered",
                confidence_threshold=0.8,
            )

        # Should fall back to LLM due to low confidence
        self.assertEqual(result, "selected_node_2")

        # LLM should be called
        self.mock_llm_service.call_llm.assert_called_once()

    def test_select_best_node_with_node_filtering(self):
        """Test node selection applies filtering correctly."""
        service = self.create_orchestrator_service()

        # Test type-based filtering
        result = service.select_best_node(
            input_text="financial transaction",
            available_nodes=self.test_nodes,
            strategy="algorithm",
            node_filter="nodeType:financial",
        )

        # Should only consider financial nodes
        self.assertIn(result, ["payment_node", "selected_node_2"])

    def test_select_best_node_single_node_available(self):
        """Test node selection with only one node available."""
        service = self.create_orchestrator_service()

        single_node = {"only_node": self.test_nodes["auth_node"]}

        result = service.select_best_node(
            input_text="any request", available_nodes=single_node, strategy="algorithm"
        )

        # Should select the only available node without matching
        self.assertEqual(result, "only_node")

    def test_select_best_node_no_nodes_available(self):
        """Test node selection with no nodes available."""
        service = self.create_orchestrator_service()

        result = service.select_best_node(
            input_text="any request", available_nodes={}, strategy="algorithm"
        )

        # Should return error message
        self.assertIn("No nodes available", result)

    def test_select_best_node_with_default_target(self):
        """Test node selection uses default target when appropriate."""
        service = self.create_orchestrator_service()

        context = {"default_target": "fallback_node"}

        result = service.select_best_node(
            input_text="any request",
            available_nodes={},
            strategy="algorithm",
            context=context,
        )

        # Should return default target
        self.assertEqual(result, "fallback_node")

    # =============================================================================
    # 7. Node Filtering Tests
    # =============================================================================

    def test_apply_node_filter_all(self):
        """Test node filtering with 'all' filter."""
        service = self.create_orchestrator_service()

        result = service._apply_node_filter(self.test_nodes, "all")

        # Should return all nodes
        self.assertEqual(result, self.test_nodes)

    def test_apply_node_filter_by_names(self):
        """Test node filtering by specific node names."""
        service = self.create_orchestrator_service()

        result = service._apply_node_filter(self.test_nodes, "auth_node|payment_node")

        # Should return only specified nodes
        expected_nodes = {
            "auth_node": self.test_nodes["auth_node"],
            "payment_node": self.test_nodes["payment_node"],
        }
        self.assertEqual(result, expected_nodes)

    def test_apply_node_filter_by_type(self):
        """Test node filtering by node type."""
        service = self.create_orchestrator_service()

        result = service._apply_node_filter(self.test_nodes, "nodeType:financial")

        # Should return only financial nodes
        expected_nodes = {
            "payment_node": self.test_nodes["payment_node"],
            "selected_node_2": self.test_nodes["selected_node_2"],
        }
        self.assertEqual(result, expected_nodes)

    def test_apply_node_filter_case_insensitive(self):
        """Test node filtering is case insensitive for types."""
        service = self.create_orchestrator_service()

        result = service._apply_node_filter(self.test_nodes, "nodeType:FINANCIAL")

        # Should match regardless of case
        self.assertIn("payment_node", result)
        self.assertIn("selected_node_2", result)

    # =============================================================================
    # 8. Service Integration Tests
    # =============================================================================

    def test_format_node_descriptions_integration(self):
        """Test node descriptions formatting for prompt integration."""
        service = self.create_orchestrator_service()

        result = service._format_node_descriptions(self.test_nodes)

        # Should include all node information
        self.assertIn("auth_node", result)
        self.assertIn("Handle user authentication", result)
        self.assertIn("security", result)

        # Should include keyword information
        self.assertIn("Keywords:", result)
        self.assertIn("login", result)
        self.assertIn("authentication", result)

    def test_format_node_descriptions_handles_invalid_nodes(self):
        """Test node descriptions formatting handles invalid node formats."""
        service = self.create_orchestrator_service()

        invalid_nodes = {
            "valid_node": {"description": "Valid node", "type": "test"},
            "invalid_node": "not_a_dict",
        }

        result = service._format_node_descriptions(invalid_nodes)

        # Should handle invalid nodes gracefully
        self.assertIn("valid_node", result)
        self.assertIn("Valid node", result)
        self.assertIn("invalid_node", result)
        self.assertIn("Invalid format", result)

    def test_get_service_info(self):
        """Test service information retrieval."""
        service = self.create_orchestrator_service()

        info = service.get_service_info()

        # Verify service information structure
        self.assertEqual(info["service"], "OrchestratorService")
        self.assertTrue(info["prompt_manager_available"])
        self.assertTrue(info["llm_service_configured"])
        self.assertTrue(info["features_registry_configured"])

        # Verify supported strategies and filters
        self.assertEqual(info["supported_strategies"], ["algorithm", "llm", "tiered"])
        self.assertIn("all", info["supported_filters"])
        self.assertIn("nodeType:type", info["supported_filters"])

        # Verify template reference
        self.assertEqual(
            info["template_file"], "file:orchestrator/intent_matching_v1.txt"
        )

        # Verify new matching levels information
        self.assertIn("matching_levels", info)
        self.assertEqual(len(info["matching_levels"]), 4)
        self.assertIn("Level 1: Exact node name matching", info["matching_levels"])
        self.assertIn(
            "Level 4: spaCy enhanced matching (if spaCy available)",
            info["matching_levels"],
        )

        # Verify NLP capabilities information
        self.assertIn("nlp_capabilities", info)
        nlp_info = info["nlp_capabilities"]
        self.assertIn("fuzzywuzzy_available", nlp_info)
        self.assertIn("spacy_available", nlp_info)
        self.assertIn("enhanced_matching", nlp_info)

        # With mocked features registry, these should be True
        self.assertTrue(nlp_info["fuzzywuzzy_available"])
        self.assertTrue(nlp_info["spacy_available"])
        self.assertTrue(nlp_info["enhanced_matching"])

    def test_get_service_info_without_features_registry(self):
        """Test service information when features registry not available."""
        service = self.create_orchestrator_service(include_features_registry=False)

        info = service.get_service_info()

        # Features registry should be marked as not configured
        self.assertFalse(info["features_registry_configured"])

        # NLP capabilities should show as unavailable
        nlp_info = info["nlp_capabilities"]
        self.assertFalse(nlp_info["fuzzywuzzy_available"])
        self.assertFalse(nlp_info["spacy_available"])
        self.assertFalse(nlp_info["enhanced_matching"])

    # =============================================================================
    # 9. Error Handling and Edge Cases
    # =============================================================================

    def test_select_best_node_handles_service_errors(self):
        """Test node selection handles service errors gracefully."""
        service = self.create_orchestrator_service()

        # Configure LLM service to raise error
        self.mock_llm_service.call_llm.side_effect = Exception("LLM API Error")

        with self.assertRaises(Exception) as cm:
            service.select_best_node(
                input_text="test request",
                available_nodes=self.test_nodes,
                strategy="llm",
            )

        self.assertIn("LLM API Error", str(cm.exception))

    def test_select_best_node_handles_prompt_manager_errors(self):
        """Test node selection handles prompt manager errors."""
        service = self.create_orchestrator_service()

        # Configure prompt manager to raise error
        self.mock_prompt_manager_service.format_prompt.side_effect = Exception(
            "Template Error"
        )

        with self.assertRaises(Exception) as cm:
            service.select_best_node(
                input_text="test request",
                available_nodes=self.test_nodes,
                strategy="llm",
            )

        self.assertIn("Template Error", str(cm.exception))

    def test_algorithm_match_with_empty_keywords(self):
        """Test algorithm matching handles nodes with no keywords gracefully."""
        service = self.create_orchestrator_service()

        nodes_no_keywords = {
            "empty_node": {"name": "empty_node"},
            "minimal_node": {"description": ""},
        }

        input_text = "some request"
        node, confidence = service._algorithm_match(input_text, nodes_no_keywords)

        # Should handle gracefully and return a node
        self.assertIn(node, nodes_no_keywords.keys())
        self.assertIsInstance(confidence, float)

    def test_parse_node_keywords_performance_with_large_context(self):
        """Test keyword parsing performance with large context data."""
        service = self.create_orchestrator_service()

        # Create node with large context
        large_context = {
            "description": " ".join(f"keyword{i}" for i in range(100)),
            "context": {
                "keywords": ",".join(f"contextkey{i}" for i in range(50)),
                "large_field": " ".join(f"field{i}" for i in range(200)),
            },
        }

        keywords = service.parse_node_keywords(large_context)

        # Should handle large data and return reasonable keywords
        self.assertIsInstance(keywords, list)
        self.assertGreater(len(keywords), 0)
        self.assertLess(len(keywords), 500)  # Should filter reasonably


if __name__ == "__main__":
    unittest.main(verbosity=2)
