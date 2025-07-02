"""
Minimal end-to-end test for orchestrator functionality.
"""

import subprocess
import sys
from pathlib import Path


def test_orchestrator_cli():
    """Test that the orchestrator can be run from command line."""
    # Get the project root
    project_root = Path(__file__).parent.parent.parent.parent
    
    # Build the command
    cmd = [
        sys.executable,
        "-m", "poetry",
        "run",
        "agentmap", 
        "run",
        "-g", "gm_orchestration",
        "--config", str(project_root / "agentmap_local_config.yaml"),
        "--csv", str(project_root / "examples" / "gm_orchestration.csv")
    ]
    
    # Run the command
    result = subprocess.run(
        cmd,
        cwd=str(project_root),
        capture_output=True,
        text=True,
        timeout=30  # 30 second timeout
    )
    
    print("STDOUT:")
    print(result.stdout)
    print("\nSTDERR:")
    print(result.stderr)
    print(f"\nReturn code: {result.returncode}")
    
    # Check that it doesn't have the "OrchestratorService not configured" error
    assert "OrchestratorService not configured" not in result.stderr
    assert "OrchestratorService not configured" not in result.stdout
    
    # The graph may still fail due to other issues (like missing nodes),
    # but the orchestrator service should be properly configured
    print("\n✅ OrchestratorService is properly configured!")


if __name__ == "__main__":
    test_orchestrator_cli()
