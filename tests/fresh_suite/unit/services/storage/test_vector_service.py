"""
Unit tests for VectorStorageService.

These tests validate the VectorStorageService implementation including:
- Vector storage and similarity search
- Indexing and query optimization
- Vector operations and transformations
- LangChain vector store integration
- Chroma and FAISS backend support
- Document embedding and retrieval
"""

import unittest
import os
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any, List

from agentmap.services.storage.vector_service import VectorStorageService
from agentmap.services.storage.types import WriteMode, StorageResult
from tests.utils.mock_service_factory import MockServiceFactory


class TestVectorStorageService(unittest.TestCase):
    """Unit tests for VectorStorageService with mocked dependencies."""
    
    def setUp(self):
        """Set up test fixtures with mocked dependencies."""
        # Create temporary directory for testing
        self.temp_dir = tempfile.mkdtemp()
        
        # Create mock services using MockServiceFactory
        self.mock_logging_service = MockServiceFactory.create_mock_logging_service()
        
        # Create context with vector configuration
        self.context = {
            "persist_directory": self.temp_dir,
            "provider": "chroma",
            "embedding_model": "openai",
            "k": 4
        }
        
        # Create VectorStorageService with mocked dependencies
        self.service = VectorStorageService(
            name="vector",
            context=self.context,
            logging_service=self.mock_logging_service
        )
        
        # Get the mock logger for verification
        self.mock_logger = self.service._logger
    
    def tearDown(self):
        """Clean up after each test."""
        # Remove temporary directory
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    # =============================================================================
    # 1. Service Initialization Tests
    # =============================================================================
    
    def test_service_initialization(self):
        """Test that service initializes correctly with all dependencies."""
        # Verify dependencies are stored
        self.assertEqual(self.service.provider_name, "vector")
        self.assertIsNotNone(self.service._logger)
        
        # Verify persist directory was created
        self.assertTrue(os.path.exists(self.temp_dir))
    
    def test_client_initialization(self):
        """Test that client initializes with correct configuration."""
        client = self.service.client
        
        # Verify client configuration has expected structure
        self.assertIsInstance(client, dict)
        
        # Check for expected configuration keys
        expected_keys = [
            "store_key", "persist_directory", "provider", 
            "embedding_model", "k", "_vector_stores", "_embeddings"
        ]
        
        for key in expected_keys:
            self.assertIn(key, client)
        
        # Verify configuration values
        self.assertEqual(client["persist_directory"], self.temp_dir)
        self.assertEqual(client["provider"], "chroma")
        self.assertEqual(client["embedding_model"], "openai")
        self.assertEqual(client["k"], 4)
    
    def test_service_health_check(self):
        """Test that health check works correctly."""
        # Mock LangChain availability
        with patch('agentmap.services.storage.vector_service.langchain'), \
             patch.object(self.service, '_get_embeddings', return_value=Mock()):
            
            # Should be healthy when dependencies are available
            self.assertTrue(self.service.health_check())
    
    def test_health_check_without_langchain(self):
        """Test health check fails without LangChain."""
        # Mock LangChain not available
        with patch('agentmap.services.storage.vector_service.langchain', None):
            # Health check should fail
            self.assertFalse(self.service.health_check())
    
    def test_health_check_with_inaccessible_directory(self):
        """Test health check fails with inaccessible directory."""
        # Create service with non-existent directory that can't be created
        bad_context = {
            "persist_directory": "/root/protected/directory",
            "provider": "chroma"
        }
        
        bad_service = VectorStorageService(
            name="vector",
            context=bad_context,
            logging_service=self.mock_logging_service
        )
        
        # Health check should fail due to directory access
        self.assertFalse(bad_service.health_check())
    
    # =============================================================================
    # 2. Embedding and LangChain Integration Tests
    # =============================================================================
    
    def test_check_langchain_availability(self):
        """Test LangChain availability checking."""
        # Mock successful import
        with patch('agentmap.services.storage.vector_service.langchain', Mock()):
            self.assertTrue(self.service._check_langchain())
        
        # Mock import failure (langchain not available)
        with patch('agentmap.services.storage.vector_service.langchain', None):
            self.assertFalse(self.service._check_langchain())
    
    @patch('agentmap.services.storage.vector_service.OpenAIEmbeddings')
    def test_get_embeddings_openai(self, mock_openai_embeddings):
        """Test OpenAI embeddings creation."""
        mock_embeddings = Mock()
        mock_openai_embeddings.return_value = mock_embeddings
        
        # Get embeddings
        result = self.service._get_embeddings()
        
        # Verify embeddings were created and cached
        self.assertEqual(result, mock_embeddings)
        self.assertEqual(self.service.client["_embeddings"], mock_embeddings)
        mock_openai_embeddings.assert_called_once()
        
        # Test caching - second call should return cached version
        result2 = self.service._get_embeddings()
        self.assertEqual(result2, mock_embeddings)
        # Should not call constructor again
        mock_openai_embeddings.assert_called_once()
    
    def test_get_embeddings_unsupported_model(self):
        """Test unsupported embedding model handling."""
        # Set unsupported embedding model
        self.service.client["embedding_model"] = "unsupported_model"
        
        with patch('agentmap.services.storage.vector_service.OpenAIEmbeddings'):
            result = self.service._get_embeddings()
            self.assertIsNone(result)
    
    @patch('agentmap.services.storage.vector_service.OpenAIEmbeddings')
    def test_get_embeddings_creation_failure(self, mock_openai_embeddings):
        """Test embeddings creation failure."""
        mock_openai_embeddings.side_effect = Exception("API key not found")
        
        result = self.service._get_embeddings()
        self.assertIsNone(result)
    
    # =============================================================================
    # 3. Vector Store Creation Tests
    # =============================================================================
    
    @patch('agentmap.services.storage.vector_service.Chroma')
    @patch.object(VectorStorageService, '_get_embeddings')
    def test_create_chroma_store(self, mock_get_embeddings, mock_chroma):
        """Test Chroma vector store creation."""
        mock_embeddings = Mock()
        mock_get_embeddings.return_value = mock_embeddings
        
        mock_store = Mock()
        mock_chroma.return_value = mock_store
        
        # Create Chroma store
        result = self.service._create_chroma_store(mock_embeddings, "test_collection")
        
        # Verify store was created with correct parameters
        self.assertEqual(result, mock_store)
        mock_chroma.assert_called_once()
        
        # Check call arguments
        call_args = mock_chroma.call_args
        self.assertIn("persist_directory", call_args.kwargs)
        self.assertIn("embedding_function", call_args.kwargs)
        self.assertIn("collection_name", call_args.kwargs)
        self.assertEqual(call_args.kwargs["collection_name"], "test_collection")
    
    def test_create_chroma_store_import_failure(self):
        """Test Chroma store creation with import failure."""
        # Mock Chroma not available
        with patch('agentmap.services.storage.vector_service.Chroma', None):
            result = self.service._create_chroma_store(Mock(), "test_collection")
            self.assertIsNone(result)
    
    @patch('agentmap.services.storage.vector_service.FAISS')
    @patch.object(VectorStorageService, '_get_embeddings')
    def test_create_faiss_store_new(self, mock_get_embeddings, mock_faiss):
        """Test FAISS vector store creation (new index)."""
        mock_embeddings = Mock()
        mock_get_embeddings.return_value = mock_embeddings
        
        mock_store = Mock()
        mock_faiss.from_texts.return_value = mock_store
        
        # Create FAISS store (no existing index)
        result = self.service._create_faiss_store(mock_embeddings, "test_collection")
        
        # Verify store was created
        self.assertEqual(result, mock_store)
        mock_faiss.from_texts.assert_called_once()
        mock_store.save_local.assert_called_once()
    
    @patch('agentmap.services.storage.vector_service.FAISS')
    @patch('os.path.exists')
    def test_create_faiss_store_existing(self, mock_exists, mock_faiss):
        """Test FAISS vector store loading (existing index)."""
        mock_embeddings = Mock()
        mock_exists.return_value = True  # Index file exists
        
        mock_store = Mock()
        mock_faiss.load_local.return_value = mock_store
        
        # Load existing FAISS store
        result = self.service._create_faiss_store(mock_embeddings, "test_collection")
        
        # Verify store was loaded
        self.assertEqual(result, mock_store)
        mock_faiss.load_local.assert_called_once()
        # Should not call from_texts for existing index
        mock_faiss.from_texts.assert_not_called()
    
    def test_create_faiss_store_import_failure(self):
        """Test FAISS store creation with import failure."""
        # Mock FAISS not available
        with patch('agentmap.services.storage.vector_service.FAISS', None):
            result = self.service._create_faiss_store(Mock(), "test_collection")
            self.assertIsNone(result)
    
    @patch.object(VectorStorageService, '_get_embeddings')
    @patch.object(VectorStorageService, '_create_chroma_store')
    def test_get_vector_store_chroma(self, mock_create_chroma, mock_get_embeddings):
        """Test getting Chroma vector store."""
        mock_embeddings = Mock()
        mock_get_embeddings.return_value = mock_embeddings
        
        mock_store = Mock()
        mock_create_chroma.return_value = mock_store
        
        # Get vector store
        result = self.service._get_vector_store("test_collection")
        
        # Verify store was created and cached
        self.assertEqual(result, mock_store)
        self.assertIn("test_collection", self.service.client["_vector_stores"])
        self.assertEqual(self.service.client["_vector_stores"]["test_collection"], mock_store)
        
        # Test caching - second call should return cached version
        result2 = self.service._get_vector_store("test_collection")
        self.assertEqual(result2, mock_store)
        # Should not create store again
        mock_create_chroma.assert_called_once()
    
    def test_get_vector_store_unsupported_provider(self):
        """Test getting vector store with unsupported provider."""
        self.service.client["provider"] = "unsupported_provider"
        
        with patch.object(self.service, '_get_embeddings', return_value=Mock()):
            result = self.service._get_vector_store("test_collection")
            self.assertIsNone(result)
    
    def test_get_vector_store_without_langchain(self):
        """Test getting vector store without LangChain."""
        with patch.object(self.service, '_check_langchain', return_value=False):
            result = self.service._get_vector_store("test_collection")
            self.assertIsNone(result)
    
    def test_get_vector_store_without_embeddings(self):
        """Test getting vector store without embeddings."""
        with patch.object(self.service, '_get_embeddings', return_value=None):
            result = self.service._get_vector_store("test_collection")
            self.assertIsNone(result)
    
    # =============================================================================
    # 4. Read Operations (Similarity Search) Tests
    # =============================================================================
    
    @patch.object(VectorStorageService, '_get_vector_store')
    def test_read_similarity_search(self, mock_get_store):
        """Test similarity search operation."""
        # Mock vector store
        mock_store = Mock()
        mock_doc1 = Mock()
        mock_doc1.page_content = "This is document 1"
        mock_doc1.metadata = {"id": "doc1", "type": "article"}
        
        mock_doc2 = Mock()
        mock_doc2.page_content = "This is document 2"
        mock_doc2.metadata = {"id": "doc2", "type": "blog"}
        
        mock_store.similarity_search.return_value = [mock_doc1, mock_doc2]
        mock_get_store.return_value = mock_store
        
        # Perform search
        query = {"text": "search query"}
        result = self.service.read("test_collection", query=query)
        
        # Verify results
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 2)
        
        # Check first result
        self.assertEqual(result[0]["content"], "This is document 1")
        self.assertEqual(result[0]["metadata"]["id"], "doc1")
        
        # Check second result
        self.assertEqual(result[1]["content"], "This is document 2")
        self.assertEqual(result[1]["metadata"]["id"], "doc2")
        
        # Verify similarity_search was called correctly
        mock_store.similarity_search.assert_called_once_with("search query", k=4)
    
    @patch.object(VectorStorageService, '_get_vector_store')
    def test_read_with_custom_k(self, mock_get_store):
        """Test similarity search with custom k parameter."""
        mock_store = Mock()
        mock_store.similarity_search.return_value = []
        mock_get_store.return_value = mock_store
        
        # Perform search with custom k
        query = {"text": "search query"}
        result = self.service.read("test_collection", query=query, k=10)
        
        # Verify k parameter was used
        mock_store.similarity_search.assert_called_once_with("search query", k=10)
    
    @patch.object(VectorStorageService, '_get_vector_store')
    def test_read_with_metadata_filtering(self, mock_get_store):
        """Test similarity search with metadata filtering."""
        mock_store = Mock()
        mock_doc = Mock()
        mock_doc.page_content = "Content"
        mock_doc.metadata = {"id": "doc1", "type": "article", "author": "John", "tags": ["tech"]}
        
        mock_store.similarity_search.return_value = [mock_doc]
        mock_get_store.return_value = mock_store
        
        # Perform search with metadata filtering
        query = {"text": "search query"}
        result = self.service.read("test_collection", query=query, metadata_keys=["id", "type"])
        
        # Verify only specified metadata keys are included
        self.assertEqual(len(result), 1)
        self.assertIn("metadata", result[0])
        self.assertEqual(set(result[0]["metadata"].keys()), {"id", "type"})
        self.assertNotIn("author", result[0]["metadata"])
        self.assertNotIn("tags", result[0]["metadata"])
    
    def test_read_without_query_text(self):
        """Test read operation without query text."""
        # No text in query
        result = self.service.read("test_collection", query={"other": "param"})
        self.assertIsNone(result)
        
        # No query at all
        result = self.service.read("test_collection")
        self.assertIsNone(result)
    
    def test_read_with_query_field(self):
        """Test read operation with 'query' field instead of 'text'."""
        with patch.object(self.service, '_get_vector_store') as mock_get_store:
            mock_store = Mock()
            mock_store.similarity_search.return_value = []
            mock_get_store.return_value = mock_store
            
            # Use 'query' field instead of 'text'
            query = {"query": "search text"}
            result = self.service.read("test_collection", query=query)
            
            # Should work with 'query' field
            mock_store.similarity_search.assert_called_once_with("search text", k=4)
    
    def test_read_without_vector_store(self):
        """Test read operation when vector store creation fails."""
        with patch.object(self.service, '_get_vector_store', return_value=None):
            result = self.service.read("test_collection", query={"text": "query"})
            self.assertIsNone(result)
    
    # =============================================================================
    # 5. Write Operations Tests
    # =============================================================================
    
    @patch.object(VectorStorageService, '_get_vector_store')
    def test_write_langchain_documents(self, mock_get_store):
        """Test writing LangChain documents."""
        mock_store = Mock()
        mock_store.add_documents.return_value = ["doc1", "doc2"]
        mock_store.persist = Mock()  # Mock persist method
        mock_get_store.return_value = mock_store
        
        # Mock LangChain documents
        mock_doc1 = Mock()
        mock_doc1.page_content = "Content 1"
        mock_doc1.metadata = {"source": "file1"}
        
        mock_doc2 = Mock()
        mock_doc2.page_content = "Content 2"
        mock_doc2.metadata = {"source": "file2"}
        
        documents = [mock_doc1, mock_doc2]
        
        # Write documents
        result = self.service.write("test_collection", documents)
        
        # Verify result
        self.assertIsInstance(result, StorageResult)
        self.assertTrue(result.success)
        self.assertEqual(result.operation, "write")
        self.assertEqual(result.collection, "test_collection")
        self.assertEqual(result.total_affected, 2)
        self.assertEqual(result.ids, ["doc1", "doc2"])
        
        # Verify add_documents was called
        mock_store.add_documents.assert_called_once_with(documents)
    
    @patch.object(VectorStorageService, '_get_vector_store')
    def test_write_single_langchain_document(self, mock_get_store):
        """Test writing single LangChain document."""
        mock_store = Mock()
        mock_store.add_documents.return_value = ["doc1"]
        mock_store.persist = Mock()  # Mock persist method
        mock_get_store.return_value = mock_store
        
        # Single document
        mock_doc = Mock()
        mock_doc.page_content = "Single document content"
        
        # Write document
        result = self.service.write("test_collection", mock_doc)
        
        # Verify result
        self.assertTrue(result.success)
        self.assertEqual(result.total_affected, 1)
        
        # Verify document was wrapped in list
        mock_store.add_documents.assert_called_once_with([mock_doc])
    
    @patch.object(VectorStorageService, '_get_vector_store')
    def test_write_text_data(self, mock_get_store):
        """Test writing plain text data."""
        mock_store = Mock()
        mock_store.add_texts.return_value = ["text1", "text2"]
        mock_store.persist = Mock()  # Mock persist method
        mock_get_store.return_value = mock_store
        
        # Text data
        texts = ["First text document", "Second text document"]
        
        # Write texts
        result = self.service.write("test_collection", texts)
        
        # Verify result
        self.assertTrue(result.success)
        self.assertEqual(result.total_affected, 2)
        self.assertEqual(result.ids, ["text1", "text2"])
        
        # Verify add_texts was called
        mock_store.add_texts.assert_called_once_with(texts)
    
    @patch.object(VectorStorageService, '_get_vector_store')
    def test_write_single_text(self, mock_get_store):
        """Test writing single text string."""
        mock_store = Mock()
        mock_store.add_texts.return_value = ["text1"]
        mock_store.persist = Mock()  # Mock persist method
        mock_get_store.return_value = mock_store
        
        # Single text
        text = "Single text document"
        
        # Write text
        result = self.service.write("test_collection", text)
        
        # Verify text was converted to list
        mock_store.add_texts.assert_called_once_with(["Single text document"])
    
    @patch.object(VectorStorageService, '_get_vector_store')
    def test_write_with_persistence(self, mock_get_store):
        """Test writing with persistence enabled."""
        mock_store = Mock()
        mock_store.add_texts.return_value = ["text1"]
        mock_store.persist = Mock()  # Mock persist method
        mock_get_store.return_value = mock_store
        
        # Write with persistence
        result = self.service.write("test_collection", "text", should_persist=True)
        
        # Verify persistence was called
        self.assertTrue(result.success)
        mock_store.persist.assert_called_once()
    
    @patch.object(VectorStorageService, '_get_vector_store')
    def test_write_without_persistence(self, mock_get_store):
        """Test writing without persistence."""
        mock_store = Mock()
        mock_store.add_texts.return_value = ["text1"]
        mock_store.persist = Mock()
        mock_get_store.return_value = mock_store
        
        # Write without persistence
        result = self.service.write("test_collection", "text", should_persist=False)
        
        # Verify persistence was not called
        self.assertTrue(result.success)
        mock_store.persist.assert_not_called()
    
    @patch.object(VectorStorageService, '_get_vector_store')
    def test_write_store_without_persist_method(self, mock_get_store):
        """Test writing when vector store doesn't have persist method."""
        mock_store = Mock()
        mock_store.add_texts.return_value = ["text1"]
        # No persist method
        del mock_store.persist
        mock_get_store.return_value = mock_store
        
        # Write (should not fail even without persist method)
        result = self.service.write("test_collection", "text", should_persist=True)
        
        # Should succeed without calling persist
        self.assertTrue(result.success)
    
    def test_write_without_vector_store(self):
        """Test write operation when vector store creation fails."""
        with patch.object(self.service, '_get_vector_store', return_value=None):
            result = self.service.write("test_collection", "text")
            
            self.assertFalse(result.success)
            self.assertIn("Failed to initialize vector store", result.error)
    
    @patch.object(VectorStorageService, '_get_vector_store')
    def test_write_operation_failure(self, mock_get_store):
        """Test write operation failure handling."""
        mock_store = Mock()
        mock_store.add_texts.side_effect = Exception("Vector store error")
        mock_store.persist = Mock()  # Mock persist method
        mock_get_store.return_value = mock_store
        
        # Write operation should handle error
        result = self.service.write("test_collection", "text")
        
        self.assertFalse(result.success)
        self.assertIn("Vector storage failed", result.error)
    
    # =============================================================================
    # 6. Delete Operations Tests
    # =============================================================================
    
    def test_delete_entire_collection(self):
        """Test deleting entire collection."""
        collection = "test_collection"
        
        # Add collection to cache
        self.service.client["_vector_stores"][collection] = Mock()
        
        # Create collection directory
        collection_dir = os.path.join(self.temp_dir, collection)
        os.makedirs(collection_dir)
        test_file = os.path.join(collection_dir, "test.txt")
        with open(test_file, 'w') as f:
            f.write("test")
        
        # Delete collection
        result = self.service.delete(collection)
        
        # Verify result
        self.assertTrue(result.success)
        self.assertEqual(result.operation, "delete")
        self.assertEqual(result.collection, collection)
        self.assertTrue(result.is_collection)
        
        # Verify collection removed from cache
        self.assertNotIn(collection, self.service.client["_vector_stores"])
        
        # Verify directory was removed
        self.assertFalse(os.path.exists(collection_dir))
    
    @patch.object(VectorStorageService, '_get_vector_store')
    def test_delete_individual_document(self, mock_get_store):
        """Test deleting individual document."""
        mock_store = Mock()
        mock_store.delete = Mock()
        mock_get_store.return_value = mock_store
        
        # Delete specific document
        result = self.service.delete("test_collection", document_id="doc123")
        
        # Verify result
        self.assertTrue(result.success)
        self.assertEqual(result.document_id, "doc123")
        self.assertEqual(result.total_affected, 1)
        
        # Verify delete was called with document ID
        mock_store.delete.assert_called_once_with(["doc123"])
    
    @patch.object(VectorStorageService, '_get_vector_store')
    def test_delete_document_unsupported(self, mock_get_store):
        """Test deleting document when vector store doesn't support it."""
        mock_store = Mock()
        # No delete method
        del mock_store.delete
        mock_get_store.return_value = mock_store
        
        # Delete should fail gracefully
        result = self.service.delete("test_collection", document_id="doc123")
        
        self.assertFalse(result.success)
        self.assertIn("not supported", result.error)
    
    def test_delete_without_vector_store(self):
        """Test delete when vector store creation fails."""
        with patch.object(self.service, '_get_vector_store', return_value=None):
            result = self.service.delete("test_collection", document_id="doc123")
            
            self.assertFalse(result.success)
            self.assertIn("not found", result.error)
    
    @patch.object(VectorStorageService, '_get_vector_store')
    def test_delete_operation_failure(self, mock_get_store):
        """Test delete operation failure handling."""
        mock_store = Mock()
        mock_store.delete.side_effect = Exception("Delete failed")
        mock_get_store.return_value = mock_store
        
        # Delete should handle error
        result = self.service.delete("test_collection", document_id="doc123")
        
        self.assertFalse(result.success)
        self.assertIn("Vector deletion failed", result.error)
    
    # =============================================================================
    # 7. Utility Operations Tests
    # =============================================================================
    
    def test_exists_operations(self):
        """Test exists functionality."""
        collection = "exists_test"
        
        # Collection doesn't exist initially
        self.assertFalse(self.service.exists(collection))
        
        # Add to cache
        self.service.client["_vector_stores"][collection] = Mock()
        
        # Should exist now
        self.assertTrue(self.service.exists(collection))
        
        # Test with persist directory
        del self.service.client["_vector_stores"][collection]
        collection_dir = os.path.join(self.temp_dir, collection)
        os.makedirs(collection_dir)
        
        # Should exist due to directory
        self.assertTrue(self.service.exists(collection))
    
    def test_count_operations(self):
        """Test count functionality (basic implementation)."""
        collection = "count_test"
        
        with patch.object(self.service, '_get_vector_store') as mock_get_store:
            # Mock vector store with similarity search
            mock_store = Mock()
            mock_results = [Mock() for _ in range(5)]  # 5 documents
            mock_store.similarity_search.return_value = mock_results
            mock_get_store.return_value = mock_store
            
            # Count documents (rough estimate)
            count = self.service.count(collection)
            
            # Should return number of results from similarity search
            self.assertEqual(count, 5)
    
    def test_count_without_vector_store(self):
        """Test count when vector store is not available."""
        with patch.object(self.service, '_get_vector_store', return_value=None):
            count = self.service.count("test_collection")
            self.assertEqual(count, 0)
    
    def test_list_collections(self):
        """Test collection listing."""
        # Initially no collections
        collections = self.service.list_collections()
        self.assertEqual(len(collections), 0)
        
        # Create some collection directories
        collection_names = ["collection1", "collection2", "collection3"]
        for name in collection_names:
            os.makedirs(os.path.join(self.temp_dir, name))
        
        # Should list all collections
        collections = self.service.list_collections()
        self.assertEqual(len(collections), 3)
        
        for name in collection_names:
            self.assertIn(name, collections)
        
        # Should be sorted
        self.assertEqual(collections, sorted(collections))
    
    def test_list_collections_with_error(self):
        """Test collection listing with directory access error."""
        # Make persist directory inaccessible
        if os.name != 'nt':  # Skip on Windows
            os.chmod(self.temp_dir, 0o000)
            
            try:
                collections = self.service.list_collections()
                self.assertEqual(collections, [])
            finally:
                # Restore permissions
                os.chmod(self.temp_dir, 0o755)
    
    # =============================================================================
    # 8. Convenience Methods Tests
    # =============================================================================
    
    @patch.object(VectorStorageService, 'read')
    def test_similarity_search_convenience(self, mock_read):
        """Test similarity_search convenience method."""
        mock_results = [{"content": "result 1"}, {"content": "result 2"}]
        mock_read.return_value = mock_results
        
        # Use convenience method
        results = self.service.similarity_search("test_collection", "query text", k=5)
        
        # Verify delegation to read method
        mock_read.assert_called_once_with(
            collection="test_collection",
            query={"text": "query text"},
            k=5
        )
        
        self.assertEqual(results, mock_results)
    
    @patch.object(VectorStorageService, 'read')
    def test_similarity_search_with_default_k(self, mock_read):
        """Test similarity_search with default k value."""
        mock_read.return_value = []
        
        # Use convenience method without k
        self.service.similarity_search("test_collection", "query")
        
        # Should use default k from client config
        mock_read.assert_called_once_with(
            collection="test_collection",
            query={"text": "query"},
            k=4  # Default from config
        )
    
    @patch.object(VectorStorageService, 'read')
    def test_similarity_search_returns_empty_on_none(self, mock_read):
        """Test similarity_search returns empty list when read returns None."""
        mock_read.return_value = None
        
        results = self.service.similarity_search("test_collection", "query")
        
        self.assertEqual(results, [])
    
    @patch.object(VectorStorageService, 'write')
    def test_add_documents_convenience(self, mock_write):
        """Test add_documents convenience method."""
        mock_result = Mock()
        mock_result.success = True
        mock_result.ids = ["doc1", "doc2"]
        mock_write.return_value = mock_result
        
        # Mock documents
        documents = [Mock(), Mock()]
        
        # Use convenience method
        ids = self.service.add_documents("test_collection", documents)
        
        # Verify delegation to write method
        mock_write.assert_called_once_with(
            collection="test_collection",
            data=documents
        )
        
        self.assertEqual(ids, ["doc1", "doc2"])
    
    @patch.object(VectorStorageService, 'write')
    def test_add_documents_failure(self, mock_write):
        """Test add_documents when write fails."""
        mock_result = Mock()
        mock_result.success = False
        mock_write.return_value = mock_result
        
        # Should return empty list on failure
        ids = self.service.add_documents("test_collection", [Mock()])
        self.assertEqual(ids, [])
    
    @patch.object(VectorStorageService, 'write')
    def test_add_documents_no_ids(self, mock_write):
        """Test add_documents when result has no ids attribute."""
        mock_result = Mock()
        mock_result.success = True
        # No ids attribute
        del mock_result.ids
        mock_write.return_value = mock_result
        
        # Should return empty list
        ids = self.service.add_documents("test_collection", [Mock()])
        self.assertEqual(ids, [])
    
    # =============================================================================
    # 9. Error Handling and Edge Cases Tests
    # =============================================================================
    
    def test_handle_error_method(self):
        """Test error handling helper method."""
        # This will be handled by the base class _handle_error method
        # We test that operations that fail get properly handled
        
        with patch.object(self.service, '_get_vector_store', side_effect=Exception("Test error")):
            result = self.service.read("test_collection", query={"text": "query"})
            
            # Should return None and log error (handled by base class)
            self.assertIsNone(result)
    
    def test_invalid_configuration(self):
        """Test service with invalid configuration."""
        # Test with missing required configuration
        bad_context = {}
        
        bad_service = VectorStorageService(
            name="vector",
            context=bad_context,
            logging_service=self.mock_logging_service
        )
        
        # Should use defaults for missing config
        client = bad_service.client
        self.assertIn("provider", client)
        self.assertIn("k", client)
    
    def test_empty_query_handling(self):
        """Test handling of various empty query scenarios."""
        # Empty string query
        result = self.service.read("test_collection", query={"text": ""})
        self.assertIsNone(result)
        
        # None query
        result = self.service.read("test_collection", query=None)
        self.assertIsNone(result)
        
        # Query without text/query keys
        result = self.service.read("test_collection", query={"other": "value"})
        self.assertIsNone(result)
    
    def test_large_document_batch_operations(self):
        """Test operations with large batches of documents."""
        with patch.object(self.service, '_get_vector_store') as mock_get_store:
            mock_store = Mock()
            mock_store.add_documents.return_value = [f"doc_{i}" for i in range(1000)]
            mock_store.persist = Mock()  # Mock persist method
            mock_get_store.return_value = mock_store
            
            # Create large batch of documents
            documents = [Mock() for _ in range(1000)]
            
            # Write large batch
            result = self.service.write("test_collection", documents)
            
            # Should handle large batch successfully
            self.assertTrue(result.success)
            self.assertEqual(result.total_affected, 1000)
    
    def test_special_characters_in_collection_names(self):
        """Test handling of special characters in collection names."""
        special_collections = [
            "collection-with-dashes",
            "collection_with_underscores",
            "collection.with.dots",
            "collection123"
        ]
        
        for collection in special_collections:
            # Should handle special characters in collection names
            with patch.object(self.service, '_get_vector_store') as mock_get_store:
                mock_store = Mock()
                mock_store.similarity_search.return_value = []
                mock_get_store.return_value = mock_store
                
                # Test read operation
                result = self.service.read(collection, query={"text": "test"})
                
                # Should not fail due to special characters
                self.assertIsInstance(result, list)
    
    def test_unicode_content_handling(self):
        """Test handling of Unicode content in documents."""
        with patch.object(self.service, '_get_vector_store') as mock_get_store:
            mock_store = Mock()
            mock_store.add_texts.return_value = ["unicode_doc"]
            mock_store.persist = Mock()  # Mock persist method
            mock_get_store.return_value = mock_store
            
            # Unicode text content
            unicode_texts = [
                "Café with émojis: 🚀 🎉",
                "Chinese characters: 你好世界",
                "Arabic text: مرحبا بالعالم",
                "Special symbols: ∑∆∂∫"
            ]
            
            # Write Unicode content
            result = self.service.write("unicode_collection", unicode_texts)
            
            # Should handle Unicode without issues
            self.assertTrue(result.success)
            mock_store.add_texts.assert_called_once_with(unicode_texts)


if __name__ == '__main__':
    unittest.main()
