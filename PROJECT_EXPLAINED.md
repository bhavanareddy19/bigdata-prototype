# BigData Platform — Complete Project Explanation
### Everything explained in simple English, with real examples

---

## TABLE OF CONTENTS

1. [What Are We Building?](#1-what-are-we-building)
2. [The Problem This Solves](#2-the-problem-this-solves)
3. [All The Tools We Use & Why](#3-all-the-tools-we-use--why)
4. [How All 10 Services Run Together (Docker)](#4-how-all-10-services-run-together-docker)
5. [The Data Pipelines — Apache Airflow](#5-the-data-pipelines--apache-airflow)
6. [The AI Brain — RAG + ChromaDB + Ollama](#6-the-ai-brain--rag--chromadb--ollama)
7. [The Backend — FastAPI](#7-the-backend--fastapi)
8. [The Frontend — Streamlit Chatbot](#8-the-frontend--streamlit-chatbot)
9. [Data Lineage — OpenLineage + Marquez](#9-data-lineage--openlineage--marquez)
10. [The Databases — PostgreSQL + Redis](#10-the-databases--postgresql--redis)
11. [The 3 Analysis Modes](#11-the-3-analysis-modes)
12. [Complete End-to-End Flow (Step by Step)](#12-complete-end-to-end-flow-step-by-step)
13. [File-by-File Explanation](#13-file-by-file-explanation)
14. [How to Run the Project](#14-how-to-run-the-project)
15. [Common Questions & Answers](#15-common-questions--answers)

---

## 1. What Are We Building?

### Simple Answer

We are building an **AI-powered Big Data Observability Platform**. It does two main things:

```
PART 1 — Data Pipeline
  Automatically collects data → cleans it → checks quality → trains ML model

PART 2 — AI Chatbot
  When something breaks in the pipeline, the AI explains WHY it broke
  and HOW to fix it — using your actual code and real error logs
```

### Real-World Analogy

Think of a **large factory with a smart engineer assistant**:

```
FACTORY (your data pipeline):
  Raw materials arrive (CSV files, API data)
       ↓
  Assembly line processes them (Airflow DAGs)
       ↓
  Quality control checks the output
       ↓
  Final product is ready (clean data, trained ML model)

SMART ENGINEER ASSISTANT (AI chatbot):
  When a machine on the assembly line breaks:
  - The engineer READS the error log from that machine
  - READS the blueprint (your code)
  - EXPLAINS exactly what broke and why
  - TELLS you the exact steps to fix it
```

Without this system, when a pipeline fails at 3am, an engineer has to:
1. Log into the server
2. Dig through hundreds of log lines
3. Figure out which line caused the failure
4. Understand the root cause
5. Figure out how to fix it

With this system, you just ask the chatbot: "Why did my pipeline fail?" and get a precise answer in 30 seconds.

---

## 2. The Problem This Solves

### Real Problems in Data Engineering

**Problem 1: Pipelines fail silently**
```
Your data_ingestion DAG ran at 3am.
It failed. Nobody noticed.
The ML model is training on 2-day-old data.
Nobody knows.
```

**Problem 2: Error logs are hard to read**
```
[2026-02-23 15:26:15] ERROR - Task failed with exception
Traceback (most recent call last):
  File "/opt/airflow/dags/data_transformation_dag.py", line 47, in transform
    df = pd.read_csv(expected_file)
FileNotFoundError: /data/curated/curated_combined_data.csv: No such file or directory
```
You have to read this and figure out:
- What file is missing?
- Why is it missing?
- What do I run first?
- Is this a code bug or a data issue?

**Our Solution:**
```
You: "Why did task_fail_data fail?"

AI: "The task failed because it tried to read
     /data/curated/curated_combined_data.csv but this file
     doesn't exist yet. This file is produced by the
     data_transformation DAG which hasn't run.
     Fix: Run data_ingestion → data_transformation first."
```

**Problem 3: "What broke what?"**
When pipeline B fails, is it because pipeline A didn't finish? Lineage tracking answers this automatically.

---

## 3. All The Tools We Use & Why

Here is every tool used, explained simply:

| Tool | What it is | Why we use it |
|------|-----------|---------------|
| **Apache Airflow** | Pipeline scheduler | Runs your data jobs automatically on a schedule |
| **FastAPI** | Web server (backend) | Handles all API requests from the chatbot |
| **Streamlit** | Python web UI | The chatbot interface you see in browser |
| **Ollama** | Local LLM runner | Runs the AI model (LLaMA) on your own computer — FREE, no API key |
| **LLaMA 3.2:1b** | The AI model | The brain that understands your question and generates answers |
| **ChromaDB** | Vector database | Stores your code as searchable embeddings for RAG |
| **sentence-transformers** | Embedding model | Converts text to numbers (vectors) for similarity search |
| **OpenLineage** | Lineage standard | Records which job reads/writes which data |
| **Marquez** | Lineage server + UI | Stores and displays the lineage graph |
| **PostgreSQL** | Relational database | Stores Airflow metadata and Marquez data |
| **Redis** | Message queue | Passes jobs between Airflow scheduler and workers |
| **Docker** | Containerization | Packages every service so it runs the same on any machine |
| **Docker Compose** | Multi-container runner | Starts all 10 services with one command |
| **Kubernetes** | Production orchestrator | Runs the platform in production at scale (optional) |
| **pandas** | Data processing | Reads, cleans, and transforms CSV data in DAGs |
| **scikit-learn** | Machine learning | Trains the RandomForest model in ml_pipeline DAG |

---

## 4. How All 10 Services Run Together (Docker)

### What is Docker?

Without Docker, you'd need to install Python, Java, Node.js, PostgreSQL, Redis, etc. on your machine — and they might conflict with each other.

Docker wraps each service in its own **container** — like a self-contained box with everything it needs inside.

```
Your computer
├── Container: backend     (Python 3.11 + FastAPI + ChromaDB)
├── Container: frontend    (Python 3.11 + Streamlit)
├── Container: ollama      (LLaMA model runner)
├── Container: airflow-webserver
├── Container: airflow-scheduler
├── Container: airflow-worker
├── Container: postgres    (Database)
├── Container: redis       (Message queue)
├── Container: marquez-api (Lineage server - Java)
└── Container: marquez-web (Lineage UI - Node.js)
```

All containers talk to each other on a private network using their **service names** (e.g., `http://ollama:11434`, `http://marquez-api:5000`).

### Docker Compose

`docker/docker-compose.yml` is the file that defines all 10 services and their configuration.

**Key environment variables for each service:**

```yaml
backend:
  OLLAMA_BASE_URL: http://ollama:11434    # where the AI model is
  OLLAMA_MODEL: llama3.2:1b              # which model to use
  CHROMADB_PERSIST_DIR: /chromadb        # where to save vector data
  AIRFLOW_USERNAME: admin                # to fetch Airflow logs
  AIRFLOW_PASSWORD: admin

airflow (all 3 containers share these):
  AIRFLOW__API__AUTH_BACKENDS: basic_auth    # allows REST API login
  OPENLINEAGE_URL: http://marquez-api:5000   # sends lineage to Marquez
  OPENLINEAGE_NAMESPACE: bigdata-platform
```

### Important: Volumes

Some data must survive container restarts. We use volumes for this:

```
chromadb-data  →  /chromadb    (your indexed code stays after restart)
postgres-data  →  /var/lib/postgresql/data  (DAG history stays)
../dags        →  /opt/airflow/dags          (DAG files mounted live)
../data        →  /data                      (CSV files shared between services)
```

### Health Checks

Each service has a health check so Docker waits for it to be truly ready before starting dependent services:

```
postgres healthy → airflow can start
redis healthy    → airflow can start
ollama healthy   → backend knows LLM is ready
```

---

## 5. The Data Pipelines — Apache Airflow

### What is Airflow?

Airflow is like a **job scheduler with a visual dashboard**. You write Python functions (tasks), connect them in order, and Airflow runs them automatically on a schedule.

A **DAG** (Directed Acyclic Graph) is just a Python file that defines:
- What tasks to run
- In what order
- On what schedule

### Your 5 DAGs (Pipelines)

#### DAG 1: `data_ingestion` — runs every hour

```
Purpose: Collect raw data and put it in the data lake

Tasks:
  ingest_csv_files  →  reads landing/sales_data.csv, landing/user_events.csv
                       copies them to /data/raw/

  ingest_api_data   →  calls a fake API endpoint
                       saves response to /data/raw/api_data_{timestamp}.json

  validate_raw_data →  checks the raw files actually exist
                       counts how many rows were ingested

Flow: ingest_csv_files → ingest_api_data → validate_raw_data
```

#### DAG 2: `data_transformation` — runs daily

```
Purpose: Clean and transform raw data into useful formats

Tasks:
  clean_data          →  removes nulls, standardizes column names
                         saves to /data/staging/

  transform_aggregate →  aggregates by product, computes totals
                         saves to /data/processed/

  enrich_with_metadata →  adds timestamps, computed fields
                          saves final output to /data/curated/

Flow: clean_data → transform_aggregate → enrich_with_metadata
```

#### DAG 3: `data_quality_checks` — runs daily

```
Purpose: Verify the data is actually good before using it

Tasks (run in parallel):
  check_schema     →  verifies expected columns exist
  check_null_rates →  fails if >5% nulls in critical columns
  check_row_counts →  fails if row count drops >50% from yesterday
  check_duplicates →  fails if duplicate primary keys found

Flow: all 4 tasks run at the same time
```

#### DAG 4: `ml_pipeline` — runs weekly

```
Purpose: Train a machine learning model on the clean data

Tasks:
  build_features →  reads curated data, creates feature columns
                    saves features.csv to /data/features/

  train_model    →  loads features.csv
                    trains a RandomForestClassifier
                    saves model.pkl to /data/models/

  evaluate_model →  loads model, evaluates accuracy
                    prints metrics (accuracy, precision, recall)

Flow: build_features → train_model → evaluate_model
```

#### DAG 5: `deploy_pipeline` — manual trigger only

```
Purpose: Deploy updated code to Kubernetes

Tasks:
  run_tests          →  runs pytest
  build_backend_image  →  docker build for FastAPI
  build_frontend_image →  docker build for Streamlit
  deploy_to_kubernetes →  kubectl apply
  check_rollout_status →  kubectl rollout status
  notify_observability →  sends status to backend API

Flow: run_tests → build images → deploy → verify → notify
```

#### DAG 6: `demo_observability` — manual trigger only

```
Purpose: Intentionally fail so you can test the AI chatbot

Tasks:
  task_ok        →  SUCCEEDS — lists files in /data/landing
  task_fail_data →  FAILS with FileNotFoundError
                    (looks for curated_combined_data.csv which doesn't exist)
  task_fail_code →  FAILS with TypeError
                    (tries to add a string "NOT_A_NUMBER" to a float)

Flow: task_ok → [task_fail_data, task_fail_code] (parallel)
```

This demo DAG is used to test that the chatbot can detect and explain failures.

### Data Flow Between DAGs

```
/data/landing/      (raw CSV files put here manually)
      ↓
data_ingestion      (reads landing/, writes to raw/)
      ↓
/data/raw/
      ↓
data_transformation (reads raw/, writes to staging/ → processed/ → curated/)
      ↓
/data/curated/
      ↓
data_quality_checks (validates curated data)
      ↓
ml_pipeline         (reads curated/, writes to features/ → models/)
      ↓
/data/models/model.pkl
```

If `data_ingestion` fails, nothing else can run because `/data/raw/` will be empty.

---

## 6. The AI Brain — RAG + ChromaDB + Ollama

This is the most important and complex part. Let me explain it step by step.

### What is RAG?

**RAG = Retrieval-Augmented Generation**

Normal LLMs (like ChatGPT) only know what they learned during training. They don't know YOUR code.

RAG solves this:
```
Instead of: "Answer this question from memory"

RAG does:   "Search our database for relevant context
             → Give that context to the LLM
             → LLM answers using YOUR actual code/logs"
```

Analogy: Imagine you ask an expert engineer a question.
- **Without RAG**: Engineer answers from general knowledge (might be wrong for your specific code)
- **With RAG**: Engineer first reads your actual source files, THEN answers (specific and accurate)

### Step 1: Indexing (Building the Knowledge Base)

When you click **"Index Codebase"** in the chatbot sidebar:

```
Backend walks every file in the project:
  backend/app/*.py
  dags/*.py
  docker/*.yml
  *.md, *.toml, *.sh, etc.

For each file, splits into chunks of 60 lines (with 10-line overlap):
  chunk_0: lines 1-60
  chunk_1: lines 51-110    ← 10 lines overlap for context
  chunk_2: lines 101-160
  ...

Each chunk gets converted to a vector:
  "def fetch_airflow_task_logs(dag_id, task_id..."
       ↓  (sentence-transformers/all-MiniLM-L6-v2)
  [0.234, -0.891, 0.123, 0.456, ...]   ← 384 numbers

Stored in ChromaDB with metadata:
  {
    "id": "md5_hash",
    "document": "actual code text",
    "embedding": [0.234, -0.891, ...],
    "metadata": {"file": "backend/app/airflow_logs.py", "start_line": 24}
  }
```

ChromaDB has 4 collections (like 4 separate search indexes):

| Collection | What it stores |
|-----------|----------------|
| `code_embeddings` | All your Python/YAML/config files |
| `dag_metadata` | DAG names, task lists, schedules |
| `log_entries` | Previously analyzed logs |
| `lineage_data` | Which job reads/writes which dataset |

**Important:** Indexing is NOT automatic. Every time you change your code, you must click "Index Codebase" again to update ChromaDB.

### Step 2: Retrieving (Finding Relevant Code)

When you ask a question like "Why did task_fail_data fail?":

```
1. Your question gets converted to a vector:
   "Why did task_fail_data fail?"
        ↓  (same embedding model)
   [0.187, -0.654, 0.234, ...]

2. ChromaDB finds the most similar chunks:
   Searches ALL 4 collections simultaneously
   Returns top 5 code chunks + 3 log chunks + 3 DAG chunks + 3 lineage chunks

3. Results sorted by similarity score (lower distance = more relevant):
   [0.12] dags/demo_observability_dag.py lines 38-72  ← most relevant
   [0.18] backend/app/airflow_logs.py lines 24-65
   [0.24] dags/data_transformation_dag.py lines 1-60
   ...
```

### Step 3: Generating (LLM Answers with Context)

```
The LLM (llama3.2:1b) receives a prompt like:

SYSTEM: "You are a senior SRE/data engineer for a Big Data platform..."

CONTEXT (retrieved from ChromaDB):
  [Code] dags/demo_observability_dag.py (relevance: 0.88)
  def task_fail_data(**context):
      expected_file = os.getenv("CURATED_ZONE") + "/curated_combined_data.csv"
      if not os.path.exists(expected_file):
          raise FileNotFoundError(f"Required dataset not found: {expected_file}")

  [Airflow Logs] (from live Airflow API):
  FileNotFoundError: /data/curated/curated_combined_data.csv

USER: "Why did task_fail_data fail? How do I fix it?"

LLM OUTPUT:
  "The task_fail_data failed because it tried to read
   /data/curated/curated_combined_data.csv at line 48 of
   demo_observability_dag.py, but this file doesn't exist.
   This file is created by the data_transformation DAG.
   Fix: Run data_ingestion first, then data_transformation."
```

### Ollama — Running the LLM Locally

Ollama is a tool that runs open-source LLMs on your own machine. No internet required, no API costs.

```
Model used: llama3.2:1b
  - Size: 1.3 GB
  - Good for: development, CPU-only machines
  - Speed: ~15-30 seconds per response on CPU

vs llama3.1:8b (the bigger model):
  - Size: 4.9 GB
  - Better quality but: ~3-5 minutes per response on CPU
  - Only use if you have a GPU
```

The backend checks if Ollama is running before every request:
```python
def llm_available() -> bool:
    try:
        r = requests.get("http://ollama:11434/api/tags", timeout=3)
        return r.status_code == 200
    except:
        return False
```

If Ollama is down, it falls back to **heuristic mode** (regex pattern matching).

---

## 7. The Backend — FastAPI

The backend is a Python web server (`backend/app/main.py`) that exposes API endpoints.

### All API Endpoints

```
GET  /health                  → checks if backend is running
                                returns: {"status": "ok"}

POST /chat                    → main chatbot endpoint
                                input: question + optional logs + optional airflow/k8s info
                                output: answer + sources + diagnostics

POST /analyze-log             → analyze pasted log text
                                input: log_text, mode (auto/heuristic/llm)
                                output: category, error_signature, root_cause, next_actions

POST /analyze-k8s-pod         → fetch + analyze Kubernetes pod logs
                                input: namespace, pod, container, tail_lines
                                output: same as analyze-log

POST /analyze-airflow-task    → fetch + analyze Airflow task logs
                                input: dag_id, dag_run_id, task_id, try_number
                                output: same as analyze-log

POST /index/codebase          → index all code into ChromaDB
                                triggers when you click "Index Codebase"

POST /index/log               → index a specific log entry into ChromaDB

GET  /index/stats             → how many items are in ChromaDB
                                returns: {code_chunks, log_entries, dag_metadata, lineage_events}

GET  /lineage/namespaces      → list all Marquez namespaces
GET  /lineage/jobs/{ns}       → list all jobs in a namespace
GET  /lineage/datasets/{ns}   → list all datasets in a namespace
POST /lineage/graph           → get lineage graph for a specific job
POST /lineage/sync            → pull lineage from Marquez into ChromaDB
```

### How the Chat Endpoint Works (`/chat`)

```python
def chat(request):
    # Step 1: Fetch logs if requested
    if request has airflow info:
        logs = fetch_airflow_task_logs(dag_id, run_id, task_id)
        analysis = analyze_logs(logs)      # heuristic + LLM analysis
        add analysis to context

    if request has k8s info:
        logs = fetch_k8s_pod_logs(namespace, pod)
        analysis = analyze_logs(logs)
        add analysis to context

    if request has pasted log_text:
        analysis = analyze_logs(log_text)
        add analysis to context

    # Step 2: RAG query
    if ollama is available:
        chunks = chromadb.search(question)    # find relevant code
        context = format(chunks + analysis)
        answer = ollama.chat(system_prompt + context + question)
        return answer + sources

    else:
        # Fallback: just return heuristic analysis + code snippets
        return repo_snippets + analysis
```

---

## 8. The Frontend — Streamlit Chatbot

The frontend (`frontend/streamlit_app.py`) is a Python web app accessible at `http://localhost:8501`.

### Sidebar Controls

```
Settings
├── Mode dropdown
│     auto      → use LLM if available, else heuristic
│     heuristic → regex only, fast, no LLM
│     llm       → always use Ollama (fails if Ollama is down)
│
├── Backend URL  → where FastAPI is running (http://localhost:8000)
│
RAG Index
├── [Index Codebase] → scans all project files, stores in ChromaDB
│                      do this once, then again after code changes
├── [View Stats]     → shows how many chunks are indexed
│
Lineage (Marquez)
├── [Sync Lineage to VectorDB] → pulls job/dataset relationships from
│                                Marquez into ChromaDB for context
│
Optional: Paste Logs
├── text area → paste any log output here for analysis
│
Optional: Kubernetes pod
├── Namespace, Pod name, Container, Tail lines
│   → fetches logs directly from Kubernetes API
│
Optional: Airflow task
├── Airflow Base URL → http://airflow-webserver:8080
├── DAG ID          → e.g. demo_observability
├── DAG Run ID      → e.g. manual__2026-02-23T15:26:15.707C
├── Task ID         → e.g. task_fail_data
├── Try number      → 1 (first attempt)
```

### Chat Flow

```
You type: "Why did task_fail_data fail?"
                    ↓
Streamlit sends POST /chat to FastAPI with:
  {
    "question": "Why did task_fail_data fail?",
    "mode": "auto",
    "airflow": {
      "dag_id": "demo_observability",
      "dag_run_id": "manual__2026-02-23T15:26:15",
      "task_id": "task_fail_data",
      "try_number": 1
    }
  }
                    ↓
FastAPI fetches real Airflow logs
FastAPI runs RAG query
FastAPI calls Ollama
                    ↓
Streamlit displays the answer

Below the answer:
  [Sources & Retrieved Context] (expandable)
    Shows which code files were retrieved from ChromaDB
    Shows the actual code snippet
    Shows the relevance score (0.88 = very relevant)

  [Diagnostics] (expandable)
    Shows internal details like:
    rag_chunks: 8        (how many code chunks were used)
    airflow: { category: "DataQuality", confidence: 0.85 }
```

---

## 9. Data Lineage — OpenLineage + Marquez

### What is Data Lineage?

Lineage records the "family tree" of your data:

```
Who created this data?
Who reads this data?
What data does this job produce?
```

Example lineage graph:
```
sales_data.csv  ──→  data_ingestion  ──→  raw/sales_data.csv
                                               ↓
                               data_transformation  ──→  curated/curated_data.csv
                                                              ↓
                                              ml_pipeline  ──→  models/model.pkl
```

### OpenLineage

OpenLineage is a **standard** for how jobs report their data lineage. It defines a JSON format:
```json
{
  "eventType": "COMPLETE",
  "job": {"name": "data_ingestion"},
  "inputs": [{"name": "landing/sales_data.csv"}],
  "outputs": [{"name": "raw/sales_data.csv"}]
}
```

The Airflow container has `openlineage-airflow` installed, so every time a DAG task runs, it automatically sends this JSON to Marquez.

### Marquez

Marquez is the server that **receives and stores** these lineage events. It has:
- REST API at `http://localhost:5000`
- Web UI at `http://localhost:3000` (visual graph)

### Namespace: bigdata-platform

All your DAGs send lineage to the `bigdata-platform` namespace. When you click "Sync Lineage to VectorDB":

```
Backend calls Marquez:
  GET /api/v1/namespaces/bigdata-platform/jobs
  → returns 21 jobs (all your DAG tasks)

For each job, gets run history:
  GET /api/v1/namespaces/bigdata-platform/jobs/data_ingestion/runs
  → returns last 5 runs with their status

Each run gets indexed into ChromaDB:
  "Lineage event: COMPLETE
   Job: data_ingestion
   Inputs: landing/sales_data.csv, landing/user_events.csv
   Outputs: raw/sales_data.csv, raw/user_events.csv"
```

Now when you ask "What does data_ingestion produce?", the LLM has this real lineage context.

---

## 10. The Databases — PostgreSQL + Redis

### PostgreSQL (port 5432)

PostgreSQL is the main relational database. It stores two separate databases:

**Database: `airflow`**
```
Stores:
  - All DAG definitions and metadata
  - Task instance records (every run, its status, start/end time)
  - Variable values
  - Connection strings
  - User accounts

Used by: airflow-webserver, airflow-scheduler, airflow-worker
```

**Database: `marquez`**
```
Stores:
  - All lineage events received from Airflow
  - Job names and namespaces
  - Dataset names and schemas
  - Run history

Used by: marquez-api
Owner: postgres user 'marquez' (separate from 'airflow' user)
```

**Database: `postgres` (default)**
```
Not really used — just the default postgres database
```

### Redis (port 6379)

Redis is an in-memory message queue. Airflow uses it to distribute work:

```
airflow-scheduler  →  creates tasks, puts them in Redis queue
                                        ↓
                              Redis queue
                                        ↓
airflow-worker     →  picks up tasks from Redis, executes them
```

Without Redis, tasks couldn't be distributed to multiple workers. This is the **CeleryExecutor** pattern.

---

## 11. The 3 Analysis Modes

When a log is analyzed, there are 3 modes:

### Mode 1: Heuristic (regex patterns)

```python
Scans logs for known error patterns:
  "Traceback"          → CodeLogic error
  "FileNotFoundError"  → DataQuality error
  "timeout"            → Infrastructure error
  "401 Unauthorized"   → Infrastructure error
  "missing column"     → DataQuality error
  "OOM/OutOfMemory"    → Infrastructure error

Returns:
  category: "DataQuality"
  signature: "FileNotFoundError: /data/curated/..."
  suspected_root_cause: "Missing file or data dependency"
  next_actions: ["Run data_transformation first", ...]
  confidence: 0.75

Speed: instant (no LLM needed)
Quality: good for common errors, generic advice
```

### Mode 2: LLM (Ollama)

```python
Takes the log traceback and sends to Ollama:
  "Analyze these logs and return JSON:
   category, error_signature, summary, suspected_root_cause,
   next_actions, confidence

   Logs:
   FileNotFoundError: /data/curated/curated_combined_data.csv
   ..."

Returns the same fields but with much more intelligent analysis.

Speed: 15-60 seconds (depends on model size)
Quality: excellent, context-aware, specific advice
```

### Mode 3: Auto (default)

```python
if ollama is running:
    use LLM mode
else:
    use heuristic mode (fallback)
```

This is the recommended mode — best of both worlds.

---

## 12. Complete End-to-End Flow (Step by Step)

Here is the complete flow of a real debugging session:

### Step 1: Something Breaks

```
data_ingestion DAG runs at 3pm (hourly schedule)
One task fails:
  task: ingest_api_data
  error: Connection refused to external API
```

### Step 2: You Notice in Airflow UI

```
Open http://localhost:8080
Login: airflow / airflow
See: data_ingestion DAG has a red circle (failed task)
Click on the DAG run
Note the Run ID: "scheduled__2026-02-23T15:00:00"
Note the Task ID: "ingest_api_data"
```

### Step 3: Open the Chatbot

```
Open http://localhost:8501

In the sidebar, fill in:
  ✓ Fetch Airflow task logs
  Airflow Base URL: http://airflow-webserver:8080
  DAG ID: data_ingestion
  DAG Run ID: scheduled__2026-02-23T15:00:00
  Task ID: ingest_api_data
  Try number: 1
  Mode: auto
```

### Step 4: Ask the Chatbot

```
Type: "Why did this task fail and how do I fix it?"
```

### Step 5: What Happens Behind the Scenes

```
Streamlit → POST /chat to FastAPI

FastAPI:
  1. Calls Airflow API:
     GET http://airflow-webserver:8080/api/v1/dags/data_ingestion/
         dagRuns/scheduled__2026-02-23T15:00:00/
         taskInstances/ingest_api_data/logs/1
     Gets: "ConnectionRefusedError: [Errno 111] Connection refused"

  2. Runs heuristic analysis:
     Pattern match: "Connection refused" → Infrastructure
     Category: Infrastructure
     Signature: "ConnectionRefusedError: Connection refused"

  3. Converts question to embedding vector

  4. Searches ChromaDB:
     Finds: dags/data_ingestion_dag.py (the actual DAG code)
     Finds: backend/app/airflow_logs.py (log fetching code)

  5. Builds prompt for Ollama:
     [System]: You are a senior SRE/data engineer...
     [Context]:
       Airflow log analysis:
       - category: Infrastructure
       - signature: ConnectionRefusedError

       [Code] dags/data_ingestion_dag.py (relevance: 0.91)
       def ingest_api_data(**context):
           url = os.getenv("API_ENDPOINT", "http://api-service/data")
           response = requests.get(url, timeout=30)
           ...

     [User]: "Why did this task fail and how do I fix it?"

  6. Ollama generates answer (20 seconds)

  7. Returns to Streamlit
```

### Step 6: You See the Answer

```
"The task ingest_api_data failed with a ConnectionRefusedError,
meaning the target API at http://api-service/data was not
reachable when the task ran.

Root cause: The API service appears to be down or the URL
is not accessible from within the Airflow container.

How to fix:
1. Check if the API service is running: curl http://api-service/data
2. Verify the API_ENDPOINT environment variable is set correctly
3. Check network connectivity from the airflow-worker container:
   docker exec airflow-worker curl http://api-service/data
4. If the API is external, check if there was a network outage
5. Consider adding retry logic to the ingest_api_data function"

Sources & Retrieved Context:
  [code] dags/data_ingestion_dag.py (relevance: 0.91)
  [code] backend/app/airflow_logs.py (relevance: 0.73)

Diagnostics:
  rag_chunks: 7
  airflow: { category: Infrastructure, confidence: 0.82 }
```

---

## 13. File-by-File Explanation

### Backend Files (`backend/app/`)

| File | What it does |
|------|-------------|
| `main.py` | FastAPI app — defines all API routes |
| `chat_agent.py` | Orchestrates the full chat flow (fetch logs → analyze → RAG → answer) |
| `rag_engine.py` | RAG pipeline (retrieve from ChromaDB → build prompt → call Ollama) |
| `embedding_pipeline.py` | Indexes code/logs/DAGs into ChromaDB using sentence-transformers |
| `vectordb_client.py` | ChromaDB wrapper (4 collections, upsert, query, count) |
| `llm_client.py` | Calls Ollama API for chat and JSON analysis |
| `log_analyzer.py` | Heuristic + LLM log analysis (regex patterns, categorization) |
| `airflow_logs.py` | Fetches task logs from Airflow REST API (handles both JSON + plain text) |
| `k8s_logs.py` | Fetches pod logs from Kubernetes API |
| `lineage_client.py` | Calls Marquez API to get job/dataset/run data |
| `repo_context.py` | Fallback code search when Ollama is down (keyword-based) |
| `models.py` | Pydantic data models (request/response shapes) |
| `settings.py` | Reads all environment variables (Ollama URL, ChromaDB path, etc.) |

### DAG Files (`dags/`)

| File | Schedule | What it does |
|------|----------|-------------|
| `data_ingestion_dag.py` | hourly | Reads CSV + API → /data/raw/ |
| `data_transformation_dag.py` | daily | Cleans/aggregates → /data/curated/ |
| `data_quality_dag.py` | daily | Validates curated data quality |
| `ml_pipeline_dag.py` | weekly | Trains RandomForest model |
| `deploy_pipeline_dag.py` | manual | Builds Docker images + deploys to K8s |
| `demo_observability_dag.py` | manual | Intentionally fails for chatbot testing |

### Docker Files (`docker/`)

| File | What it does |
|------|-------------|
| `docker-compose.yml` | Defines all 10 services, their config, volumes, networks |
| `Dockerfile.backend` | Builds the FastAPI container (Python + ChromaDB + sentence-transformers) |
| `Dockerfile.airflow` | Builds Airflow container (adds openlineage-airflow + pandas + sklearn) |
| `Dockerfile.frontend` | Builds Streamlit container |
| `init-multiple-dbs.sh` | Creates 3 PostgreSQL databases on first start (airflow, marquez, default) |

### Scripts (`scripts/`)

| File | How to use | What it does |
|------|-----------|-------------|
| `index_codebase.py` | `python scripts/index_codebase.py` | Same as clicking "Index Codebase" button |
| `sync_lineage.py` | `python scripts/sync_lineage.py` | Same as clicking "Sync Lineage" button |
| `analyze_command.py` | `python scripts/analyze_command.py "some logs"` | Analyze logs from command line |
| `analyze_k8s_pod.py` | `python scripts/analyze_k8s_pod.py` | Analyze K8s pod logs from CLI |
| `analyze_airflow_task.py` | `python scripts/analyze_airflow_task.py` | Analyze Airflow task logs from CLI |
| `post_logs.py` | `python scripts/post_logs.py` | Post a log file to the backend API |

---

## 14. How to Run the Project

### First Time Setup

```bash
# 1. Clone the repo
git clone <repo-url>
cd bigdata-prototype

# 2. Start all containers
docker compose -f docker/docker-compose.yml up -d

# 3. Wait ~2 minutes for everything to start
docker ps   # check all containers are healthy

# 4. Create Airflow admin user (first time only)
docker exec airflow-webserver airflow users create \
  --username admin --password admin \
  --firstname Admin --lastname User \
  --role Admin --email admin@example.com
```

### After Everything is Running

```bash
# Open the Airflow UI
http://localhost:8080   (admin / admin)

# Open the Chatbot
http://localhost:8501

# Open the Marquez Lineage UI
http://localhost:3000

# Check backend API docs
http://localhost:8000/docs
```

### Using the Chatbot

```
Step 1: Click "Index Codebase" in the sidebar
        Wait for: "Indexed X code chunks"
        (This gives the LLM knowledge of your code)

Step 2: Run a DAG in Airflow UI
        - Go to http://localhost:8080
        - Click demo_observability → Trigger DAG
        - Wait for it to fail (should take ~30 seconds)
        - Note the Run ID from the DAG runs list

Step 3: Fill in Airflow task details in chatbot sidebar
        - Check "Fetch Airflow task logs"
        - Airflow Base URL: http://airflow-webserver:8080
        - DAG ID: demo_observability
        - DAG Run ID: (the Run ID you copied)
        - Task ID: task_fail_data
        - Try number: 1

Step 4: Ask your question
        "Why did this task fail?"
        "How do I fix this error?"
        "What is the root cause?"

Step 5 (optional): Sync lineage
        Click "Sync Lineage to VectorDB"
        This gives the LLM knowledge of your data dependencies
```

### Rebuilding After Code Changes

```bash
# If you changed backend code
docker compose -f docker/docker-compose.yml up -d --build backend

# If you changed DAG files
# No rebuild needed — DAGs are bind-mounted live
# Just refresh Airflow UI

# If you changed frontend
docker compose -f docker/docker-compose.yml up -d --build frontend

# After rebuilding backend, re-index codebase in chatbot
# (so ChromaDB has your latest code)
Click "Index Codebase" in chatbot sidebar
```

---

## 15. Common Questions & Answers

**Q: The chatbot says "Ollama is not running". What do I do?**
```
A: Check if the ollama container is healthy:
   docker ps | grep ollama

   If it shows "(health: starting)", wait 1-2 minutes.
   If it shows "(unhealthy)":
   docker logs ollama
   docker restart ollama
```

**Q: I get "Synced 0 lineage events". Why?**
```
A: Make sure your DAGs have actually run at least once.
   Go to Airflow UI and trigger data_ingestion.
   After it completes, click "Sync Lineage to VectorDB".

   Also make sure the namespace is "bigdata-platform" (not "default").
```

**Q: Index Codebase says "Indexed 0 chunks". Why?**
```
A: The backend might not be able to find the project files.
   Check docker logs backend for any errors.
```

**Q: Why does the LLM take so long?**
```
A: llama3.2:1b on CPU takes 15-30 seconds per response.
   This is normal. For faster responses, you need a GPU.
   The bigger llama3.1:8b model would take 3-5 minutes on CPU.
```

**Q: I changed my code but the chatbot still references old code. Why?**
```
A: ChromaDB is not updated automatically.
   After every code change, click "Index Codebase" to re-index.
```

**Q: What is the difference between "Paste Logs" and "Fetch Airflow task logs"?**
```
Paste Logs:
  - You manually copy-paste any log text into the text box
  - Good for: logs from any source (kubectl logs, journalctl, etc.)
  - No connection to Airflow required

Fetch Airflow task logs:
  - Backend automatically fetches logs from Airflow API
  - Good for: specifically debugging an Airflow task
  - Requires: Airflow running + DAG Run ID + Task ID
```

**Q: How is this different from just asking ChatGPT?**
```
ChatGPT:
  - Doesn't know your code
  - Doesn't have your actual logs
  - Gives generic advice based on training data
  - Can hallucinate

This system:
  - READS your actual source files (from ChromaDB)
  - READS your actual error logs (from Airflow API)
  - Gives advice specific to your codebase
  - Cannot hallucinate about your code because it has the actual text
  - Runs 100% locally, no data sent to the internet
```

**Q: Can I use a better/bigger LLM?**
```
Yes. In docker/docker-compose.yml, change:
  OLLAMA_MODEL: llama3.2:1b
to:
  OLLAMA_MODEL: llama3.1:8b     (better quality, needs 5GB RAM, very slow on CPU)
  OLLAMA_MODEL: mistral:7b      (good alternative)
  OLLAMA_MODEL: codellama:7b    (optimized for code)
  OLLAMA_MODEL: llama3.1:70b   (best quality, needs GPU, 40GB RAM)

Then rebuild: docker compose up -d --build backend
And pull the new model: docker exec ollama ollama pull llama3.1:8b
```

**Q: What is Kubernetes for in this project?**
```
Docker Compose = runs everything on ONE machine (for development)
Kubernetes = runs everything across MULTIPLE machines (for production)

The k8s/ folder has YAML files to deploy this platform on a real
Kubernetes cluster (like AWS EKS, Google GKE, or Azure AKS).

For local development, Docker Compose is all you need.
```

**Q: Why does marquez need its own postgres user?**
```
Marquez's Docker image has a hardcoded config that uses:
  user: marquez
  password: marquez

It ignores the POSTGRES_USER environment variable.
So we created a dedicated 'marquez' PostgreSQL user with:
  CREATE USER marquez WITH PASSWORD 'marquez';
  GRANT ALL PRIVILEGES ON DATABASE marquez TO marquez;
```

---

## Architecture Diagram

```
                           ┌─────────────────────────────────────────────┐
                           │            USER'S BROWSER                   │
                           └──────────────┬──────────────────────────────┘
                                          │
                           ┌──────────────▼──────────────────────────────┐
                           │   FRONTEND: Streamlit (port 8501)           │
                           │   - Chat UI                                  │
                           │   - Sidebar: Mode, Index, Airflow, K8s      │
                           └──────────────┬──────────────────────────────┘
                                          │ HTTP POST /chat
                           ┌──────────────▼──────────────────────────────┐
                           │   BACKEND: FastAPI (port 8000)              │
                           │   ┌─────────┐  ┌──────────┐  ┌──────────┐  │
                           │   │  chat   │  │   rag    │  │   log    │  │
                           │   │ _agent  │  │ _engine  │  │_analyzer │  │
                           │   └────┬────┘  └────┬─────┘  └──────────┘  │
                           └────────┼────────────┼────────────────────────┘
                                    │            │
              ┌─────────────────────┼────────────┼──────────────────────┐
              │                     │            │                       │
   ┌──────────▼────────┐  ┌─────────▼──────┐  ┌─▼───────────────────┐  │
   │ Airflow API       │  │ ChromaDB       │  │ Ollama (port 11434) │  │
   │ (port 8080)       │  │ (vector store) │  │ llama3.2:1b         │  │
   │                   │  │ 4 collections: │  │                     │  │
   │ Fetches real      │  │ - code_chunks  │  │ LLM that generates  │  │
   │ task logs         │  │ - dag_metadata │  │ the final answer    │  │
   │                   │  │ - log_entries  │  │                     │  │
   └──────────┬────────┘  │ - lineage_data │  └─────────────────────┘  │
              │            └────────────────┘                           │
   ┌──────────▼────────────────────────────────────────────────────────┐│
   │ Apache Airflow                                                     ││
   │  webserver (8080) + scheduler + worker                            ││
   │                                                                   ││
   │  DAGs:                                                            ││
   │  data_ingestion (hourly) → /data/raw/                            ││
   │  data_transformation (daily) → /data/curated/                   ││
   │  data_quality (daily) → validates curated data                  ││
   │  ml_pipeline (weekly) → /data/models/model.pkl                  ││
   │  demo_observability (manual) → intentional failures             ││
   │                          │                                       ││
   │                          │ OpenLineage events                    ││
   │                          ▼                                       ││
   │                  Marquez API (5000) + Web (3000)                ││
   │                  stores: job→dataset relationships               ││
   └───────────────────────────────────────────────────────────────────┘│
              │                                                          │
   ┌──────────▼────────────────────────────────────────────────────────┐│
   │  PostgreSQL (5432)          Redis (6379)                          ││
   │  - airflow database         - Celery broker                       ││
   │  - marquez database         - job queue between scheduler+worker  ││
   └───────────────────────────────────────────────────────────────────┘│
```

---

*This project is 100% open-source and runs entirely on your local machine. No cloud services, no API keys, no costs.*
