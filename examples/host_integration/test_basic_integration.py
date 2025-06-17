#!/usr/bin/env python3
"""
Simple test to verify basic host integration functionality.

This simplified test checks core functionality without complex setup.
"""

import sys
from pathlib import Path

# Add AgentMap to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

def test_basic_imports():
    """Test that we can import all required modules."""
    print("🔍 Testing basic imports...")
    
    try:
        # Test AgentMap imports
        from agentmap.di.containers import ApplicationContainer
        print("   ✅ ApplicationContainer imported")
        
        from agentmap.agents.base_agent import BaseAgent
        print("   ✅ BaseAgent imported")
        
        # Test host service imports
        from host_services import DatabaseService, EmailService, NotificationService
        print("   ✅ Host services imported")
        
        from host_protocols import DatabaseServiceProtocol, EmailServiceProtocol
        print("   ✅ Host protocols imported")
        
        from custom_agents import DatabaseAgent, EmailAgent, MultiServiceAgent
        print("   ✅ Custom agents imported")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Import failed: {e}")
        return False

def test_container_creation():
    """Test that we can create a container and register host services."""
    print("\n🏗️ Testing container creation...")
    
    try:
        from agentmap.di.containers import ApplicationContainer
        from host_services import create_database_service
        from host_protocols import DatabaseServiceProtocol
        
        # Create container
        container = ApplicationContainer()
        print("   ✅ Container created")
        
        # Register a simple host service
        container.register_host_factory(
            service_name="test_db_service",
            factory_function=create_database_service,
            dependencies=["app_config_service", "logging_service"],
            protocols=[DatabaseServiceProtocol]
        )
        print("   ✅ Host service registered")
        
        # Check if service is registered
        if container.has_host_service("test_db_service"):
            print("   ✅ Service registration verified")
            return True
        else:
            print("   ❌ Service not found after registration")
            return False
            
    except Exception as e:
        print(f"   ❌ Container test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_agent_creation():
    """Test that we can create custom agents."""
    print("\n👤 Testing agent creation...")
    
    try:
        from custom_agents import DatabaseAgent, EmailAgent, MultiServiceAgent
        
        # Create agents
        db_agent = DatabaseAgent("test_db")
        email_agent = EmailAgent("test_email")
        multi_agent = MultiServiceAgent("test_multi")
        
        print("   ✅ All agents created successfully")
        
        # Check agent types
        from host_protocols import DatabaseServiceProtocol, EmailServiceProtocol
        
        if isinstance(db_agent, DatabaseServiceProtocol):
            print("   ✅ DatabaseAgent implements DatabaseServiceProtocol")
        else:
            print("   ❌ DatabaseAgent protocol check failed")
            return False
            
        if isinstance(email_agent, EmailServiceProtocol):
            print("   ✅ EmailAgent implements EmailServiceProtocol")
        else:
            print("   ❌ EmailAgent protocol check failed")
            return False
            
        return True
        
    except Exception as e:
        print(f"   ❌ Agent creation failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run basic host integration tests."""
    print("🧪 AgentMap Host Integration - Basic Tests")
    print("=" * 50)
    
    tests = [
        ("Basic Imports", test_basic_imports),
        ("Container Creation", test_container_creation),
        ("Agent Creation", test_agent_creation)
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"❌ Test '{test_name}' crashed: {e}")
            results[test_name] = False
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 Test Results")
    
    passed = sum(1 for success in results.values() if success)
    total = len(results)
    
    for test_name, success in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"  {test_name:<20} {status}")
    
    print(f"\n🎯 Result: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 Basic host integration is working!")
        print("\nNext steps:")
        print("1. Run full integration example: python integration_example.py")
        print("2. Run comprehensive tests: python test_host_integration.py")
        return 0
    else:
        print("⚠️ Some basic tests failed. Check configuration and dependencies.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
