"""
Tests for Firebase document storage agents.

These tests verify that the Firebase document agents work correctly
for both Firestore and Realtime Database operations.
"""
import os
import unittest
from unittest.mock import MagicMock, patch

import pytest

# Skip tests if firebase-admin is not installed
try:
    import firebase_admin
    from firebase_admin import credentials, firestore, db
    FIREBASE_AVAILABLE = True
except ImportError:
    FIREBASE_AVAILABLE = False

# Import Firebase agents
if FIREBASE_AVAILABLE:
    from agentmap.agents.builtins.storage.firebase.base_agent import FirebaseDocumentAgent
    from agentmap.agents.builtins.storage.firebase.reader import FirebaseDocumentReaderAgent
    from agentmap.agents.builtins.storage.firebase.writer import FirebaseDocumentWriterAgent
    from agentmap.agents.builtins.storage.document.base_agent import WriteMode


# Mark the entire module to be skipped if Firebase is not available
pytestmark = pytest.mark.skipif(not FIREBASE_AVAILABLE, reason="firebase-admin not installed")


@pytest.fixture
def mock_firebase_config():
    """Mock configuration for Firebase tests."""
    return {
        "firebase": {
            "default_project": "test-project",
            "auth": {
                "service_account_key": "test_service_account.json"
            },
            "firestore": {
                "collections": {
                    "users": {
                        "collection_path": "users"
                    },
                    "products": {
                        "collection_path": "products"
                    }
                }
            },
            "realtime_db": {
                "collections": {
                    "active_users": {
                        "db_url": "https://test-project.firebaseio.com",
                        "path": "users/active"
                    }
                }
            }
        }
    }


@pytest.fixture
def mock_storage_config(mock_firebase_config):
    """Mock the storage config loading."""
    with patch("agentmap.agents.builtins.storage.firebase_document_agent.load_storage_config") as mock_load:
        mock_load.return_value = mock_firebase_config
        yield mock_load


@pytest.fixture
def mock_firebase_app():
    """Mock Firebase app initialization."""
    with patch("firebase_admin.initialize_app") as mock_init, \
         patch("firebase_admin.get_app", side_effect=ValueError), \
         patch("firebase_admin.delete_app") as mock_delete:
        
        mock_app = MagicMock()
        mock_app.name = "test-app"
        mock_init.return_value = mock_app
        
        yield mock_app


@pytest.fixture
def mock_firestore_client():
    """Mock Firestore client."""
    with patch("firebase_admin.firestore.client") as mock_client:
        # Create mock collection and document references
        mock_doc = MagicMock()
        mock_doc.id = "test-doc"
        mock_doc.get.return_value.exists = True
        mock_doc.get.return_value.to_dict.return_value = {"name": "Test User", "age": 30}
        
        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc
        mock_collection.stream.return_value = [mock_doc]
        
        # Set up the client to return the mock collection
        mock_client_instance = MagicMock()
        mock_client_instance.collection.return_value = mock_collection
        mock_client.return_value = mock_client_instance
        
        yield mock_client_instance


@pytest.fixture
def mock_realtime_db():
    """Mock Realtime Database."""
    with patch("firebase_admin.db.reference") as mock_ref:
        # Create mock reference
        mock_db_ref = MagicMock()
        mock_db_ref.get.return_value = {
            "user1": {"name": "Alice", "status": "online"},
            "user2": {"name": "Bob", "status": "offline"}
        }
        mock_db_ref.child.return_value = mock_db_ref
        
        mock_ref.return_value = mock_db_ref
        
        yield mock_db_ref


class TestFirebaseDocumentAgent:
    """Tests for the base Firebase document agent."""
    
    def test_initialization(self, mock_storage_config, mock_firebase_app):
        """Test that the agent initializes correctly."""
        agent = FirebaseDocumentAgent(name="TestAgent", prompt="Test prompt")
        
        # Access client to trigger initialization
        client = agent.client
        
        # Check that the app was initialized
        assert agent._app is not None
        assert agent._app.name == "test-app"
    
    def test_resolve_collection_path(self, mock_storage_config, mock_firebase_app):
        """Test that collection paths are resolved correctly."""
        agent = FirebaseDocumentAgent(name="TestAgent", prompt="Test prompt")
        
        # Initialize client
        client = agent.client
        
        # Test resolving a known Firestore collection
        path, config, db_type = agent._resolve_collection_path("users")
        assert path == "users"
        assert db_type == "firestore"
        
        # Test resolving a known Realtime DB collection
        path, config, db_type = agent._resolve_collection_path("active_users")
        assert path == "users/active"
        assert db_type == "realtime"
        
        # Test resolving an unknown collection (default to Firestore)
        path, config, db_type = agent._resolve_collection_path("unknown")
        assert path == "unknown"
        assert db_type == "firestore"
    
    def test_get_db_reference(self, mock_storage_config, mock_firebase_app, mock_firestore_client, mock_realtime_db):
        """Test getting database references."""
        agent = FirebaseDocumentAgent(name="TestAgent", prompt="Test prompt")
        
        # Initialize client
        client = agent.client
        
        # Test getting Firestore reference
        ref, path, config = agent._get_db_reference("users")
        assert path == "users"
        
        # Test getting Realtime DB reference
        ref, path, config = agent._get_db_reference("active_users")
        assert path == "users/active"


class TestFirebaseDocumentReaderAgent:
    """Tests for the Firebase document reader agent."""
    
    def test_read_document_from_firestore(self, mock_storage_config, mock_firebase_app, mock_firestore_client):
        """Test reading a document from Firestore."""
        agent = FirebaseDocumentReaderAgent(name="TestReader", prompt="Test prompt")
        
        # Test reading a document by ID
        result = agent._read_document("users", document_id="test-doc")
        
        assert result["success"] is True
        assert result["document_id"] == "test-doc"
        assert result["data"]["name"] == "Test User"
        assert result["data"]["age"] == 30
    
    def test_read_collection_from_firestore(self, mock_storage_config, mock_firebase_app, mock_firestore_client):
        """Test reading a collection from Firestore."""
        agent = FirebaseDocumentReaderAgent(name="TestReader", prompt="Test prompt")
        
        # Test reading all documents in a collection
        result = agent._read_document("users")
        
        assert result["success"] is True
        assert result["is_collection"] is True
        assert isinstance(result["data"], list)
        assert len(result["data"]) > 0
    
    def test_read_with_query(self, mock_storage_config, mock_firebase_app, mock_firestore_client):
        """Test reading with a query filter."""
        agent = FirebaseDocumentReaderAgent(name="TestReader", prompt="Test prompt")
        
        # Mock the query results
        mock_query = MagicMock()
        mock_doc = MagicMock()
        mock_doc.id = "filtered-doc"
        mock_doc.to_dict.return_value = {"name": "Filtered User", "age": 25}
        mock_query.stream.return_value = [mock_doc]
        
        # Make where method return the mock query
        mock_firestore_client.collection.return_value.where.return_value = mock_query
        
        # Test reading with a query
        result = agent._read_document("users", query={"age": 25})
        
        assert result["success"] is True
        assert result["is_collection"] is True
        assert len(result["data"]) > 0
        assert result["data"][0]["name"] == "Filtered User"
    
    def test_read_from_realtime_db(self, mock_storage_config, mock_firebase_app, mock_realtime_db):
        """Test reading from Realtime Database."""
        agent = FirebaseDocumentReaderAgent(name="TestReader", prompt="Test prompt")
        
        # Test reading all data
        result = agent._read_document("active_users")
        
        assert result["success"] is True
        assert result["data"][0]["name"] == "Alice"
        assert result["data"][1]["name"] == "Bob"
    
    def test_process_method(self, mock_storage_config, mock_firebase_app, mock_firestore_client):
        """Test the process method."""
        agent = FirebaseDocumentReaderAgent(
            name="TestReader", 
            prompt="", 
            context={"input_fields": ["collection", "document_id"], "output_field": "result"}
        )
        
        # Test processing a document request
        result = agent.process({
            "collection": "users",
            "document_id": "test-doc"
        })
        
        assert result["success"] is True
        assert result["document_id"] == "test-doc"
        assert result["data"]["name"] == "Test User"


class TestFirebaseDocumentWriterAgent:
    """Tests for the Firebase document writer agent."""
    
    def test_write_document_to_firestore(self, mock_storage_config, mock_firebase_app, mock_firestore_client):
        """Test writing a document to Firestore."""
        agent = FirebaseDocumentWriterAgent(name="TestWriter", prompt="Test prompt")
        
        # Test writing a new document
        result = agent._write_document(
            "users", 
            {"name": "New User", "email": "new@example.com"},
            document_id="new-user"
        )
        
        assert result.success is True
        assert result.document_id == "new-user"
        assert result.mode == WriteMode.WRITE.value
    
    def test_update_document_in_firestore(self, mock_storage_config, mock_firebase_app, mock_firestore_client):
        """Test updating a document in Firestore."""
        agent = FirebaseDocumentWriterAgent(name="TestWriter", prompt="Test prompt")
        
        # Test updating an existing document
        result = agent._write_document(
            "users", 
            {"email": "updated@example.com"},
            document_id="test-doc",
            mode=WriteMode.UPDATE
        )
        
        assert result.success is True
        assert result.document_id == "test-doc"
        assert result.mode == WriteMode.UPDATE.value
    
    def test_merge_document_in_firestore(self, mock_storage_config, mock_firebase_app, mock_firestore_client):
        """Test merging a document in Firestore."""
        agent = FirebaseDocumentWriterAgent(name="TestWriter", prompt="Test prompt")
        
        # Test merging with an existing document
        result = agent._write_document(
            "users", 
            {"email": "merged@example.com"},
            document_id="test-doc",
            mode=WriteMode.MERGE
        )
        
        assert result.success is True
        assert result.document_id == "test-doc"
        assert result.mode == WriteMode.MERGE.value
    
    def test_delete_document_from_firestore(self, mock_storage_config, mock_firebase_app, mock_firestore_client):
        """Test deleting a document from Firestore."""
        agent = FirebaseDocumentWriterAgent(name="TestWriter", prompt="Test prompt")
        
        # Test deleting a document
        result = agent._write_document(
            "users", 
            None,
            document_id="test-doc",
            mode=WriteMode.DELETE
        )
        
        assert result.success is True
        assert result.document_id == "test-doc"
        assert result.mode == WriteMode.DELETE.value
    
    def test_write_to_realtime_db(self, mock_storage_config, mock_firebase_app, mock_realtime_db):
        """Test writing to Realtime Database."""
        agent = FirebaseDocumentWriterAgent(name="TestWriter", prompt="Test prompt")
        
        # Test writing data
        result = agent._write_document(
            "active_users", 
            {"name": "New User", "status": "online"},
            document_id="user3"
        )
        
        assert result.success is True
        assert result.document_id == "user3"
    
    def test_process_method(self, mock_storage_config, mock_firebase_app, mock_firestore_client):
        """Test the process method."""
        agent = FirebaseDocumentWriterAgent(
            name="TestWriter", 
            prompt="", 
            context={
                "input_fields": ["collection", "data", "document_id", "mode"], 
                "output_field": "result"
            }
        )
        
        # Test processing a write request
        result = agent.process({
            "collection": "users",
            "data": {"name": "New User"},
            "document_id": "new-user",
            "mode": "write"
        })
        
        assert result.success is True
        assert result.document_id == "new-user"


if __name__ == "__main__":
    unittest.main()