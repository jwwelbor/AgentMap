# tests/test_csv_storage_agents.py
import os
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from agentmap.agents.builtins.storage.csv.reader import CSVReaderAgent
from agentmap.agents.builtins.storage.csv.writer import CSVWriterAgent


@pytest.fixture
def sample_csv_path():
    """Create a temporary CSV file for testing."""
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as temp:
        # Create a test CSV file
        df = pd.DataFrame({
            "id": [1, 2, 3, 4, 5],
            "name": ["Alice", "Bob", "Charlie", "David", "Eve"],
            "age": [30, 25, 35, 40, 22]
        })
        df.to_csv(temp.name, index=False)
        path = temp.name
    
    # Return the path to the test file
    yield path
    
    # Clean up after the test
    if os.path.exists(path):
        os.remove(path)


def test_csv_reader_basic(sample_csv_path):
    """Test basic CSV reading functionality."""
    # Create a reader agent
    reader = CSVReaderAgent(
        name="TestReader",
        prompt="",
        context={
            "input_fields": ["collection"],
            "output_field": "users"
        }
    )
    
    # Run the agent with a simple input
    result = reader.process({"collection": sample_csv_path})
    
    # Verify the result
    assert isinstance(result, list)
    assert len(result) == 5
    assert result[0]["name"] == "Alice"
    assert result[1]["age"] == 25


def test_csv_reader_query(sample_csv_path):
    """Test CSV reading with query filtering."""
    # Create a reader agent
    reader = CSVReaderAgent(
        name="TestReader",
        prompt="",
        context={
            "input_fields": ["collection", "query"],
            "output_field": "users"
        }
    )
    
    # Test with string query
    result = reader.process({
        "collection": sample_csv_path,
        "query": "age > 30"
    })
    
    # Verify filtered results
    assert len(result) == 2  # Charlie and David
    assert all(user["age"] > 30 for user in result)
    
    # Test with dict query
    result = reader.process({
        "collection": sample_csv_path,
        "query": {"name": "Bob"}
    })
    
    # Verify filtered results
    assert len(result) == 1
    assert result[0]["name"] == "Bob"
    assert result[0]["age"] == 25


def test_csv_reader_id_lookup(sample_csv_path):
    """Test CSV reading with ID lookup."""
    # Create a reader agent
    reader = CSVReaderAgent(
        name="TestReader",
        prompt="",
        context={
            "input_fields": ["collection", "id"],
            "output_field": "user"
        }
    )
    
    # Test with ID lookup
    result = reader.process({
        "collection": sample_csv_path,
        "id": 3,
        "id_field": "id"
    })
    
    # Verify single record returned
    assert isinstance(result, dict)
    assert result["name"] == "Charlie"
    assert result["age"] == 35


def test_csv_reader_limit(sample_csv_path):
    """Test CSV reading with limit."""
    # Create a reader agent
    reader = CSVReaderAgent(
        name="TestReader",
        prompt="",
        context={
            "input_fields": ["collection", "limit"],
            "output_field": "users"
        }
    )
    
    # Test with limit
    result = reader.process({
        "collection": sample_csv_path,
        "limit": 2
    })
    
    # Verify limited results
    assert len(result) == 2
    assert result[0]["name"] == "Alice"
    assert result[1]["name"] == "Bob"


def test_csv_writer_basic():
    """Test basic CSV writing functionality."""
    # Create a temporary file path
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as temp:
        temp_path = temp.name
    
    try:
        # Create a writer agent
        writer = CSVWriterAgent(
            name="TestWriter",
            prompt="",
            context={
                "input_fields": ["collection", "data"],
                "output_field": "result"
            }
        )
        
        # Test data to write
        data = [
            {"id": 1, "name": "Alice", "age": 30},
            {"id": 2, "name": "Bob", "age": 25}
        ]
        
        # Write the data
        result = writer.process({
            "collection": temp_path,
            "data": data
        })
        
        # Verify the result
        assert result["success"] is True
        assert result["rows_written"] == 2
        assert result["file_path"] == temp_path
        
        # Verify the file was created with the correct data
        df = pd.read_csv(temp_path)
        assert len(df) == 2
        assert df.iloc[0]["name"] == "Alice"
        assert df.iloc[1]["age"] == 25
    
    finally:
        # Clean up
        if os.path.exists(temp_path):
            os.remove(temp_path)


def test_csv_writer_append():
    """Test CSV appending functionality."""
    # Create a temporary file with initial data
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as temp:
        df = pd.DataFrame({
            "id": [1],
            "name": ["Alice"],
            "age": [30]
        })
        df.to_csv(temp.name, index=False)
        temp_path = temp.name
    
    try:
        # Create a writer agent
        writer = CSVWriterAgent(
            name="TestWriter",
            prompt="",
            context={
                "input_fields": ["collection", "data", "mode"],
                "output_field": "result"
            }
        )
        
        # Test data to append
        data = [
            {"id": 2, "name": "Bob", "age": 25}
        ]
        
        # Append the data
        result = writer.process({
            "collection": temp_path,
            "data": data,
            "mode": "append"
        })
        
        # Verify the result
        assert result["success"] is True
        assert result["rows_written"] == 1
        assert result["file_path"] == temp_path
        assert result["mode"] == "append"
        
        # Verify the data was appended correctly
        df = pd.read_csv(temp_path)
        assert len(df) == 2
        assert df.iloc[0]["name"] == "Alice"
        assert df.iloc[1]["name"] == "Bob"
    
    finally:
        # Clean up
        if os.path.exists(temp_path):
            os.remove(temp_path)


def test_csv_writer_update():
    """Test CSV update functionality."""
    # Create a temporary file with initial data
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as temp:
        df = pd.DataFrame({
            "id": [1, 2, 3],
            "name": ["Alice", "Bob", "Charlie"],
            "age": [30, 25, 35]
        })
        df.to_csv(temp.name, index=False)
        temp_path = temp.name
    
    try:
        # Create a writer agent
        writer = CSVWriterAgent(
            name="TestWriter",
            prompt="",
            context={
                "input_fields": ["collection", "data", "mode", "id_field"],
                "output_field": "result"
            }
        )
        
        # Test data with updates and new records
        data = [
            {"id": 2, "name": "Bob", "age": 26},  # Update age
            {"id": 4, "name": "David", "age": 40}  # New record
        ]
        
        # Update the data
        result = writer.process({
            "collection": temp_path,
            "data": data,
            "mode": "update",
            "id_field": "id"
        })
        
        # Verify the result
        assert result["success"] is True
        assert result["rows_updated"] == 1
        assert result["rows_added"] == 1
        assert result["total_affected"] == 2
        assert 2 in result["updated_ids"]
        
        # Verify the data was updated correctly
        df = pd.read_csv(temp_path)
        assert len(df) == 4
        bob_row = df[df["id"] == 2].iloc[0]
        assert bob_row["age"] == 26  # Age updated
        david_row = df[df["id"] == 4].iloc[0]
        assert david_row["name"] == "David"  # New record added
    
    finally:
        # Clean up
        if os.path.exists(temp_path):
            os.remove(temp_path)


def test_agent_run_method():
    """Test the full agent run method with state management."""
    # Create a temporary file path
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as temp:
        temp_path = temp.name
    
    try:
        # Create a writer agent
        writer = CSVWriterAgent(
            name="TestWriter",
            prompt="",
            context={
                "input_fields": ["collection", "data"],
                "output_field": "write_result"
            }
        )
        
        # Create a test state
        state = {
            "collection": temp_path,
            "data": [
                {"id": 1, "name": "Alice", "age": 30},
                {"id": 2, "name": "Bob", "age": 25}
            ]
        }
        
        # Run the agent
        result_state = writer.run(state)
        
        # Verify the state was updated correctly
        assert "write_result" in result_state
        assert result_state["write_result"]["success"] is True
        assert result_state["last_action_success"] is True
        
        # Now read the data back with a reader agent
        reader = CSVReaderAgent(
            name="TestReader",
            prompt="",
            context={
                "input_fields": ["collection"],
                "output_field": "users"
            }
        )
        
        read_state = {
            "collection": temp_path
        }
        
        result_state = reader.run(read_state)
        
        # Verify the state was updated correctly
        assert "users" in result_state
        assert len(result_state["users"]) == 2
        assert result_state["users"][0]["name"] == "Alice"
        assert result_state["last_action_success"] is True
    
    finally:
        # Clean up
        if os.path.exists(temp_path):
            os.remove(temp_path)