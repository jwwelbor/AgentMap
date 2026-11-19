"""Tests for values returned across the optional AWS SDK boundary."""

import unittest

from agentmap.services.messaging.aws_adapter import _response_string


class TestAWSMessagingAdapterResponseTyping(unittest.TestCase):
    def test_response_string_returns_string_value(self):
        self.assertEqual(
            _response_string({"QueueUrl": "https://sqs.example/queue"}, "QueueUrl"),
            "https://sqs.example/queue",
        )

    def test_response_string_rejects_missing_or_non_string_value(self):
        self.assertIsNone(_response_string({}, "QueueUrl"))
        self.assertIsNone(_response_string({"QueueUrl": None}, "QueueUrl"))
        self.assertIsNone(_response_string({"QueueUrl": 123}, "QueueUrl"))
