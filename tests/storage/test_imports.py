#!/usr/bin/env python3
"""Simple test to check if imports work."""

import sys
import os
import traceback

# Add the src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def main():
    print("Testing Phase 1 imports...")
    
    try:
        print("1. Testing storage types...")
        from agentmap.services.storage import WriteMode, DocumentResult, StorageError
        print("   ✅ Storage types imported successfully")
        
        print("2. Testing storage mixins...")
        from agentmap.agents.mixins import StorageErrorHandlerMixin
        print("   ✅ Storage mixins imported successfully")
        
        print("3. Testing base storage agent...")
        from agentmap.agents.builtins.storage.base_storage_agent import BaseStorageAgent
        print("   ✅ BaseStorageAgent imported successfully")
        
        print("4. Testing orchestrator agent...")
        from agentmap.agents.builtins.orchestrator_agent import OrchestratorAgent
        print("   ✅ OrchestratorAgent imported successfully")
        
        print("5. Testing CSV agents...")
        from agentmap.agents.builtins.storage.csv.reader import CSVReaderAgent
        from agentmap.agents.builtins.storage.csv.writer import CSVWriterAgent
        print("   ✅ CSV agents imported successfully")
        
        print("6. Testing file agents...")
        from agentmap.agents.builtins.storage.file.reader import FileReaderAgent
        from agentmap.agents.builtins.storage.file.writer import FileWriterAgent
        print("   ✅ File agents imported successfully")
        
        print("\n🎉 Phase 1 Complete - All imports successful!")
        print("The circular import issue has been resolved.")
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\nFull traceback:")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
