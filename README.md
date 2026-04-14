# BigData Platform — Observability Agent

A complete data platform with **Airflow DAGs**, **OpenLineage/Marquez lineage tracking**, **Kubernetes deployment**, and a **RAG-powered chatbot** (ChromaDB + Ollama LLaMA 3.1) that analyzes logs, explains failures, and answers questions about your codebase, DAGs, and data lineage.

**100% free & open-source** — no OpenAI, no paid APIs.

## Architecture

```
┌─────────────┐    ┌─────────────────────────────────────────────────────┐
│  Streamlit   │───▶│  FastAPI Backend                                  |
│  Chat UI     │    │  /chat  /analyze-log  /index/*  /lineage/*         │
└─────────────┘    └────┬──────────┬──────────┬──────────┬───────────────┘
                        │          │          │          │
                   ┌────▼───┐ ┌───▼────┐ ┌───▼────┐ ┌──▼──────────┐
                   │  RAG   │ │  Log   │ │Lineage │ │  Embedding  │
                   │ Engine │ │Analyzer│ │ Client │ │  Pipeline   │
                   └───┬────┘ └────────┘ └───┬────┘ └──┬──────────┘
                       │                     │         │
                  ┌────▼────┐          ┌─────▼───┐ ┌───▼──────────┐
                  │ Ollama  │          │ Marquez │ │   ChromaDB   │
                  │LLaMA3.1│          │(lineage)│ │ (vector DB)  │
                  └─────────┘          └────┬────┘ └──────────────┘
                                            │
                                    ┌───────▼────────┐
                                    │ Apache Airflow  │
                                    │ 5 DAGs + OL     │
                                    └────────────────┘
```

## What's Built

| Component | Technology | Purpose |
|---|---|---|
| LLM | Ollama + LLaMA 3.1:8b | Free local inference for chat & log analysis |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) | Embed code, logs, DAG metadata, lineage into vectors |
| Vector DB | ChromaDB | Store & search embeddings for RAG |
| RAG Engine | Custom (retrieve → assemble → prompt → LLM) | Answer questions using indexed project context |
| Data Pipelines | Apache Airflow (5 DAGs) | Ingestion, transformation, quality, ML, deployment |
| Lineage | OpenLineage + Marquez | Track data lineage across all DAG tasks |
| Backend | FastAPI | REST API for analysis, chat, indexing, lineage |
| Frontend | Streamlit | Chat UI with indexing & lineage controls |
| Containers | Docker + docker-compose | All services containerized |
| Orchestration | Kubernetes manifests | Production deployment with namespaces, PVCs, Ingress |

## Airflow DAGs

| DAG | Schedule | What it does |
|---|---|---|
| `data_ingestion` | `@hourly` | Ingests CSV files + API data into raw data lake |
| `data_transformation` | `@daily` | Cleans, aggregates, enriches data → curated zone |
| `data_quality_checks` | `@daily` | Schema validation, null checks, row counts, duplicates |
| `ml_pipeline` | `@weekly` | Feature engineering + RandomForest training + evaluation |
| `deploy_pipeline` | Manual | Tests → Docker build → K8s deploy → observability notify |

## API Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Health check |
| POST | `/chat` | RAG-powered chat (uses ChromaDB + Ollama) |
| POST | `/analyze-log` | Analyze pasted logs (heuristic + LLM) |
| POST | `/analyze-k8s-pod` | Fetch + analyze Kubernetes pod logs |
| POST | `/analyze-airflow-task` | Fetch + analyze Airflow task logs |
| POST | `/index/codebase` | Index project code into ChromaDB |
| POST | `/index/log` | Index a log entry into ChromaDB |
| GET | `/index/stats` | VectorDB collection statistics |
| GET | `/lineage/namespaces` | List Marquez namespaces |
| GET | `/lineage/jobs/{ns}` | List lineage jobs |
| GET | `/lineage/datasets/{ns}` | List lineage datasets |
| POST | `/lineage/graph` | Get lineage graph for a job/dataset |
| POST | `/lineage/sync` | Sync Marquez lineage into ChromaDB |

---

## Quick Start (Local Development)

### Prerequisites

- Python 3.11+
- [Ollama](https://ollama.com) installed
- Docker & Docker Compose (for full stack)

### Step 1: Install Ollama and pull the model

```bash
# Install from https://ollama.com, then:
ollama pull llama3.1:8b
```

This downloads the free LLaMA 3.1 8B model (~4.7 GB). It runs entirely on your machine.

### Step 2: Clone and set up

```bat
git clone <your-repo-url>
cd bigdata-prototype

python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

copy .env.example .env
```

### Step 3: Index the codebase into ChromaDB

```bat
python scripts\index_codebase.py
```

This walks all project files, chunks them, embeds with `all-MiniLM-L6-v2`, and stores in ChromaDB. Takes ~30 seconds on first run.

### Step 4: Start the backend

```bat
python -m uvicorn backend.app.main:app --reload --port 8000
```

### Step 5: Start the frontend (new terminal)

```bat
streamlit run frontend\streamlit_app.py
```

### Step 6: Chat!

Open http://localhost:8501 and ask questions like:
- "What DAGs are in this project?"
- "Explain the data_transformation DAG"
- "What does the RAG engine do?"
- Paste failing logs and ask "Why did this fail?"

---

## Full Stack with Docker Compose

This runs ALL services: Backend, Frontend, Ollama, Airflow (webserver + scheduler + worker), PostgreSQL, Redis, Marquez (API + Web UI).

### Step 1: Start everything

```bash
cd docker
docker-compose up -d
```

### Step 2: Pull the LLM model inside the Ollama container

```bash
docker exec -it ollama ollama pull llama3.1:8b
```

### Step 3: Initialize Airflow

```bash
# This runs automatically via airflow-init, but if you need to re-run:
docker exec -it airflow-webserver airflow db init
docker exec -it airflow-webserver airflow users create \
  --username admin --password admin \
  --firstname Admin --lastname User --role Admin --email admin@example.com
```

### Step 4: Index the codebase

```bash
# From inside the backend container:
docker exec -it backend python scripts/index_codebase.py
```

### Step 5: Access the services

| Service | URL | Credentials |
|---|---|---|
| Streamlit Chat UI | http://localhost:8501 | — |
| FastAPI Backend | http://localhost:8000 | — |
| FastAPI Docs | http://localhost:8000/docs | — |
| Airflow UI | http://localhost:8080 | admin / admin |
| Marquez Lineage UI | http://localhost:3000 | — |
| Marquez API | http://localhost:5000 | — |
| Ollama | http://localhost:11434 | — |

### Step 6: Enable and trigger DAGs

1. Open Airflow UI at http://localhost:8080
2. Unpause the DAGs you want to run
3. Trigger `data_ingestion` first, then `data_transformation`, then `data_quality_checks`
4. Lineage events are automatically sent to Marquez via OpenLineage
5. View lineage graph at http://localhost:3000

### Step 7: Sync lineage to VectorDB

```bash
# From the Streamlit sidebar, click "Sync Lineage to VectorDB"
# Or via API:
curl -X POST http://localhost:8000/lineage/sync
```

Now the chatbot can answer lineage questions like "What datasets does data_ingestion produce?"

---

## Kubernetes Deployment

### Prerequisites

- A Kubernetes cluster (minikube, kind, EKS, GKE, AKS)
- `kubectl` configured
- Docker images built and pushed to a registry

### Step 1: Build and push images

```bash
# From project root:
docker build -t your-registry/bigdata-backend:latest -f docker/Dockerfile.backend .
docker build -t your-registry/bigdata-airflow:latest -f docker/Dockerfile.airflow .
docker build -t your-registry/bigdata-frontend:latest -f docker/Dockerfile.frontend .

docker push your-registry/bigdata-backend:latest
docker push your-registry/bigdata-airflow:latest
docker push your-registry/bigdata-frontend:latest
```

### Step 2: Create namespaces

```bash
kubectl apply -f k8s/namespaces.yaml
```

### Step 3: Deploy all services

```bash
kubectl apply -f k8s/ --recursive
```

This creates:
- **backend** namespace: FastAPI (2 replicas), Ollama, Frontend, ChromaDB PVC
- **airflow** namespace: Webserver, Scheduler, Worker (2 replicas), Redis, Data Lake PVC
- **data** namespace: PostgreSQL, Marquez API, Marquez Web
- **Ingress** rules for external access

### Step 4: Pull Ollama model in the cluster

```bash
kubectl exec -it deployment/ollama -n backend -- ollama pull llama3.1:8b
```

### Step 5: Access via Ingress

Add to your `/etc/hosts` (or DNS):
```
<INGRESS_IP>  bigdata.local api.bigdata.local airflow.bigdata.local lineage.bigdata.local
```

| Host | Service |
|---|---|
| bigdata.local | Streamlit UI |
| api.bigdata.local | FastAPI Backend |
| airflow.bigdata.local | Airflow UI |
| lineage.bigdata.local | Marquez Lineage UI |

---

## Project Structure

```
bigdata-prototype/
├── backend/app/
│   ├── main.py                 # FastAPI app with all endpoints
│   ├── models.py               # Pydantic request/response models
│   ├── settings.py             # Environment configuration
│   ├── chat_agent.py           # Chat endpoint → RAG engine
│   ├── rag_engine.py           # RAG: retrieve → assemble → LLM
│   ├── vectordb_client.py      # ChromaDB client (local/server)
│   ├── embedding_pipeline.py   # Embed code, logs, DAGs, lineage
│   ├── lineage_client.py       # Marquez/OpenLineage API client
│   ├── llm_client.py           # Ollama LLM client (chat + JSON)
│   ├── llm_ollama.py           # Ollama HTTP API wrapper
│   ├── log_analyzer.py         # Heuristic + LLM log analysis
│   ├── repo_context.py         # Fallback file-walk search
│   ├── k8s_logs.py             # Kubernetes pod log fetcher
│   └── airflow_logs.py         # Airflow REST API log fetcher
├── dags/
│   ├── data_ingestion_dag.py   # Ingest CSV + API data
│   ├── data_transformation_dag.py  # Clean, aggregate, enrich
│   ├── data_quality_dag.py     # Schema, null, row, duplicate checks
│   ├── ml_pipeline_dag.py      # Features + model training
│   └── deploy_pipeline_dag.py  # Test → build → deploy → notify
├── docker/
│   ├── Dockerfile.backend      # FastAPI + RAG + embeddings
│   ├── Dockerfile.airflow      # Airflow + OpenLineage + DAGs
│   ├── Dockerfile.frontend     # Streamlit UI
│   ├── docker-compose.yml      # Full stack (11 services)
│   └── init-multiple-dbs.sh    # PostgreSQL multi-DB init
├── k8s/
│   ├── namespaces.yaml         # backend, airflow, data, monitoring
│   ├── ingress.yaml            # External access rules
│   ├── backend/
│   │   ├── deployment.yaml     # FastAPI + ConfigMap + PVC
│   │   ├── ollama.yaml         # Ollama LLM server
│   │   └── frontend.yaml       # Streamlit UI
│   ├── airflow/
│   │   └── deployment.yaml     # Webserver + Scheduler + Worker + Redis
│   └── data/
│       ├── postgres.yaml       # PostgreSQL + PVC
│       └── marquez.yaml        # Marquez API + Web UI
├── frontend/
│   └── streamlit_app.py        # Chat UI with RAG controls
├── scripts/
│   ├── index_codebase.py       # Index project code → ChromaDB
│   ├── sync_lineage.py         # Sync Marquez lineage → ChromaDB
│   ├── analyze_command.py      # Wrap deploy command with analysis
│   ├── analyze_k8s_pod.py      # CLI: analyze K8s pod logs
│   ├── analyze_airflow_task.py # CLI: analyze Airflow task logs
│   └── post_logs.py            # POST log file to backend
├── ci/
│   └── github-actions-example.yml
├── requirements.txt
├── .env.example
└── README.md
```

## Technology Choices (All Free & Open-Source)

| Need | Choice | Why |
|---|---|---|
| LLM | **LLaMA 3.1:8b via Ollama** | Best open-source model at 8B scale. Runs on CPU (slow) or GPU (fast). Ollama makes it trivial to run locally. |
| Embeddings | **all-MiniLM-L6-v2** (sentence-transformers) | Only ~80 MB, runs on CPU, excellent quality for semantic search. No API needed. |
| Vector DB | **ChromaDB** | Simple, Python-native, persistent storage, cosine similarity built-in. Zero config. |
| Lineage | **OpenLineage + Marquez** | Linux Foundation projects. OpenLineage is the standard for lineage events. Marquez stores + visualizes them. |
| Orchestration | **Apache Airflow** | Industry standard for data pipeline orchestration. Native OpenLineage support. |
| Container runtime | **Docker** | Standard containerization. |
| K8s deployment | **Kubernetes manifests** | Production-grade orchestration, scaling, self-healing. |
| Backend | **FastAPI** | Async, fast, auto-generated OpenAPI docs. |
| Frontend | **Streamlit** | Quick Python-native UI for data tools. |

## How the RAG Pipeline Works

```
User Question
      │
      ▼
 ┌────────────────┐
 │ Encode query    │  ← sentence-transformers (all-MiniLM-L6-v2)
 │ into embedding  │
 └───────┬────────┘
         │
         ▼
 ┌────────────────┐
 │ Search ChromaDB │  ← Query 4 collections:
 │  (cosine sim)   │     code_embeddings, log_embeddings,
 │                 │     dag_metadata, lineage_data
 └───────┬────────┘
         │
         ▼
 ┌────────────────┐
 │ Filter & rank   │  ← Distance threshold, sort by relevance
 │ retrieved chunks│
 └───────┬────────┘
         │
         ▼
 ┌────────────────┐
 │ Assemble prompt │  ← System prompt + context + history + question
 │ with context    │
 └───────┬────────┘
         │
         ▼
 ┌────────────────┐
 │ Call Ollama     │  ← LLaMA 3.1:8b generates answer
 │ (LLaMA 3.1)    │
 └───────┬────────┘
         │
         ▼
    Answer + Sources
```

## Troubleshooting

| Issue | Solution |
|---|---|
| Ollama not responding | Run `ollama serve` and check http://localhost:11434 is accessible |
| "No indexed context" in chat | Run `python scripts\index_codebase.py` to index the codebase |
| Slow LLM responses | LLaMA 3.1:8b on CPU takes ~30-60s. Use a GPU or try `ollama pull phi3:mini` for faster (smaller) model |
| ChromaDB errors | Delete `.chromadb/` folder and re-index |
| Airflow DAGs not showing | Check that `dags/` folder is mounted into the Airflow container |
| Marquez unreachable | Verify Marquez is running at the configured `MARQUEZ_URL` |
| Docker compose OOM | Increase Docker Desktop memory to at least 8 GB |
