# tests/storage/test_document_path_mixin.py

import pytest

from agentmap.agents.builtins.storage.document_path_mixin import \
    DocumentPathMixin


class TestDocumentPathMixin:
    """Tests for DocumentPathMixin path manipulation functionality."""
    
    @pytest.fixture
    def mixin(self):
        """Create a simple instance of DocumentPathMixin for testing."""
        return DocumentPathMixin()
    
    @pytest.fixture
    def sample_data(self):
        """Sample nested document structure for testing."""
        return {
            "users": [
                {"id": "1", "name": "Alice", "profile": {"age": 30, "role": "admin"}},
                {"id": "2", "name": "Bob", "profile": {"age": 25, "role": "user"}}
            ],
            "settings": {
                "theme": "dark",
                "notifications": True,
                "nested": {
                    "level1": {
                        "level2": "value"
                    }
                }
            },
            "tags": ["important", "archived"]
        }
    
    def test_parse_path(self, mixin):
        """Test parsing paths into components."""
        assert mixin._parse_path("users.0.name") == ["users", "0", "name"]
        assert mixin._parse_path("$.users.0.name") == ["users", "0", "name"]
        assert mixin._parse_path("settings.theme") == ["settings", "theme"]
        assert mixin._parse_path("$") == []
        assert mixin._parse_path("") == []
    
    def test_apply_path_dict_access(self, mixin, sample_data):
        """Test extracting values from dictionary paths."""
        assert mixin._apply_path(sample_data, "settings.theme") == "dark"
        assert mixin._apply_path(sample_data, "settings.notifications") is True
        assert mixin._apply_path(sample_data, "settings.nested.level1.level2") == "value"
        assert mixin._apply_path(sample_data, "settings.missing") is None
    
    def test_apply_path_list_access(self, mixin, sample_data):
        """Test extracting values from list indices."""
        assert mixin._apply_path(sample_data, "users.0.name") == "Alice"
        assert mixin._apply_path(sample_data, "users.1.profile.age") == 25
        assert mixin._apply_path(sample_data, "tags.0") == "important"
        assert mixin._apply_path(sample_data, "tags.3") is None  # Out of bounds
    
    def test_apply_path_root(self, mixin, sample_data):
        """Test extracting the root document."""
        assert mixin._apply_path(sample_data, "$") == sample_data
        assert mixin._apply_path(sample_data, "") == sample_data
    
    def test_update_path_dict(self, mixin, sample_data):
        """Test updating values in dictionaries."""
        # Update existing field
        result = mixin._update_path(sample_data, "settings.theme", "light")
        assert result["settings"]["theme"] == "light"
        # Original data should be unchanged
        assert sample_data["settings"]["theme"] == "dark"
        
        # Add new field
        result = mixin._update_path(sample_data, "settings.new_field", "value")
        assert result["settings"]["new_field"] == "value"
        assert "new_field" not in sample_data["settings"]
    
    def test_update_path_list(self, mixin, sample_data):
        """Test updating values in lists."""
        # Update existing item
        result = mixin._update_path(sample_data, "users.1.name", "Robert")
        assert result["users"][1]["name"] == "Robert"
        assert sample_data["users"][1]["name"] == "Bob"  # Original unchanged
        
        # Update with new index (extend list)
        result = mixin._update_path(sample_data, "tags.3", "new_tag")
        assert result["tags"][3] == "new_tag"
        assert len(sample_data["tags"]) == 2  # Original unchanged
    
    def test_update_path_nested_creation(self, mixin):
        """Test creating nested paths that don't exist."""
        # Create completely new nested structure
        data = {}
        result = mixin._update_path(data, "a.b.c", "value")
        assert result["a"]["b"]["c"] == "value"
        
        # Create mixed list/dict structure
        data = {}
        result = mixin._update_path(data, "items.0.name", "first")
        assert result["items"][0]["name"] == "first"
    
    def test_update_path_root(self, mixin, sample_data):
        """Test updating the root document."""
        new_data = {"completely": "new"}
        result = mixin._update_path(sample_data, "$", new_data)
        assert result == new_data
        assert sample_data != new_data  # Original unchanged
        
        result = mixin._update_path(sample_data, "", new_data)
        assert result == new_data
    
    def test_delete_path_dict(self, mixin, sample_data):
        """Test deleting fields from dictionaries."""
        result = mixin._delete_path(sample_data, "settings.theme")
        assert "theme" not in result["settings"]
        assert "theme" in sample_data["settings"]  # Original unchanged
    
    def test_delete_path_list(self, mixin, sample_data):
        """Test deleting items from lists."""
        result = mixin._delete_path(sample_data, "tags.0")
        assert result["tags"] == ["archived"]  # First item removed
        assert len(sample_data["tags"]) == 2  # Original unchanged
    
    def test_delete_path_nested(self, mixin, sample_data):
        """Test deleting deeply nested fields."""
        result = mixin._delete_path(sample_data, "settings.nested.level1.level2")
        assert "level2" not in result["settings"]["nested"]["level1"]
        assert "level2" in sample_data["settings"]["nested"]["level1"]  # Original unchanged
    
    def test_delete_path_root(self, mixin, sample_data):
        """Test deleting the entire document."""
        result = mixin._delete_path(sample_data, "$")
        assert result == {}
        assert sample_data != {}  # Original unchanged
        
        result = mixin._delete_path(sample_data, "")
        assert result == {}
    
    def test_deep_copy(self, mixin, sample_data):
        """Test deep copying data structures."""
        copy = mixin._deep_copy(sample_data)
        assert copy == sample_data
        assert copy is not sample_data
        
        # Modify the copy, original should be unchanged
        copy["settings"]["theme"] = "modified"
        assert sample_data["settings"]["theme"] == "dark"
    
    def test_merge_documents(self, mixin):
        """Test merging two dictionaries."""
        dict1 = {"a": 1, "b": {"c": 2, "d": 3}}
        dict2 = {"b": {"e": 4}, "f": 5}
        
        result = mixin._merge_documents(dict1, dict2)
        
        # Check that the result has the expected structure
        assert result["a"] == 1
        assert result["b"]["c"] == 2
        assert result["b"]["d"] == 3
        assert result["b"]["e"] == 4
        assert result["f"] == 5
        
        # Original dictionaries should be unchanged
        assert "e" not in dict1["b"]
        assert "f" not in dict1