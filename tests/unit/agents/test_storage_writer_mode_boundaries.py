"""Regression tests for malformed storage writer mode values."""

import unittest

from agentmap.agents.builtins.storage.document.writer import DocumentWriterAgent
from agentmap.agents.builtins.storage.json.writer import JSONDocumentWriterAgent
from agentmap.models.storage import DocumentResult
from tests.utils.mock_service_factory import MockServiceFactory


class TestStorageWriterModeBoundaries(unittest.TestCase):
    def setUp(self):
        self.logging_service = MockServiceFactory.create_mock_logging_service()
        self.execution_tracking_service = (
            MockServiceFactory.create_mock_execution_tracking_service()
        )
        self.state_adapter_service = (
            MockServiceFactory.create_mock_state_adapter_service()
        )
        self.logger = self.logging_service.get_class_logger(
            TestStorageWriterModeBoundaries
        )

    def _create_writer(self, writer_type):
        return writer_type(
            name="test_writer",
            prompt="output.json",
            context={},
            logger=self.logger,
            execution_tracking_service=self.execution_tracking_service,
            state_adapter_service=self.state_adapter_service,
        )

    def test_json_writer_returns_error_for_non_string_mode(self):
        agent = self._create_writer(JSONDocumentWriterAgent)

        result = agent.process(
            {
                "collection": "output.json",
                "data": {"key": "value"},
                "mode": None,
            }
        )

        self.assertIsInstance(result, DocumentResult)
        self.assertFalse(result.success)
        self.assertEqual(result.error, "Write mode must be a string")

    def test_document_writer_rejects_non_string_mode_before_execution(self):
        agent = self._create_writer(DocumentWriterAgent)
        inputs = {"collection": "output.json", "data": {}, "mode": None}

        with self.assertRaisesRegex(ValueError, "Write mode must be a string"):
            agent._validate_inputs(inputs)

        process_result = agent.process(inputs)
        self.assertIsInstance(process_result, DocumentResult)
        self.assertFalse(process_result.success)
        self.assertIn("Write mode must be a string", process_result.error)

        result = agent._execute_operation("output.json", inputs)

        self.assertIsInstance(result, DocumentResult)
        self.assertFalse(result.success)
        self.assertEqual(result.error, "Write mode must be a string")
