# main.py — Azure Functions adapter for AgentMap
# Provides entries for Service Bus (queue/topic) and HTTP triggers.
# NOTE: In Azure Functions Python, the entry file is typically __init__.py,
# but this example uses main.py for clarity; set scriptFile in function.json.

import json
import azure.functions as func

# Import the thin Azure handlers from AgentMap
from agentmap.deployment.serverless.azure_functions import (
    azure_servicebus_handler,
    azure_http_handler,
)

def servicebus_entry(msg: func.ServiceBusMessage) -> None:
    """Service Bus-triggered function entry.
    The message body should be a JSON string:
       {"graph":"MyGraph","state":{...},"action":"run"}
    """
    return azure_servicebus_handler(msg)

def http_entry(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP-triggered function entry for local testing/webhooks."""
    return azure_http_handler(req)
