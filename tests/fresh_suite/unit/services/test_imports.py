#!/usr/bin/env python3
"""Simple test runner to verify imports for GraphBuilderService tests."""

import sys
from pathlib import Path

# Add src to path
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

def test_imports():
    """Test all required imports for GraphBuilderService tests."""
    try:
        print("Testing imports...")
        
        # Test service import
        from agentmap.services.graph_builder_service import GraphBuilderService
        print("✅ GraphBuilderService imported successfully")
        
        # Test model imports
        from agentmap.models.graph import Graph
        from agentmap.models.node import Node
        print("✅ Graph and Node models imported successfully")
        
        # Test MockServiceFactory
        from tests.utils.mock_service_factory import MockServiceFactory
        print("✅ MockServiceFactory imported successfully")
        
        # Test exceptions
        from agentmap.exceptions.graph_exceptions import InvalidEdgeDefinitionError
        print("✅ Exception imports successful")
        
        print("\n🎉 All imports successful!")
        return True
        
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        return False

if __name__ == "__main__":
    success = test_imports()
    sys.exit(0 if success else 1)
