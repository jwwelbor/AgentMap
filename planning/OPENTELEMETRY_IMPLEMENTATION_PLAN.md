# OpenTelemetry Implementation Plan for AgentMap

**Author:** DevOps Agent
**Date:** 2025-11-19
**Status:** Draft
**Target Version:** 0.3.0

---

## Executive Summary

This document outlines a comprehensive plan to integrate OpenTelemetry (OTEL) into AgentMap, enabling distributed tracing, metrics collection, and log correlation across all deployment modes (CLI, HTTP API, Serverless). The implementation leverages AgentMap's existing DI architecture and execution tracking infrastructure to provide observability with minimal code changes.

---

## Table of Contents

1. [Goals and Objectives](#1-goals-and-objectives)
2. [Architecture Overview](#2-architecture-overview)
3. [Dependencies](#3-dependencies)
4. [Configuration Model](#4-configuration-model)
5. [Implementation Phases](#5-implementation-phases)
6. [Instrumentation Points](#6-instrumentation-points)
7. [Service Design](#7-service-design)
8. [Testing Strategy](#8-testing-strategy)
9. [Deployment Considerations](#9-deployment-considerations)
10. [Migration Path](#10-migration-path)

---

## 1. Goals and Objectives

### Primary Goals

1. **Distributed Tracing** - Track workflow execution across all nodes with span propagation
2. **Metrics Collection** - Capture latency, throughput, and error rates for workflows and agents
3. **Log Correlation** - Correlate logs with trace/span IDs for unified observability
4. **Backend Flexibility** - Support multiple backends (Jaeger, Zipkin, OTLP, Prometheus)

### Success Criteria

- [ ] All workflow executions generate proper traces with spans per node
- [ ] LLM agent calls include token usage and latency metrics
- [ ] HTTP API requests are automatically instrumented
- [ ] Configuration-driven enablement (can disable with zero overhead)
- [ ] Less than 5% performance overhead when enabled
- [ ] Backward compatible with existing execution tracking

### Non-Goals

- Real-time alerting (handled by backend systems)
- APM-specific features (vendor-specific implementations)
- Automatic error remediation

---

## 2. Architecture Overview

### Current State

```
┌─────────────────────────────────────────────────┐
│              AgentMap Application               │
├─────────────────────────────────────────────────┤
│  LoggingService ──► Python logging              │
│  ExecutionTrackingService ──► In-memory tracker │
│  No distributed tracing                         │
│  No metrics collection                          │
└─────────────────────────────────────────────────┘
```

### Target State

```
┌─────────────────────────────────────────────────────────────┐
│                    AgentMap Application                     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────┐    ┌─────────────────────┐        │
│  │  TelemetryService   │    │   LoggingService    │        │
│  │  (OTEL Provider)    │◄───┤   (OTEL Handler)    │        │
│  └─────────┬───────────┘    └─────────────────────┘        │
│            │                                                │
│  ┌─────────▼───────────┐    ┌─────────────────────┐        │
│  │   TracerProvider    │    │   MeterProvider     │        │
│  │   (Spans)           │    │   (Metrics)         │        │
│  └─────────┬───────────┘    └─────────┬───────────┘        │
│            │                          │                     │
│  ┌─────────▼──────────────────────────▼───────────┐        │
│  │              Exporters (Configurable)          │        │
│  │  OTLP │ Jaeger │ Zipkin │ Prometheus │ Console │        │
│  └─────────────────────────────────────────────────┘        │
│                                                             │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
              ┌───────────────────────────┐
              │   Observability Backend   │
              │  (Jaeger/Grafana/etc.)    │
              └───────────────────────────┘
```

### Integration Points

| Component | Integration Type | Purpose |
|-----------|-----------------|---------|
| `ApplicationContainer` | Provider Registration | Initialize OTEL at startup |
| `GraphExecutionService` | Root Span | Parent span for workflow execution |
| `ExecutionTrackingService` | Child Spans | Span per node execution |
| `BaseAgent` | Span Decorator | Instrument agent execution |
| `LLMAgent` | Semantic Conventions | LLM-specific attributes |
| `FastAPI Server` | Middleware | HTTP request tracing |
| `LoggingService` | Log Handler | Trace/span ID injection |

---

## 3. Dependencies

### Required Packages

Add to `pyproject.toml`:

```toml
[tool.poetry.dependencies]
# Core OTEL SDK
opentelemetry-api = "^1.27.0"
opentelemetry-sdk = "^1.27.0"

# Instrumentation
opentelemetry-instrumentation = "^0.48b0"
opentelemetry-instrumentation-fastapi = "^0.48b0"
opentelemetry-instrumentation-logging = "^0.48b0"
opentelemetry-instrumentation-requests = "^0.48b0"  # For HTTP calls

# Exporters (all optional, configurable)
opentelemetry-exporter-otlp = "^1.27.0"
opentelemetry-exporter-jaeger = "^1.21.0"
opentelemetry-exporter-prometheus = "^0.48b0"

# Semantic conventions
opentelemetry-semantic-conventions = "^0.48b0"
```

### Beta Package Risk Management

**Risk:** Several instrumentation packages (e.g., `^0.48b0`) are in beta and may introduce breaking changes in future updates.

**Mitigation Strategy:**

1. **Pin exact versions in production** - Use exact versions (e.g., `==0.48b0`) in production deployments to ensure stability
2. **Separate dependency group** - Consider placing beta packages in an optional group:
   ```toml
   [tool.poetry.group.otel.dependencies]
   ```
3. **Version monitoring** - Track OpenTelemetry release notes for graduation to stable
4. **Upgrade cadence** - Plan quarterly reviews of OTEL dependencies
5. **Migration budget** - Allocate 1-2 days per quarter for dependency updates and API changes
6. **Test coverage** - Ensure comprehensive tests for all OTEL integrations to catch breaking changes early

**Timeline:** Beta packages typically graduate to stable within 6-12 months. Plan for migration work when stable versions are released.

### Optional AI/LLM Instrumentation

```toml
[tool.poetry.group.otel-llm.dependencies]
# For LangChain-specific instrumentation
opentelemetry-instrumentation-langchain = "^0.1.0"  # If available
```

### Version Compatibility

- OpenTelemetry API/SDK: 1.27.0+ (stable APIs)
- Python: 3.11+ (matches AgentMap requirement)
- FastAPI instrumentation: Match FastAPI 0.111.0

---

## 4. Configuration Model

### YAML Configuration

Add to `agentmap_config.yaml`:

```yaml
telemetry:
  enabled: true
  service_name: "agentmap"
  service_version: "${AGENTMAP_VERSION:-0.3.0}"

  # Tracing configuration
  tracing:
    enabled: true
    sampler:
      type: "parentbased_traceidratio"  # or "always_on", "always_off"
      ratio: 1.0  # Sample 100% in dev, lower in prod
    propagators:
      - "tracecontext"
      - "baggage"

  # Metrics configuration
  metrics:
    enabled: true
    export_interval_ms: 60000  # 1 minute

  # Logging integration
  logging:
    enabled: true
    inject_trace_context: true  # Add trace_id/span_id to logs

  # Exporters configuration
  exporters:
    # OTLP (recommended for production)
    otlp:
      enabled: false
      endpoint: "http://localhost:4317"
      headers: {}
      compression: "gzip"
      timeout_ms: 10000

    # Jaeger (for local development)
    jaeger:
      enabled: true
      agent_host: "localhost"
      agent_port: 6831

    # Prometheus (metrics only)
    prometheus:
      enabled: false
      port: 9464

    # Console (for debugging)
    console:
      enabled: false
      pretty_print: true

  # Resource attributes
  resource_attributes:
    deployment.environment: "${ENVIRONMENT:-development}"
    host.name: "${HOSTNAME:-unknown}"

  # Instrumentation toggles
  instrumentation:
    fastapi: true
    requests: true
    langchain: true  # If instrumentation available
```

### Pydantic Configuration Model

Create `src/agentmap/models/telemetry_config.py`:

```python
from pydantic import BaseModel, Field
from typing import Dict, List, Optional
from enum import Enum

class SamplerType(str, Enum):
    ALWAYS_ON = "always_on"
    ALWAYS_OFF = "always_off"
    TRACEIDRATIO = "traceidratio"
    PARENTBASED_TRACEIDRATIO = "parentbased_traceidratio"

class SamplerConfig(BaseModel):
    type: SamplerType = SamplerType.PARENTBASED_TRACEIDRATIO
    ratio: float = Field(1.0, ge=0.0, le=1.0)

class TracingConfig(BaseModel):
    enabled: bool = True
    sampler: SamplerConfig = Field(default_factory=SamplerConfig)
    propagators: List[str] = ["tracecontext", "baggage"]

class MetricsConfig(BaseModel):
    enabled: bool = True
    export_interval_ms: int = 60000

class LoggingIntegrationConfig(BaseModel):
    enabled: bool = True
    inject_trace_context: bool = True

class OTLPExporterConfig(BaseModel):
    enabled: bool = False
    endpoint: str = "http://localhost:4317"
    headers: Dict[str, str] = {}
    compression: str = "gzip"
    timeout_ms: int = 10000

class JaegerExporterConfig(BaseModel):
    enabled: bool = False
    agent_host: str = "localhost"
    agent_port: int = 6831

class PrometheusExporterConfig(BaseModel):
    enabled: bool = False
    port: int = 9464

class ConsoleExporterConfig(BaseModel):
    enabled: bool = False
    pretty_print: bool = True

class ExportersConfig(BaseModel):
    otlp: OTLPExporterConfig = Field(default_factory=OTLPExporterConfig)
    jaeger: JaegerExporterConfig = Field(default_factory=JaegerExporterConfig)
    prometheus: PrometheusExporterConfig = Field(default_factory=PrometheusExporterConfig)
    console: ConsoleExporterConfig = Field(default_factory=ConsoleExporterConfig)

class InstrumentationConfig(BaseModel):
    fastapi: bool = True
    requests: bool = True
    langchain: bool = True

class TelemetryConfigModel(BaseModel):
    enabled: bool = False
    service_name: str = "agentmap"
    service_version: str = "0.3.0"
    tracing: TracingConfig = Field(default_factory=TracingConfig)
    metrics: MetricsConfig = Field(default_factory=MetricsConfig)
    logging: LoggingIntegrationConfig = Field(default_factory=LoggingIntegrationConfig)
    exporters: ExportersConfig = Field(default_factory=ExportersConfig)
    resource_attributes: Dict[str, str] = {}
    instrumentation: InstrumentationConfig = Field(default_factory=InstrumentationConfig)
```

---

## 5. Implementation Phases

### Phase 1: Foundation (Week 1-2)

**Objective:** Set up OTEL infrastructure and basic tracing

#### Tasks

1. **Add dependencies to pyproject.toml**
   - Core OTEL packages
   - Exporter packages
   - Run `poetry lock && poetry install`

2. **Create TelemetryService**
   - Location: `src/agentmap/services/telemetry_service.py`
   - Responsibilities:
     - Initialize TracerProvider, MeterProvider
     - Configure exporters based on config
     - Provide tracer/meter access
     - Shutdown handling

3. **Create configuration models**
   - Location: `src/agentmap/models/telemetry_config.py`
   - Add to main config model

4. **Register in DI container**
   - Location: `src/agentmap/di/container_parts/`
   - Create `telemetry_parts.py`
   - Wire into ApplicationContainer

5. **Basic workflow tracing**
   - Add root span to `GraphExecutionService`
   - Propagate context to node executions

#### Deliverables

- [ ] TelemetryService with TracerProvider
- [ ] Configuration model and YAML schema
- [ ] Root span for workflow execution
- [ ] Console exporter working
- [ ] Unit tests for TelemetryService

---

### Phase 2: Node-Level Instrumentation (Week 3-4)

**Objective:** Instrument individual node/agent executions

#### Tasks

1. **Instrument ExecutionTrackingService**
   - Create child spans for `record_node_start/end`
   - Attach execution data as span attributes
   - Handle errors with span status

2. **Instrument BaseAgent**
   - Add span creation in `execute()` method
   - Include agent type, context, and output size
   - Support async agents

3. **LLM Agent semantic conventions**
   - Token usage (input/output/total)
   - Model name and provider
   - Temperature and other parameters
   - Latency breakdown

4. **Storage agent instrumentation**
   - Operation type (read/write)
   - Record count
   - Storage type (CSV, JSON, etc.)

#### Deliverables

- [ ] Span per node execution
- [ ] LLM-specific attributes
- [ ] Storage operation spans
- [ ] Nested subgraph support
- [ ] Integration tests

---

### Phase 3: Metrics Collection (Week 5-6)

**Objective:** Add metrics for performance monitoring

#### Tasks

1. **Define metrics**
   ```python
   # Counters
   - agentmap.workflow.executions (total workflows run)
   - agentmap.node.executions (total nodes executed)
   - agentmap.agent.errors (errors by agent type)

   # Histograms
   - agentmap.workflow.duration (workflow execution time)
   - agentmap.node.duration (node execution time)
   - agentmap.llm.latency (LLM call latency)
   - agentmap.llm.tokens (token usage)

   # Gauges
   - agentmap.workflow.active (currently running workflows)
   ```

2. **Implement metrics recording in services**
   - Components acquire `Meter` instances via `TelemetryService.get_meter()`
   - Record metrics directly at instrumentation points (no separate MetricsService needed)
   - Define metric instruments (counters, histograms) as module-level singletons
   - Add Prometheus endpoint (optional)

   > **Note:** A separate MetricsService is not required. The `TelemetryService.get_meter()`
   > method follows the standard OpenTelemetry pattern where components directly acquire meters
   > and record metrics. This keeps telemetry centralized while avoiding unnecessary abstraction.

3. **Dashboard templates**
   - Grafana dashboard JSON
   - Key metrics visualization

#### Deliverables

- [ ] Counters, histograms, gauges
- [ ] Prometheus exporter
- [ ] Grafana dashboard template
- [ ] Metrics documentation

---

### Phase 4: HTTP API Integration (Week 7)

**Objective:** Full HTTP API observability

#### Tasks

1. **FastAPI middleware**
   - Use opentelemetry-instrumentation-fastapi
   - Configure in server startup
   - Request/response attributes

2. **Endpoint-specific spans**
   - `/workflow/{name}/run` - workflow execution
   - `/workflow/{name}/status` - status checks
   - `/graphs` - graph listing

3. **Error handling**
   - HTTP status code mapping
   - Exception recording

#### Deliverables

- [ ] Automatic HTTP request tracing
- [ ] Request/response attributes
- [ ] Error span status
- [ ] Integration tests

---

### Phase 5: Log Correlation (Week 8)

**Objective:** Unified logs with trace context

#### Tasks

1. **Integrate OTEL log handler**
   - Modify LoggingService configuration
   - Inject trace_id and span_id
   - Format handler setup

2. **Update log format**
   ```
   %(asctime)s [%(levelname)s] [trace_id=%(otelTraceId)s span_id=%(otelSpanId)s] %(name)s: %(message)s
   ```

3. **Log export to OTEL**
   - Optional: Export logs via OTLP
   - Configure log exporter

#### Deliverables

- [ ] Trace context in all logs
- [ ] Log format with OTEL fields
- [ ] Optional OTLP log export
- [ ] Documentation update

---

### Phase 6: Advanced Features (Week 9-10)

**Objective:** Production-ready enhancements

#### Tasks

1. **Sampling strategies**
   - ParentBased sampler
   - Rate limiting sampler
   - Custom sampler for long workflows

2. **Context propagation**
   - HTTP headers (W3C Trace Context)
   - State-based propagation
   - Cross-workflow correlation

3. **Baggage support**
   - User ID propagation
   - Request ID correlation
   - Custom attributes

4. **Performance optimization**
   - Batch span processor
   - Async export
   - Memory limits

#### Deliverables

- [ ] Configurable sampling
- [ ] Context propagation
- [ ] Performance benchmarks
- [ ] Production documentation

---

## 6. Instrumentation Points

### Critical Instrumentation

| Location | Span Name | Type | Attributes |
|----------|-----------|------|------------|
| `GraphExecutionService.execute_compiled_graph()` | `{graph_name}.execute` | Root | graph_name, inputs_count, config |
| `ExecutionTrackingService.record_node_start()` | `{node_name}.execute` | Child | node_name, agent_type, context_keys |
| `BaseAgent.execute()` | `agent.{type}.execute` | Child | agent_type, description, output_size |
| `LLMAgent._call_llm()` | `llm.{provider}.call` | Child | model, tokens_*, temperature |
| `StorageAgent.read/write()` | `storage.{type}.{op}` | Child | storage_type, record_count |

### HTTP API Instrumentation

| Endpoint | Span Name | Attributes |
|----------|-----------|------------|
| `POST /workflow/{name}/run` | `http.workflow.run` | graph_name, input_keys |
| `GET /workflow/{name}/status` | `http.workflow.status` | graph_name, thread_id |
| `GET /graphs` | `http.graphs.list` | count |

### Semantic Conventions

Follow OpenTelemetry semantic conventions:

```python
from opentelemetry.semconv.trace import SpanAttributes

# General service attributes
service_attributes = {
    SpanAttributes.SERVICE_NAME: "agentmap",
}

# LLM (proposed conventions)
# Example attributes for an LLM span
llm_attributes = {
    "gen_ai.system": "openai",  # or "anthropic", "google"
    "gen_ai.request.model": "gpt-4",
    "gen_ai.request.temperature": 0.7,
    "gen_ai.usage.input_tokens": 150,
    "gen_ai.usage.output_tokens": 500,
    "gen_ai.usage.total_tokens": 650,
}

# Custom AgentMap conventions
agentmap_attributes = {
    "agentmap.graph.name": "my_workflow",
    "agentmap.node.name": "process_data",
    "agentmap.agent.type": "OpenAIAgent",
    "agentmap.execution.success": True,
}

# Usage in span creation
with tracer.start_as_current_span("llm.openai.call") as span:
    span.set_attributes(llm_attributes)
    span.set_attributes(agentmap_attributes)
```

---

## 7. Service Design

### TelemetryService

```python
# src/agentmap/services/telemetry_service.py

from typing import Optional
from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.resources import Resource
from opentelemetry.trace import Tracer
from opentelemetry.metrics import Meter

class TelemetryService:
    """
    Centralized OpenTelemetry service for AgentMap.

    Manages TracerProvider, MeterProvider, and exporters.
    Follows DI-only pattern (no global state).
    """

    def __init__(self, config: TelemetryConfigModel):
        self._config = config
        self._tracer_provider: Optional[TracerProvider] = None
        self._meter_provider: Optional[MeterProvider] = None
        self._initialized = False

    def initialize(self) -> None:
        """Initialize OTEL providers and exporters."""
        if not self._config.enabled:
            return

        # Create resource
        resource = self._create_resource()

        # Initialize tracing
        if self._config.tracing.enabled:
            self._init_tracing(resource)

        # Initialize metrics
        if self._config.metrics.enabled:
            self._init_metrics(resource)

        self._initialized = True

    def get_tracer(self, name: str) -> Tracer:
        """Get a tracer for the given instrumentation scope."""
        if not self._initialized or not self._config.tracing.enabled:
            return trace.get_tracer(name)  # No-op tracer
        return self._tracer_provider.get_tracer(name)

    def get_meter(self, name: str) -> Meter:
        """Get a meter for the given instrumentation scope."""
        if not self._initialized or not self._config.metrics.enabled:
            return metrics.get_meter(name)  # No-op meter
        return self._meter_provider.get_meter(name)

    def shutdown(self) -> None:
        """Gracefully shutdown providers."""
        if self._tracer_provider:
            self._tracer_provider.shutdown()
        if self._meter_provider:
            self._meter_provider.shutdown()

    def _create_resource(self) -> Resource:
        """Create OTEL resource with service info."""
        return Resource.create({
            "service.name": self._config.service_name,
            "service.version": self._config.service_version,
            **self._config.resource_attributes
        })

    def _init_tracing(self, resource: Resource) -> None:
        """Initialize TracerProvider with exporters."""
        # Implementation details...
        pass

    def _init_metrics(self, resource: Resource) -> None:
        """Initialize MeterProvider with exporters."""
        # Implementation details...
        pass
```

### DI Container Integration

```python
# src/agentmap/di/container_parts/telemetry_parts.py

from dependency_injector import containers, providers

class TelemetryContainer(containers.DeclarativeContainer):
    """Container for telemetry-related services."""

    config = providers.Configuration()

    telemetry_config = providers.Singleton(
        TelemetryConfigModel,
        **config.telemetry
    )

    telemetry_service = providers.Singleton(
        TelemetryService,
        config=telemetry_config
    )
```

### Instrumentation Decorator

The `traced` decorator relies on `self._telemetry_service` being available on the decorated class. There are two approaches for dependency injection:

**Approach 1: Protocol-based injection (Recommended)**

Classes that use the decorator must implement a protocol or inherit from a mixin that provides `_telemetry_service`. This follows AgentMap's existing pattern with `BaseAgent`:

```python
# src/agentmap/services/telemetry_service.py

from functools import wraps
from typing import Protocol
from opentelemetry.trace import Status, StatusCode

class TelemetryAware(Protocol):
    """Protocol for classes that can be instrumented with telemetry."""
    _telemetry_service: 'TelemetryService'

def traced(span_name: str = None, attributes: dict = None):
    """
    Decorator to automatically trace function execution.

    Requirements:
        The decorated method's class must have a `_telemetry_service` attribute.
        This is typically injected via DI in the constructor.

    Usage:
        class MyService:
            def __init__(self, telemetry_service: TelemetryService):
                self._telemetry_service = telemetry_service

            @traced("my_operation", {"key": "value"})
            def my_function(self):
                pass
    """
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            tracer = self._telemetry_service.get_tracer(__name__)
            name = span_name or f"{self.__class__.__name__}.{func.__name__}"

            with tracer.start_as_current_span(name) as span:
                if attributes:
                    for key, value in attributes.items():
                        span.set_attribute(key, value)

                try:
                    result = func(self, *args, **kwargs)
                    span.set_status(Status(StatusCode.OK))
                    return result
                except Exception as e:
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    span.record_exception(e)
                    raise

        return wrapper
    return decorator
```

**Approach 2: BaseAgent integration**

For agents, the `TelemetryService` will be injected via the existing `BaseAgent` constructor pattern:

```python
# In BaseAgent.__init__
def __init__(self, ..., telemetry_service: TelemetryService = None):
    self._telemetry_service = telemetry_service or NoOpTelemetryService()
```

This ensures all agents automatically have access to telemetry without requiring code changes to individual agent implementations.

---

## 8. Testing Strategy

### Unit Tests

```python
# tests/unit/services/test_telemetry_service.py

import pytest
from unittest.mock import Mock, patch
from agentmap.services.telemetry_service import TelemetryService
from agentmap.models.telemetry_config import TelemetryConfigModel

class TestTelemetryService:

    def test_disabled_telemetry_returns_noop(self):
        """When disabled, should return no-op tracer."""
        config = TelemetryConfigModel(enabled=False)
        service = TelemetryService(config)
        service.initialize()

        tracer = service.get_tracer("test")
        # Verify no-op behavior

    def test_initialization_creates_providers(self):
        """Should create providers when enabled."""
        config = TelemetryConfigModel(
            enabled=True,
            exporters={"console": {"enabled": True}}
        )
        service = TelemetryService(config)
        service.initialize()

        assert service._tracer_provider is not None
        assert service._meter_provider is not None

    def test_span_creation(self):
        """Should create spans with correct attributes."""
        # Test implementation
        pass

    def test_shutdown_cleanup(self):
        """Should properly shutdown providers."""
        # Test implementation
        pass
```

### Integration Tests

```python
# tests/integration/test_telemetry_integration.py

import pytest
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

class TestTelemetryIntegration:

    @pytest.fixture
    def memory_exporter(self):
        return InMemorySpanExporter()

    def test_workflow_creates_spans(self, memory_exporter, container):
        """Workflow execution should create expected spans."""
        # Run workflow
        result = container.runtime().run_workflow("test_graph", {})

        # Check spans
        spans = memory_exporter.get_finished_spans()
        span_names = [s.name for s in spans]

        assert "test_graph.execute" in span_names
        # Verify node spans exist

    def test_error_recording(self, memory_exporter, container):
        """Errors should be recorded in span status."""
        # Run failing workflow
        # Check span status is ERROR
        pass

    def test_llm_attributes(self, memory_exporter, container):
        """LLM calls should have token usage attributes."""
        # Run LLM workflow
        # Check gen_ai.usage.* attributes
        pass
```

### Performance Tests

```python
# tests/performance/test_telemetry_overhead.py

import pytest
import time

class TestTelemetryPerformance:

    def test_overhead_under_threshold(self, container):
        """Telemetry overhead should be under 5%."""
        # Baseline without telemetry
        start = time.time()
        for _ in range(100):
            run_workflow_without_telemetry()
        baseline = time.time() - start

        # With telemetry
        start = time.time()
        for _ in range(100):
            run_workflow_with_telemetry()
        with_telemetry = time.time() - start

        overhead = (with_telemetry - baseline) / baseline
        assert overhead < 0.05, f"Overhead {overhead:.2%} exceeds 5%"
```

---

## 9. Deployment Considerations

### Environment Variables

```bash
# Service identification
OTEL_SERVICE_NAME=agentmap
OTEL_SERVICE_VERSION=0.3.0

# Exporter configuration
OTEL_EXPORTER_OTLP_ENDPOINT=http://collector:4317
OTEL_EXPORTER_OTLP_HEADERS=api-key=xxx

# Sampling
OTEL_TRACES_SAMPLER=parentbased_traceidratio
OTEL_TRACES_SAMPLER_ARG=0.1  # 10% sampling in production

# Resource attributes
OTEL_RESOURCE_ATTRIBUTES=deployment.environment=production,host.name=prod-1
```

### Docker Compose (Development)

```yaml
# docker-compose.otel.yaml
version: '3.8'

services:
  agentmap:
    build: .
    environment:
      - OTEL_EXPORTER_OTLP_ENDPOINT=http://jaeger:4317
    depends_on:
      - jaeger

  jaeger:
    image: jaegertracing/all-in-one:latest
    ports:
      - "16686:16686"  # Jaeger UI
      - "4317:4317"    # OTLP gRPC
      - "4318:4318"    # OTLP HTTP

  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    ports:
      - "9090:9090"

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    environment:
      - GF_AUTH_ANONYMOUS_ENABLED=true
```

### Kubernetes (Production)

```yaml
# k8s/agentmap-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: agentmap
spec:
  template:
    spec:
      containers:
        - name: agentmap
          env:
            - name: OTEL_SERVICE_NAME
              value: "agentmap"
            - name: OTEL_EXPORTER_OTLP_ENDPOINT
              value: "http://otel-collector:4317"
            - name: OTEL_TRACES_SAMPLER
              value: "parentbased_traceidratio"
            - name: OTEL_TRACES_SAMPLER_ARG
              value: "0.1"
```

### Serverless (AWS Lambda)

```python
# src/agentmap/deployment/serverless/aws_lambda.py

from opentelemetry.instrumentation.aws_lambda import AwsLambdaInstrumentor

def initialize_lambda_telemetry():
    """Initialize OTEL for Lambda environment."""
    # Use Lambda-specific configuration
    # Batch processor with smaller batch size
    # Lambda extension for export
    pass

AwsLambdaInstrumentor().instrument()
```

---

## 10. Migration Path

### From Existing ExecutionTracking

The current `ExecutionTrackingService` will continue to work alongside OTEL:

1. **Phase 1:** OTEL runs in parallel, data duplication
2. **Phase 2:** Deprecate in-memory tracking for external use
3. **Phase 3:** ExecutionTracker becomes span-backed

### Backward Compatibility

- Configuration defaults to `enabled: false`
- No performance impact when disabled
- Existing APIs unchanged
- ExecutionSummary continues to work

### Migration Commands

```bash
# Verify telemetry configuration
agentmap config validate --section telemetry

# Test OTLP connectivity
agentmap telemetry test-connection

# View local traces
agentmap telemetry show-traces --last 10
```

---

## Appendix A: File Structure

```
src/agentmap/
├── models/
│   └── telemetry_config.py          # Configuration models
├── services/
│   └── telemetry_service.py         # Main telemetry service
├── di/
│   └── container_parts/
│       └── telemetry_parts.py       # DI container
├── deployment/
│   └── http/api/
│       └── middleware/
│           └── telemetry.py         # FastAPI middleware
└── instrumentation/
    ├── __init__.py
    ├── base.py                      # Base instrumentation
    ├── agents.py                    # Agent instrumentation
    └── llm.py                       # LLM-specific instrumentation
```

---

## Appendix B: Useful Resources

- [OpenTelemetry Python Documentation](https://opentelemetry.io/docs/instrumentation/python/)
- [Semantic Conventions](https://opentelemetry.io/docs/concepts/semantic-conventions/)
- [LLM Semantic Conventions (Draft)](https://github.com/open-telemetry/semantic-conventions/blob/main/docs/gen-ai/gen-ai-spans.md)
- [OTEL Collector Configuration](https://opentelemetry.io/docs/collector/configuration/)

---

## Appendix C: Estimated Timeline

| Phase | Duration | Dependencies | Risk Level |
|-------|----------|--------------|------------|
| Phase 1: Foundation | 2 weeks | None | Low |
| Phase 2: Node Instrumentation | 2 weeks | Phase 1 | Medium |
| Phase 3: Metrics | 2 weeks | Phase 1 | Low |
| Phase 4: HTTP Integration | 1 week | Phase 1 | Low |
| Phase 5: Log Correlation | 1 week | Phase 1 | Low |
| Phase 6: Advanced Features | 2 weeks | All previous | Medium |

**Total Estimated Time: 10 weeks**

---

## Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 0.1 | 2025-11-19 | DevOps Agent | Initial draft |
| 0.2 | 2025-11-20 | DevOps Agent | Address review feedback: beta package risk management, clarify metrics pattern, fix semantic conventions syntax, document decorator DI requirements |
