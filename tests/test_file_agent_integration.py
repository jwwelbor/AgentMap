# tests/test_file_agent_integration.py
import os
import tempfile
import unittest

from agentmap.agents.builtins.storage.file.reader import FileReaderAgent
from agentmap.agents.builtins.storage.file.writer import FileWriterAgent


class TestFileAgentIntegration(unittest.TestCase):
    """Integration tests for FileReaderAgent and FileWriterAgent."""

    def setUp(self):
        """Set up test fixtures."""
        # Create temporary directory for test files
        self.test_dir = tempfile.TemporaryDirectory()
        self.test_file_path = os.path.join(self.test_dir.name, "test_file.txt")
        
        # Create writer and reader agents
        self.writer = FileWriterAgent(
            name="TestWriter",
            prompt="",
            context={"input_fields": ["collection", "data", "mode"], "output_field": "result"}
        )
        
        self.reader = FileReaderAgent(
            name="TestReader",
            prompt="",
            context={"input_fields": ["collection"], "output_field": "result"}
        )

    def tearDown(self):
        """Clean up after tests."""
        self.test_dir.cleanup()

    def test_write_and_read_cycle(self):
        """Test writing then reading from the same file."""
        # Write content to file
        write_result = self.writer.process({
            "collection": self.test_file_path,
            "data": "Test content for integration test."
        })
        
        # Verify write was successful
        self.assertTrue(write_result.success)
        self.assertTrue(os.path.exists(self.test_file_path))
        
        # Read content from the file
        read_result = self.reader.process({
            "collection": self.test_file_path,
            "format": "text"
        })
        
        # Verify content matches what was written
        self.assertEqual(read_result, "Test content for integration test.")

    def test_append_and_read_cycle(self):
        """Test appending to a file and reading the result."""
        # Write initial content
        self.writer.process({
            "collection": self.test_file_path,
            "data": "Initial content."
        })
        
        # Append additional content
        append_result = self.writer.process({
            "collection": self.test_file_path,
            "data": "Appended content.",
            "mode": "append"
        })
        
        # Verify append was successful
        self.assertTrue(append_result.success)
        
        # Read the combined content
        read_result = self.reader.process({
            "collection": self.test_file_path,
            "format": "text"
        })
        
        # Verify content contains both parts
        self.assertIn("Initial content", read_result)
        self.assertIn("Appended content", read_result)


if __name__ == "__main__":
    unittest.main()