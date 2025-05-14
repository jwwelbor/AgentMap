# tests/test_file_reader_agent.py
import os
import unittest
from unittest.mock import patch, MagicMock, mock_open

from agentmap.agents.builtins.storage.file.reader import FileReaderAgent
from agentmap.agents.builtins.storage.base_storage_agent import DocumentResult

class TestFileReaderAgent(unittest.TestCase):
    """Test cases for FileReaderAgent."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a basic agent for testing
        self.agent = FileReaderAgent(
            name="TestReader",
            prompt="test.txt",
            context={
                "input_fields": ["collection", "document_id", "query", "path", "format"],
                "output_field": "result",
                "chunk_size": 500,
                "chunk_overlap": 100,
                "should_split": False
            }
        )
        
        # Mock document with content
        self.mock_document = MagicMock()
        self.mock_document.page_content = "Test content"
        self.mock_document.metadata = {"source": "test.txt", "page": 1}

    def test_initialization(self):
        """Test agent initialization with different parameters."""
        # Test with default parameters
        agent = FileReaderAgent("DefaultTest", "test.txt")
        self.assertEqual(agent.name, "DefaultTest")
        self.assertEqual(agent.prompt, "test.txt")
        self.assertEqual(agent.chunk_size, 1000)
        self.assertEqual(agent.chunk_overlap, 200)
        self.assertFalse(agent.should_split)
        
        # Test with custom parameters
        agent = FileReaderAgent("CustomTest", "test.txt", {
            "chunk_size": 300,
            "chunk_overlap": 50,
            "should_split": True
        })
        self.assertEqual(agent.chunk_size, 300)
        self.assertEqual(agent.chunk_overlap, 50)
        self.assertTrue(agent.should_split)

    def test_initialize_client(self):
        """Test _initialize_client does nothing (as expected)."""
        # This should not raise any errors
        self.agent._initialize_client()
        # Client should remain None
        self.assertIsNone(self.agent._client)

    def test_read_text_file(self):
        """Test reading a text file with injected loader."""
        # Create a proper document mock
        mock_document = MagicMock()
        mock_document.page_content = "Test content"
        mock_document.metadata = {"source": "test.txt", "page": 1}

        class TestLoader:
            def load():
                # This is a function that returns our test document
                document = type('SimpleDocument', (), {
                    'page_content': "Test content",
                    'metadata': {"source": "test.txt", "page": 1}
                })
                return [document]
        
        # Create mock loader
        mock_loader = TestLoader
        
        # Set the test loader directly
        self.agent._test_loader = mock_loader
        
        # Call process with the correct inputs
        result = self.agent.process({
            "collection": "test.txt"
        })
        
        # Verify result
        self.assertIsInstance(result, DocumentResult)
        self.assertTrue(result.success)
        self.assertEqual(result.file_path, "test.txt")
        self.assertIsNotNone(result.data)
        
        # Check content in data structure
        if isinstance(result.data, list):
            self.assertEqual(result.data[0]["content"], "Test content")
        else:
            self.assertEqual(result.data["content"], "Test content")

    @patch('os.path.exists')
    def test_nonexistent_file(self, mock_exists):
        """Test handling of non-existent files."""
        # Setup mock
        mock_exists.return_value = False
        
        # Call process
        result = self.agent.process({
            "collection": "nonexistent.txt"
        })
        
        # Verify error result
        self.assertIsInstance(result, DocumentResult)
        self.assertFalse(result.success)
        self.assertEqual(result.file_path, "nonexistent.txt")
        self.assertIn("not found", result.error)

    # @patch('os.path.exists')
    # @patch('agentmap.agents.builtins.storage.file.reader.TextLoader')
    # def test_file_read_permission_error(self, mock_text_loader, mock_exists):
    #     """Test handling of permission errors."""
    #     # Setup mocks
    #     mock_exists.return_value = True
    #     mock_loader = MagicMock()
    #     mock_loader.load.side_effect = PermissionError("Permission denied")
    #     mock_text_loader.return_value = mock_loader
        
    #     # Call process
    #     result = self.agent.process({
    #         "collection": "test.txt"
    #     })
        
    #     # Verify error result
    #     self.assertIsInstance(result, DocumentResult)
    #     self.assertFalse(result.success)
    #     self.assertEqual(result.file_path, "test.txt")
    #     self.assertIn("Permission denied", result.error)

    # @patch('os.path.exists')
    # @patch('agentmap.agents.builtins.storage.file.reader.TextLoader')
    # @patch('agentmap.agents.builtins.storage.file.reader.RecursiveCharacterTextSplitter')
    # def test_document_splitting(self, mock_splitter, mock_text_loader, mock_exists):
    #     """Test document splitting functionality."""
    #     # Setup agent with splitting enabled
    #     agent = FileReaderAgent("SplitTest", "test.txt", {
    #         "should_split": True,
    #         "input_fields": ["collection"],
    #         "output_field": "result"
    #     })
        
    #     # Setup mocks
    #     mock_exists.return_value = True
    #     mock_loader = MagicMock()
    #     mock_loader.load.return_value = [self.mock_document]
    #     mock_text_loader.return_value = mock_loader
        
    #     mock_splitter_instance = MagicMock()
    #     mock_splitter_instance.split_documents.return_value = [
    #         self.mock_document, self.mock_document
    #     ]  # Return two chunks
    #     mock_splitter.return_value = mock_splitter_instance
        
    #     # Call process
    #     result = agent.process({
    #         "collection": "test.txt"
    #     })
        
    #     # Verify splitting was called
    #     mock_splitter_instance.split_documents.assert_called_once()
        
    #     # Verify result has two documents
    #     self.assertIsInstance(result, DocumentResult)
    #     self.assertTrue(result.success)
    #     self.assertEqual(result.count, 2)

    # @patch('os.path.exists')
    # @patch('agentmap.agents.builtins.storage.file.reader.TextLoader')
    # def test_query_filtering(self, mock_text_loader, mock_exists):
    #     """Test query filtering of documents."""
    #     # Setup mocks
    #     mock_exists.return_value = True
        
    #     doc1 = MagicMock()
    #     doc1.page_content = "Test content with keyword"
    #     doc1.metadata = {"category": "test"}
        
    #     doc2 = MagicMock()
    #     doc2.page_content = "Other content"
    #     doc2.metadata = {"category": "other"}
        
    #     mock_loader = MagicMock()
    #     mock_loader.load.return_value = [doc1, doc2]
    #     mock_text_loader.return_value = mock_loader
        
    #     # Test string query
    #     result = self.agent.process({
    #         "collection": "test.txt",
    #         "query": "keyword"
    #     })
        
    #     # Verify only doc1 is returned
    #     self.assertIsInstance(result, DocumentResult)
    #     self.assertTrue(result.success)
    #     self.assertEqual(result.count, 1)
        
    #     # Test dict query
    #     result = self.agent.process({
    #         "collection": "test.txt",
    #         "query": {"category": "test"}
    #     })
        
    #     # Verify only doc1 is returned
    #     self.assertIsInstance(result, DocumentResult)
    #     self.assertTrue(result.success)
    #     self.assertEqual(result.count, 1)

    # @patch('os.path.exists')
    # @patch('agentmap.agents.builtins.storage.file.reader.TextLoader')
    # def test_output_formats(self, mock_text_loader, mock_exists):
    #     """Test different output formats."""
    #     # Setup mocks
    #     mock_exists.return_value = True
    #     mock_loader = MagicMock()
    #     mock_loader.load.return_value = [self.mock_document]
    #     mock_text_loader.return_value = mock_loader
        
    #     # Test default format
    #     result = self.agent.process({
    #         "collection": "test.txt"
    #     })
    #     self.assertIsInstance(result, DocumentResult)
        
    #     # Test text format
    #     result = self.agent.process({
    #         "collection": "test.txt",
    #         "format": "text"
    #     })
    #     self.assertEqual(result, "Test content")
        
    #     # Test raw format
    #     result = self.agent.process({
    #         "collection": "test.txt",
    #         "format": "raw"
    #     })
    #     self.assertEqual(result[0], self.mock_document)

    # @patch('os.path.exists')
    # @patch('agentmap.agents.builtins.storage.file.reader.TextLoader')
    # def test_document_path_extraction(self, mock_text_loader, mock_exists):
    #     """Test extracting specific paths from documents."""
    #     # Setup mocks
    #     mock_exists.return_value = True
    #     mock_loader = MagicMock()
    #     mock_loader.load.return_value = [self.mock_document]
    #     mock_text_loader.return_value = mock_loader
        
    #     # Test metadata path extraction
    #     result = self.agent.process({
    #         "collection": "test.txt",
    #         "path": "metadata.source",
    #         "format": "raw"
    #     })
        
    #     # Verify we get the source
    #     self.assertEqual(result[0], "test.txt")


if __name__ == "__main__":
    unittest.main()