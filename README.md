# BigData Platform — AI Observability Agent

A production-grade big data platform deployed on **Google Kubernetes Engine (GKE)** with an AI-powered observability chatbot. Engineers can diagnose pipeline failures, analyze Kubernetes pod issues, trace data lineage, and get instant answers about the platform — all through a RAG-powered chat interface backed by Google Gemini.

## Live Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                  React Frontend (Vite + Tailwind)            │
│  Chat │ Log Analysis │ Airflow │ Kubernetes │ Lineage        │
└───────────────────────┬─────────────────────────────────────┘
                        │ nginx reverse proxy
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI Backend                           │
│  /chat  /analyze-log  /analyze-airflow-task                  │
│  /analyze-k8s-pod  /lineage/*  /ops/*  /index/*             │
└──────┬──────────┬──────────┬──────────┬──────────┬──────────┘
       │          │          │          │          │
  ┌────▼───┐ ┌───▼────┐ ┌───▼────┐ ┌───▼────┐ ┌───▼──────┐
  │  RAG   │ │  Log   │ │  K8s  │ │Lineage │ │  Ops     │
  │ Engine │ │Analyzer│ │ Logs  │ │ Client │ │  Sync    │
  └───┬────┘ └────────┘ └───────┘ └───┬────┘ └──┬───────┘
      │                               │          │
 ┌────▼────┐                   ┌──────▼──┐ ┌────▼────────┐
 │ Gemini  │                   │ Marquez │ │  Apache     │
 │  Flash  │                   │Lineage  │ │  Airflow    │
 └─────────┘                   └─────────┘ └─────────────┘
      │
 ┌────▼────┐
 │ChromaDB │  ← code + logs + DAG metadata + lineage
 │(PVC)    │
 └─────────┘
```

## What's Built

| Component | Technology | Details |
|---|---|---|
| **Frontend** | React + Vite + Tailwind CSS | Multi-page SPA: Chat, Log Analysis, Airflow, K8s, Lineage |
| **Backend** | FastAPI (Python) | REST API, background sync, RAG engine |
| **LLM** | Google Gemini 2.5 Flash | Via Google AI Studio API key |
| **Embeddings** | all-MiniLM-L6-v2 | Local sentence-transformers, no API needed |
| **Vector DB** | ChromaDB (local, PVC-backed) | 4 collections: code, logs, DAG metadata, lineage |
| **Pipelines** | Apache Airflow (6 DAGs) | Full data lake pipeline with OpenLineage emission |
| **Lineage** | OpenLineage + Marquez | Data flow tracking from landing → models |
| **Infra** | GKE (Google Kubernetes Engine) | 3 namespaces, LoadBalancer services, PVCs |

## Airflow DAGs

| DAG | Schedule | What it does |
|---|---|---|
| `data_ingestion` | `@daily` | Ingests CSV files + REST API data into raw zone |
| `data_transformation` | `@daily` | Cleans, aggregates, enriches data through staging → curated |
| `data_quality_checks` | `@daily` | Schema validation, null ratios, row counts, duplicate detection |
| `ml_pipeline` | `@weekly` | Feature engineering + RandomForest training + evaluation |
| `demo_pipeline` | Manual | End-to-end demo with clean/bad data toggle (`inject_bad_data: true/false`) |
| `demo_observability` | Manual | Intentionally failing DAG for chatbot diagnosis demo |

### Data Lake Zones

```
External APIs / CSVs
        ↓
   landing/          ← raw uploads
        ↓
    raw/             ← ingested files
        ↓
   staging/          ← cleaned data
        ↓
  processed/         ← aggregated
        ↓
   curated/          ← enriched + quality-checked
        ↓
  features/          ← ML feature matrices
        ↓
   models/           ← trained model artifacts
```

## Frontend Pages

| Page | Path | What it does |
|---|---|---|
| **Chat** | `/` | RAG-powered chatbot — ask anything about pipelines, pods, errors |
| **Log Analysis** | `/logs` | Paste any log text → AI diagnosis (category, root cause, next actions) |
| **Airflow** | `/airflow` | Auto-fills from recent failures, analyzes task logs |
| **Kubernetes** | `/k8s` | Browse pods/namespaces, view events, diagnose issues |
| **Lineage** | `/lineage` | Data flow overview, pipeline task I/O, zone-by-zone view |

## API Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Health check |
| POST | `/chat` | RAG chat (Gemini + ChromaDB) |
| POST | `/analyze-log` | Analyze raw log text |
| POST | `/analyze-k8s-pod` | Fetch + analyze Kubernetes pod logs |
| POST | `/analyze-airflow-task` | Fetch + analyze Airflow task logs |
| GET | `/ops/summary` | Live pipeline status (from Airflow) |
| GET | `/ops/latest-failures` | Recent failed tasks with AI summaries |
| GET | `/ops/list-dags` | List all Airflow DAGs |
| GET | `/k8s/namespaces` | List K8s namespaces |
| GET | `/k8s/pods/{namespace}` | List pods in a namespace |
| GET | `/k8s/diagnose/{namespace}` | AI diagnosis of all pods in namespace |
| GET | `/k8s/events/{namespace}` | Recent K8s events |
| GET | `/lineage/namespaces` | List Marquez namespaces |
| GET | `/lineage/jobs/{ns}` | List pipeline jobs with lineage |
| GET | `/lineage/datasets/{ns}` | List datasets |
| POST | `/lineage/sync` | Sync Marquez lineage → ChromaDB |
| POST | `/index/codebase` | Re-index codebase into ChromaDB |
| GET | `/index/stats` | ChromaDB collection stats |

## GKE Deployment

### Prerequisites

- Google Cloud account with a project
- `gcloud` CLI installed and authenticated
- `kubectl` + `gke-gcloud-auth-plugin` installed
- Docker Desktop
- A Google AI Studio API key ([get one free](https://aistudio.google.com))

### One-command deploy

```bash
# Set your API key in .env first:
echo "GOOGLE_API_KEY=your-key-here" > .env

# Deploy everything (cluster + images + all services):
./scripts/deploy-gke.sh
```

The script:
1. Enables GCP APIs
2. Creates Artifact Registry repo
3. Creates GKE cluster (`e2-standard-4`, 2 nodes, spot instances)
4. Builds and pushes 3 Docker images (backend, frontend, airflow)
5. Deploys Postgres, Marquez, Airflow, Backend, Frontend
6. Waits for LoadBalancer IPs and prints access URLs

### Manual deploy (CMD on Windows)

```cmd
set PROJECT_ID=your-gcp-project-id
set REGION=us-central1
set REGISTRY=us-central1-docker.pkg.dev/%PROJECT_ID%/bigdata
set TAG=v1

:: Auth
gcloud container clusters get-credentials bigdata-lean --zone us-central1-a
gcloud auth configure-docker us-central1-docker.pkg.dev

:: Build & push
docker build -t %REGISTRY%/frontend:%TAG% -f docker/Dockerfile.frontend .
docker build -t %REGISTRY%/backend:%TAG% -f docker/Dockerfile.backend .
docker build -t %REGISTRY%/airflow:%TAG% -f docker/Dockerfile.airflow .
docker push %REGISTRY%/frontend:%TAG%
docker push %REGISTRY%/backend:%TAG%
docker push %REGISTRY%/airflow:%TAG%

:: Inject API key (never commit this)
kubectl -n backend create secret generic backend-secrets ^
  --from-literal=GOOGLE_API_KEY="YOUR_KEY" ^
  --dry-run=client -o yaml | kubectl apply -f -

:: Apply manifests
kubectl apply -f k8s/namespaces.yaml
kubectl apply -f k8s/backend/rbac.yaml
kubectl apply -f k8s/data/postgres.yaml
kubectl apply -f k8s/data/marquez.yaml

:: Substitute image placeholders and apply
python -c "import sys; open('_tmp.yaml','w').write(open('k8s/backend/deployment.yaml').read().replace('IMAGE_BACKEND','%REGISTRY%/backend:%TAG%'))" && kubectl apply -f _tmp.yaml
python -c "import sys; open('_tmp.yaml','w').write(open('k8s/backend/frontend.yaml').read().replace('IMAGE_FRONTEND','%REGISTRY%/frontend:%TAG%'))" && kubectl apply -f _tmp.yaml
python -c "import sys; open('_tmp.yaml','w').write(open('k8s/airflow/deployment.yaml').read().replace('IMAGE_AIRFLOW','%REGISTRY%/airflow:%TAG%'))" && kubectl apply -f _tmp.yaml
```

### K8s Namespaces

| Namespace | Services |
|---|---|
| `backend` | FastAPI backend, React frontend (nginx) |
| `airflow` | Airflow webserver + scheduler |
| `data` | PostgreSQL, Marquez API, Marquez Web UI |
| `demo-faults` | Intentionally broken pods for observability demo |

### Service URLs (after deploy)

```bash
kubectl -n backend get svc frontend        # Main app (port 80)
kubectl -n airflow get svc airflow-webserver  # Airflow UI (port 80)
```

## Demo Scenarios

### 1. Pipeline failure diagnosis

1. Open Airflow UI → trigger `demo_pipeline` with `{"inject_bad_data": true}`
2. Wait for tasks to fail (red)
3. Open the main app → **Airflow Task Logs** page
4. Click any red failure button in "Recent Failures" to auto-fill the form
5. Click **Analyze** → AI diagnosis appears
6. Click **Ask in Chat** → chatbot explains and suggests fixes

### 2. Kubernetes observability demo

The `demo-faults` namespace has 4 permanently broken pods:

```bash
kubectl get pods -n demo-faults
```

| Pod | Status | Scenario |
|---|---|---|
| `crash-loop-app` | CrashLoopBackOff | DB connection refused on startup |
| `image-pull-error` | ImagePullBackOff | Non-existent container image |
| `oom-killed-app` | OOMKilled | Memory limit exceeded (exit 137) |
| `resource-starved` | Pending | Impossible resource request (999 CPUs) |

Go to the **Kubernetes** page → select `demo-faults` namespace → view pod details and events.

### 3. Data lineage exploration

1. Run a DAG in Airflow (any of the 6)
2. Go to the **Lineage** page
3. See the data flow overview: External → Landing → Raw → Staging → Processed → Curated → Features → Models
4. Click any pipeline section to expand and see per-task input/output datasets
5. Click **Sync to VectorDB** to make lineage searchable in chat

## Project Structure

```
bigdata-prototype/
├── backend/app/
│   ├── main.py                  # FastAPI app + lifespan + background sync
│   ├── models.py                # Pydantic request/response models
│   ├── settings.py              # Environment configuration
│   ├── chat_agent.py            # Chat orchestration (ops + K8s + Airflow + RAG)
│   ├── rag_engine.py            # RAG: retrieve → assemble → Gemini
│   ├── llm_client.py            # LLM dispatcher (Vertex / Ollama)
│   ├── llm_vertex.py            # Google Gemini client (google-genai SDK)
│   ├── embedding_pipeline.py    # Embed code, logs, DAGs, lineage → ChromaDB
│   ├── vectordb_client.py       # ChromaDB client
│   ├── lineage_client.py        # Marquez REST API client
│   ├── log_analyzer.py          # Heuristic + LLM log analysis
│   ├── airflow_logs.py          # Airflow REST API log fetcher
│   ├── airflow_status_client.py # Airflow DAG/run/task API client
│   ├── k8s_logs.py              # Kubernetes pod log + diagnosis
│   ├── ops_sync.py              # Background Airflow status sync
│   ├── ops_store.py             # Ops snapshot persistence (ChromaDB PVC)
│   └── repo_context.py          # Fallback repo file search
├── dags/
│   ├── data_ingestion_dag.py    # Ingest CSV + API → raw zone
│   ├── data_transformation_dag.py  # Clean → staging → processed → curated
│   ├── data_quality_dag.py      # Schema, null, row count, duplicate checks
│   ├── ml_pipeline_dag.py       # Features + RandomForest training
│   ├── demo_pipeline_dag.py     # Full end-to-end demo (clean/bad data)
│   ├── demo_observability_dag.py # Intentionally failing tasks for demo
│   └── utils/
│       ├── lineage.py           # emit_dataset_lineage() → Marquez
│       ├── storage_io.py        # File I/O helpers (GCS-compatible)
│       └── storage_paths.py     # Data lake zone path builder
├── frontend/src/
│   ├── pages/
│   │   ├── ChatPage.jsx         # RAG chatbot with markdown rendering
│   │   ├── LogAnalysisPage.jsx  # Paste logs → AI diagnosis
│   │   ├── AirflowPage.jsx      # Task log analysis + recent failures
│   │   ├── K8sPage.jsx          # Pod browser + namespace diagnosis
│   │   └── LineagePage.jsx      # Data flow + task lineage view
│   └── components/
│       ├── Sidebar.jsx           # Navigation + ChromaDB stats + actions
│       ├── ModeSelector.jsx      # LLM mode selector
│       └── LogResultDisplay.jsx  # Analysis result card + Ask in Chat
├── docker/
│   ├── Dockerfile.backend       # FastAPI + embeddings + google-genai
│   ├── Dockerfile.airflow       # Airflow + OpenLineage + DAGs
│   └── Dockerfile.frontend      # React build → nginx
├── k8s/
│   ├── namespaces.yaml          # backend, airflow, data namespaces
│   ├── backend/
│   │   ├── deployment.yaml      # Backend + ConfigMap + Secret + PVC
│   │   ├── frontend.yaml        # Frontend nginx + Service (LoadBalancer)
│   │   └── rbac.yaml            # ServiceAccount + ClusterRoleBinding
│   ├── airflow/
│   │   └── deployment.yaml      # Webserver + Scheduler + Service (LoadBalancer)
│   ├── data/
│   │   ├── postgres.yaml        # PostgreSQL StatefulSet + PVC
│   │   └── marquez.yaml         # Marquez API + Web UI
│   └── demo-faults.yaml         # Broken pods for K8s observability demo
└── scripts/
    ├── deploy-gke.sh            # Full one-command GKE deployment
    └── teardown-gke.sh          # Delete cluster and all resources
```

## How the RAG Pipeline Works

```
User question (e.g. "Why did validate_raw_data fail?")
        │
        ▼
  Encode with all-MiniLM-L6-v2
        │
        ▼
  Search 4 ChromaDB collections
  ├── code_embeddings   (DAG source, backend code)
  ├── log_embeddings    (analyzed failure logs)
  ├── dag_metadata      (DAG/task descriptions)
  └── lineage_data      (dataset I/O from Marquez)
        │
        ▼
  Inject live context (if relevant):
  ├── Airflow ops snapshot (DAG states, recent failures)
  ├── Kubernetes namespace diagnosis
  └── Airflow task log analysis
        │
        ▼
  Build prompt: system prompt + retrieved chunks + live context + question
        │
        ▼
  Google Gemini Flash → answer
        │
        ▼
  Response + cited sources
```

## Environment Variables

Set in `k8s/backend/deployment.yaml` (ConfigMap) and as a K8s Secret:

| Variable | Where | Description |
|---|---|---|
| `GOOGLE_API_KEY` | Secret | Google AI Studio API key |
| `LLM_PROVIDER` | ConfigMap | `vertex` (uses Gemini) |
| `VERTEX_MODEL` | ConfigMap | `gemini-2.5-flash` or `gemini-2.0-flash` |
| `EMBEDDING_MODEL` | ConfigMap | `all-MiniLM-L6-v2` |
| `CHROMADB_MODE` | ConfigMap | `local` |
| `CHROMADB_PERSIST_DIR` | ConfigMap | `/chromadb` (PVC-mounted) |
| `AIRFLOW_BASE_URL` | ConfigMap | Internal cluster URL for Airflow API |
| `AIRFLOW_USERNAME` | ConfigMap | `admin` |
| `AIRFLOW_PASSWORD` | ConfigMap | `admin` |
| `MARQUEZ_URL` | ConfigMap | Internal cluster URL for Marquez |

> **Never run `kubectl apply -f k8s/backend/deployment.yaml` directly** — it contains `REPLACE_ME` as the API key placeholder. Always inject the secret separately:
> ```cmd
> kubectl -n backend create secret generic backend-secrets --from-literal=GOOGLE_API_KEY="your-key" --dry-run=client -o yaml | kubectl apply -f -
> ```

## Troubleshooting

| Issue | Solution |
|---|---|
| Chat returns "API key not valid" | Re-inject the secret: `kubectl -n backend create secret generic backend-secrets --from-literal=GOOGLE_API_KEY="key" --dry-run=client -o yaml \| kubectl apply -f -`, then `kubectl -n backend rollout restart deployment/backend` |
| Chat returns "503 Unavailable" | Gemini rate limit — wait 1-2 min, or switch `VERTEX_MODEL` to `gemini-2.0-flash` |
| Recent failures not showing | Background sync takes ~5s after pod start. Wait and hard refresh (`Ctrl+Shift+R`) |
| Airflow "Errno -2 Name or service not known" | Re-apply ConfigMap: `kubectl apply -f k8s/backend/deployment.yaml` (API key will be overwritten — re-inject secret after) |
| `kubectl` fails with `gke-gcloud-auth-plugin not found` | Run: `gcloud components install gke-gcloud-auth-plugin` |
| `InvalidImageName` on deployment | Variables not set in CMD session — re-run `set REGISTRY=...` and `set TAG=...` before `kubectl set image` |
| Lineage shows "no datasets" | Expand a task to see inputs/outputs. If still empty, DAGs haven't run yet — trigger a DAG in Airflow first |
| Backend pod restarting | Check logs: `kubectl -n backend logs deployment/backend --tail=50` |
