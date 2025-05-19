import sys
from uvicorn.main import main as uvicorn_main

def main():
    """Entry point for the AgentMap server."""
    # Prepare the arguments for uvicorn
    sys.argv = [
        sys.argv[0],  # Keep the script name
        "agentmap.fastapi_server:app",
        "--reload"
    ]
    # Run uvicorn with our arguments
    uvicorn_main()

if __name__ == "__main__":
    main()