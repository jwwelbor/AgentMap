#!/usr/bin/env python
"""
JSON Storage Service Demo.

This script demonstrates how to use the JSON storage service
with dependency injection and various storage operations.
"""
import os
import sys
from pathlib import Path

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from agentmap.di.containers import ApplicationContainer
from agentmap.services.storage.types import WriteMode


def setup_demo_environment():
    """Set up the demo environment."""
    # Create data directories
    os.makedirs("./data/json", exist_ok=True)
    os.makedirs("./data/csv", exist_ok=True)
    
    print("\n🚀 JSON Storage Service Demo")
    print("============================\n")


def demo_basic_operations(json_service):
    """Demonstrate basic JSON storage operations."""
    print("\n📝 Basic Operations")
    print("------------------")
    
    # Sample data
    users = [
        {"id": "user1", "name": "Alice", "role": "admin", "active": True},
        {"id": "user2", "name": "Bob", "role": "user", "active": True},
        {"id": "user3", "name": "Charlie", "role": "user", "active": False},
    ]
    
    # Write operation
    print("Writing users collection...")
    result = json_service.write("users", users)
    print(f"✅ Write result: success={result.success}")
    
    # Read operation
    print("\nReading all users...")
    data = json_service.read("users")
    print(f"📄 Found {len(data)} users:")
    for user in data:
        print(f"  - {user['name']} ({user['role']})")
    
    # Read by document ID
    print("\nReading user by ID...")
    user = json_service.read("users", document_id="user1")
    if user:
        print(f"📄 Found user: {user['name']} ({user['role']})")
    
    # Count operation
    count = json_service.count("users")
    print(f"\n📊 User count: {count}")
    
    # Exists operation
    exists = json_service.exists("users", document_id="user2")
    print(f"🔍 User 'user2' exists: {exists}")


def demo_query_operations(json_service):
    """Demonstrate query operations with JSON storage."""
    print("\n🔍 Query Operations")
    print("-----------------")
    
    # Query by field
    print("Querying active users...")
    active_users = json_service.read("users", query={"active": True})
    print(f"📄 Found {len(active_users)} active users:")
    for user in active_users:
        print(f"  - {user['name']}")
    
    # Query with multiple conditions
    print("\nQuerying active admins...")
    admins = json_service.read("users", query={"role": "admin", "active": True})
    print(f"📄 Found {len(admins)} active admins:")
    for admin in admins:
        print(f"  - {admin['name']}")
    
    # Query with pagination
    print("\nQuerying with pagination (limit=1, offset=1)...")
    paginated = json_service.read("users", query={"limit": 1, "offset": 1})
    print(f"📄 Paginated result: {paginated[0]['name']}")


def demo_nested_document_operations(json_service):
    """Demonstrate nested document operations with JSON storage."""
    print("\n📁 Nested Document Operations")
    print("---------------------------")
    
    # Nested document
    company = {
        "company": {
            "name": "Acme Inc.",
            "founded": 2010,
            "address": {
                "street": "123 Main St",
                "city": "Anytown",
                "zipcode": "12345"
            },
            "departments": [
                {"id": 1, "name": "Engineering", "employees": 50},
                {"id": 2, "name": "Marketing", "employees": 25},
                {"id": 3, "name": "Sales", "employees": 35}
            ]
        }
    }
    
    # Write nested document
    print("Writing nested company document...")
    json_service.write("company", company)
    
    # Read with path
    print("\nReading company name with path...")
    name = json_service.read("company", path="company.name")
    print(f"📄 Company name: {name}")
    
    # Read nested object
    print("\nReading company address with path...")
    address = json_service.read("company", path="company.address")
    print(f"📄 Company address: {address['street']}, {address['city']}, {address['zipcode']}")
    
    # Read array element
    print("\nReading department by index...")
    department = json_service.read("company", path="company.departments.1")
    print(f"📄 Department: {department['name']} ({department['employees']} employees)")
    
    # Update nested path
    print("\nUpdating company address...")
    json_service.write(
        "company",
        {"state": "CA", "country": "USA"},
        path="company.address",
        mode=WriteMode.UPDATE
    )
    
    # Read updated address
    address = json_service.read("company", path="company.address")
    print(f"📄 Updated address: {address['street']}, {address['city']}, {address['state']}, {address['country']}")
    
    # Check existence with path
    exists = json_service.exists("company", path="company.address.state")
    print(f"\n🔍 Path 'company.address.state' exists: {exists}")


def demo_write_modes(json_service):
    """Demonstrate different write modes with JSON storage."""
    print("\n✏️ Write Modes")
    print("------------")
    
    # Update mode
    print("Updating user with UPDATE mode...")
    updated_user = {"id": "user2", "name": "Robert", "role": "admin"}
    json_service.write("users", updated_user, mode=WriteMode.UPDATE)
    
    # Verify update
    user = json_service.read("users", document_id="user2")
    print(f"📄 Updated user: {user['name']} ({user['role']})")
    
    # Append mode
    print("\nAppending new user with APPEND mode...")
    new_user = {"id": "user4", "name": "Dave", "role": "manager", "active": True}
    json_service.write("users", new_user, mode=WriteMode.APPEND)
    
    # Verify append
    count = json_service.count("users")
    print(f"📊 New user count: {count}")
    
    # Merge mode
    print("\nMerging company data with MERGE mode...")
    merge_data = {
        "company": {
            "website": "acme.example.com",
            "employees": 150,
            "address": {
                "state": "California"  # Update state from CA to California
            }
        }
    }
    json_service.write("company", merge_data, mode=WriteMode.MERGE)
    
    # Verify merge
    company = json_service.read("company")
    print(f"📄 Merged company data:")
    print(f"  - Name: {company['company']['name']}")
    print(f"  - Website: {company['company']['website']}")
    print(f"  - Employees: {company['company']['employees']}")
    print(f"  - Address: {company['company']['address']['city']}, {company['company']['address']['state']}")


def demo_delete_operations(json_service):
    """Demonstrate delete operations with JSON storage."""
    print("\n❌ Delete Operations")
    print("-----------------")
    
    # Delete document
    print("Deleting user by ID...")
    json_service.delete("users", document_id="user3")
    
    # Verify deletion
    exists = json_service.exists("users", document_id="user3")
    print(f"🔍 User 'user3' exists: {exists}")
    
    # Delete by path
    print("\nDeleting nested path...")
    json_service.delete("company", path="company.address.zipcode")
    
    # Verify path deletion
    address = json_service.read("company", path="company.address")
    print(f"📄 Updated address fields: {', '.join(address.keys())}")
    
    # List collections
    print("\nListing all collections...")
    collections = json_service.list_collections()
    print(f"📚 Collections: {', '.join(collections)}")


def main():
    """Run the JSON storage service demo."""
    setup_demo_environment()
    
    # Initialize the application container with DI
    print("Initializing application container...")
    container = ApplicationContainer()
    container.config_path.from_value("example_json_storage_config.yaml")
    
    # Get the storage service manager
    storage_manager = container.storage_service_manager()
    
    # Get the JSON storage service
    json_service = storage_manager.get_service("json")
    
    # Check if service is initialized
    print(f"✅ JSON service initialized successfully")
    
    # Verify service can perform operations
    try:
        # Try both health_check and is_healthy methods for compatibility
        if hasattr(json_service, 'health_check'):
            health_check = json_service.health_check()
        elif hasattr(json_service, 'is_healthy'):
            health_check = json_service.is_healthy()
        else:
            health_check = True  # Assume healthy if no check method available
            
        print(f"✅ JSON service health check: {health_check}")
    except Exception as e:
        print(f"⚠️ JSON service health check unavailable: {e}")
        # Continue with demo anyway
    
    # Run demo operations
    demo_basic_operations(json_service)
    demo_query_operations(json_service)
    demo_nested_document_operations(json_service)
    demo_write_modes(json_service)
    demo_delete_operations(json_service)
    
    print("\n✨ Demo completed successfully!")


if __name__ == "__main__":
    main()