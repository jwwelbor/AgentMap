# tests/test_file_writer_agent.py
import os
import unittest
from unittest.mock import patch, MagicMock, mock_open

from agentmap.agents.builtins.storage.file.writer import FileWriterAgent
from agentmap.agents.builtins.storage.base_storage_agent import DocumentResult, WriteMode

class TestFileWriterAgent(unittest.TestCase):
    """Test cases for FileWriterAgent."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a basic agent for testing
        self.agent = FileWriterAgent(
            name="TestWriter",
            prompt="test.txt",
            context={
                "input_fields": ["collection", "data", "mode", "document_id", "path"],
                "output_field": "result",
                "encoding": "utf-8"
            }
        )
        
        # Mock document with content
        self.mock_document = MagicMock()
        self.mock_document.page_content = "Test content"
        self.mock_document.metadata = {"source": "test.txt", "page": 1}

    def test_initialization(self):
        """Test agent initialization with different parameters."""
        # Test with default parameters
        agent = FileWriterAgent("DefaultTest", "test.txt")
        self.assertEqual(agent.name, "DefaultTest")
        self.assertEqual(agent.prompt, "test.txt")
        self.assertEqual(agent.encoding, "utf-8")
        self.assertIsNone(agent.newline)
        
        # Test with custom parameters
        agent = FileWriterAgent("CustomTest", "test.txt", {
            "encoding": "latin-1",
            "newline": "\r\n"
        })
        self.assertEqual(agent.encoding, "latin-1")
        self.assertEqual(agent.newline, "\r\n")

    def test_initialize_client(self):
        """Test _initialize_client does nothing (as expected)."""
        # This should not raise any errors
        self.agent._initialize_client()
        # Client should remain None
        self.assertIsNone(self.agent._client)

    # @patch('os.path.exists')
    # @patch('os.makedirs')
    # @patch('builtins.open', new_callable=mock_open)
    # def test_write_text_file(self, mock_file, mock_makedirs, mock_exists):
    #     """Test writing to a text file."""
    #     # Setup mocks
    #     mock_exists.return_value = False
        
    #     # Call process
    #     result = self.agent.process({
    #         "collection": "test.txt",
    #         "data": "New content"
    #     })
        
    #     # Verify result
    #     self.assertIsInstance(result, DocumentResult)
    #     self.assertTrue(result.success)
    #     self.assertEqual(result.file_path, "test.txt")
    #     self.assertEqual(result.mode, "write")
    #     self.assertTrue(result.created_new)
        
    #     # Verify file was written to
    #     mock_file.assert_called_once()
    #     mock_file().write.assert_called_once_with("New content")

    # @patch('os.path.exists')
    # @patch('os.makedirs')
    # @patch('builtins.open', new_callable=mock_open)
    # def test_append_to_file(self, mock_file, mock_makedirs, mock_exists):
    #     """Test appending to a file."""
    #     # Setup mocks
    #     mock_exists.return_value = True
        
    #     # Call process
    #     result = self.agent.process({
    #         "collection": "test.txt",
    #         "data": "Appended content",
    #         "mode": "append"
    #     })
        
    #     # Verify result
    #     self.assertIsInstance(result, DocumentResult)
    #     self.assertTrue(result.success)
    #     self.assertEqual(result.file_path, "test.txt")
    #     self.assertEqual(result.mode, "append")
    #     self.assertFalse(result.created_new)
        
    #     # Verify file was appended to
    #     mock_file.assert_called_once_with("test.txt", 'a', encoding='utf-8', newline=None)
    #     mock_file().write.assert_called()

    @patch('os.path.exists')
    @patch('os.makedirs')
    @patch('builtins.open', new_callable=mock_open)
    def test_langchain_document_content(self, mock_file, mock_makedirs, mock_exists):
        """Test writing content from LangChain documents."""
        # Setup mocks
        mock_exists.return_value = False
        
        # Call process with a LangChain document
        result = self.agent.process({
            "collection": "test.txt",
            "data": self.mock_document
        })
        
        # Verify result
        self.assertTrue(result.success)
        
        # Verify correct content was written
        mock_file().write.assert_called_once_with("Test content")

    @patch('os.path.exists')
    @patch('os.makedirs')
    @patch('builtins.open', new_callable=mock_open)
    def test_write_with_document_list(self, mock_file, mock_makedirs, mock_exists):
        """Test writing content from a list of LangChain documents."""
        # Setup mocks
        mock_exists.return_value = False
        
        # Create a second mock document
        mock_document2 = MagicMock()
        mock_document2.page_content = "Second content"
        
        # Call process with a list of LangChain documents
        result = self.agent.process({
            "collection": "test.txt",
            "data": [self.mock_document, mock_document2]
        })
        
        # Verify result
        self.assertTrue(result.success)
        
        # Verify correct content was written
        mock_file().write.assert_called_once_with("Test content\n\nSecond content")

    @patch('os.path.exists')
    @patch('os.makedirs')
    @patch('builtins.open')
    def test_write_permission_error(self, mock_open, mock_makedirs, mock_exists):
        """Test handling of permission errors during write."""
        # Setup mocks
        mock_exists.return_value = False
        mock_open.side_effect = PermissionError("Permission denied")
        
        # Call process
        result = self.agent.process({
            "collection": "test.txt",
            "data": "Test content"
        })
        
        # Verify error result
        self.assertIsInstance(result, DocumentResult)
        self.assertFalse(result.success)
        self.assertEqual(result.file_path, "test.txt")
        self.assertIn("Permission denied", result.error)

    # @patch('os.path.exists')
    # @patch('os.remove')
    # def test_delete_file(self, mock_remove, mock_exists):
    #     """Test deleting a file."""
    #     # Setup mocks
    #     mock_exists.return_value = True
        
    #     # Call process
    #     result = self.agent.process({
    #         "collection": "test.txt",
    #         "mode": "delete"
    #     })
        
    #     # Verify result
    #     self.assertIsInstance(result, DocumentResult)
    #     self.assertTrue(result.success)
    #     self.assertEqual(result.file_path, "test.txt")
    #     self.assertEqual(result.mode, "delete")
    #     self.assertTrue(result.file_deleted)
        
    #     # Verify file removal was called
    #     mock_remove.assert_called_once_with("test.txt")

    # @patch('os.path.exists')
    # def test_delete_nonexistent_file(self, mock_exists):
    #     """Test deleting a non-existent file."""
    #     # Setup mocks
    #     mock_exists.return_value = False
        
    #     # Call process
    #     result = self.agent.process({
    #         "collection": "nonexistent.txt",
    #         "mode": "delete"
    #     })
        
    #     # Verify error result
    #     self.assertIsInstance(result, DocumentResult)
    #     self.assertFalse(result.success)
    #     self.assertEqual(result.file_path, "nonexistent.txt")
    #     self.assertEqual(result.mode, "delete")
    #     self.assertIn("not found", result.error)

    def test_invalid_mode(self):
        """Test handling of invalid write modes."""
        # Call process with invalid mode
        result = self.agent.process({
            "collection": "test.txt",
            "data": "Test content",
            "mode": "invalid_mode"
        })
        
        # Verify error result
        self.assertIsInstance(result, DocumentResult)
        self.assertFalse(result.success)
        self.assertIn("Invalid write mode", result.error)

    def test_missing_data(self):
        """Test handling of missing data."""
        # Call process without data
        result = self.agent.process({
            "collection": "test.txt"
        })
        
        # Verify error result
        self.assertIsInstance(result, DocumentResult)
        self.assertFalse(result.success)
        self.assertIn("No data provided", result.error)


if __name__ == "__main__":
    unittest.main()