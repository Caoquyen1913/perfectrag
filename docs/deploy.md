# Cloud deploy

`perfectrag deploy <target>` renders production deployment assets into a folder.
Review the output, then use the native CLI (`helm`, `fly`, `railway`) to ship.

## Targets

### Helm (Kubernetes)

```bash
perfectrag deploy helm --project ./my-rag --out ./k8s-chart
helm lint ./k8s-chart
helm install my-rag ./k8s-chart
```

Produces: `Chart.yaml`, `values.yaml`, `templates/{qdrant,ollama,app}.yaml`.

GPU: if `recipe.gpu_enabled`, `values.yaml` includes `nvidia.com/gpu: 1` reservation.

### Fly.io

```bash
perfectrag deploy flyio --project ./my-rag --out ./fly
cd fly && fly launch --copy-config
fly deploy
```

Produces a root `fly.toml`. Deploy ollama + qdrant as separate Fly apps first (see comments in `fly.toml`).

### Railway

```bash
perfectrag deploy railway --project ./my-rag --out ./railway
# Push to GitHub, connect repo in Railway dashboard; railway.json is auto-detected
```

## Which templates support which targets

Only `custom-naive-rag` ships deploy assets in v1.0. RAGFlow/Dify/LightRAG have
dozens of services — use their upstream helm charts directly or roll your own.

To check: `perfectrag list` or `GET /api/deploy/targets?template=ragflow-stack`.

## Adding a deploy target

1. Create `src/perfectrag/deploy/<target>/<template>/<file>.jinja`
2. Files use Jinja — remember to escape Helm syntax: `{{ '{{' }} .Values.x {{ '}}' }}`
3. `deployer.available_targets("<template>")` auto-discovers presence of the dir
