# AgentMap Deployment Architecture

**Document Version**: 1.0
**Last Updated**: 2025-10-28
**Maintainer**: Architecture Team

---

## Executive Summary

AgentMap supports **four primary deployment modes** from a single unified codebase: CLI, HTTP/FastAPI standalone, HTTP embedded, and serverless (AWS Lambda, Azure Functions, GCP Cloud Functions). This document details the deployment architecture, runtime adapter patterns, configuration management, and best practices for each deployment mode.

### Deployment Modes

| Mode | Use Case | Entry Point | Scaling |
|------|----------|-------------|---------|
| **CLI** | Local development, scripting, automation | `agentmap` command | N/A (local) |
| **HTTP Standalone** | Microservice, API server | `agentmap serve` | Horizontal |
| **HTTP Embedded** | Integrated into larger app | `create_sub_application()` | App-dependent |
| **Serverless** | Event-driven, auto-scaling | Lambda/Azure/GCP handlers | Automatic |

### Key Features

- **Single Codebase**: All deployment modes share core services via DI
- **Runtime Facade**: `runtime_api.py` provides unified initialization
- **Service Adapter**: Standardized result formatting across modes
- **Trigger Strategies**: Automatic event parsing for serverless triggers
- **Configuration Flexibility**: Per-deployment configuration support

---

## 1. Deployment Architecture Overview

### 1.1 Unified Deployment Strategy

```
┌─────────────────────────────────────────────────────────┐
│                  DEPLOYMENT ADAPTERS                    │
│  ┌──────────┬──────────┬──────────┬─────────────────┐  │
│  │   CLI    │   HTTP   │  HTTP    │   Serverless    │  │
│  │ (Typer)  │(FastAPI) │(Embedded)│(Lambda/Azure/GCP)│  │
│  └────┬─────┴────┬─────┴────┬─────┴────────┬─────────┘  │
└───────┼──────────┼──────────┼──────────────┼────────────┘
        │          │          │              │
        ▼          ▼          ▼              ▼
┌───────────────────────────────────────────────────────┐
│           ORCHESTRATION LAYER                         │
│  ┌──────────────────────────────────────────────┐    │
│  │  WorkflowOrchestrationService (Unified API)  │    │
│  │  - execute_workflow()                        │    │
│  │  - resume_workflow()                         │    │
│  └────────────────┬─────────────────────────────┘    │
└───────────────────┼──────────────────────────────────┘
                    │
                    ▼
┌───────────────────────────────────────────────────────┐
│           SERVICE ADAPTER (Formatting)                │
│  - extract_result_state()                             │
│  - handle_execution_error()                           │
│  - format_http_response()                             │
│  - TriggerParameterExtractor (serverless)             │
│  - ResponseFormatter (CLI/API/serverless)             │
└───────────────────┬───────────────────────────────────┘
                    │
                    ▼
┌───────────────────────────────────────────────────────┐
│           DI CONTAINER (Shared Services)              │
│  ApplicationContainer with all services               │
└───────────────────────────────────────────────────────┘
```

### 1.2 Runtime Facade Pattern

**Purpose**: Consistent initialization across all deployment modes.

```python
# runtime_api.py - Single source of truth
def ensure_initialized(config_file: Optional[str] = None) -> None:
    """Initialize DI container (idempotent)."""
    global _container
    if _container is None:
        _container = initialize_di(config_file)

def get_container() -> ApplicationContainer:
    """Get initialized container."""
    if _container is None:
        raise AgentMapNotInitialized()
    return _container

def execute_workflow(...) -> ExecutionResult:
    """Execute workflow (runtime facade)."""
    ensure_initialized(config_file)
    return WorkflowOrchestrationService.execute_workflow(...)

def resume_workflow(...) -> ExecutionResult:
    """Resume workflow (runtime facade)."""
    ensure_initialized(config_file)
    return WorkflowOrchestrationService.resume_workflow(...)
```

**Benefits:**
- Single initialization logic for all deployments
- Idempotent initialization prevents double-init
- Clear error handling for uninitialized state
- Easy testing and mocking

### 1.3 Deployment Adapter Pattern

Each deployment mode provides a thin adapter layer:

```python
# Adapter responsibilities:
1. Parse input format (CLI args, HTTP request, serverless event)
2. Call WorkflowOrchestrationService
3. Format response for deployment mode
4. Handle deployment-specific concerns (auth, CORS, etc.)
```

---

## 2. CLI Deployment

### 2.1 CLI Architecture

```
User Terminal
    ↓
agentmap command (entry point via pyproject.toml)
    ↓
deployment/cli/main_cli.py (Typer app)
    ↓
Command-specific modules:
├── run_command.py (execute workflows)
├── resume_command.py (resume from checkpoint)
├── scaffold_command.py (code generation)
├── validate_command.py (validation)
├── diagnose_command.py (diagnostics)
├── serve_command.py (start HTTP server)
└── ... (other commands)
    ↓
WorkflowOrchestrationService
    ↓
ExecutionResult
    ↓
CLI output formatting (rich library)
```

### 2.2 CLI Commands

**Primary Commands:**

```bash
# Execute workflow
agentmap run workflow.csv --graph MyGraph --state '{"key": "value"}'
agentmap run workflow/GraphName  # Repository shorthand

# Resume suspended workflow
agentmap resume --thread-id abc123 --action approve --data '{"approved": true}'

# Generate scaffold code
agentmap scaffold --csv workflow.csv --output ./agents/

# Validate workflow
agentmap validate --csv workflow.csv

# Start HTTP server
agentmap serve --host 0.0.0.0 --port 8000

# System diagnostics
agentmap diagnose
agentmap diagnose --csv workflow.csv  # Workflow-specific
```

**Configuration Commands:**

```bash
# Initialize configuration
agentmap init-config

# Authentication setup
agentmap auth generate-key
agentmap auth list-keys
agentmap auth revoke-key <key>
```

**Diagnostic Commands:**

```bash
# Bundle cache management
agentmap refresh --csv workflow.csv
agentmap refresh --all

# Validation
agentmap validate --csv workflow.csv
```

### 2.3 CLI Implementation

**Entry Point (pyproject.toml):**
```toml
[project.scripts]
agentmap = "agentmap.deployment.cli.main_cli:main_cli"
AgentMap = "agentmap.deployment.cli.main_cli:main_cli"
```

**Main CLI Structure:**
```python
# deployment/cli/main_cli.py
app = typer.Typer(
    name="agentmap",
    help="AgentMap: Build and deploy LangGraph workflows from CSV files"
)

# Command registration
app.command("run")(run_command)
app.command("resume")(resume_command)
app.command("scaffold")(scaffold_command)
app.command("validate")(validate_command)
app.command("diagnose")(diagnose_cmd)
app.command("serve")(serve_command)
# ... more commands

def main_cli():
    """Main CLI entry point."""
    try:
        app()
    except typer.Exit as e:
        sys.exit(e.exit_code)
    except KeyboardInterrupt:
        typer.echo("\nOperation cancelled by user")
        sys.exit(1)
    except Exception as e:
        typer.secho(f"❌ Unexpected error: {e}", fg=typer.colors.RED)
        sys.exit(1)
```

**Run Command Example:**
```python
# deployment/cli/run_command.py
def run_command(
    workflow: Optional[str] = typer.Argument(None),
    csv: Optional[str] = typer.Option(None),
    graph: Optional[str] = typer.Option(None),
    state: Optional[str] = typer.Option(None),
    config: Optional[str] = typer.Option(None),
    validate_csv: bool = typer.Option(False),
    pretty: bool = typer.Option(True),
    verbose: bool = typer.Option(False)
):
    """Execute workflow from CSV definition."""
    try:
        # Delegate to orchestration service
        result = WorkflowOrchestrationService.execute_workflow(
            workflow=workflow or csv,
            graph_name=graph,
            initial_state=state,
            config_file=config,
            validate_csv=validate_csv
        )

        # Format output
        if pretty:
            display_pretty_result(result)
        else:
            display_json_result(result)

    except Exception as e:
        typer.secho(f"❌ Error: {e}", fg=typer.colors.RED)
        raise typer.Exit(1)
```

### 2.4 CLI Configuration

**Configuration Discovery:**
```python
# Order of precedence (highest to lowest):
1. --config parameter
2. agentmap_config.yaml in current directory
3. ~/.agentmap/agentmap_config.yaml
4. System defaults
```

**Environment Variables:**
```bash
# Override config values
AGENTMAP_LOG_LEVEL=DEBUG
AGENTMAP_CACHE_FOLDER=./cache
AGENTMAP_OPENAI_API_KEY=sk-...
AGENTMAP_ANTHROPIC_API_KEY=sk-ant-...
```

### 2.5 CLI Output Formatting

**Pretty Output (default):**
```python
from rich.console import Console
from rich.table import Table

def display_pretty_result(result: ExecutionResult):
    console = Console()

    if result.success:
        console.print("✅ [green]Workflow completed successfully[/green]")
        console.print(f"[cyan]Graph:[/cyan] {result.graph_name}")
        console.print(f"[cyan]Duration:[/cyan] {result.total_duration:.2f}s")

        # Display final state
        table = Table(title="Final State")
        table.add_column("Key", style="cyan")
        table.add_column("Value", style="yellow")

        for key, value in result.final_state.items():
            table.add_row(key, str(value))

        console.print(table)
    else:
        console.print(f"❌ [red]Workflow failed:[/red] {result.error}")
```

**JSON Output:**
```python
def display_json_result(result: ExecutionResult):
    output = {
        "success": result.success,
        "graph_name": result.graph_name,
        "final_state": result.final_state,
        "execution_time": result.total_duration,
        "error": result.error
    }
    print(json.dumps(output, indent=2))
```

---

## 3. HTTP Standalone Deployment

### 3.1 HTTP Architecture

```
HTTP Request
    ↓
Uvicorn (ASGI server)
    ↓
FastAPI Application (deployment/http/api/server.py)
    ↓
Middleware Stack:
├── CORSMiddleware (cross-origin)
├── AuthMiddleware (API keys/bearer tokens)
└── Exception handlers
    ↓
Route handlers (routes/)
├── execute.py: Workflow execution
├── workflows.py: Workflow management
└── admin.py: System diagnostics
    ↓
dependencies.py (FastAPI DI)
    ↓
WorkflowOrchestrationService
    ↓
ExecutionResult
    ↓
ServiceAdapter.format_http_response()
    ↓
JSON response
```

### 3.2 HTTP Server Implementation

**FastAPI Application:**
```python
# deployment/http/api/server.py
class FastAPIServer:
    def __init__(self, config_file: Optional[str] = None):
        self.config_file = config_file
        self.app = self.create_app()

    def create_app(self) -> FastAPI:
        app = FastAPI(
            title="AgentMap Workflow Automation API",
            version="2.0",
            lifespan=create_lifespan(self.config_file)
        )

        # Middleware
        app.add_middleware(CORSMiddleware, allow_origins=["*"])

        # Exception handlers
        self._add_exception_handlers(app)

        # Routes
        self._add_routes(app)

        return app

    def _add_routes(self, app: FastAPI):
        from agentmap.deployment.http.api.routes.execute import router as exec_router
        from agentmap.deployment.http.api.routes.workflows import router as wf_router
        from agentmap.deployment.http.api.routes.admin import router as admin_router

        app.include_router(exec_router)
        app.include_router(wf_router)
        app.include_router(admin_router)

def create_fastapi_app(config_file: Optional[str] = None) -> FastAPI:
    """Factory function for FastAPI app."""
    server = FastAPIServer(config_file)
    return server.app
```

**Lifespan Management:**
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Initialize AgentMap runtime during FastAPI startup.
    Shutdown during FastAPI shutdown.
    """
    try:
        # Initialize via runtime facade
        ensure_initialized(config_file=config_file)

        # Store container in app.state for dependency injection
        container = get_container()
        app.state.container = container

        # Pre-warm critical services
        _ = container.app_config_service()
        _ = container.auth_service()

        print("AgentMap runtime initialized successfully")
        yield
    except Exception as e:
        print(f"Failed to initialize AgentMap runtime: {e}")
        raise
    finally:
        print("AgentMap runtime shutting down")
```

### 3.3 HTTP Routes

**Execution Routes (routes/execute.py):**
```python
router = APIRouter(prefix="/execute", tags=["Execution"])

@router.post("/{workflow}/{graph}")
async def execute_workflow(
    workflow: str,
    graph: str,
    request: ExecuteWorkflowRequest,
    container: ApplicationContainer = Depends(get_container)
):
    """Execute workflow from repository or file."""
    try:
        result = WorkflowOrchestrationService.execute_workflow(
            workflow=workflow,
            graph_name=graph,
            initial_state=request.initial_state,
            config_file=request.config_file
        )

        return ServiceAdapter(container).format_http_response(result)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/resume/{thread_id}")
async def resume_workflow(
    thread_id: str,
    request: ResumeWorkflowRequest,
    container: ApplicationContainer = Depends(get_container)
):
    """Resume suspended workflow."""
    try:
        result = WorkflowOrchestrationService.resume_workflow(
            thread_id=thread_id,
            response_action=request.response_action,
            response_data=request.response_data,
            config_file=request.config_file
        )

        return ServiceAdapter(container).format_http_response(result)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

**Workflow Management Routes (routes/workflows.py):**
```python
router = APIRouter(prefix="/workflows", tags=["Workflows"])

@router.get("/")
async def list_workflows(
    container: ApplicationContainer = Depends(get_container)
):
    """List available workflows from repository."""
    app_config = container.app_config_service()
    repo_path = app_config.get_csv_repository_path()

    workflows = []
    for csv_file in repo_path.glob("*.csv"):
        workflows.append({
            "name": csv_file.stem,
            "path": str(csv_file),
            "graphs": _extract_graph_names(csv_file)
        })

    return {"workflows": workflows}

@router.get("/{workflow}/graphs")
async def list_graphs(
    workflow: str,
    container: ApplicationContainer = Depends(get_container)
):
    """List graphs in a workflow."""
    csv_path = _resolve_workflow_path(workflow, container)
    graphs = _extract_graph_names(csv_path)
    return {"workflow": workflow, "graphs": graphs}
```

**Admin Routes (routes/admin.py):**
```python
router = APIRouter(prefix="/admin", tags=["Administration"])

@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "agentmap-api",
        "timestamp": datetime.now().isoformat()
    }

@router.get("/diagnose")
async def diagnose_system(
    container: ApplicationContainer = Depends(get_container)
):
    """System diagnostics."""
    # Check service availability
    services = {
        "llm": _check_llm_services(container),
        "storage": _check_storage_services(container),
        "config": _check_config(container)
    }

    return {
        "services": services,
        "cache_status": container.get_cache_status()
    }
```

### 3.4 FastAPI Dependencies

**Dependency Injection Integration:**
```python
# deployment/http/api/dependencies.py
def get_container() -> ApplicationContainer:
    """FastAPI dependency to get DI container."""
    from agentmap.runtime_api import get_container
    return get_container()

def require_auth(
    authorization: Optional[str] = Header(None),
    api_key: Optional[str] = Header(None, alias="X-API-Key"),
    container: ApplicationContainer = Depends(get_container)
) -> bool:
    """Authentication dependency."""
    auth_service = container.auth_service()

    if api_key:
        return auth_service.verify_api_key(api_key)
    elif authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
        return auth_service.verify_bearer_token(token)
    else:
        raise HTTPException(status_code=401, detail="Authentication required")
```

### 3.5 HTTP Server Startup

**Command-Line Startup:**
```bash
# Using AgentMap CLI
agentmap serve --host 0.0.0.0 --port 8000 --reload

# Using uvicorn directly
uvicorn agentmap.deployment.http.api.server:create_fastapi_app \
    --factory \
    --host 0.0.0.0 \
    --port 8000 \
    --reload
```

**Programmatic Startup:**
```python
from agentmap.deployment.http.api.server import run_server

# Start server
run_server(
    host="0.0.0.0",
    port=8000,
    reload=True,
    config_file="./agentmap_config.yaml"
)
```

**Production Deployment:**
```bash
# With Gunicorn (multiple workers)
gunicorn agentmap.deployment.http.api.server:create_fastapi_app \
    --workers 4 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:8000

# With Docker
docker run -p 8000:8000 \
    -v $(pwd)/config:/app/config \
    agentmap-api:latest
```

---

## 4. HTTP Embedded Deployment

### 4.1 Embedded Architecture

**Purpose**: Mount AgentMap as a sub-application within a larger FastAPI app.

```
Host FastAPI Application
    ↓
app.mount("/agentmap", agentmap_app)
    ↓
AgentMap Sub-Application (isolated routing)
    ↓
Shared or isolated DI container
    ↓
WorkflowOrchestrationService
```

### 4.2 Embedding Implementation

**Host Application:**
```python
# host_app.py
from fastapi import FastAPI
from agentmap.deployment.http.api.server import create_sub_application

# Create host application
app = FastAPI(title="My Application")

# Create AgentMap sub-application
agentmap_app = create_sub_application(
    config_file="./agentmap_config.yaml",
    title="AgentMap Integration",
    prefix="/agentmap"
)

# Mount AgentMap
app.mount("/agentmap", agentmap_app)

# Host application routes
@app.get("/")
async def root():
    return {"message": "Host application"}

# Start server
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

**Sub-Application Factory:**
```python
# deployment/http/api/server.py
def create_sub_application(
    config_file: Optional[str] = None,
    title: str = "AgentMap API",
    prefix: str = ""
) -> FastAPI:
    """
    Create FastAPI app for sub-application mounting.

    Args:
        config_file: Optional config file path
        title: API title for OpenAPI docs
        prefix: URL prefix for the sub-application

    Returns:
        FastAPI app configured for mounting
    """
    app = FastAPI(
        title=title,
        description="AgentMap workflow execution API",
        version="2.0",
        lifespan=create_lifespan(config_file),
        openapi_url=f"{prefix}/openapi.json" if prefix else "/openapi.json",
        docs_url=f"{prefix}/docs" if prefix else "/docs",
        redoc_url=f"{prefix}/redoc" if prefix else "/redoc"
    )

    # CORS middleware
    app.add_middleware(CORSMiddleware, allow_origins=["*"])

    # Store config in app.state
    app.state.config_file = config_file

    # Add routes (standard AgentMap routes)
    _add_routes(app)

    return app
```

### 4.3 Isolation Strategies

**Shared Container (default):**
```python
# Both host and AgentMap share DI container
app.state.container = get_container()

# Host can access AgentMap services
@app.get("/host/workflow-status")
async def get_workflow_status(request: Request):
    container = request.app.state.container
    tracker = container.execution_tracking_service()
    return {"status": tracker.get_current_status()}
```

**Isolated Container:**
```python
# AgentMap has isolated container
agentmap_app = create_sub_application(config_file="./agentmap_config.yaml")
agentmap_app.state.isolated = True  # Mark as isolated

# Host cannot access AgentMap services directly
# Must use HTTP calls to /agentmap/* endpoints
```

### 4.4 Authentication Integration

**Shared Authentication:**
```python
# Host application handles auth
from fastapi import Depends, HTTPException

def verify_user(token: str = Depends(oauth2_scheme)):
    """Host application auth."""
    user = decode_jwt(token)
    if not user:
        raise HTTPException(status_code=401)
    return user

# Apply to AgentMap routes
@agentmap_app.post("/execute/{workflow}/{graph}")
async def execute_workflow(
    workflow: str,
    graph: str,
    user: User = Depends(verify_user)  # Host auth
):
    # AgentMap execution with host auth
    ...
```

**Delegated Authentication:**
```python
# Host delegates to AgentMap auth
@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    if request.url.path.startswith("/agentmap/"):
        # Let AgentMap handle its own auth
        return await call_next(request)
    else:
        # Host auth for other routes
        return await verify_host_auth(request, call_next)
```

---

## 5. Serverless Deployment

### 5.1 Serverless Architecture

```
Cloud Event Source
├── HTTP API Gateway
├── Message Queue (SQS, Service Bus, Pub/Sub)
├── Storage Event (S3, Blob, Cloud Storage)
├── Timer/Scheduler (EventBridge, Event Grid, Cloud Scheduler)
└── Stream (DynamoDB Streams, Change Feed, Firestore)
    ↓
Serverless Function (Lambda, Azure Functions, Cloud Functions)
    ↓
BaseHandler.handle_request_sync()
    ↓
TriggerStrategy.parse_event()
    ↓
TriggerParameterExtractor.extract_workflow_parameters()
    ↓
WorkflowOrchestrationService.execute_workflow()
    ↓
ExecutionResult
    ↓
ResponseFormatter.for_serverless()
    ↓
Cloud Response Format
```

### 5.2 AWS Lambda Deployment

**Handler Implementation:**
```python
# deployment/serverless/aws_lambda.py
class AWSLambdaHandler(BaseHandler):
    """AWS Lambda handler using facade pattern."""

    def lambda_handler(self, event: Dict, context: Any) -> Dict:
        """AWS Lambda entry point."""
        return self.handle_request_sync(event, context)

# Global handler instance
_lambda_handler_instance: Optional[AWSLambdaHandler] = None

def lambda_handler(event: Dict, context: Any) -> Dict:
    """Main Lambda handler function."""
    global _lambda_handler_instance

    if _lambda_handler_instance is None:
        _lambda_handler_instance = AWSLambdaHandler(
            config_file=os.environ.get("AGENTMAP_CONFIG_FILE")
        )

    return _lambda_handler_instance.lambda_handler(event, context)
```

**Lambda Configuration (serverless.yml):**
```yaml
service: agentmap-workflows

provider:
  name: aws
  runtime: python3.11
  memorySize: 512
  timeout: 300
  environment:
    AGENTMAP_CONFIG_FILE: ${file(agentmap_config.yaml)}
    OPENAI_API_KEY: ${env:OPENAI_API_KEY}
    ANTHROPIC_API_KEY: ${env:ANTHROPIC_API_KEY}

functions:
  execute_workflow:
    handler: agentmap.deployment.serverless.aws_lambda.lambda_handler
    events:
      # HTTP API Gateway
      - httpApi:
          path: /execute/{workflow}/{graph}
          method: post

      # SQS Queue
      - sqs:
          arn: arn:aws:sqs:us-east-1:123456789:workflow-queue
          batchSize: 10

      # S3 Event
      - s3:
          bucket: workflow-inputs
          event: s3:ObjectCreated:*

      # EventBridge Schedule
      - schedule:
          rate: cron(0 0 * * ? *)  # Daily

      # DynamoDB Stream
      - stream:
          type: dynamodb
          arn: arn:aws:dynamodb:us-east-1:123456789:table/WorkflowTriggers/stream
```

**Lambda Package:**
```bash
# Package Lambda deployment
cd agentmap/
pip install -r requirements.txt -t ./package
cp -r src/agentmap ./package/
cd package
zip -r ../agentmap-lambda.zip .

# Deploy with AWS CLI
aws lambda update-function-code \
    --function-name agentmap-execute-workflow \
    --zip-file fileb://agentmap-lambda.zip
```

### 5.3 Azure Functions Deployment

**Handler Implementation:**
```python
# deployment/serverless/azure_functions.py
import azure.functions as func
from agentmap.deployment.serverless.base_handler import BaseHandler

class AzureFunctionsHandler(BaseHandler):
    """Azure Functions handler using facade pattern."""

    def azure_handler(self, req: func.HttpRequest) -> func.HttpResponse:
        """Azure Functions HTTP entry point."""
        # Convert Azure request to standard dict
        event = {
            "httpMethod": req.method,
            "body": req.get_body().decode("utf-8"),
            "queryStringParameters": dict(req.params),
            "headers": dict(req.headers)
        }

        # Use base handler
        result = self.handle_request_sync(event, None)

        # Convert to Azure response
        return func.HttpResponse(
            body=result["body"],
            status_code=result["statusCode"],
            headers=result["headers"]
        )

# Global handler instance
_azure_handler_instance = None

def main(req: func.HttpRequest) -> func.HttpResponse:
    """Azure Functions entry point."""
    global _azure_handler_instance

    if _azure_handler_instance is None:
        _azure_handler_instance = AzureFunctionsHandler()

    return _azure_handler_instance.azure_handler(req)
```

**Azure Configuration (function.json):**
```json
{
  "scriptFile": "agentmap/deployment/serverless/azure_functions.py",
  "bindings": [
    {
      "authLevel": "function",
      "type": "httpTrigger",
      "direction": "in",
      "name": "req",
      "methods": ["post"],
      "route": "execute/{workflow}/{graph}"
    },
    {
      "type": "http",
      "direction": "out",
      "name": "$return"
    }
  ]
}
```

### 5.4 GCP Cloud Functions Deployment

**Handler Implementation:**
```python
# deployment/serverless/gcp_functions.py
import functions_framework
from agentmap.deployment.serverless.base_handler import BaseHandler

class GCPCloudFunctionsHandler(BaseHandler):
    """GCP Cloud Functions handler using facade pattern."""

    def gcp_handler(self, request):
        """GCP Cloud Functions HTTP entry point."""
        # Convert Flask request to standard dict
        event = {
            "httpMethod": request.method,
            "body": request.get_data(as_text=True),
            "queryStringParameters": dict(request.args),
            "headers": dict(request.headers)
        }

        # Use base handler
        result = self.handle_request_sync(event, None)

        # Return Flask response
        return (result["body"], result["statusCode"], result["headers"])

# Global handler instance
_gcp_handler_instance = None

@functions_framework.http
def main(request):
    """GCP Cloud Functions entry point."""
    global _gcp_handler_instance

    if _gcp_handler_instance is None:
        _gcp_handler_instance = GCPCloudFunctionsHandler()

    return _gcp_handler_instance.gcp_handler(request)
```

**GCP Configuration (gcloud):**
```bash
# Deploy function
gcloud functions deploy agentmap-execute-workflow \
    --runtime python311 \
    --trigger-http \
    --entry-point main \
    --source . \
    --allow-unauthenticated \
    --memory 512MB \
    --timeout 300s \
    --set-env-vars AGENTMAP_CONFIG_FILE=gs://my-bucket/agentmap_config.yaml
```

### 5.5 Trigger Strategies

**Base Handler with Trigger Detection:**
```python
# deployment/serverless/base_handler.py
class BaseHandler:
    """Base handler for serverless functions."""

    def __init__(self, config_file: Optional[str] = None):
        self.config_file = config_file
        self.trigger_strategies = self._initialize_strategies()

    def handle_request_sync(self, event: Dict, context: Any) -> Dict:
        """Handle request synchronously."""
        try:
            # Detect trigger type
            strategy = self._detect_trigger_strategy(event)

            # Parse event
            params = strategy.parse_event(event)

            # Execute workflow
            result = WorkflowOrchestrationService.execute_workflow(
                workflow=params.get("workflow"),
                graph_name=params.get("graph_name"),
                initial_state=params.get("initial_state"),
                config_file=self.config_file
            )

            # Format response
            return ResponseFormatter.for_serverless(result)

        except Exception as e:
            return self._handle_error(e)

    def _detect_trigger_strategy(self, event: Dict) -> TriggerStrategy:
        """Detect event type and return appropriate strategy."""
        if "httpMethod" in event:
            return self.trigger_strategies["http"]
        elif "Records" in event:
            if "eventSource" in event["Records"][0]:
                source = event["Records"][0]["eventSource"]
                if source == "aws:sqs":
                    return self.trigger_strategies["aws_sqs"]
                elif source == "aws:s3":
                    return self.trigger_strategies["aws_s3"]
                elif source == "aws:dynamodb":
                    return self.trigger_strategies["aws_ddb_stream"]
        # ... more detection logic

        return self.trigger_strategies["http"]  # Default
```

**Trigger Strategy Implementations:**

```python
# deployment/serverless/trigger_strategies/http_strategy.py
class HTTPTriggerStrategy:
    """Parse HTTP API Gateway events."""

    def parse_event(self, event: Dict) -> Dict:
        """Extract workflow parameters from HTTP request."""
        if event.get("httpMethod", "").upper() == "POST":
            body = json.loads(event.get("body", "{}"))
        else:
            body = event.get("queryStringParameters", {})

        path_params = event.get("pathParameters", {})

        return {
            "workflow": path_params.get("workflow"),
            "graph_name": path_params.get("graph"),
            "initial_state": body.get("initial_state", {}),
            **body
        }

# deployment/serverless/trigger_strategies/aws_sqs_strategy.py
class AWSSQSTriggerStrategy:
    """Parse SQS queue messages."""

    def parse_event(self, event: Dict) -> Dict:
        """Extract workflow parameters from SQS message."""
        record = event["Records"][0]
        body = json.loads(record["body"])

        return {
            "workflow": body.get("workflow"),
            "graph_name": body.get("graph_name"),
            "initial_state": body.get("initial_state", {}),
            "message_id": record["messageId"]
        }

# deployment/serverless/trigger_strategies/aws_s3_strategy.py
class AWSS3TriggerStrategy:
    """Parse S3 object creation events."""

    def parse_event(self, event: Dict) -> Dict:
        """Extract workflow parameters from S3 event."""
        record = event["Records"][0]
        s3_info = record["s3"]

        bucket = s3_info["bucket"]["name"]
        key = s3_info["object"]["key"]

        return {
            "workflow": "s3_processing",  # Default workflow
            "graph_name": "ProcessS3File",
            "initial_state": {
                "bucket": bucket,
                "key": key,
                "size": s3_info["object"]["size"]
            }
        }
```

### 5.6 Cold Start Optimization

**Strategies:**

```python
# 1. Global handler instance (reuse across invocations)
_handler_instance = None

def lambda_handler(event, context):
    global _handler_instance
    if _handler_instance is None:
        _handler_instance = AWSLambdaHandler()
    return _handler_instance.lambda_handler(event, context)

# 2. Lazy service initialization
# Services created only when needed via DI

# 3. Bundle caching
# Bundles loaded from cache on warm starts

# 4. Connection pooling
# HTTP connections reused across invocations
```

**Performance Metrics:**

| Metric | Cold Start | Warm Start |
|--------|------------|------------|
| Container init | ~500ms | 0ms (reused) |
| DI initialization | ~200ms | 0ms (cached) |
| Bundle loading | ~25ms (static) | ~1ms (cached) |
| Total overhead | ~725ms | ~1ms |

---

## 6. Configuration Management

### 6.1 Configuration Discovery

**Priority Order:**

```
1. Explicit config_file parameter (highest)
2. Environment variable: AGENTMAP_CONFIG_FILE
3. agentmap_config.yaml in current directory
4. ~/.agentmap/agentmap_config.yaml
5. System defaults (lowest)
```

### 6.2 Deployment-Specific Configuration

**CLI Configuration:**
```yaml
# agentmap_config.yaml (local development)
execution:
  use_direct_import_agents: true
  default_success_policy: "all_nodes"

storage:
  cache_folder: "~/.agentmap/cache"
  csv_repository_path: "~/.agentmap/csv_repository"

logging:
  level: "DEBUG"
  log_to_file: true
  log_file: "./agentmap.log"
```

**HTTP Configuration:**
```yaml
# agentmap_config.yaml (HTTP server)
execution:
  use_direct_import_agents: true

storage:
  cache_folder: "/var/cache/agentmap"
  csv_repository_path: "/app/workflows"

logging:
  level: "INFO"
  format: "json"
  log_to_file: false  # Use stdout for container logs

auth:
  enabled: true
  api_key_required: true
```

**Serverless Configuration:**
```yaml
# agentmap_config.yaml (Lambda/Azure/GCP)
execution:
  use_direct_import_agents: true
  enable_checkpoints: false  # Use external checkpoint storage

storage:
  cache_folder: "/tmp/agentmap/cache"  # Ephemeral
  use_s3_for_bundles: true
  bundle_bucket: "agentmap-bundles"

logging:
  level: "INFO"
  format: "json"
  correlation_id_enabled: true

performance:
  bundle_cache_enabled: true
  preload_services: ["llm_service", "storage_service"]
```

### 6.3 Environment Variables

**Common Variables:**
```bash
# API Keys
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=...

# Storage
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AZURE_STORAGE_CONNECTION_STRING=...
GOOGLE_APPLICATION_CREDENTIALS=/path/to/credentials.json

# Configuration
AGENTMAP_CONFIG_FILE=/path/to/config.yaml
AGENTMAP_LOG_LEVEL=INFO
AGENTMAP_CACHE_FOLDER=/var/cache/agentmap
```

**Deployment-Specific:**
```bash
# CLI (local development)
export AGENTMAP_LOG_LEVEL=DEBUG
export AGENTMAP_CACHE_FOLDER=./cache

# HTTP (Docker container)
ENV AGENTMAP_LOG_LEVEL=INFO
ENV AGENTMAP_CACHE_FOLDER=/var/cache/agentmap
ENV AGENTMAP_AUTH_ENABLED=true

# Serverless (Lambda environment)
AGENTMAP_CACHE_FOLDER=/tmp/agentmap/cache
AGENTMAP_USE_S3_FOR_BUNDLES=true
AGENTMAP_BUNDLE_BUCKET=agentmap-bundles
```

---

## 7. Authentication & Security

### 7.1 Authentication Methods

**API Key Authentication:**
```python
# HTTP header
X-API-Key: agm_abc123def456...

# Verification
auth_service.verify_api_key(api_key)
```

**Bearer Token Authentication:**
```python
# HTTP header
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# Verification
auth_service.verify_bearer_token(token)
```

**Public Mode:**
```yaml
# agentmap_config.yaml
auth:
  enabled: false  # No authentication required
```

### 7.2 Security Best Practices

**API Keys:**
```bash
# Generate API key
agentmap auth generate-key --name "production-key"

# Store in environment (not in code)
export AGENTMAP_API_KEY=agm_...

# Rotate keys regularly
agentmap auth revoke-key <old-key>
agentmap auth generate-key --name "new-key"
```

**Secrets Management:**
```python
# Never hardcode secrets
# ❌ Bad
llm_service.call_llm(api_key="sk-...")

# ✅ Good
llm_service.call_llm()  # Reads from environment
```

**Network Security:**
```yaml
# Use HTTPS in production
# Configure reverse proxy (nginx, ALB)

# CORS configuration
cors:
  allow_origins:
    - https://app.example.com
  allow_credentials: true
```

---

## 8. Monitoring & Observability

### 8.1 Logging

**Structured Logging:**
```python
# All deployments use structured logging
logger.info(
    "Workflow executed",
    extra={
        "workflow": workflow_name,
        "graph": graph_name,
        "duration": execution_time,
        "success": result.success
    }
)
```

**Log Aggregation:**
```yaml
# CLI: Local file
logging:
  log_to_file: true
  log_file: "./agentmap.log"

# HTTP: Stdout (captured by container runtime)
logging:
  log_to_file: false

# Serverless: CloudWatch/AppInsights/Cloud Logging (automatic)
```

### 8.2 Metrics

**Execution Metrics:**
```python
# Tracked automatically by ExecutionTrackingService
- workflow_execution_time
- node_execution_time
- node_success_rate
- workflow_success_rate
```

**System Metrics:**
```python
# Available via diagnose endpoint
- cache_hit_rate
- bundle_creation_time
- service_availability
- llm_api_latency
```

### 8.3 Tracing (Future)

**OpenTelemetry Integration (Planned):**
```python
# Automatic tracing across all deployments
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

with tracer.start_as_current_span("execute_workflow"):
    result = WorkflowOrchestrationService.execute_workflow(...)
```

---

## 9. Deployment Best Practices

### 9.1 CLI Deployment

**Best Practices:**
- Use virtual environments for isolation
- Pin dependency versions in requirements.txt
- Configure logging for debugging
- Use `--validate-csv` flag in CI/CD
- Store workflows in version control

**CI/CD Integration:**
```bash
# .github/workflows/test.yml
- name: Validate workflows
  run: |
    agentmap validate --csv workflows/*.csv

- name: Run workflow tests
  run: |
    agentmap run workflows/test.csv --graph TestGraph
```

### 9.2 HTTP Deployment

**Production Checklist:**
- [ ] Enable authentication
- [ ] Configure CORS appropriately
- [ ] Use HTTPS (reverse proxy)
- [ ] Set up health checks
- [ ] Configure log aggregation
- [ ] Monitor error rates
- [ ] Set resource limits
- [ ] Use multiple workers (Gunicorn)
- [ ] Configure graceful shutdown
- [ ] Implement rate limiting

**Docker Deployment:**
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY src/ ./src/
COPY agentmap_config.yaml .

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Run server
CMD ["uvicorn", "agentmap.deployment.http.api.server:create_fastapi_app", \
     "--factory", "--host", "0.0.0.0", "--port", "8000"]
```

### 9.3 Serverless Deployment

**Best Practices:**
- Optimize cold start time (minimize dependencies)
- Use environment variables for configuration
- Configure appropriate timeout (workflows can be long)
- Set adequate memory (512MB minimum)
- Use dead letter queues for failed executions
- Monitor invocation metrics
- Implement retry logic for transient failures
- Use VPC only if needed (adds cold start time)

**Cost Optimization:**
```yaml
# Right-size memory allocation
functions:
  execute_workflow:
    memorySize: 512  # Start here, adjust based on metrics
    timeout: 300     # 5 minutes max for most workflows

# Use reserved concurrency for predictable workloads
    reservedConcurrency: 10

# Enable provisioned concurrency for low-latency requirements
    provisionedConcurrency: 2
```

---

## 10. Troubleshooting

### 10.1 Common Issues

**Issue: "AgentMap not initialized"**
```
Cause: Container not initialized before use
Solution: Ensure ensure_initialized() called first
```

**Issue: "Bundle not found"**
```
Cause: Cache invalidated or bundle never created
Solution: Run with validate_csv=True or agentmap refresh
```

**Issue: "Service unavailable"**
```
Cause: Required service dependency missing
Solution: Check dependencies with agentmap diagnose
```

**Issue: "Authentication failed"**
```
Cause: Invalid or expired API key/token
Solution: Regenerate key with agentmap auth generate-key
```

### 10.2 Diagnostic Commands

```bash
# Check system health
agentmap diagnose

# Check workflow-specific issues
agentmap diagnose --csv workflow.csv

# Validate workflow
agentmap validate --csv workflow.csv

# Refresh bundle cache
agentmap refresh --csv workflow.csv
agentmap refresh --all

# Test workflow execution
agentmap run workflow.csv --graph TestGraph --state '{"test": true}'
```

---

## 11. Related Documentation

- **[SYSTEM_ARCHITECTURE.md](./SYSTEM_ARCHITECTURE.md)**: Core architectural patterns
- **[SERVICE_CATALOG.md](./SERVICE_CATALOG.md)**: Service inventory and details
- **[HTTP API Reference](../../docs-docusaurus/docs/deployment/06-http-api-reference.md)**: HTTP endpoint documentation
- **[CLI Commands](../../docs-docusaurus/docs/deployment/04-cli-commands.md)**: Complete CLI reference

---

**End of Deployment Architecture Document**
