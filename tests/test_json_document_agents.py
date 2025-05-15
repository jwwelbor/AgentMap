# tests/storage/test_json_document_agents.py

import json
import os
import tempfile
from pathlib import Path

import pytest

from agentmap.agents.builtins.storage.document.base_agent import \
    WriteMode
from agentmap.agents.builtins.storage.json.reader import \
    JSONDocumentReaderAgent
from agentmap.agents.builtins.storage.json.writer import \
    JSONDocumentWriterAgent


class TestJSONDocumentAgents:
    """Tests for JSON document reader and writer agents."""
    
    @pytest.fixture
    def reader_agent(self):
        """Create JSON document reader agent for testing."""
        return JSONDocumentReaderAgent(
            name="TestReader",
            prompt="",
            context={"input_fields": ["collection"], "output_field": "result"}
        )
    
    @pytest.fixture
    def writer_agent(self):
        """Create JSON document writer agent for testing."""
        return JSONDocumentWriterAgent(
            name="TestWriter",
            prompt="",
            context={"input_fields": ["collection", "data"], "output_field": "result"}
        )
    
    @pytest.fixture
    def sample_json_dict(self):
        """Sample JSON data in dictionary format."""
        return {
            "user1": {"name": "Alice", "role": "admin"},
            "user2": {"name": "Bob", "role": "user"}
        }
    
    @pytest.fixture
    def sample_json_list(self):
        """Sample JSON data in list format."""
        return [
            {"id": "doc1", "title": "First Document", "tags": ["important"]},
            {"id": "doc2", "title": "Second Document", "tags": ["archive"]}
        ]
    
    @pytest.fixture
    def json_dict_file(self, sample_json_dict):
        """Create a temporary JSON file with dictionary data."""
        with tempfile.NamedTemporaryFile(suffix=".json", mode='w', delete=False) as temp:
            json.dump(sample_json_dict, temp)
            temp_path = temp.name
        
        yield temp_path
        
        # Cleanup
        if os.path.exists(temp_path):
            os.remove(temp_path)
    
    @pytest.fixture
    def json_list_file(self, sample_json_list):
        """Create a temporary JSON file with list data."""
        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as temp:
            json.dump(sample_json_list, temp)
            temp_path = temp.name
        
        yield temp_path
        
        # Cleanup
        if os.path.exists(temp_path):
            os.remove(temp_path)
    
    # Reader tests
    
    def test_read_entire_file_dict(self, reader_agent, json_dict_file, sample_json_dict):
        """Test reading an entire JSON file with dictionary structure."""
        result = reader_agent.process({'collection': json_dict_file})
        assert result == {'success': True, 'document_id': os.path.basename(json_dict_file),'data': {'user1': {'name': 'Alice', 'role': 'admin'}, 'user2': {'name': 'Bob', 'role': 'user'}}, 'is_collection': True}
    
    def test_read_entire_file_list(self, reader_agent, json_list_file, sample_json_list):
        """Test reading an entire JSON file with list structure."""
        result = reader_agent.process({"collection": json_list_file})
        assert result["data"] == sample_json_list
    
    def test_read_document_by_id_from_dict(self, reader_agent, json_dict_file):
        """Test reading a specific document by ID from a dictionary structure."""
        result = reader_agent.process({
            "collection": json_dict_file,
            "document_id": "user1"
        })
        
        assert result == {'success': True, 'document_id': "user1",'data': {"name": "Alice", "role": "admin"}, 'is_collection': False}
    
    def test_read_document_by_id_from_list(self, reader_agent, json_list_file):
        """Test reading a specific document by ID from a list structure."""
        result = reader_agent.process({
            "collection": json_list_file,
            "document_id": "doc2"
        })
        # {'success': True, 'document_id': 'doc2', 'data': {'id': 'doc2', 'title': 'Second Document', 'tags': [...]}, 'is_collection': False}
        assert result == {'success': True, 'document_id': 'doc2', 'data': {"id": "doc2", "title": "Second Document", "tags": ["archive"]}, 'is_collection': False}

    def test_read_with_path(self, reader_agent, json_dict_file):
        """Test reading a specific path from a JSON file."""
        result = reader_agent.process({
            "collection": json_dict_file,
            "path": "user1.name"
        })
        
        assert result == {'success': True, 'document_id': f"{os.path.basename(json_dict_file)}.user1.name", 'data': 'Alice', 'is_collection': False}
    
    def test_read_with_document_id_and_path(self, reader_agent, json_list_file):
        """Test reading a path within a specific document."""
        result = reader_agent.process({
            "collection": json_list_file,
            "document_id": "doc1",
            "path": "tags.0"
        })
        
        assert result == {'data': 'important', 'success': True, 'document_id': 'doc1', 'is_collection': False}
    
    def test_read_with_query_list(self, reader_agent, json_list_file):
        """Test filtering list data with a query."""
        result = reader_agent.process({
            "collection": json_list_file,
            "query": {"title": "First Document"}
        })
        import json
        assert len(result["data"]) == 1
        assert result["data"][0]["title"] == "First Document"
        assert result["data"][0]["id"] == "doc1"
    
    def test_read_nonexistent_file(self, reader_agent):
        """Test reading a file that doesn't exist."""
        with pytest.raises(Exception):
            reader_agent.process({"collection": "nonexistent.json"})
    
    def test_read_with_default_value(self, reader_agent, json_dict_file):
        """Test using a default value for missing paths."""
        result = reader_agent.process({
            "collection": json_dict_file,
            "path": "missing.path",
            "default": "default_value"
        })
        
        assert result == "default_value"
    
    # Writer tests
    
    def test_write_new_file(self, writer_agent, sample_json_dict):
        """Test writing a new JSON file."""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as temp:
            temp_path = temp.name
        
        try:
            # Remove the file so we can test creation
            os.remove(temp_path)
            
            result = writer_agent.process({
                "collection": temp_path,
                "data": sample_json_dict
            })
            
            assert result["success"] is True
            assert os.path.exists(temp_path)
            
            # Verify contents
            with open(temp_path, 'r') as f:
                saved_data = json.load(f)
                assert saved_data == sample_json_dict
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
    
    def test_write_document_to_dict(self, writer_agent, json_dict_file):
        """Test writing a document to a dictionary structure."""
        result = writer_agent.process({
            "collection": json_dict_file,
            "data": {"name": "Charlie", "role": "guest"},
            "document_id": "user3",
            "mode": "write"
        })
        
        assert result["success"] is True
        
        # Verify the file was updated correctly
        with open(json_dict_file, 'r') as f:
            saved_data = json.load(f)
            assert saved_data["user3"] == {"name": "Charlie", "role": "guest"}
            # Original data should still be there
            assert "user1" in saved_data
            assert "user2" in saved_data
    
    def test_write_document_to_list(self, writer_agent, json_list_file):
        """Test writing a document to a list structure."""
        result = writer_agent.process({
            "collection": json_list_file,
            "data": {"title": "Third Document", "tags": ["new"]},
            "document_id": "doc3",
            "mode": "write"
        })
        
        assert result["success"] is True
        
        # Verify the file was updated correctly
        with open(json_list_file, 'r') as f:
            saved_data = json.load(f)
            # Find the new document
            doc3 = next((doc for doc in saved_data if doc.get("id") == "doc3"), None)
            assert doc3 is not None
            assert doc3["title"] == "Third Document"
            assert doc3["tags"] == ["new"]
            # Original documents should still be there (length = 3)
            assert len(saved_data) == 3
    
    def test_update_document(self, writer_agent, json_list_file):
        """Test updating an existing document."""
        result = writer_agent.process({
            "collection": json_list_file,
            "data": {"title": "Updated Document"},
            "document_id": "doc1",
            "mode": "update"
        })
        
        assert result["success"] is True
        
        # Verify the file was updated correctly
        with open(json_list_file, 'r') as f:
            saved_data = json.load(f)
            doc1 = next((doc for doc in saved_data if doc.get("id") == "doc1"), None)
            assert doc1["title"] == "Updated Document"
            # Original fields should be removed in an update
            assert "tags" not in doc1
    
    def test_update_path(self, writer_agent, json_dict_file):
        """Test updating a specific path."""
        result = writer_agent.process({
            "collection": json_dict_file,
            "data": "super-admin",
            "document_id": "user1",
            "path": "role",
            "mode": "update"
        })
        
        assert result["success"] is True
        
        # Verify the file was updated correctly
        with open(json_dict_file, 'r') as f:
            saved_data = json.load(f)
            assert saved_data["user1"]["role"] == "super-admin"
            # Other fields should be preserved
            assert saved_data["user1"]["name"] == "Alice"
    
    def test_merge_document(self, writer_agent, json_dict_file):
        """Test merging data with an existing document."""
        result = writer_agent.process({
            "collection": json_dict_file,
            "data": {"email": "alice@example.com"},
            "document_id": "user1",
            "mode": "merge"
        })
        
        assert result["success"] is True
        
        # Verify the file was updated correctly
        with open(json_dict_file, 'r') as f:
            saved_data = json.load(f)
            assert saved_data["user1"]["email"] == "alice@example.com"
            # Original fields should be preserved
            assert saved_data["user1"]["name"] == "Alice"
            assert saved_data["user1"]["role"] == "admin"
    
    def test_delete_document(self, writer_agent, json_list_file):
        """Test deleting a document."""
        result = writer_agent.process({
            "collection": json_list_file,
            "document_id": "doc1",
            "mode": "delete"
        })
        
        assert result["success"] is True
        
        # Verify the file was updated correctly
        with open(json_list_file, 'r') as f:
            saved_data = json.load(f)
            # Document should be removed
            assert len(saved_data) == 1
            assert saved_data[0]["id"] == "doc2"
    
    def test_delete_path(self, writer_agent, json_dict_file):
        """Test deleting a specific path."""
        result = writer_agent.process({
            "collection": json_dict_file,
            "document_id": "user1",
            "path": "role",
            "mode": "delete"
        })
        
        assert result["success"] is True
        
        # Verify the file was updated correctly
        with open(json_dict_file, 'r') as f:
            saved_data = json.load(f)
            # Field should be removed
            assert "role" not in saved_data["user1"]
            # Other fields should be preserved
            assert saved_data["user1"]["name"] == "Alice"
    
    def test_delete_by_query(self, writer_agent, json_list_file):
        """Test deleting documents based on a query."""
        # Create a file with multiple documents for testing
        with open(json_list_file, 'w') as f:
            json.dump([
                {"id": "doc1", "category": "A", "active": True},
                {"id": "doc2", "category": "B", "active": True},
                {"id": "doc3", "category": "A", "active": False},
                {"id": "doc4", "category": "C", "active": True}
            ], f)
        
        result = writer_agent.process({
            "collection": json_list_file,
            "data": {"category": "A"},  # Delete all with category A
            "mode": "delete"
        })
        
        assert result["success"] is True
        assert result["count"] == 2
        
        # Verify the file was updated correctly
        with open(json_list_file, 'r') as f:
            saved_data = json.load(f)
            # Should have two documents left
            assert len(saved_data) == 2
            # Check remaining document IDs
            ids = sorted([doc["id"] for doc in saved_data])
            assert ids == ["doc2", "doc4"]
    
    def test_agent_run_method(self, writer_agent, reader_agent):
        """Test full agent run method with state management."""
        # Create a temporary file
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as temp:
            temp_path = temp.name
        
        try:
            # Initial state for writer
            write_state = {
                "collection": temp_path,
                "data": {"greeting": "Hello, World!"}
            }
            
            # Run the writer agent
            result_state = writer_agent.run(write_state)
            
            # Verify state was updated correctly
            assert "result" in result_state
            assert result_state["result"]["success"] is True
            assert result_state["last_action_success"] is True
            
            # Read state for verification
            read_state = {"collection": temp_path}
            
            # Run the reader agent
            result_state = reader_agent.run(read_state)
            
            # Verify state was updated correctly
            assert "result" in result_state
            assert result_state["result"]["data"]["greeting"] == "Hello, World!"
            assert result_state["last_action_success"] is True
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
