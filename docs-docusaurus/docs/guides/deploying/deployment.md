---
sidebar_position: 1
title: Deployment Strategies & Infrastructure
description: Comprehensive deployment strategies for AgentMap including infrastructure setup, storage services, cloud integration, and production deployment patterns.
keywords: [AgentMap deployment, infrastructure, cloud storage, production, deployment strategies, scalability]
---

# Deployment Strategies & Infrastructure

This guide covers comprehensive deployment strategies for AgentMap in production environments, including infrastructure setup, storage service configuration, cloud integration, and scalability considerations.

## Overview

AgentMap supports various deployment models to meet different organizational needs:

- **Local Development**: Quick setup for development and testing
- **Cloud-Native**: Full cloud deployment with managed services
- **Hybrid**: Combination of on-premises and cloud resources
- **Multi-Cloud**: Distributed across multiple cloud providers
- **Edge Deployment**: Distributed processing at edge locations

## Infrastructure Requirements

### System Requirements

#### Minimum Requirements
- **CPU**: 2 cores
- **Memory**: 4GB RAM
- **Storage**: 20GB available space
- **Network**: Broadband internet connection
- **OS**: Linux (Ubuntu 20.04+), macOS 10.15+, Windows 10+

#### Recommended Production Requirements
- **CPU**: 8+ cores
- **Memory**: 16GB+ RAM
- **Storage**: 100GB+ SSD storage
- **Network**: High-speed internet with redundancy
- **OS**: Linux (Ubuntu 22.04 LTS recommended)

#### High-Availability Requirements
- **CPU**: 16+ cores across multiple nodes
- **Memory**: 32GB+ RAM per node
- **Storage**: 500GB+ distributed storage
- **Network**: Multiple network paths with load balancing
- **Redundancy**: Multi-zone deployment

### Storage Architecture

AgentMap provides a unified storage service system that supports multiple storage backends for scalable, reliable data operations.

#### Available Storage Services

##### Local File Storage
- **CSV Storage**: Pandas-based operations with intelligent ID field detection
- **JSON Storage**: Document-based operations with path access
- **File Storage**: Text and binary file handling with optional LangChain integration

##### Cloud Storage Integration
- **Azure Blob Storage**: Container-based organization with metadata support
- **AWS S3**: Bucket-based storage with versioning capabilities
- **Google Cloud Storage**: Global storage with fine-grained permissions

#### Storage Service Principles

All AgentMap storage services follow consistent principles:

- **Unified Interface**: All services implement the same base protocol
- **Missing Documents Return `None`**: Consistent error handling
- **Raw Content by Default**: Direct content access for simplicity
- **Structured Format Available**: Metadata-rich objects when needed
- **Type Safety**: Comprehensive typing and error handling

## Deployment Patterns

### 1. Development Deployment

For local development and testing:

```yaml
# agentmap_config.yaml
app:
  environment: "development"
  debug: true
  log_level: "DEBUG"

storage:
  csv:
    provider: csv
    options:
      base_directory: "./data/csv"
      encoding: "utf-8"
  
  json:
    provider: json
    options:
      base_directory: "./data/json"
      encoding: "utf-8"
      indent: 2
  
  file:
    provider: file
    options:
      base_directory: "./data/files"
      allow_binary: true
      encoding: "utf-8"

execution:
  tracking:
    enabled: true
    track_outputs: true
    track_inputs: true
  
  success_policy:
    type: "all_nodes"
```

#### Docker Development Setup

```dockerfile
# Dockerfile.dev
FROM python:3.11-slim

WORKDIR /app

# Install development dependencies
COPY requirements-dev.txt .
RUN pip install -r requirements-dev.txt

# Copy application code
COPY . .

# Create data directories
RUN mkdir -p data/{csv,json,files}

# Development server
CMD ["python", "-m", "agentmap.server", "--reload", "--port", "8000"]
```

```yaml
# docker-compose.dev.yml
version: '3.8'

services:
  agentmap:
    build:
      context: .
      dockerfile: Dockerfile.dev
    ports:
      - "8000:8000"
    volumes:
      - .:/app
      - ./data:/app/data
    environment:
      - AGENTMAP_ENV=development
      - AGENTMAP_DEBUG=true
```

### 2. Production Deployment

#### Single-Node Production

```yaml
# agentmap_config.yaml
app:
  environment: "production"
  debug: false
  log_level: "INFO"
  workers: 4

storage:
  csv:
    provider: csv
    options:
      base_directory: "/var/app/data/csv"
      encoding: "utf-8"
      validate_paths: true
      max_file_size: "100MB"
  
  json:
    provider: json
    options:
      base_directory: "/var/app/data/json"
      encoding: "utf-8"
      validate_json: true
      backup_enabled: true
  
  file:
    provider: file
    options:
      base_directory: "/var/app/data/files"
      allow_binary: false
      max_file_size: "50MB"
      allowed_extensions: [".txt", ".md", ".json", ".csv"]

execution:
  tracking:
    enabled: true
    track_outputs: false
    track_inputs: false
  
  success_policy:
    type: "critical_nodes"
    critical_nodes:
      - "validateInput"
      - "processPayment"

security:
  api_keys:
    enabled: true
    encryption_enabled: true
  
  rate_limiting:
    enabled: true
    requests_per_minute: 1000
```

#### Production Docker Setup

```dockerfile
# Dockerfile.prod
FROM python:3.11-slim

# Create non-root user
RUN groupadd -r agentmap && useradd -r -g agentmap agentmap

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY --chown=agentmap:agentmap . .

# Create data directories with proper permissions
RUN mkdir -p /var/app/data/{csv,json,files} && \
    chown -R agentmap:agentmap /var/app/data

# Switch to non-root user
USER agentmap

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Production server
EXPOSE 8000
CMD ["gunicorn", "agentmap.server:app", "--bind", "0.0.0.0:8000", "--workers", "4"]
```

### 3. Cloud-Native Deployment

#### Azure Container Instances

```yaml
# azure-container-instance.yml
apiVersion: v1
kind: ConfigMap
metadata:
  name: agentmap-config
data:
  agentmap_config.yaml: |
    app:
      environment: "production"
    storage:
      json:
        default_provider: "azure"
        providers:
          azure:
            connection_string: "env:AZURE_STORAGE_CONNECTION_STRING"
            default_container: "documents"

---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: agentmap
spec:
  replicas: 3
  selector:
    matchLabels:
      app: agentmap
  template:
    metadata:
      labels:
        app: agentmap
    spec:
      containers:
      - name: agentmap
        image: myregistry.azurecr.io/agentmap:latest
        ports:
        - containerPort: 8000
        env:
        - name: AZURE_STORAGE_CONNECTION_STRING
          valueFrom:
            secretKeyRef:
              name: azure-storage-secret
              key: connection-string
        volumeMounts:
        - name: config
          mountPath: /app/config
        resources:
          requests:
            memory: "2Gi"
            cpu: "1000m"
          limits:
            memory: "4Gi"
            cpu: "2000m"
      volumes:
      - name: config
        configMap:
          name: agentmap-config
```

#### AWS ECS with Fargate

```json
{
  "family": "agentmap",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "1024",
  "memory": "2048",
  "executionRoleArn": "arn:aws:iam::account:role/ecsTaskExecutionRole",
  "taskRoleArn": "arn:aws:iam::account:role/agentmapTaskRole",
  "containerDefinitions": [
    {
      "name": "agentmap",
      "image": "account.dkr.ecr.region.amazonaws.com/agentmap:latest",
      "portMappings": [
        {
          "containerPort": 8000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {
          "name": "AWS_DEFAULT_REGION",
          "value": "us-west-2"
        }
      ],
      "secrets": [
        {
          "name": "AWS_ACCESS_KEY_ID",
          "valueFrom": "arn:aws:secretsmanager:region:account:secret:agentmap/aws-credentials:access_key_id::"
        },
        {
          "name": "AWS_SECRET_ACCESS_KEY",
          "valueFrom": "arn:aws:secretsmanager:region:account:secret:agentmap/aws-credentials:secret_access_key::"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/agentmap",
          "awslogs-region": "us-west-2",
          "awslogs-stream-prefix": "ecs"
        }
      }
    }
  ]
}
```

#### Google Cloud Run

```yaml
# cloud-run-service.yaml
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: agentmap
  annotations:
    run.googleapis.com/ingress: all
spec:
  template:
    metadata:
      annotations:
        autoscaling.knative.dev/maxScale: "10"
        run.googleapis.com/cpu-throttling: "false"
    spec:
      containerConcurrency: 1000
      containers:
      - image: gcr.io/project-id/agentmap:latest
        ports:
        - containerPort: 8000
        env:
        - name: GCP_PROJECT_ID
          value: "project-id"
        - name: GOOGLE_APPLICATION_CREDENTIALS
          value: "/var/secrets/google/key.json"
        volumeMounts:
        - name: google-cloud-key
          mountPath: /var/secrets/google
        resources:
          limits:
            cpu: "2"
            memory: "4Gi"
      volumes:
      - name: google-cloud-key
        secret:
          secretName: google-cloud-key
```

### 4. Kubernetes Deployment

#### Full Kubernetes Deployment

```yaml
# k8s-deployment.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: agentmap

---
apiVersion: v1
kind: Secret
metadata:
  name: agentmap-secrets
  namespace: agentmap
type: Opaque
stringData:
  azure-connection-string: "DefaultEndpointsProtocol=https;AccountName=..."
  aws-access-key: "AKIA..."
  aws-secret-key: "..."
  gcp-credentials: |
    {
      "type": "service_account",
      "project_id": "...",
      ...
    }

---
apiVersion: v1
kind: ConfigMap
metadata:
  name: agentmap-config
  namespace: agentmap
data:
  agentmap_config.yaml: |
    app:
      environment: "production"
      workers: 4
    
    storage:
      json:
        providers:
          azure:
            connection_string: "env:AZURE_STORAGE_CONNECTION_STRING"
            default_container: "documents"
          aws:
            region: "us-west-2"
            access_key: "env:AWS_ACCESS_KEY_ID"
            secret_key: "env:AWS_SECRET_ACCESS_KEY"
            default_bucket: "agentmap-data"
          gcp:
            project_id: "env:GCP_PROJECT_ID"
            credentials_file: "/var/secrets/gcp/credentials.json"
            default_bucket: "agentmap-storage"

---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: agentmap
  namespace: agentmap
spec:
  replicas: 3
  selector:
    matchLabels:
      app: agentmap
  template:
    metadata:
      labels:
        app: agentmap
    spec:
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        fsGroup: 1000
      containers:
      - name: agentmap
        image: agentmap:latest
        ports:
        - containerPort: 8000
        env:
        - name: AZURE_STORAGE_CONNECTION_STRING
          valueFrom:
            secretKeyRef:
              name: agentmap-secrets
              key: azure-connection-string
        - name: AWS_ACCESS_KEY_ID
          valueFrom:
            secretKeyRef:
              name: agentmap-secrets
              key: aws-access-key
        - name: AWS_SECRET_ACCESS_KEY
          valueFrom:
            secretKeyRef:
              name: agentmap-secrets
              key: aws-secret-key
        - name: GCP_PROJECT_ID
          value: "your-project-id"
        volumeMounts:
        - name: config
          mountPath: /app/config
        - name: gcp-credentials
          mountPath: /var/secrets/gcp
        resources:
          requests:
            memory: "2Gi"
            cpu: "1000m"
          limits:
            memory: "4Gi"
            cpu: "2000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
      volumes:
      - name: config
        configMap:
          name: agentmap-config
      - name: gcp-credentials
        secret:
          secretName: agentmap-secrets
          items:
          - key: gcp-credentials
            path: credentials.json

---
apiVersion: v1
kind: Service
metadata:
  name: agentmap-service
  namespace: agentmap
spec:
  selector:
    app: agentmap
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8000
  type: LoadBalancer

---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: agentmap-ingress
  namespace: agentmap
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
    cert-manager.io/cluster-issuer: letsencrypt-prod
spec:
  tls:
  - hosts:
    - agentmap.example.com
    secretName: agentmap-tls
  rules:
  - host: agentmap.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: agentmap-service
            port:
              number: 80
```

## Cloud Storage Configuration

### Multi-Cloud Storage Setup

```yaml
# storage_config.yaml
json:
  default_provider: "local"
  providers:
    local:
      base_dir: "data/json"
    
    azure:
      connection_string: "env:AZURE_STORAGE_CONNECTION_STRING"
      default_container: "documents"
      containers:
        users: "users-prod-container"
        reports: "reports-container"
        configs: "app-configs-v2"
    
    aws:
      region: "us-west-2"
      access_key: "env:AWS_ACCESS_KEY_ID"
      secret_key: "env:AWS_SECRET_ACCESS_KEY"
      default_bucket: "agentmap-data"
      buckets:
        analytics: "analytics-prod-us-west-2"
        backups: "system-backups-encrypted"
        ml_models: "ml-models-versioned"
    
    gcp:
      project_id: "env:GCP_PROJECT_ID"
      credentials_file: "/var/secrets/gcp/credentials.json"
      default_bucket: "agentmap-storage"
      buckets:
        documents: "documents-prod-global"
        images: "images-cdn-optimized"
        archives: "long-term-archives"
  
  collections:
    # Production data
    prod_users: "azure://users/data.json"
    prod_analytics: "s3://analytics/data.json"
    prod_documents: "gs://documents/archive.json"
    
    # Multi-region backups
    backup_users_azure: "azure://backups/users.json"
    backup_users_aws: "s3://backups/users.json"
    backup_users_gcp: "gs://backups/users.json"
```

### Storage URI Patterns

```yaml
# Environment-specific collections
collections:
  # Production
  prod_users: "azure://prod-users/data.json"
  prod_config: "s3://prod-config/app.json"
  prod_logs: "gs://prod-logs/application.json"
  
  # Staging
  staging_users: "azure://staging-users/data.json"
  staging_config: "s3://staging-config/app.json"
  staging_logs: "gs://staging-logs/application.json"
  
  # Development
  dev_users: "local://users.json"
  dev_config: "local://config.json"
  dev_logs: "local://logs.json"
  
  # Cross-cloud replication
  global_backup: [
    "azure://global-backup/data.json",
    "s3://global-backup/data.json",
    "gs://global-backup/data.json"
  ]
```

## Scaling Strategies

### Horizontal Scaling

#### Load Balancer Configuration

```nginx
# nginx.conf
upstream agentmap_backend {
    least_conn;
    server agentmap-1:8000 weight=1 max_fails=3 fail_timeout=30s;
    server agentmap-2:8000 weight=1 max_fails=3 fail_timeout=30s;
    server agentmap-3:8000 weight=1 max_fails=3 fail_timeout=30s;
}

server {
    listen 80;
    server_name agentmap.example.com;
    
    location / {
        proxy_pass http://agentmap_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Timeout settings
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
        
        # Buffer settings
        proxy_buffering on;
        proxy_buffer_size 4k;
        proxy_buffers 8 4k;
    }
    
    location /health {
        access_log off;
        proxy_pass http://agentmap_backend;
    }
}
```

#### Auto-scaling Configuration

```yaml
# k8s-hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: agentmap-hpa
  namespace: agentmap
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: agentmap
  minReplicas: 3
  maxReplicas: 20
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
      - type: Percent
        value: 10
        periodSeconds: 60
    scaleUp:
      stabilizationWindowSeconds: 0
      policies:
      - type: Percent
        value: 100
        periodSeconds: 15
      - type: Pods
        value: 4
        periodSeconds: 15
      selectPolicy: Max
```

### Vertical Scaling

#### Resource Optimization

```yaml
# Resource limits for different workloads
containers:
  # Light workload
  - name: agentmap-light
    resources:
      requests:
        memory: "1Gi"
        cpu: "500m"
      limits:
        memory: "2Gi"
        cpu: "1000m"
  
  # Standard workload
  - name: agentmap-standard
    resources:
      requests:
        memory: "2Gi"
        cpu: "1000m"
      limits:
        memory: "4Gi"
        cpu: "2000m"
  
  # Heavy workload
  - name: agentmap-heavy
    resources:
      requests:
        memory: "4Gi"
        cpu: "2000m"
      limits:
        memory: "8Gi"
        cpu: "4000m"
```

## Monitoring and Observability

### Health Checks

```python
# health_check.py
from fastapi import FastAPI, HTTPException
import asyncio
import time

app = FastAPI()

async def check_storage_health():
    """Check storage service connectivity."""
    try:
        # Check local storage
        local_health = await check_local_storage()
        
        # Check cloud storage
        cloud_health = await check_cloud_storage()
        
        return {
            "storage": {
                "local": local_health,
                "cloud": cloud_health
            }
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Storage check failed: {str(e)}")

async def check_cloud_storage():
    """Check cloud storage provider connectivity."""
    health_status = {}
    
    providers = ["azure", "aws", "gcp"]
    for provider in providers:
        try:
            start_time = time.time()
            result = await test_provider_connection(provider)
            response_time = time.time() - start_time
            
            health_status[provider] = {
                "status": "healthy" if result else "degraded",
                "response_time": response_time
            }
        except Exception as e:
            health_status[provider] = {
                "status": "error",
                "error": str(e)
            }
    
    return health_status

@app.get("/health")
async def health_check():
    """Basic health check endpoint."""
    return {"status": "healthy", "timestamp": time.time()}

@app.get("/ready")
async def readiness_check():
    """Readiness check with dependency validation."""
    try:
        storage_health = await check_storage_health()
        return {
            "status": "ready",
            "checks": storage_health,
            "timestamp": time.time()
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))
```

### Metrics Collection

```yaml
# prometheus-config.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'agentmap'
    static_configs:
      - targets: ['agentmap-service:8000']
    metrics_path: '/metrics'
    scrape_interval: 5s
    
  - job_name: 'agentmap-storage'
    static_configs:
      - targets: ['agentmap-service:8000']
    metrics_path: '/storage/metrics'
    scrape_interval: 30s
```

### Logging Configuration

```yaml
# logging.yaml
version: 1
disable_existing_loggers: false

formatters:
  standard:
    format: '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
  json:
    '()': 'pythonjsonlogger.jsonlogger.JsonFormatter'
    format: '%(asctime)s %(name)s %(levelname)s %(message)s'

handlers:
  console:
    class: logging.StreamHandler
    level: INFO
    formatter: standard
    stream: ext://sys.stdout
  
  file:
    class: logging.handlers.RotatingFileHandler
    level: INFO
    formatter: json
    filename: /var/log/agentmap/app.log
    maxBytes: 10485760  # 10MB
    backupCount: 5
  
  error_file:
    class: logging.handlers.RotatingFileHandler
    level: ERROR
    formatter: json
    filename: /var/log/agentmap/error.log
    maxBytes: 10485760
    backupCount: 5

loggers:
  agentmap:
    level: INFO
    handlers: [console, file, error_file]
    propagate: false

root:
  level: INFO
  handlers: [console]
```

## Security Considerations

### Network Security

```yaml
# Security group / firewall rules
ingress_rules:
  - port: 443
    protocol: tcp
    source: "0.0.0.0/0"
    description: "HTTPS from anywhere"
  
  - port: 80
    protocol: tcp
    source: "0.0.0.0/0"
    description: "HTTP from anywhere (redirect to HTTPS)"
  
  - port: 8000
    protocol: tcp
    source: "10.0.0.0/8"
    description: "Internal API access"

egress_rules:
  - port: 443
    protocol: tcp
    destination: "0.0.0.0/0"
    description: "HTTPS outbound for cloud services"
  
  - port: 53
    protocol: udp
    destination: "0.0.0.0/0"
    description: "DNS resolution"
```

### Secret Management

```yaml
# Kubernetes secrets management
apiVersion: v1
kind: Secret
metadata:
  name: agentmap-secrets
  namespace: agentmap
type: Opaque
stringData:
  # Database credentials
  database-url: "postgresql://user:password@db:5432/agentmap"
  
  # Cloud storage credentials
  azure-storage-connection: "DefaultEndpointsProtocol=https;..."
  aws-access-key-id: "AKIA..."
  aws-secret-access-key: "..."
  gcp-service-account: |
    {
      "type": "service_account",
      ...
    }
  
  # API keys
  openai-api-key: "sk-..."
  anthropic-api-key: "..."
  
  # Application secrets
  jwt-secret: "..."
  encryption-key: "..."
```

### TLS Configuration

```yaml
# TLS certificate management
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: agentmap-tls
  namespace: agentmap
spec:
  secretName: agentmap-tls
  issuerRef:
    name: letsencrypt-prod
    kind: ClusterIssuer
  dnsNames:
  - agentmap.example.com
  - api.agentmap.example.com
```

## Backup and Disaster Recovery

### Automated Backup Strategy

```yaml
# backup-config.yaml
backup:
  storage:
    # Local backup
    local:
      enabled: true
      schedule: "0 2 * * *"  # Daily at 2 AM
      retention_days: 30
      destination: "/var/backups/agentmap"
    
    # Cloud backup
    cloud:
      enabled: true
      schedule: "0 3 * * *"  # Daily at 3 AM
      retention_days: 90
      destinations:
        - "s3://agentmap-backups/daily"
        - "azure://backups/daily"
        - "gs://agentmap-backups/daily"
  
  database:
    enabled: true
    schedule: "0 1 * * *"  # Daily at 1 AM
    retention_days: 30
    compression: true
    encryption: true
```

### Disaster Recovery Plan

```bash
#!/bin/bash
# disaster-recovery.sh

set -e

ENVIRONMENT=${1:-production}
BACKUP_DATE=${2:-latest}

echo "Starting disaster recovery for environment: $ENVIRONMENT"

# 1. Verify backup integrity
echo "Verifying backup integrity..."
verify_backup_integrity "$BACKUP_DATE"

# 2. Restore storage data
echo "Restoring storage data..."
restore_storage_data "$ENVIRONMENT" "$BACKUP_DATE"

# 3. Restore configuration
echo "Restoring configuration..."
restore_configuration "$ENVIRONMENT" "$BACKUP_DATE"

# 4. Restart services
echo "Restarting services..."
kubectl rollout restart deployment/agentmap -n agentmap

# 5. Verify system health
echo "Verifying system health..."
kubectl wait --for=condition=ready pod -l app=agentmap -n agentmap --timeout=300s

# 6. Run health checks
echo "Running health checks..."
curl -f http://agentmap-service/health || exit 1

echo "Disaster recovery completed successfully"
```

## Performance Optimization

### Caching Strategies

```yaml
# caching-config.yaml
cache:
  # Application-level caching
  application:
    enabled: true
    backend: "redis"
    redis_url: "redis://redis-cluster:6379/0"
    default_ttl: 3600
    max_memory: "2GB"
  
  # Storage-level caching
  storage:
    enabled: true
    local_cache:
      max_size: 1000
      ttl: 300
    redis_cache:
      enabled: true
      ttl: 600
      key_prefix: "agentmap:storage:"
  
  # Cloud storage caching
  cloud_storage:
    enabled: true
    local_cache_size: "500MB"
    cache_duration: 1800
    prefetch_enabled: true
```

### Connection Pooling

```yaml
# connection-pool-config.yaml
connection_pools:
  azure:
    max_connections: 20
    max_idle_connections: 5
    idle_timeout: 300
    connection_timeout: 30
  
  aws:
    max_connections: 20
    max_retries: 3
    backoff_mode: "adaptive"
    timeout: 30
  
  gcp:
    max_connections: 20
    keepalive_timeout: 300
    timeout: 30
  
  database:
    pool_size: 20
    max_overflow: 30
    pool_timeout: 30
    pool_recycle: 3600
```

## Cost Optimization

### Resource Allocation

```yaml
# cost-optimization.yaml
resources:
  # Use resource requests and limits appropriately
  production:
    requests:
      memory: "2Gi"
      cpu: "1000m"
    limits:
      memory: "4Gi"
      cpu: "2000m"
  
  staging:
    requests:
      memory: "1Gi"
      cpu: "500m"
    limits:
      memory: "2Gi"
      cpu: "1000m"
  
  development:
    requests:
      memory: "512Mi"
      cpu: "250m"
    limits:
      memory: "1Gi"
      cpu: "500m"

# Storage lifecycle policies
storage_lifecycle:
  azure:
    rules:
      - name: "archive_old_data"
        enabled: true
        filters:
          blob_types: ["blockBlob"]
          prefix_match: ["archive/"]
        actions:
          base_blob:
            tier_to_cool:
              days_after_modification_greater_than: 30
            tier_to_archive:
              days_after_modification_greater_than: 90
  
  aws:
    rules:
      - id: "archive_old_data"
        status: "Enabled"
        filter:
          prefix: "archive/"
        transitions:
          - days: 30
            storage_class: "STANDARD_IA"
          - days: 90
            storage_class: "GLACIER"
          - days: 365
            storage_class: "DEEP_ARCHIVE"
  
  gcp:
    rules:
      - condition:
          age: 30
          matches_prefix: ["archive/"]
        action:
          type: "SetStorageClass"
          storage_class: "NEARLINE"
      - condition:
          age: 90
          matches_prefix: ["archive/"]
        action:
          type: "SetStorageClass"
          storage_class: "COLDLINE"
```

## Troubleshooting

### Common Deployment Issues

#### Container Startup Failures

```bash
# Debug container startup
kubectl describe pod -l app=agentmap -n agentmap
kubectl logs -l app=agentmap -n agentmap --previous

# Check resource constraints
kubectl top pod -n agentmap
kubectl get events -n agentmap --sort-by='.lastTimestamp'
```

#### Storage Connectivity Issues

```bash
# Test cloud storage connectivity
kubectl exec -it deployment/agentmap -n agentmap -- python -c "
import os
from agentmap.services.storage import get_storage_service

# Test Azure
try:
    azure_service = get_storage_service('azure')
    result = azure_service.read('test-container/health-check.json')
    print(f'Azure: {\"OK\" if result else \"Failed\"}')
except Exception as e:
    print(f'Azure: Error - {e}')

# Test AWS
try:
    aws_service = get_storage_service('aws')
    result = aws_service.read('test-bucket/health-check.json')
    print(f'AWS: {\"OK\" if result else \"Failed\"}')
except Exception as e:
    print(f'AWS: Error - {e}')

# Test GCP
try:
    gcp_service = get_storage_service('gcp')
    result = gcp_service.read('test-bucket/health-check.json')
    print(f'GCP: {\"OK\" if result else \"Failed\"}')
except Exception as e:
    print(f'GCP: Error - {e}')
"
```

#### Performance Issues

```bash
# Monitor resource usage
kubectl top pod -n agentmap
kubectl top node

# Check storage performance
kubectl exec -it deployment/agentmap -n agentmap -- python -c "
import time
from agentmap.services.storage import get_storage_service

storage = get_storage_service('azure')

# Test read performance
start = time.time()
data = storage.read('large-collection')
read_time = time.time() - start
print(f'Read time: {read_time:.2f}s')

# Test write performance
start = time.time()
storage.write('test-collection', {'test': 'data'}, 'perf-test')
write_time = time.time() - start
print(f'Write time: {write_time:.2f}s')
"
```

## Migration Guide

### From Development to Production

```bash
#!/bin/bash
# migrate-to-production.sh

# 1. Export development data
echo "Exporting development data..."
python scripts/export_data.py --environment=dev --output=migration/

# 2. Create production infrastructure
echo "Creating production infrastructure..."
kubectl apply -f k8s/production/

# 3. Configure production storage
echo "Configuring production storage..."
kubectl create secret generic agentmap-secrets \
  --from-env-file=.env.production \
  -n agentmap

# 4. Import data to production
echo "Importing data to production..."
python scripts/import_data.py --environment=prod --input=migration/

# 5. Verify migration
echo "Verifying migration..."
python scripts/verify_migration.py --environment=prod

echo "Migration completed successfully"
```

### From Single Cloud to Multi-Cloud

```python
# migrate_to_multicloud.py
import asyncio
from agentmap.services.storage import get_storage_service

async def migrate_to_multicloud():
    """Migrate from single cloud provider to multi-cloud setup."""
    
    # Source and destination services
    source = get_storage_service('aws')
    destinations = [
        get_storage_service('azure'),
        get_storage_service('gcp')
    ]
    
    # Get all collections to migrate
    collections = source.list_collections()
    
    for collection in collections:
        print(f"Migrating collection: {collection}")
        
        # Read from source
        data = await source.read(collection)
        
        # Write to all destinations
        for dest in destinations:
            try:
                result = await dest.write(collection, data)
                print(f"  ✓ Migrated to {dest.provider}")
            except Exception as e:
                print(f"  ✗ Failed to migrate to {dest.provider}: {e}")
    
    print("Multi-cloud migration completed")

if __name__ == "__main__":
    asyncio.run(migrate_to_multicloud())
```

## Best Practices

### Production Checklist

- [ ] **Security**: All secrets properly managed and encrypted
- [ ] **Monitoring**: Health checks, metrics, and logging configured
- [ ] **Scaling**: Auto-scaling policies defined and tested
- [ ] **Backup**: Automated backup strategy implemented
- [ ] **Recovery**: Disaster recovery plan documented and tested
- [ ] **Performance**: Resource limits and caching configured
- [ ] **Networking**: TLS/SSL certificates and firewall rules in place
- [ ] **Compliance**: Data governance and compliance requirements met

### Operational Excellence

1. **Infrastructure as Code**: All infrastructure defined in version control
2. **Automated Deployment**: CI/CD pipelines for consistent deployments
3. **Environment Parity**: Development, staging, and production environments aligned
4. **Configuration Management**: Centralized configuration with environment-specific overrides
5. **Secret Rotation**: Automated credential rotation and management
6. **Monitoring and Alerting**: Comprehensive observability across all components
7. **Documentation**: Up-to-date runbooks and troubleshooting guides

## Related Documentation

- [Performance Optimization](/docs/guides/production/performance) - Optimize AgentMap for high performance
- [Security Best Practices](/docs/guides/production/security) - Secure your AgentMap deployment
- [Monitoring & Observability](/docs/guides/production/monitoring) - Monitor AgentMap in production
- [Configuration Reference](/docs/reference/configuration) - Complete configuration options

:::tip Next Steps

For production deployments, ensure you have:
1. **Comprehensive monitoring** for all system components
2. **Security hardening** following industry best practices
3. **Performance optimization** based on your workload patterns
4. **Disaster recovery** procedures tested and documented
5. **Cost optimization** strategies to manage cloud spend

:::
