"""Tests for local messaging storage and decoded JSON boundaries."""

import asyncio
import logging
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from agentmap.services.messaging.local_adapter import LocalMessageAdapter


class TestLocalMessageAdapter(unittest.TestCase):
    def test_publish_and_read_message(self):
        with tempfile.TemporaryDirectory() as storage_path:
            adapter = LocalMessageAdapter(
                {"storage_path": storage_path}, logging.getLogger(__name__)
            )

            result = asyncio.run(
                adapter.publish("updates", {"state": "ready"}, {"source": "test"})
            )

            self.assertTrue(result.success)
            self.assertIsNotNone(result.data)
            message = adapter.read_message("updates", result.data["message_id"])
            self.assertEqual(message["payload"], {"state": "ready"})

    def test_read_message_ignores_non_object_json(self):
        with tempfile.TemporaryDirectory() as storage_path:
            adapter = LocalMessageAdapter(
                {"storage_path": storage_path}, logging.getLogger(__name__)
            )
            topic_dir = Path(storage_path) / "updates"
            topic_dir.mkdir()
            (topic_dir / "invalid.json").write_text("[]", encoding="utf-8")

            adapter.logger = Mock()

            self.assertIsNone(adapter.read_message("updates", "invalid"))
            adapter.logger.warning.assert_not_called()

    def test_list_messages_skips_non_object_json_and_keeps_valid_messages(self):
        with tempfile.TemporaryDirectory() as storage_path:
            adapter = LocalMessageAdapter(
                {"storage_path": storage_path}, logging.getLogger(__name__)
            )
            topic_dir = Path(storage_path) / "updates"
            topic_dir.mkdir()
            (topic_dir / "invalid.json").write_text("[]", encoding="utf-8")
            (topic_dir / "valid.json").write_text(
                '{"message_id": "valid-id", "timestamp": "now", "topic": "updates"}',
                encoding="utf-8",
            )

            with self.assertLogs(adapter.logger, level="WARNING") as logs:
                messages = adapter.list_messages("updates")

            self.assertEqual(
                [message["message_id"] for message in messages], ["valid-id"]
            )
            self.assertTrue(
                any(
                    "Ignoring non-object message file" in entry for entry in logs.output
                )
            )
