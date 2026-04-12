# BigData Platform — Observability Agent

An AI-powered chatbot for monitoring Airflow DAGs, analyzing pipeline failures, and answering questions about your data platform using RAG (Retrieval-Augmented Generation).

---

## Live URLs

| Service | URL |
|---|---|
| **Frontend (Chatbot)** | https://bigdata-frontend-a2vn2ihr2a-uc.a.run.app |
| **Backend API** | https://bigdata-backend-770757350817.us-central1.run.app |
| **Airflow UI** | https://3d7249feafb548c683a6a11e7186446b-dot-us-central1.composer.googleusercontent.com |
| **GCP Console** | https://console.cloud.google.com/home/dashboard?project=bda-project-gcp |

---

## Architecture

```
Cloud Composer (Airflow DAGs)
        ↓ auto
Cloud Logging
        ↓ Log Router Sinks
   ┌────┴──────────────┐
BigQuery              Pub/Sub
(SQL archive)           ↓
                Cloud Function (airflow-log-indexer)
                        ↓
                Backend /index/log
                        ↓
            ChromaDB (vector store + RAG)
                        ↓
            Vertex AI Gemini (chat answers)
                        ↑
                React Frontend (nginx)
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React + Vite + Tailwind + nginx |
| Backend API | FastAPI (Python 3.11) |
| LLM | Google Gemini (`gemini-3.1-pro-preview`) via AI Studio API key |
| Vector Store | ChromaDB |
| Embeddings | `all-MiniLM-L6-v2` (baked into Docker image) |
| Orchestration | Cloud Composer (managed Airflow 2.10.5) |
| Data Lake | Google Cloud Storage (`bda-project-bigdata`) |
| Log Capture | Cloud Logging → Pub/Sub → Cloud Functions |
| Log Archive | BigQuery (`airflow_logs` dataset) |
| CI/CD | Cloud Build + Artifact Registry |
| Hosting | Cloud Run (backend + frontend) |
| Secrets | Google Secret Manager |

---

## Project Structure

```
bigdata-prototype/
├── backend/
│   └── app/
│       ├── main.py                  # FastAPI app + lifespan auto-indexer
│       ├── chat_agent.py            # Chat endpoint with RAG + tool context
│       ├── rag_engine.py            # RAG pipeline: retrieve → prompt → LLM
│       ├── llm_client.py            # LLM provider abstraction
│       ├── llm_vertex.py            # Gemini client (API key or Vertex AI)
│       ├── embedding_pipeline.py    # ChromaDB indexing
│       ├── ops_sync.py              # Airflow DAG status sync
│       ├── airflow_status_client.py # Airflow REST API client (v1 + IAM auth)
│       ├── airflow_logs.py          # Fetch Airflow task logs
│       ├── log_analyzer.py          # Heuristic + LLM log analysis
│       ├── lineage_client.py        # Marquez lineage integration
│       └── settings.py              # Env var config
├── frontend/
│   └── src/
│       ├── pages/
│       │   ├── ChatPage.jsx         # Main chatbot UI
│       │   ├── AirflowPage.jsx      # DAG monitoring
│       │   ├── LogAnalysisPage.jsx  # Paste + analyze logs
│       │   ├── K8sPage.jsx          # Kubernetes pod logs
│       │   └── LineagePage.jsx      # Data lineage (Marquez)
│       └── components/
│           ├── Navbar.jsx
│           └── Sidebar.jsx          # Index + stats controls
├── dags/
│   ├── data_ingestion_dag.py        # @daily — CSV + API ingestion
│   ├── data_transformation_dag.py   # @daily — clean + transform
│   ├── data_quality_dag.py          # @daily — curated data validation
│   ├── ml_pipeline_dag.py           # @weekly — feature eng + training
│   ├── demo_pipeline_dag.py         # @daily — full pipeline demo
│   ├── demo_observability_dag.py    # @daily — intentional failures
│   ├── deploy_pipeline_dag.py       # @weekly — build + deploy
│   └── utils/
│       ├── storage_io.py            # GCS + local storage abstraction
│       └── storage_paths.py         # Zone path builder
├── cloud_functions/
│   └── log_indexer/
│       ├── main.py                  # Pub/Sub → /index/log indexer
│       └── requirements.txt
├── docker/
│   ├── Dockerfile.backend           # Python 3.11 + embedded ML model
│   ├── Dockerfile.frontend          # Node 20 build + nginx serve
│   └── nginx-frontend.conf          # Reverse proxy to backend
├── cloudbuild.backend.yaml          # Backend CI/CD pipeline
├── cloudbuild.frontend.yaml         # Frontend CI/CD pipeline
└── requirements.txt                 # Python dependencies
```

---

## Quick Start — Full Deployment

### 1. Authenticate
```bash
gcloud auth login
gcloud config set project bda-project-gcp
cd ~/bigdata-prototype
```

### 2. Store API Key in Secret Manager
Get your key from https://aistudio.google.com/app/apikey
```bash
echo -n "YOUR_API_KEY" | gcloud secrets create GOOGLE_API_KEY \
  --data-file=- --project=bda-project-gcp

gcloud secrets add-iam-policy-binding GOOGLE_API_KEY \
  --member="serviceAccount:770757350817-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor" --project=bda-project-gcp
```

### 3. Deploy Backend
```bash
gcloud builds submit --config cloudbuild.backend.yaml .
```

### 4. Deploy Frontend
```bash
gcloud builds submit --config cloudbuild.frontend.yaml .
```

### 5. Index Codebase
```bash
curl -X POST https://bigdata-backend-770757350817.us-central1.run.app/index/codebase \
  -H "Content-Type: application/json" -d '{"reset": true}'
```

### 6. Upload DAGs to Composer
```bash
DAGS_BUCKET=$(gcloud composer environments describe bigdata-composer \
  --location=us-central1 --format="value(config.dagGcsPrefix)")

gsutil -m cp dags/*.py ${DAGS_BUCKET}/
gsutil -m cp dags/utils/*.py ${DAGS_BUCKET}/utils/
```

### 7. Sync Airflow Status
```bash
curl -X POST https://bigdata-backend-770757350817.us-central1.run.app/ops/sync-airflow
```

### 8. Test Chat
```bash
curl -X POST https://bigdata-backend-770757350817.us-central1.run.app/chat \
  -H "Content-Type: application/json" \
  -d '{"question":"Which DAGs are failing and why?","history":[],"mode":"auto","include_repo_context":true}'
```

---

## After Every Backend Rebuild

> **Critical:** Run these every time you deploy a new backend image.

```bash
# 1. Re-index codebase (ChromaDB resets on new revision)
curl -X POST https://bigdata-backend-770757350817.us-central1.run.app/index/codebase \
  -H "Content-Type: application/json" -d '{"reset": true}'

# 2. Re-sync Airflow status
curl -X POST https://bigdata-backend-770757350817.us-central1.run.app/ops/sync-airflow
```

---

## After Every Frontend Rebuild

> **Critical:** Verify folder structure before building.

```bash
ls frontend/
# Must show: src/ index.html package.json vite.config.js
# Must NOT show: streamlit_app.py or nested frontend/ folder

grep -E "listen|proxy_pass" docker/nginx-frontend.conf
# Must show: listen 8080
# Must show: proxy_pass https://bigdata-backend-770757350817.us-central1.run.app
```

---

## Environment Variables

Set on the Cloud Run backend service. **Always use `--set-env-vars` (not `--update-env-vars`) to avoid wiping existing vars.**

| Variable | Value |
|---|---|
| `LLM_PROVIDER` | `vertex` |
| `VERTEX_PROJECT_ID` | `bda-project-gcp` |
| `VERTEX_LOCATION` | `us-central1` |
| `VERTEX_MODEL` | `gemini-3.1-pro-preview` |
| `GOOGLE_CLOUD_PROJECT` | `bda-project-gcp` |
| `GOOGLE_GENAI_USE_VERTEXAI` | `True` |
| `CHROMADB_MODE` | `local` |
| `CHROMADB_PERSIST_DIR` | `/tmp/chromadb` |
| `APP_ENV` | `prod` |
| `GCS_DATA_BUCKET` | `bda-project-bigdata` |
| `AIRFLOW_BASE_URL` | `https://3d7249feafb548c683a6a11e7186446b-dot-us-central1.composer.googleusercontent.com` |
| `GOOGLE_API_KEY` | Stored in Secret Manager — not plain text |

---

## Secrets

```bash
# Store a secret
echo -n "VALUE" | gcloud secrets create SECRET_NAME \
  --data-file=- --project=bda-project-gcp

# Update a secret
echo -n "NEW_VALUE" | gcloud secrets versions add SECRET_NAME \
  --data-file=- --project=bda-project-gcp

# Reference in Cloud Run (not --set-env-vars)
--set-secrets=GOOGLE_API_KEY=GOOGLE_API_KEY:latest
```

---

## DAGs

| DAG | Schedule | Purpose |
|---|---|---|
| `data_ingestion` | `@daily` | Ingest CSV + API data into raw zone |
| `data_transformation` | `@daily` | Clean, transform, enrich to curated zone |
| `data_quality_checks` | `@daily` | Validate curated data quality |
| `ml_pipeline` | `@weekly` | Feature engineering + model training |
| `demo_pipeline` | `@daily` | Full end-to-end pipeline demo |
| `demo_observability` | `@daily` | Intentional failures for chatbot testing |
| `deploy_pipeline` | `@weekly` | Build + deploy services |

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Health check |
| `POST` | `/chat` | RAG-powered chat |
| `POST` | `/analyze-log` | Analyze pasted log text |
| `POST` | `/index/codebase` | Index repo into ChromaDB |
| `GET` | `/index/stats` | ChromaDB chunk counts |
| `POST` | `/ops/sync-airflow` | Sync live DAG status from Composer |
| `GET` | `/ops/summary` | Get cached DAG snapshot |
| `GET` | `/ops/list-dags` | List all Airflow DAGs |
| `POST` | `/lineage/sync` | Sync Marquez lineage to ChromaDB |

---

## Troubleshooting

| Issue | Fix |
|---|---|
| `LLM failed; using heuristic` | API key missing or model not found. Check `GOOGLE_API_KEY` secret. |
| `RAG returns 0 chunks` | Re-index: `POST /index/codebase` |
| `Airflow sync returns UNKNOWN` | `AIRFLOW_BASE_URL` not set. Use `--set-env-vars` with all vars. |
| `nginx 403 Forbidden` | Port must be `8080` in `nginx-frontend.conf` |
| `nginx 502 Bad Gateway` | `proxy_pass` must use full HTTPS URL, not `http://backend:8000` |
| `Frontend shows Streamlit` | Nested folder issue: `cp -r frontend/frontend/* frontend/ && rm -rf frontend/frontend && rm frontend/streamlit_app.py` |
| `Cloud Build permission denied` | Grant `roles/run.admin` and `roles/iam.serviceAccountUser` to compute SA |
| `cloudbuild.yaml parse error` | File corrupted — recreate with `cat > cloudbuild.backend.yaml << 'EOF'` |
| `--update-env-vars wipes vars` | Always use `--set-env-vars` with ALL env vars listed together |

---

## Team Access

```bash
USER_EMAIL="teammate@gmail.com"

# GCP Console access
gcloud projects add-iam-policy-binding bda-project-gcp \
  --member="user:${USER_EMAIL}" --role="roles/viewer"

# Cloud Composer access
gcloud projects add-iam-policy-binding bda-project-gcp \
  --member="user:${USER_EMAIL}" --role="roles/composer.user"

# Airflow UI access
gcloud composer environments run bigdata-composer \
  --location=us-central1 users create -- \
  --username="${USER_EMAIL}" --role=Op \
  --email="${USER_EMAIL}" --firstname=First --lastname=Last \
  --use-random-password
```

---

## Key Lessons Learned

- **Always `--set-env-vars`** — `--update-env-vars` wipes all other env vars on the new revision
- **Always re-index after backend rebuild** — ChromaDB is in-memory and resets on new Cloud Run revisions
- **Use `--min-instances=1`** — prevents scale-to-zero from wiping ChromaDB data between requests
- **Airflow Composer 3 uses `/api/v1/`** — not `/api/v2/`
- **Airflow auth uses access token** — `google.auth.default()`, not identity token or basic auth
- **Embed the ML model in Docker** — avoids HuggingFace rate limits at runtime
- **nginx must listen on port 8080** — Cloud Run default, not 80
- **`proxy_pass` needs full HTTPS URL** — not `http://backend:8000` (Docker Compose hostname)
- **Gemini Publisher Models unavailable** — use Google AI Studio API key stored in Secret Manager
