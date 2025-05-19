from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agentmap.runner import run_graph

app = FastAPI(title="AgentMap Graph API")

# Optional CORS for browser-based tools
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class RunRequest(BaseModel):
    graph: str
    state: dict  # Changed from input
    autocompile: bool = False

@app.post("/run")
def run(request: RunRequest):
    try:
        output = run_graph(request.graph, request.state, autocompile_override=request.autocompile) 
        return { "output": output }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))