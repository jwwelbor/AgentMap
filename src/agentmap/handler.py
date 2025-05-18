"""
Serverless handler for AgentMap. Compatible with AWS Lambda or Google Cloud Functions.
"""

import json

from agentmap.runner import run_graph


def handler(event, context=None):
    try:
        # Handle API Gateway-style HTTP event
        if "body" in event:
            body = json.loads(event["body"])
        else:
            body = event

        graph_name = body.get("graph")  # Now optional
        initial_state = body.get("state", {}) 
        autocompile = body.get("autocompile", False)

        # Run the graph - graph_name can now be None
        output = run_graph(graph_name, initial_state, autocompile_override=autocompile) 

        return {
            "statusCode": 200,
            "body": json.dumps({ "output": output })
        }

    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({ "error": str(e) })
        }