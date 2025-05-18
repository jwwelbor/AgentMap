from fastapi import FastAPI
from pydantic import BaseModel
from agentmap.agents.features import HAS_LLM_AGENTS, HAS_STORAGE_AGENTS

from agentmap.runner import run_graph

app = FastAPI()

class GraphRequest(BaseModel):
    graph: str
    state: dict = {} 

@app.post("/run")
def run_graph_api(body: GraphRequest):
    output = run_graph(graph_name=body.graph, initial_state=body.state, state=body.state)  
    return {"output": output}


@app.get("/agents/available")
def list_available_agents():
    """Return information about available agents in this environment."""
    return {
        "core_agents": True,  # Always available
        "llm_agents": HAS_LLM_AGENTS,
        "storage_agents": HAS_STORAGE_AGENTS,
        "install_instructions": {
            "llm": "pip install agentmap[llm]",
            "storage": "pip install agentmap[storage]",
            "all": "pip install agentmap[all]"
        }
    }