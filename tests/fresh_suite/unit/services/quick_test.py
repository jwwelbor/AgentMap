#!/usr/bin/env python3
"""Quick test to verify GraphBuilderService test setup."""

import os
import sys
from pathlib import Path

# Add src to Python path
project_root = Path(__file__).parent.parent.parent.parent.parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))


def run_quick_test():
    """Run a quick test to verify the setup."""
    try:
        print("🔄 Testing GraphBuilderService imports...")

        # Test service import
        from agentmap.services.graph_builder_service import GraphBuilderService

        print("✅ GraphBuilderService imported")

        # Test MockServiceFactory import
        sys.path.insert(0, str(project_root / "tests"))
        from utils.mock_service_factory import MockServiceFactory

        print("✅ MockServiceFactory imported")

        # Test creating mock services
        mock_logging = MockServiceFactory.create_mock_logging_service()
        mock_config = MockServiceFactory.create_mock_app_config_service()
        print("✅ Mock services created")

        # Test service initialization
        service = GraphBuilderService(
            logging_service=mock_logging, app_config_service=mock_config
        )
        print("✅ Service initialized successfully")

        # Test logger access
        logger = service.logger
        logger_calls = logger.calls
        print(f"✅ Logger working, calls tracked: {len(logger_calls)}")

        print("\n🎉 All basic tests passed!")
        return True

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_quick_test()
    exit(0 if success else 1)
