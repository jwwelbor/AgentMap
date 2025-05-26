from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, Optional

from agentmap.agents.features import is_llm_enabled, is_storage_enabled
from agentmap.runner import run_graph

app = FastAPI(title="AgentMap Graph API")

# Optional CORS for browser-based tools
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class GraphRunRequest(BaseModel):
    """Request model for running a graph."""
    graph: Optional[str] = None  # Optional graph name (defaults to first graph in CSV)
    state: Dict[str, Any] = {}   # Initial state (defaults to empty dict)
    autocompile: bool = False    # Whether to autocompile the graph if missing

@app.post("/run")
def run_graph_api(request: GraphRunRequest):
    """Run a graph with the provided parameters."""
    try:
        output = run_graph(
            graph_name=request.graph, 
            initial_state=request.state, 
            autocompile_override=request.autocompile
        ) 
        return {"output": output}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/agents/available")
def list_available_agents():
    """Return information about available agents in this environment."""
    return {
        "core_agents": True,  # Always available
        "llm_agents": is_llm_enabled(),
        "storage_agents": is_storage_enabled(),
        "install_instructions": {
            "llm": "pip install agentmap[llm]",
            "storage": "pip install agentmap[storage]",
            "all": "pip install agentmap[all]"
        }
    }