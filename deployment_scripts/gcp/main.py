# functions/main.py — Google Cloud Functions (2nd gen) adapter for AgentMap
# Entrypoints:
#   - pubsub_entry:  Pub/Sub trigger
#   - http_entry:    HTTP trigger (optional for testing/webhooks)

from agentmap.deployment.serverless.gcp_functions import (
    gcp_pubsub_handler,
    gcp_http_handler,
)

def pubsub_entry(event, context):
    """Pub/Sub-triggered Cloud Function entrypoint.
    Expects event['data'] to be a base64-encoded JSON of the form:
        {"graph":"MyGraph","state":{...},"action":"run"}
    """
    return gcp_pubsub_handler(event, context)

def http_entry(request):
    """HTTP-triggered Cloud Function entrypoint.
    Accepts JSON body with {"graph":..., "state":...}.
    """
    return gcp_http_handler(request)
