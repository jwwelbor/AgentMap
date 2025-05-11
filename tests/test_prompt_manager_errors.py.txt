from agentmap.prompts.manager import PromptManager

# Error handling tests


def test_invalid_yaml_reference(mock_config):
    """Test handling of invalid YAML references."""
    manager = PromptManager()
    
    # Missing # separator
    invalid_ref = "yaml:file.yaml"
    assert "[Invalid YAML reference" in manager.resolve_prompt(invalid_ref)

def test_read_error_handling(mock_config, temp_dir, mocker):
    """Test handling of file read errors."""
    manager = PromptManager()
    
    # Mock open to raise an exception
    mocker.patch("builtins.open", side_effect=IOError("Mock file error"))
    
    file_ref = "file:some_file.txt"
    assert "[Error reading prompt file" in manager.resolve_prompt(file_ref)
    
    yaml_ref = "yaml:some_file.yaml#key"
    assert "[Error reading YAML file" in manager.resolve_prompt(yaml_ref)

def test_invalid_yaml_content(mock_config, temp_dir):
    """Test handling of invalid YAML content."""
    # Create file with invalid YAML
    invalid_yaml_path = temp_dir / "invalid.yaml"
    with open(invalid_yaml_path, 'w') as f:
        f.write("this is not valid yaml: :")
    
    manager = PromptManager()
    yaml_ref = f"yaml:{invalid_yaml_path.name}#key"
    assert "[Error reading YAML file" in manager.resolve_prompt(yaml_ref)

def test_registry_save_error(mock_config, temp_dir, mocker):
    """Test handling of registry save errors."""
    manager = PromptManager()
    
    # Mock yaml.dump to raise an exception
    mocker.patch("yaml.dump", side_effect=Exception("Mock save error"))
    
    # Attempt to save the registry should return False
    result = manager._save_registry()
    assert result is False