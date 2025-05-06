from fastapi import FastAPI
from pydantic import BaseModel

from agentmap.runner import run_graph

app = FastAPI()

class GraphRequest(BaseModel):
    graph: str
    state: dict = {} 

@app.post("/run")
def run_graph_api(body: GraphRequest):
    output = run_graph(graph_name=body.graph, initial_state=body.state, state=body.state)  
    return {"output": output}