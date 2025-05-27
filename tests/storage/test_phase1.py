#!/usr/bin/env python3
"""
Test script to verify Phase 1 fixes the circular import issue.
"""

import sys
import os

# Add the src directory to Python path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
src_path = os.path.join(project_root, 'src')
sys.path.insert(0, src_path)

def test_phase1_imports():
    """Test that the circular import is fixed and storage types are properly organized."""
    print("Testing Phase 1 - Storage Types Restructured")
    print("=" * 50)
    
    try:
        # Test storage types import
        from agentmap.services.storage import WriteMode, DocumentResult, StorageError
        print("✅ Successfully imported storage types")
        
        # Test storage mixins import
        from agentmap.agents.mixins import StorageErrorHandlerMixin
        print("✅ Successfully imported storage mixins")
        
        # Test base storage agent import
        from agentmap.agents.builtins.storage.base_storage_agent import BaseStorageAgent
        print("✅ Successfully imported BaseStorageAgent")
        
        # Test orchestrator agent import (this was failing before)
        from agentmap.agents.builtins.orchestrator_agent import OrchestratorAgent
        print("✅ Successfully imported OrchestratorAgent")
        
        # Test convenience imports from services module
        from agentmap.services import WriteMode as ServiceWriteMode, DocumentResult as ServiceDocumentResult
        print("✅ Successfully imported convenience exports from services")
        
        print("\n🎉 Phase 1 Complete - Storage types properly restructured!")
        print("Storage types are now organized under agentmap.services.storage")
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Other error: {e}")
        return False

if __name__ == "__main__":
    success = test_phase1_imports()
    sys.exit(0 if success else 1)
