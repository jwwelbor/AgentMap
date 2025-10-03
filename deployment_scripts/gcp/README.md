# AgentMap — Google Cloud Functions (Gen 2) Starter

## Files
- `main.py` — thin adapter that delegates to AgentMap's GCF handlers
- `requirements.txt` — AgentMap + Google libs

## Deploy (Pub/Sub)
```bash
gcloud functions deploy agentmap-pubsub \      --gen2 \      --runtime=python312 \      --region=us-central1 \      --entry-point=pubsub_entry \      --source=. \      --trigger-topic=agentmap-events \      --set-env-vars=AGENTMAP_CONFIG_FILE=config/agentmap.yaml
```

## Deploy (HTTP)
```bash
gcloud functions deploy agentmap-http \      --gen2 \      --runtime=python312 \      --region=us-central1 \      --entry-point=http_entry \      --source=. \      --trigger-http \      --allow-unauthenticated \      --set-env-vars=AGENTMAP_CONFIG_FILE=config/agentmap.yaml
```

## Pub/Sub Message Shape
Base64-encoded JSON:
```json
{"graph":"Demo","state":{"hello":"world"},"action":"run"}
```
