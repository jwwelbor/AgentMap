"""
NLP capability checking for AgentMap.

This module handles detection and status checking of NLP libraries
like fuzzywuzzy and spaCy.
Extracted from FeaturesRegistryService for better separation of concerns.
"""

from typing import Any, Dict

from agentmap.services.config.availability_cache_service import AvailabilityCacheService


class NLPCapabilityChecker:
    """
    Checks availability and capabilities of NLP libraries.

    Handles detection and testing of:
    - fuzzywuzzy for fuzzy string matching
    - spaCy with English language model
    """

    def __init__(
        self,
        availability_cache_service: AvailabilityCacheService,
        logger,
    ):
        """
        Initialize NLP capability checker.

        Args:
            availability_cache_service: Cache service for availability data
            logger: Logger instance
        """
        self.availability_cache_service = availability_cache_service
        self.logger = logger

    def has_fuzzywuzzy(self) -> bool:
        """
        Check if fuzzywuzzy is available for fuzzy string matching.

        Returns:
            True if fuzzywuzzy is available, False otherwise
        """
        # Check cache first
        cached = self.availability_cache_service.get_availability(
            "capability.nlp", "fuzzywuzzy"
        )
        if cached is not None:
            self.logger.trace(
                "[NLPCapabilityChecker] Cache hit for capability.nlp.fuzzywuzzy"
            )
            return cached.get("available", False)

        # Perform actual check
        try:
            import fuzzywuzzy
            from fuzzywuzzy import fuzz

            # Test basic functionality
            test_score = fuzz.ratio("test", "test")
            available = test_score == 100

            # Cache result
            self.availability_cache_service.set_availability(
                "capability.nlp",
                "fuzzywuzzy",
                {"available": available, "type": "nlp_library"},
            )

            if available:
                self.logger.debug(
                    "[NLPCapabilityChecker] fuzzywuzzy is available (cached)"
                )
            else:
                self.logger.debug(
                    "[NLPCapabilityChecker] fuzzywuzzy failed basic test (cached)"
                )
            return available

        except ImportError:
            # Cache negative result
            self.availability_cache_service.set_availability(
                "capability.nlp",
                "fuzzywuzzy",
                {"available": False, "type": "nlp_library", "reason": "ImportError"},
            )
            self.logger.debug(
                "[NLPCapabilityChecker] fuzzywuzzy not available (cached)"
            )
            return False
        except Exception as e:
            # Cache negative result
            self.availability_cache_service.set_availability(
                "capability.nlp",
                "fuzzywuzzy",
                {"available": False, "type": "nlp_library", "reason": str(e)},
            )
            self.logger.debug(f"[NLPCapabilityChecker] fuzzywuzzy error: {e} (cached)")
            return False

    def has_spacy(self) -> bool:
        """
        Check if spaCy is available with English model.

        Returns:
            True if spaCy and en_core_web_sm model are available, False otherwise
        """
        # Check cache first
        cached = self.availability_cache_service.get_availability(
            "capability.nlp", "spacy"
        )
        if cached is not None:
            self.logger.trace(
                "[NLPCapabilityChecker] Cache hit for capability.nlp.spacy"
            )
            return cached.get("available", False)

        # Perform actual check
        try:
            import spacy

            # Check if English model is available
            nlp = spacy.load("en_core_web_sm")

            # Test basic functionality
            doc = nlp("test sentence")
            available = len(doc) > 0

            # Cache result
            self.availability_cache_service.set_availability(
                "capability.nlp",
                "spacy",
                {
                    "available": available,
                    "type": "nlp_library",
                    "model": "en_core_web_sm",
                },
            )

            if available:
                self.logger.debug(
                    "[NLPCapabilityChecker] spaCy with en_core_web_sm is available (cached)"
                )
            else:
                self.logger.debug(
                    "[NLPCapabilityChecker] spaCy failed basic test (cached)"
                )
            return available

        except ImportError:
            # Cache negative result
            self.availability_cache_service.set_availability(
                "capability.nlp",
                "spacy",
                {"available": False, "type": "nlp_library", "reason": "ImportError"},
            )
            self.logger.debug(
                "[NLPCapabilityChecker] spaCy or en_core_web_sm not available (cached)"
            )
            return False
        except OSError:
            # Cache negative result
            self.availability_cache_service.set_availability(
                "capability.nlp",
                "spacy",
                {
                    "available": False,
                    "type": "nlp_library",
                    "reason": "OSError - model not installed",
                },
            )
            self.logger.debug(
                "[NLPCapabilityChecker] spaCy en_core_web_sm model not installed (cached)"
            )
            return False
        except Exception as e:
            # Cache negative result
            self.availability_cache_service.set_availability(
                "capability.nlp",
                "spacy",
                {"available": False, "type": "nlp_library", "reason": str(e)},
            )
            self.logger.debug(f"[NLPCapabilityChecker] spaCy error: {e} (cached)")
            return False

    def get_nlp_capabilities(self) -> Dict[str, Any]:
        """
        Get available NLP capabilities summary.

        Returns:
            Dictionary with NLP library availability and capabilities
        """
        capabilities = {
            "fuzzywuzzy_available": self.has_fuzzywuzzy(),
            "spacy_available": self.has_spacy(),
            "enhanced_matching": False,
            "fuzzy_threshold_default": 80,
            "supported_features": [],
        }

        # Add supported features based on available libraries
        if capabilities["fuzzywuzzy_available"]:
            capabilities["supported_features"].append("fuzzy_string_matching")
            capabilities["supported_features"].append("typo_tolerance")

        if capabilities["spacy_available"]:
            capabilities["supported_features"].append("advanced_tokenization")
            capabilities["supported_features"].append("keyword_extraction")
            capabilities["supported_features"].append("lemmatization")

        # Enhanced matching available if either library is present
        capabilities["enhanced_matching"] = (
            capabilities["fuzzywuzzy_available"] or capabilities["spacy_available"]
        )

        self.logger.debug(f"[NLPCapabilityChecker] NLP capabilities: {capabilities}")
        return capabilities

    def invalidate_cache(self) -> None:
        """
        Invalidate all cached capability checks (NLP libraries, etc.).
        """
        self.availability_cache_service.invalidate_cache("capability")
        self.logger.debug("[NLPCapabilityChecker] Invalidated all capability cache")
