"""
Example of using the clean API orchestration layer.

This demonstrates how to create and run an API server using the new
server factory pattern that maintains clean architecture principles.
"""

from agentmap.core.api import create_api_server, create_default_api_server
from agentmap.di import ApplicationContainer


def main():
    """Example of starting the API server using clean architecture."""
    # Create the dependency injection container
    container = ApplicationContainer()

    # Option 1: Create default API server (FastAPI)
    server = create_default_api_server(container)

    # Option 2: Explicitly specify server type
    # server = create_api_server(container, server_type="fastapi")

    # Option 3: Create with custom configuration
    # config = {
    #     "title": "AgentMap API",
    #     "version": "2.0.0",
    #     "docs_url": "/api/docs"
    # }
    # server = create_api_server(container, server_type="fastapi", config=config)

    # Run the server
    server.run(host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
