"""Tests for YAML configuration validation."""

import unittest
from unittest.mock import Mock

from agentmap.models.validation.validation_models import ValidationResult
from agentmap.services.config.llm_models_config_service import LLMModelsConfigService
from agentmap.services.validation.config_validation_service import (
    ConfigValidationService,
)
from tests.utils.mock_service_factory import MockServiceFactory


class TestConfigValidationService(unittest.TestCase):
    def setUp(self):
        self.service = ConfigValidationService(
            logging_service=MockServiceFactory.create_mock_logging_service(),
            llm_models_config_service=Mock(spec=LLMModelsConfigService),
        )

    def test_schema_validation_preserves_field_name(self):
        result = ValidationResult(file_path="config.yaml", file_type="config")

        self.service._validate_schema({"csv_path": "invalid.txt"}, result)

        self.assertFalse(result.is_valid)
        self.assertEqual(result.errors[0].field_name, "csv_path")

    def test_provider_model_names_are_left_to_provider_apis(self):
        result = ValidationResult(file_path="config.yaml", file_type="config")

        self.service._validate_provider_config(
            "openai",
            {
                "api_key": "sk-valid-test-key",
                "model": "provider-specific-model",
                "temperature": 0.7,
            },
            result,
        )

        self.assertEqual(result.errors, [])
