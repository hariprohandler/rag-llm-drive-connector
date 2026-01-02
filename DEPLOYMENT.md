# Deployment Guide

This guide covers deployment strategies for the RAG LLM Drive Connector.

## Table of Contents

- [Docker Deployment](#docker-deployment)
- [Kubernetes Deployment](#kubernetes-deployment)
- [ArgoCD Deployment](#argocd-deployment)
- [Environment-Specific Configurations](#environment-specific-configurations)
- [Troubleshooting](#troubleshooting)

## Docker Deployment

### Prerequisites

- Docker Engine 20.10+
- Docker Compose 2.0+

### Steps

1. **Prepare Environment**

   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

2. **Build and Start**

   ```bash
   docker-compose up -d
   ```

3. **Initialize Database**

   ```bash
   docker-compose exec app python setup_db.py
   ```

4. **Verify Deployment**

   ```bash
   docker-compose ps
   docker-compose logs -f app
   ```

5. **Access Application**

   - API: http://localhost:8000/docs
   - UI: http://localhost:7860

## Kubernetes Deployment

### Prerequisites

- Kubernetes cluster (1.24+)
- kubectl configured
- Access to container registry
- Ingress controller installed

### Manual Deployment

#### 1. Create Namespace

```bash
kubectl apply -f k8s/namespace.yaml
```

#### 2. Create Secrets

**Important:** Never commit `secret.yaml` to git!

```bash
# Copy template
cp k8s/secret.yaml.example k8s/secret.yaml

# Edit with your values
vim k8s/secret.yaml

# Apply
kubectl apply -f k8s/secret.yaml
```

Alternatively, create secrets via CLI:

```bash
kubectl create secret generic rag-app-secrets \
  --from-literal=OPENAI_API_KEY=your-key \
  --from-literal=POSTGRES_PASSWORD=your-password \
  --from-literal=POSTGRES_USER=postgres \
  --from-literal=DATABASE_URL=postgresql+psycopg2://postgres:password@postgres-service:5432/postgres \
  -n rag-system
```

#### 3. Create ConfigMap

```bash
kubectl apply -f k8s/configmap.yaml
```

#### 4. Deploy PostgreSQL

```bash
kubectl apply -f k8s/postgres-deployment.yaml

# Wait for PostgreSQL to be ready
kubectl wait --for=condition=ready pod -l app=postgres -n rag-system --timeout=300s
```

#### 5. Initialize Database

```bash
# Get PostgreSQL pod name
POD_NAME=$(kubectl get pod -l app=postgres -n rag-system -o jsonpath='{.items[0].metadata.name}')

# Execute setup
kubectl exec -it $POD_NAME -n rag-system -- psql -U postgres -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

#### 6. Build and Push Docker Image

```bash
# Build
docker build -t your-registry/rag-llm-drive-connector:latest .

# Push
docker push your-registry/rag-llm-drive-connector:latest
```

#### 7. Update Kustomization

Edit `k8s/kustomization.yaml`:

```yaml
images:
  - name: rag-llm-drive-connector
    newName: your-registry/rag-llm-drive-connector
    newTag: latest
```

#### 8. Deploy Application

```bash
kubectl apply -k k8s/

# Wait for deployment
kubectl rollout status deployment/rag-app -n rag-system
```

#### 9. Configure Ingress

Edit `k8s/ingress.yaml` with your domain:

```yaml
spec:
  rules:
  - host: rag-app.your-domain.com
```

Apply:

```bash
kubectl apply -f k8s/ingress.yaml
```

### Verify Deployment

```bash
# Check pods
kubectl get pods -n rag-system

# Check services
kubectl get svc -n rag-system

# Check ingress
kubectl get ingress -n rag-system

# View logs
kubectl logs -f deployment/rag-app -n rag-system

# Check events
kubectl get events -n rag-system --sort-by='.lastTimestamp'
```

## ArgoCD Deployment

### Prerequisites

- ArgoCD installed in cluster
- Repository access configured
- ArgoCD CLI installed (optional)

### Setup

#### 1. Configure Repository in ArgoCD

Via UI:
1. Go to Settings > Repositories
2. Connect repository (HTTPS or SSH)
3. Add credentials if private

Via CLI:
```bash
argocd repo add https://github.com/your-org/rag-llm-drive-connector.git \
  --username your-username \
  --password your-token
```

#### 2. Update Application Manifest

Edit `argocd/application.yaml`:

```yaml
spec:
  source:
    repoURL: https://github.com/your-org/rag-llm-drive-connector.git
    targetRevision: main
    path: k8s
```

#### 3. Deploy Application

```bash
kubectl apply -f argocd/application.yaml -n argocd
```

#### 4. Sync Application

Via UI:
1. Open ArgoCD UI
2. Find `rag-llm-drive-connector` application
3. Click "Sync"

Via CLI:
```bash
argocd app sync rag-llm-drive-connector
```

#### 5. Enable Auto-Sync (Optional)

Edit application:

```yaml
spec:
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
```

Or via CLI:
```bash
argocd app set rag-llm-drive-connector --sync-policy automated --auto-prune --self-heal
```

### App of Apps Pattern

For managing multiple applications:

```bash
kubectl apply -f argocd/app-of-apps.yaml -n argocd
```

## Environment-Specific Configurations

### Development

```yaml
# k8s/configmap.yaml
ENVIRONMENT: development
LOG_LEVEL: DEBUG
```

### Staging

```yaml
# k8s/configmap.yaml
ENVIRONMENT: staging
LOG_LEVEL: INFO
```

### Production

```yaml
# k8s/configmap.yaml
ENVIRONMENT: production
LOG_LEVEL: WARNING
```

Use Kustomize overlays for environment-specific configs:

```
k8s/
├── base/
│   └── ...
├── overlays/
│   ├── development/
│   ├── staging/
│   └── production/
```

## Troubleshooting

### Pods Not Starting

```bash
# Check pod status
kubectl describe pod <pod-name> -n rag-system

# Check logs
kubectl logs <pod-name> -n rag-system

# Check events
kubectl get events -n rag-system
```

### Database Connection Issues

```bash
# Test connection
kubectl exec -it deployment/rag-app -n rag-system -- \
  python -c "import psycopg2; psycopg2.connect('$DATABASE_URL')"

# Check PostgreSQL logs
kubectl logs -l app=postgres -n rag-system
```

### Image Pull Errors

```bash
# Check image pull secrets
kubectl get secrets -n rag-system

# Verify image exists
docker pull your-registry/rag-llm-drive-connector:latest

# Check registry credentials
kubectl create secret docker-registry regcred \
  --docker-server=your-registry \
  --docker-username=user \
  --docker-password=pass \
  -n rag-system
```

### Ingress Not Working

```bash
# Check ingress controller
kubectl get pods -n ingress-nginx

# Check ingress status
kubectl describe ingress rag-app-ingress -n rag-system

# Test service directly
kubectl port-forward svc/rag-app-service 8000:80 -n rag-system
```

### ArgoCD Sync Issues

```bash
# Check application status
argocd app get rag-llm-drive-connector

# Check sync history
argocd app history rag-llm-drive-connector

# Force refresh
argocd app get rag-llm-drive-connector --refresh
```

## Rolling Updates

### Manual Rollout

```bash
# Update image
kubectl set image deployment/rag-app \
  rag-app=your-registry/rag-llm-drive-connector:v1.1.0 \
  -n rag-system

# Watch rollout
kubectl rollout status deployment/rag-app -n rag-system

# Rollback if needed
kubectl rollout undo deployment/rag-app -n rag-system
```

### Blue-Green Deployment

Use Argo Rollouts for advanced deployment strategies:

```bash
kubectl apply -f k8s/rollout.yaml
```

## Scaling

### Horizontal Scaling

```bash
# Scale deployment
kubectl scale deployment/rag-app --replicas=3 -n rag-system

# Auto-scaling (requires metrics-server)
kubectl autoscale deployment rag-app \
  --min=2 --max=10 \
  --cpu-percent=70 \
  -n rag-system
```

### Vertical Scaling

Edit `k8s/app-deployment.yaml`:

```yaml
resources:
  requests:
    memory: "1Gi"
    cpu: "500m"
  limits:
    memory: "4Gi"
    cpu: "2000m"
```

## Backup and Recovery

### Database Backup

```bash
# Backup
kubectl exec -it <postgres-pod> -n rag-system -- \
  pg_dump -U postgres postgres > backup.sql

# Restore
kubectl exec -i <postgres-pod> -n rag-system -- \
  psql -U postgres postgres < backup.sql
```

### Persistent Volume Backup

Use Velero or similar tools for volume snapshots.

## Monitoring

### Health Checks

```bash
# Check health endpoint
curl http://rag-app.your-domain.com/health

# Check readiness
curl http://rag-app.your-domain.com/ready
```

### Metrics

If Prometheus is installed:

```bash
# Check metrics endpoint
curl http://rag-app.your-domain.com/metrics
```

## Security Considerations

1. **Secrets Management**
   - Use sealed-secrets or external-secrets operator
   - Rotate secrets regularly
   - Never commit secrets to git

2. **Network Policies**
   - Implement network policies
   - Restrict pod-to-pod communication
   - Use service mesh if needed

3. **RBAC**
   - Use least privilege principle
   - Create service accounts with minimal permissions
   - Review RBAC rules regularly

4. **Image Security**
   - Scan images regularly
   - Use minimal base images
   - Keep images updated

5. **TLS/SSL**
   - Enable TLS for all external traffic
   - Use cert-manager for certificate management
   - Enforce HTTPS redirects

