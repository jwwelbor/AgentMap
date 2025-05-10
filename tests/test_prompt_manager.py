# tests/prompts/test_manager.py

import os
import pytest
from pathlib import Path
import yaml
import tempfile
import shutil
from agentmap.prompts.manager import PromptManager, get_prompt_manager, resolve_prompt

# Test fixtures
@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)

@pytest.fixture
def prompt_registry(temp_dir):
    """Create a test prompt registry."""
    registry = {
        "greeting": "Hello, {name}!",
        "farewell": "Goodbye, {name}. See you soon!",
        "error": "An error occurred: {error_message}"
    }
    
    registry_path = temp_dir / "registry.yaml"
    with open(registry_path, 'w') as f:
        yaml.dump(registry, f)
    
    return registry_path

@pytest.fixture
def text_prompt_file(temp_dir):
    """Create a test text prompt file."""
    content = "This is a test prompt for {topic}."
    file_path = temp_dir / "test_prompt.txt"
    
    with open(file_path, 'w') as f:
        f.write(content)
    
    return file_path

@pytest.fixture
def yaml_prompt_file(temp_dir):
    """Create a test YAML prompt file with nested structure."""
    content = {
        "templates": {
            "simple": "A simple template for {item}.",
            "complex": {
                "standard": "A standard complex template for {item}.",
                "advanced": "An advanced complex template for {item} with {feature}."
            }
        },
        "messages": {
            "welcome": "Welcome to the application, {name}!",
            "error": {
                "not_found": "The {resource} was not found.",
                "permission": "You don't have permission to access {resource}."
            }
        }
    }
    
    file_path = temp_dir / "test_prompts.yaml"
    
    with open(file_path, 'w') as f:
        yaml.dump(content, f)
    
    return file_path

@pytest.fixture
def mock_config(monkeypatch, temp_dir, prompt_registry):
    """Mock configuration for testing."""
    def mock_get_prompts_config(*args, **kwargs):
        return {
            "directory": str(temp_dir),
            "registry_file": str(prompt_registry),
            "enable_cache": True
        }
    
    def mock_get_prompts_directory(*args, **kwargs):
        return temp_dir
    
    def mock_get_prompt_registry_path(*args, **kwargs):
        return prompt_registry
    
    # Patch the config functions
    monkeypatch.setattr("agentmap.prompts.manager.get_prompts_config", mock_get_prompts_config)
    monkeypatch.setattr("agentmap.prompts.manager.get_prompts_directory", mock_get_prompts_directory)
    monkeypatch.setattr("agentmap.prompts.manager.get_prompt_registry_path", mock_get_prompt_registry_path)


# Tests for initialization
def test_init(mock_config):
    """Test PromptManager initialization."""
    manager = PromptManager()
    
    assert manager.config is not None
    assert manager.prompts_dir is not None
    assert manager.registry_path is not None
    assert manager.enable_cache is True
    assert hasattr(manager, '_registry')
    assert hasattr(manager, '_cache')

def test_load_registry(mock_config, prompt_registry):
    """Test loading the prompt registry."""
    manager = PromptManager()
    
    # Registry should be loaded during initialization
    assert len(manager._registry) == 3
    assert "greeting" in manager._registry
    assert "farewell" in manager._registry
    assert "error" in manager._registry
    
    # Content should match
    assert manager._registry["greeting"] == "Hello, {name}!"

# Tests for resolving prompts
def test_resolve_registry_prompt(mock_config):
    """Test resolving prompts from registry."""
    manager = PromptManager()
    
    # Resolve existing prompts
    assert manager.resolve_prompt("prompt:greeting") == "Hello, {name}!"
    assert manager.resolve_prompt("prompt:farewell") == "Goodbye, {name}. See you soon!"
    
    # Resolve non-existent prompt
    assert "[Prompt not found" in manager.resolve_prompt("prompt:nonexistent")

def test_resolve_file_prompt(mock_config, text_prompt_file):
    """Test resolving prompts from files."""
    manager = PromptManager()
    
    # Resolve existing file
    file_ref = f"file:{text_prompt_file.name}"
    assert manager.resolve_prompt(file_ref) == "This is a test prompt for {topic}."
    
    # Resolve non-existent file
    assert "[Prompt file not found" in manager.resolve_prompt("file:nonexistent.txt")

def test_resolve_yaml_prompt(mock_config, yaml_prompt_file):
    """Test resolving prompts from YAML files."""
    manager = PromptManager()
    
    # Resolve simple path
    yaml_ref = f"yaml:{yaml_prompt_file.name}#templates.simple"
    assert manager.resolve_prompt(yaml_ref) == "A simple template for {item}."
    
    # Resolve nested path
    yaml_ref = f"yaml:{yaml_prompt_file.name}#templates.complex.advanced"
    assert manager.resolve_prompt(yaml_ref) == "An advanced complex template for {item} with {feature}."
    
    # Resolve with invalid key
    yaml_ref = f"yaml:{yaml_prompt_file.name}#nonexistent.key"
    assert "[Key not found" in manager.resolve_prompt(yaml_ref)
    
    # Resolve with invalid YAML path
    yaml_ref = "yaml:nonexistent.yaml#key"
    assert "[YAML prompt file not found" in manager.resolve_prompt(yaml_ref)

def test_prompt_with_no_reference(mock_config):
    """Test that non-reference prompts are returned as-is."""
    manager = PromptManager()
    
    assert manager.resolve_prompt("Hello world") == "Hello world"
    assert manager.resolve_prompt(None) is None
    assert manager.resolve_prompt(123) == 123  # Non-string values returned as-is

# Tests for prompt registration
def test_register_prompt(mock_config, temp_dir):
    """Test registering new prompts."""
    manager = PromptManager()
    
    # Register a new prompt
    result = manager.register_prompt("test_prompt", "This is a test prompt", save=False)
    assert result is True
    assert "test_prompt" in manager._registry
    assert manager._registry["test_prompt"] == "This is a test prompt"
    
    # Verify the prompt can be resolved
    assert manager.resolve_prompt("prompt:test_prompt") == "This is a test prompt"
    
    # Update an existing prompt
    result = manager.register_prompt("greeting", "Updated greeting", save=False)
    assert result is True
    assert manager._registry["greeting"] == "Updated greeting"
    
    # Verify the update can be resolved
    assert manager.resolve_prompt("prompt:greeting") == "Updated greeting"

def test_save_registry(mock_config, temp_dir):
    """Test saving the registry to disk."""
    manager = PromptManager()
    
    # Add a new prompt
    manager.register_prompt("new_prompt", "A new prompt", save=True)
    
    # Verify the file was written
    with open(manager.registry_path, 'r') as f:
        saved_registry = yaml.safe_load(f)
    
    assert "new_prompt" in saved_registry
    assert saved_registry["new_prompt"] == "A new prompt"

# Tests for caching
def test_prompt_caching(mock_config, mocker):
    """Test that prompts are cached correctly."""
    manager = PromptManager()
    
    # Spy on the _resolve_registry_prompt method
    spy = mocker.spy(manager, '_resolve_registry_prompt')
    
    # First call should hit the registry
    result1 = manager.resolve_prompt("prompt:greeting")
    assert result1 == "Hello, {name}!"
    assert spy.call_count == 1
    
    # Second call should use the cache
    result2 = manager.resolve_prompt("prompt:greeting")
    assert result2 == "Hello, {name}!"
    assert spy.call_count == 1  # Still 1, cache was used
    
    # Test clearing the cache
    manager.clear_cache()
    
    # After cache clear, should hit registry again
    result3 = manager.resolve_prompt("prompt:greeting")
    assert result3 == "Hello, {name}!"
    assert spy.call_count == 2

def test_cache_disabled(mock_config):
    """Test behavior when cache is disabled."""
    manager = PromptManager()
    manager.enable_cache = False
    
    # Without caching, content should still resolve correctly
    assert manager.resolve_prompt("prompt:greeting") == "Hello, {name}!"
    assert "prompt:greeting" not in manager._cache  # Cache shouldn't be used

# Tests for global utility functions
def test_get_prompt_manager(mock_config):
    """Test that get_prompt_manager returns a singleton instance."""
    manager1 = get_prompt_manager()
    manager2 = get_prompt_manager()
    
    assert manager1 is manager2  # Same instance
    assert isinstance(manager1, PromptManager)

def test_resolve_prompt_function(mock_config):
    """Test the standalone resolve_prompt function."""
    # Should handle reference prompts
    assert resolve_prompt("prompt:greeting") == "Hello, {name}!"
    
    # Should return non-reference prompts as-is
    assert resolve_prompt("Hello world") == "Hello world"
    assert resolve_prompt(None) is None