# BigData Platform — Complete Project Explanation
### Everything explained in simple English, with real examples

---

## TABLE OF CONTENTS

1. [What Are We Building? (Big Picture)](#1-what-are-we-building)
2. [The Problem This Solves](#2-the-problem-this-solves)
3. [All The Tools We Use & Why](#3-all-the-tools-we-use--why)
4. [Docker — Explained From Scratch](#4-docker--explained-from-scratch)
   - What is Docker?
   - Docker Images
   - Docker Containers
   - Docker Registry
   - Dockerfile
   - Docker Compose
   - How we use Docker in this project
5. [Kubernetes — Explained From Scratch](#5-kubernetes--explained-from-scratch)
   - What is Kubernetes?
   - Pods
   - Deployments
   - Services
   - Namespaces
   - Ingress
   - PersistentVolumeClaim
   - ConfigMap
   - How we use Kubernetes in this project
6. [The Backend — FastAPI](#6-the-backend--fastapi)
7. [The AI Brain — RAG + ChromaDB + Ollama](#7-the-ai-brain--rag--chromadb--ollama)
8. [The Data Pipelines — Apache Airflow](#8-the-data-pipelines--apache-airflow)
9. [Data Lineage — OpenLineage + Marquez](#9-data-lineage--openlineage--marquez)
10. [The Frontend — Streamlit](#10-the-frontend--streamlit)
11. [The Databases — PostgreSQL + Redis](#11-the-databases--postgresql--redis)
12. [How Everything Connects Together](#12-how-everything-connects-together)
13. [File-by-File Code Explanation](#13-file-by-file-code-explanation)
14. [How to Run the Project](#14-how-to-run-the-project)
15. [Common Questions & Answers](#15-common-questions--answers)

---

## 1. What Are We Building?

### Simple Answer:
We are building an **AI-powered Big Data Platform** that does 5 things:

```
1. COLLECTS data automatically (from CSV files and APIs)
2. CLEANS & TRANSFORMS that data (removes bad data, reshapes it)
3. CHECKS data quality (makes sure data is valid)
4. TRAINS a machine learning model on that data
5. EXPLAINS what went wrong when something breaks (using AI)
```

### Real-world Analogy:
Imagine you run a **factory that processes raw materials** (like cotton → fabric → clothes).

- **Raw materials** = your raw data (CSV files, API responses)
- **Factory machines** = Apache Airflow (processes data step by step)
- **Quality inspector** = Data quality checks
- **Factory manager** = Kubernetes (keeps everything running)
- **Smart AI assistant** = Our chatbot (tells you when/why something broke)
- **Shipping containers** = Docker (packages each machine separately)
- **Warehouse records** = Marquez (tracks where every material came from and went)

---

## 2. The Problem This Solves

### Without this platform:
- Data engineers manually check logs when pipelines fail
- Nobody knows where data came from or how it was transformed
- Debugging a failure means reading thousands of log lines manually
- Scaling services requires manual server management

### With this platform:
- **Automatic log analysis** → paste logs, AI tells you exactly what broke and why
- **Data lineage** → click any dataset, see its complete history
- **AI chatbot** → ask "why did my pipeline fail?" in plain English
- **Kubernetes** → services auto-heal and auto-scale without human intervention

---

## 3. All The Tools We Use & Why

| Tool | Category | What It Does | Why We Use It |
|------|----------|--------------|---------------|
| **FastAPI** | Backend API | Handles HTTP requests, routes them to right functions | Fastest Python web framework, auto-generates API docs |
| **Streamlit** | Frontend UI | Creates the chat web interface | Build web UI in pure Python — no HTML/CSS/JavaScript needed |
| **Ollama + LLaMA 3.1** | AI / LLM | Runs AI locally on your computer | 100% free, no API costs, data stays private on your machine |
| **ChromaDB** | Vector Database | Stores code/logs as searchable AI embeddings | Fast similarity search — finds relevant code even with different words |
| **sentence-transformers** | AI Embeddings | Converts text to numbers (vectors) for search | Free, tiny (80MB), runs on CPU, no GPU needed |
| **Apache Airflow** | Orchestration | Schedules and runs data pipeline tasks | Industry standard for data workflows, visual UI, retry logic |
| **OpenLineage + Marquez** | Data Lineage | Tracks data origin and flow through the system | See exactly where data came from and where it went |
| **PostgreSQL** | Database | Stores Airflow metadata and Marquez lineage data | Reliable, production-grade relational database |
| **Redis** | Message Broker | Distributes tasks between Airflow workers | Fast in-memory queue, perfect for task distribution |
| **Docker** | Containerization | Packages each service into isolated containers | Same environment everywhere — works on any computer |
| **Docker Compose** | Local Orchestration | Starts all services with one command locally | Simple way to run all 12 services together on one machine |
| **Kubernetes** | Production Orchestration | Manages containers across multiple servers | Auto-healing, auto-scaling, production-grade reliability |
| **pandas** | Data Processing | Reads, cleans, and transforms CSV/tabular data | Standard Python data processing library |
| **scikit-learn** | Machine Learning | Trains RandomForest classification model | Simple, reliable ML library |
| **pytest** | Testing | Runs automated tests to catch bugs | Standard Python testing framework |

---

## 4. Docker — Explained From Scratch

### What is Docker?

**Simple Analogy:** Think of a restaurant.

Without Docker: Every chef (developer) sets up their own kitchen differently. One chef has a gas stove, another has electric. One uses brand X olive oil, another uses brand Y. The food (software) tastes different depending on which kitchen made it.

With Docker: Every chef uses **exactly the same kitchen** — same stove, same ingredients, same tools. It doesn't matter if the kitchen is in New York or Tokyo, the food always tastes identical.

**Docker is a tool that makes your software run identically on ANY computer.**

---

### Docker Images

**What is an image?**

An image is a **snapshot** — like a photograph — of your entire application. It contains:
- The operating system (Linux)
- Python (or Node.js, Java, etc.)
- All the libraries your code needs
- Your actual code
- Instructions on how to start

**Real-world analogy:** An image is like a **recipe card** for a meal.

The recipe card says:
```
1. Start with a base of Ubuntu Linux
2. Install Python 3.11
3. Install packages: fastapi, chromadb, sentence-transformers
4. Copy my code files
5. Run: uvicorn app.main:app
```

The image is NOT running. It's just the instructions + all the ingredients bundled together.

**In our project, we have 3 images:**

```
Image 1: bigdata-backend
  Contains: Python 3.11 + FastAPI + ChromaDB + AI embeddings + our backend code
  Built from: docker/Dockerfile.backend

Image 2: bigdata-airflow
  Contains: Airflow 2.8 + Python + our 5 data pipeline DAGs
  Built from: docker/Dockerfile.airflow

Image 3: bigdata-frontend
  Contains: Python 3.11 + Streamlit + our chat UI code
  Built from: docker/Dockerfile.frontend
```

**How to build an image:**
```bash
docker build -t bigdata-backend:latest -f docker/Dockerfile.backend .
#             ↑ name:tag                ↑ which Dockerfile to use  ↑ where the code is
```

---

### Docker Containers

**What is a container?**

A container is what you get when you **run an image**. If the image is a recipe, the container is the actual cooked meal.

**Real-world analogy:**
- Image = Cake recipe card (just instructions, not edible)
- Container = The actual cake you baked using that recipe (running, doing things)

You can bake **multiple cakes from the same recipe** — similarly, you can run **multiple containers from the same image**.

```
Image: bigdata-backend  →  Container 1: backend-pod-1 (running on server A)
                        →  Container 2: backend-pod-2 (running on server B)
```

**In our project:**
```
bigdata-backend image → "backend" container  (runs FastAPI on port 8000)
bigdata-airflow image → "airflow-webserver" container (Airflow UI on port 8080)
                     → "airflow-scheduler" container (triggers DAGs)
                     → "airflow-worker" container (runs actual tasks)
                     → "airflow-init" container (one-time DB setup)
bigdata-frontend image → "frontend" container (Streamlit on port 8501)
```

**Key difference:**
```
IMAGE = frozen, static, not running (like a blueprint)
CONTAINER = alive, running, doing work (like a building made from the blueprint)
```

---

### Docker Registry

**What is a Registry?**

A registry is an **app store for Docker images**. Instead of downloading apps, you download images.

**Real-world analogy:** Docker Hub is like the **Google Play Store or Apple App Store**, but for Docker images.

```
Public Registry (Docker Hub):
  postgres:16-alpine        ← PostgreSQL database image
  redis:7-alpine            ← Redis message broker image
  ollama/ollama:latest      ← Ollama LLM server image
  marquezproject/marquez    ← Marquez lineage server image

Private Registry:
  your-company.registry.io/bigdata-backend:v1.2   ← your custom image
  your-company.registry.io/bigdata-airflow:v1.2   ← your custom image
```

**When you run `docker compose up`, Docker:**
1. Checks if the image exists locally
2. If not → downloads it from Docker Hub (like installing an app)
3. Runs it as a container

**Our images (bigdata-backend, bigdata-airflow, bigdata-frontend) are built locally.** For production, you'd push them to a registry:
```bash
# Push to Docker Hub
docker push yourusername/bigdata-backend:latest

# Or to AWS ECR (private registry)
docker push 123456789.dkr.ecr.us-east-1.amazonaws.com/bigdata-backend:latest
```

---

### Dockerfile

A Dockerfile is the **recipe card** — step-by-step instructions for building an image.

**Our backend Dockerfile (docker/Dockerfile.backend) explained:**

```dockerfile
# Step 1: Start with Python 3.11 on a small Linux system
FROM python:3.11-slim
# Why slim? Smaller = faster to download and run

# Step 2: Set the working directory inside the container
WORKDIR /opt/app
# This is like "cd /opt/app" — all future commands run here

# Step 3: Install system tools we need
RUN apt-get update && apt-get install -y build-essential curl git
# build-essential = compilers (needed to install some Python packages)
# curl = download tool (needed for healthchecks)

# Step 4: Install Python packages
COPY requirements.txt .
RUN pip install -r requirements.txt
# COPY first, then pip install — this is a Docker caching trick
# If requirements.txt hasn't changed, Docker reuses the cached layer
# = much faster builds

# Step 5: Copy our application code
COPY backend/ backend/
COPY scripts/ scripts/
COPY dags/ dags/

# Step 6: Pre-download the AI embedding model into the image
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"
# This bakes the 80MB AI model into the image
# = container starts instantly without downloading the model

# Step 7: Tell Docker which port our app listens on
EXPOSE 8000

# Step 8: The command to run when container starts
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

### Docker Compose

Docker Compose is a tool to **start multiple containers together** with a single command.

**Real-world analogy:**
Running a restaurant requires: chef, waiter, cashier, dishwasher. You don't hire them one by one. You write a job description for all of them and hire everyone at once.

Docker Compose is the "hire everyone at once" tool for containers.

**Our docker-compose.yml defines 12 services:**

```yaml
services:
  backend:       ← FastAPI + AI engine
  frontend:      ← Streamlit chat UI
  ollama:        ← AI LLM server
  ollama-init:   ← Downloads AI model (runs once)
  postgres:      ← Database
  redis:         ← Message queue
  marquez-api:   ← Lineage tracking server
  marquez-web:   ← Lineage web UI
  airflow-webserver:  ← Airflow dashboard
  airflow-scheduler:  ← Triggers DAGs on schedule
  airflow-worker:     ← Runs actual pipeline tasks
  airflow-init:       ← Sets up Airflow DB (runs once)
```

**Start everything:**
```bash
cd docker
docker compose up --build -d
#                  ↑          ↑
#                  rebuild    run in background (detached)
```

---

### How We Use Docker in This Project

```
YOUR LAPTOP
│
├── docker compose up  ←── Reads docker-compose.yml
│
├── Builds 3 images:
│   ├── bigdata-backend    (from Dockerfile.backend)
│   ├── bigdata-airflow    (from Dockerfile.airflow)
│   └── bigdata-frontend   (from Dockerfile.frontend)
│
├── Downloads 5 images from Docker Hub:
│   ├── postgres:16-alpine
│   ├── redis:7-alpine
│   ├── ollama/ollama:latest
│   ├── marquezproject/marquez:latest
│   └── marquezproject/marquez-web:latest
│
└── Starts 12 containers, all talking to each other:
    backend:8000 ←──── frontend:8501
    backend:8000 ←──── ollama:11434  (AI model)
    backend:8000 ←──── marquez-api:5000  (lineage)
    airflow:8080 ←──── postgres:5432 + redis:6379
    marquez-api  ←──── postgres:5432
```

---

## 5. Kubernetes — Explained From Scratch

### What is Kubernetes?

**Simple Analogy:**

Docker Compose runs everything on **one computer** (like one chef doing everything in a restaurant).

Kubernetes is a **restaurant chain manager** who manages HUNDREDS of restaurants (servers) at once, making sure:
- Every restaurant has enough chefs (auto-scaling)
- If one restaurant burns down, customers go to another (self-healing)
- New menu items roll out to all restaurants without closing any (rolling updates)

**Kubernetes = Professional Container Manager for multiple servers**

The short name "K8s" comes from counting letters: K-u-b-e-r-n-e-t-e-s → K + 8 letters + s = K8s.

---

### Pods

**What is a Pod?**

A Pod is the **smallest unit in Kubernetes**. A Pod contains one or more containers that run together.

**Real-world analogy:**
A pod is like a **delivery truck** carrying one or more packages (containers). The packages inside one truck share the same space, address, and communication network.

```
Pod: backend-pod-xyz123
├── Container: backend  (FastAPI app, port 8000)
└── (usually just one container per pod)

Pod: airflow-worker-abc456
├── Container: worker   (Celery worker, runs DAG tasks)
```

**Key facts about Pods:**
- A Pod has its own IP address inside the cluster
- Pods are **temporary** — they can die and be replaced
- When a Pod dies, a new one is created with a NEW name and IP
- That's why we have Services (stable addresses) — explained below

**In our project, we have these pods:**
```
Namespace: backend
  backend-xxxxx          ← FastAPI API (2 replicas = 2 pods)
  frontend-xxxxx         ← Streamlit UI (1 pod)
  ollama-xxxxx           ← LLM AI server (1 pod)

Namespace: airflow
  airflow-webserver-xxx  ← Airflow dashboard (1 pod)
  airflow-scheduler-xxx  ← Schedules DAGs (1 pod)
  airflow-worker-xxx     ← Runs tasks (2 pods)
  redis-xxxxx            ← Message queue (1 pod)

Namespace: data
  postgres-xxxxx         ← Database (1 pod)
  marquez-api-xxxxx      ← Lineage API (1 pod)
  marquez-web-xxxxx      ← Lineage UI (1 pod)
```

---

### Deployments

**What is a Deployment?**

A Deployment tells Kubernetes: "**Always keep exactly N copies of this pod running.**"

**Real-world analogy:**
You tell your restaurant manager: "I always want 2 cashiers working at the counter. If one quits, hire another immediately."

A Deployment does this automatically for containers.

```yaml
# From our k8s/backend/deployment.yaml:
spec:
  replicas: 2          # "I always want 2 backend pods running"
  selector:
    matchLabels:
      app: backend     # This deployment manages pods labeled 'app: backend'
```

**What Kubernetes does:**
1. You say `replicas: 2`
2. Kubernetes starts 2 backend pods
3. One pod crashes → Kubernetes immediately starts a replacement
4. You change to `replicas: 5` → Kubernetes starts 3 more pods

**Our deployments:**
```yaml
backend:         replicas: 2   ← always 2 backend pods running
frontend:        replicas: 1   ← 1 Streamlit pod
ollama:          replicas: 1   ← 1 Ollama pod (AI model)
airflow-worker:  replicas: 2   ← 2 workers to process tasks in parallel
```

---

### Services

**What is a Service?**

Pods are temporary — they die and get replaced with new names. A Service provides a **stable, permanent address** for your pods.

**Real-world analogy:**
Your friend moves houses frequently, but their phone number never changes. You always call the same number — it doesn't matter where they live.

A Service is the **stable phone number** for your pods.

```
Without Service:
  backend-pod-abc123:192.168.1.5  ← pod dies
  backend-pod-xyz789:192.168.1.9  ← new pod, new IP!
  frontend doesn't know new IP → broken!

With Service:
  Service "backend":10.96.0.5     ← stable address, never changes
  frontend always calls this → always works!
```

**In our project:**
```yaml
# k8s/backend/deployment.yaml:
Service:
  name: backend
  namespace: backend
  port: 8000
  → All pods labeled "app: backend" receive traffic

# Other services can reach it at:
# http://backend.backend.svc.cluster.local:8000
#          ↑       ↑        ↑              ↑
#      service  namespace  cluster   port
```

**All our Services:**
```
backend.backend.svc.cluster.local:8000     ← FastAPI API
frontend.backend.svc.cluster.local:8501    ← Streamlit UI
ollama.backend.svc.cluster.local:11434     ← Ollama LLM
postgres.data.svc.cluster.local:5432       ← PostgreSQL
marquez-api.data.svc.cluster.local:5000    ← Marquez
redis.airflow.svc.cluster.local:6379       ← Redis
airflow-webserver.airflow.svc.cluster.local:8080 ← Airflow UI
```

---

### Namespaces

**What is a Namespace?**

Namespaces are **folders** to organize your pods. They keep different parts of your system separated.

**Real-world analogy:**
A big company building has different floors:
- Floor 1: Engineering team
- Floor 2: Sales team
- Floor 3: Finance team

Each floor is a namespace — organized, separate, but they can still communicate.

**Our 4 namespaces:**
```
backend/    ← FastAPI backend, Streamlit frontend, Ollama AI
airflow/    ← All Airflow components + Redis
data/       ← PostgreSQL database, Marquez lineage server
monitoring/ ← (reserved for future Prometheus + Grafana)
```

**Why separate?**
- Cleaner organization
- You can apply different permissions to different namespaces
- Teams can work independently
- Easy to delete/restart one namespace without affecting others

---

### Ingress

**What is Ingress?**

Ingress is the **front door** of your Kubernetes cluster. It routes external web traffic to the right internal service.

**Real-world analogy:**
A hotel receptionist. When guests arrive at the hotel, the receptionist says:
- "Are you here for Room 101? Go to the east wing"
- "Are you here for the conference? Go to the meeting room"

Ingress does the same for HTTP traffic using URLs:

```yaml
# k8s/ingress.yaml:

bigdata.local          → frontend:8501    (Streamlit chat UI)
api.bigdata.local      → backend:8000     (FastAPI REST API)
airflow.bigdata.local  → airflow-webserver:8080  (Airflow dashboard)
lineage.bigdata.local  → marquez-web:3000 (Lineage UI)
```

---

### PersistentVolumeClaim (PVC)

**What is a PVC?**

Containers are temporary — when they die, all data inside them is lost. A PVC is a **request for permanent storage** that survives container restarts.

**Real-world analogy:**
You rent a car (container). When you return it, everything inside gets cleaned out. If you want to keep your stuff, you put it in a **storage unit** (PVC) that you rent separately. Tomorrow you can get a new car and your stuff is still in the storage unit.

```yaml
# k8s/backend/deployment.yaml:
PersistentVolumeClaim:
  name: chromadb-pvc
  size: 5Gi           # Request 5 gigabytes of storage
  accessMode: ReadWriteOnce  # Only one pod can write at a time
```

**Our PVCs:**
```
chromadb-pvc  (5GB)   ← Stores ChromaDB vector embeddings
ollama-pvc    (20GB)  ← Stores downloaded AI models (LLaMA 3.1)
postgres-pvc  (10GB)  ← Stores all database data
data-lake-pvc (50GB)  ← Stores all pipeline data (CSV files etc.)
```

---

### ConfigMap

**What is a ConfigMap?**

A ConfigMap stores **configuration values** (like environment variables) separately from the container.

**Real-world analogy:**
Instead of hard-coding your restaurant's opening hours into every menu, you put them on a sign (ConfigMap). When hours change, you update the sign — all menus stay the same.

```yaml
# k8s/backend/deployment.yaml:
ConfigMap:
  name: backend-config
  data:
    OLLAMA_BASE_URL: "http://ollama.backend.svc.cluster.local:11434"
    OLLAMA_MODEL: "llama3.1:8b"
    MARQUEZ_URL: "http://marquez-api.data.svc.cluster.local:5000"
```

The pod reads these as environment variables. To change the Ollama URL, you update the ConfigMap — no need to rebuild the Docker image.

---

### How We Use Kubernetes in This Project

```
kubectl apply -f k8s/namespaces.yaml     # Create 4 namespaces
kubectl apply -f k8s/ --recursive        # Deploy everything

Kubernetes then:
1. Creates 4 namespaces (backend, airflow, data, monitoring)
2. Creates ConfigMaps (configuration)
3. Creates PVCs (storage requests)
4. Starts Deployments (which create Pods)
5. Creates Services (stable addresses)
6. Configures Ingress (external routing)
7. Monitors health → restarts crashed pods automatically
```

---

## 6. The Backend — FastAPI

### What is FastAPI?

FastAPI is a **Python web framework** for building APIs (Application Programming Interfaces).

An API is like a **waiter** in a restaurant. You (the frontend) tell the waiter (API) what you want. The waiter goes to the kitchen (business logic) and brings back your food (data).

### Our API Endpoints (the "menu"):

```
GET  /health              ← "Is the server alive?"
POST /analyze-log         ← "Analyze this log text for me"
POST /analyze-k8s-pod     ← "Fetch and analyze Kubernetes pod logs"
POST /analyze-airflow-task← "Fetch and analyze Airflow task logs"
POST /chat                ← "Answer this question using AI + code search"
POST /index/codebase      ← "Index all project code into ChromaDB"
POST /index/log           ← "Store this log in ChromaDB"
GET  /index/stats         ← "How many items are indexed?"
GET  /lineage/namespaces  ← "List Marquez namespaces"
GET  /lineage/jobs/{ns}   ← "List pipeline jobs in namespace"
POST /lineage/graph       ← "Get lineage graph for a job"
POST /lineage/sync        ← "Sync Marquez lineage into ChromaDB"
```

**You can see all endpoints at:** `http://localhost:8000/docs` (interactive Swagger UI)

### Key Files:

**`backend/app/main.py`** — The entry point. Like a reception desk — receives all requests and routes them.

**`backend/app/models.py`** — Defines the shape of requests and responses:
```python
class ChatRequest(BaseModel):
    question: str           # What the user asked
    history: list           # Previous messages
    log_text: str | None    # Optional: paste logs here
    mode: str               # "auto", "heuristic", or "llm"
```

**`backend/app/settings.py`** — Reads configuration from environment variables:
```python
def get_ollama_base_url():
    return os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    #                 ↑ reads from .env file or system env  ↑ default if not set
```

---

## 7. The AI Brain — RAG + ChromaDB + Ollama

This is the most advanced part of the project. Let's break it down step by step.

### What is RAG (Retrieval-Augmented Generation)?

RAG is a technique where instead of asking an AI model "what do you know?", you say "here's some relevant information — now answer using THIS."

**Real-world analogy:**
- **Without RAG:** Ask a doctor a question. They answer from memory.
- **With RAG:** Hand the doctor your medical records FIRST, then ask the question. Now they answer based on YOUR specific case.

**RAG in our project:**
```
User asks: "Why did the data_ingestion DAG fail?"

Step 1 — RETRIEVE:
  Search ChromaDB for code + logs related to "data ingestion fail"
  Find: the data_ingestion_dag.py code, recent error logs, lineage events

Step 2 — AUGMENT:
  Build a prompt: "Here is the relevant code: [code] Here are the logs: [logs]
                   Now answer: Why did the data_ingestion DAG fail?"

Step 3 — GENERATE:
  Send that complete prompt to Ollama LLaMA
  Get back a specific, grounded answer

Result: "The DAG failed because line 49 in data_ingestion_dag.py had a broken
        import of the os module. The fix is to move 'import os' to the top."
```

### What is ChromaDB?

ChromaDB is a **Vector Database** — a special kind of database that stores text as mathematical numbers (vectors) and can find similar text extremely fast.

**Real-world analogy:**
Normal databases search by EXACT match: "Find rows where name = 'John'"

ChromaDB searches by MEANING: "Find text that means something similar to what I typed"

```
You search for: "database connection error"
ChromaDB finds: "PostgreSQL refused connection" (different words, same meaning!)
```

**How text becomes numbers (vectors):**
```
"airflow dag failed" → [0.23, -0.45, 0.78, 0.12, ...]  (384 numbers)
"pipeline task error" → [0.21, -0.43, 0.75, 0.14, ...]  (very similar numbers!)
```

Similar meanings → similar number patterns → ChromaDB finds them.

**Our 4 ChromaDB collections:**
```
code_embeddings    ← All project code (.py, .yml, .sql files), chunked into 60-line pieces
log_embeddings     ← Error logs that were analyzed, stored for future reference
dag_metadata       ← Information about each Airflow DAG (id, tasks, schedule)
lineage_data       ← Job runs and their input/output datasets from Marquez
```

### What is Ollama?

Ollama is a **tool that runs AI language models locally on your computer**.

**Real-world analogy:**
Normally, AI (like ChatGPT) runs on huge servers in the cloud. You send your question over the internet, they process it on expensive GPUs, send back an answer.

Ollama is like having that AI model installed on YOUR computer. No internet needed. No API costs. Data stays private.

```
ChatGPT:  Your text → Internet → OpenAI servers → Answer back  (costs money, data leaves your machine)
Ollama:   Your text → Your CPU/GPU → Answer back              (free, data stays local)
```

**The model we use: LLaMA 3.1:8b**
- Made by Meta (Facebook)
- "8b" = 8 billion parameters (a medium-sized model)
- Good at: code explanation, log analysis, question answering
- Size: ~4.7GB download
- Runs on CPU (slower) or GPU (faster)

### How It All Works Together (RAG Pipeline):

```
                    backend/app/rag_engine.py

User question: "What does the ml_pipeline DAG do?"
       ↓
Step 1: embed_single(question)
  → sentence-transformers converts question to vector [0.34, -0.12, ...]
       ↓
Step 2: query ChromaDB (4 collections)
  code_embeddings:  finds ml_pipeline_dag.py (most similar code)
  dag_metadata:     finds "ml_pipeline" DAG entry
  log_embeddings:   finds related error logs (if any)
  lineage_data:     finds lineage events for ml jobs
       ↓
Step 3: Build context block
  "--- Code: dags/ml_pipeline_dag.py ---
   def build_features(**context):
       ...builds ML features from curated data...
   def train_model(**context):
       ...trains RandomForest, saves model.pkl..."
       ↓
Step 4: Build full prompt
  SYSTEM: "You are a senior data engineer..."
  USER: "Context: [code above] Question: What does ml_pipeline DAG do?"
       ↓
Step 5: call_ollama_chat(messages)
  → HTTP POST to http://ollama:11434/api/chat
  → Ollama runs LLaMA 3.1
  → Returns answer text
       ↓
Result: "The ml_pipeline DAG runs weekly and does 3 things:
         1. build_features: reads curated CSV data and creates ML features
         2. train_model: trains a RandomForest classifier, saves model.pkl
         3. evaluate_model: checks accuracy meets minimum threshold (0.5)"
```

### Key Files for AI:

**`backend/app/rag_engine.py`** — The orchestrator. Retrieves → builds context → calls LLM → returns answer.

**`backend/app/embedding_pipeline.py`** — Converts code/logs/DAGs to vectors and stores in ChromaDB.

**`backend/app/vectordb_client.py`** — Talks to ChromaDB (creates collections, stores documents, queries).

**`backend/app/llm_client.py`** — Talks to Ollama (sends prompt, gets response).

**`backend/app/log_analyzer.py`** — Analyzes logs using pattern matching (heuristic) + LLM (when available).

**`backend/app/chat_agent.py`** — Combines everything: log analysis + K8s logs + Airflow logs + RAG query.

---

## 8. The Data Pipelines — Apache Airflow

### What is Apache Airflow?

Airflow is a **workflow orchestrator** — it schedules and monitors jobs (called DAGs).

**Real-world analogy:**
Airflow is like a **project manager** for data tasks.

Without Airflow: You have a shell script that runs all steps. If step 3 fails, you don't know. You run everything again from step 1.

With Airflow:
- Step 3 fails → Airflow retries 2 times automatically
- Still fails → Airflow sends you an alert
- You see a beautiful visual showing which step failed and why
- You can re-run ONLY the failed step, not everything

### What is a DAG?

DAG = **Directed Acyclic Graph**

In simple terms, a DAG is a **flowchart of tasks** where:
- Tasks run in a specific order
- Some tasks can run in parallel
- No loops (you can't go backwards)

**Example from our project:**
```
data_ingestion DAG:

[ingest_csv_files] ──┐
                      ├──→ [validate_raw_data]
[ingest_api_data]  ──┘

Read: "First run ingest_csv_files AND ingest_api_data (in parallel),
       THEN run validate_raw_data (only after both succeed)"
```

### Our 5 DAGs Explained:

**DAG 1: `data_ingestion` (runs every hour)**
```
Purpose: Bring raw data into the system

[ingest_csv_files]    ← Copies CSV files from /data/landing to /data/raw
[ingest_api_data]     ← Simulates fetching data from an API, saves JSON to /data/raw
        ↓ (both must succeed)
[validate_raw_data]   ← Checks raw files are not empty
```

**DAG 2: `data_transformation` (runs every day)**
```
Purpose: Clean and shape the data

[clean_data]          ← Reads CSVs from raw zone, drops empty rows,
                        normalizes column names, saves to staging/
        ↓
[transform_aggregate] ← Combines all cleaned files, groups by 'status',
                        saves aggregated CSV to processed/
        ↓
[enrich_with_metadata]← Adds columns: _processed_at, _source_file,
                        _pipeline_version → saves to curated/
```

**DAG 3: `data_quality_checks` (runs every day)**
```
Purpose: Make sure data is valid before ML training

All 4 checks run IN PARALLEL:
[check_schema_conformance] ← Required columns exist? (_processed_at, _source_file, etc.)
[check_null_ratios]        ← Are null values below 30% threshold?
[check_row_counts]         ← Does each file have at least 1 row?
[check_duplicates]         ← Are duplicates below 5% threshold?
```

**DAG 4: `ml_pipeline` (runs every week)**
```
Purpose: Train a machine learning model

[build_features]   ← Reads curated CSV, encodes categories as numbers,
                     fills nulls, saves features.csv
        ↓
[train_model]      ← Trains RandomForest classifier on features.csv,
                     saves model.pkl + metrics.json (with accuracy score)
        ↓
[evaluate_model]   ← Loads metrics.json, checks accuracy ≥ 50%,
                     raises error if model is too bad
```

**DAG 5: `deploy_pipeline` (triggered manually)**
```
Purpose: Build, test, and deploy the platform

[run_tests]        ← Runs pytest tests/
        ↓
[build_backend_image] ──┐  (run in parallel)
[build_airflow_image] ──┘
        ↓
[deploy_to_kubernetes] ← kubectl apply -f k8s/ --recursive
        ↓
[check_rollout_status] ← kubectl rollout status deployment/backend
        ↓
[notify_observability] ← Calls our own /chat API to ask "did deployment succeed?"
```

### Key Airflow Files:

```
dags/data_ingestion_dag.py     ← hourly data collection
dags/data_transformation_dag.py← daily data cleaning
dags/data_quality_dag.py       ← daily quality validation
dags/ml_pipeline_dag.py        ← weekly model training
dags/deploy_pipeline_dag.py    ← manual deployment workflow
```

### How OpenLineage Works with Airflow:

Every task in Airflow automatically emits **lineage events** to Marquez when you install the `openlineage-airflow` package.

```
Airflow task "clean_data" runs:
  → Reads from: /data/raw/sales_data.csv
  → Writes to:  /data/staging/cleaned_sales_data.csv

OpenLineage automatically sends to Marquez:
  {
    "job": "data_transformation.clean_data",
    "inputs": ["/data/raw/sales_data.csv"],
    "outputs": ["/data/staging/cleaned_sales_data.csv"],
    "run": { "state": "COMPLETE", "duration": "45s" }
  }
```

Now Marquez knows the complete data journey.

---

## 9. Data Lineage — OpenLineage + Marquez

### What is Data Lineage?

Data lineage = **knowing where data came from and where it went**.

**Real-world analogy:**
You're eating a burger. Data lineage would tell you:
- The beef came from Farm X in Texas
- It was processed at Facility Y in Chicago
- Shipped to Restaurant Z in New York
- Cooked at 165°F by Chef A

If someone gets sick, you can **trace exactly** which farm to blame.

For data:
- If your ML model gives wrong predictions → lineage shows which dataset had bad data
- If a report shows wrong numbers → lineage shows which transformation changed the values

### What is Marquez?

Marquez is an **open-source metadata service** that stores and visualizes data lineage.

It provides:
1. **REST API** — Stores lineage events sent by Airflow
2. **Web UI** — Visual graph showing data flow (port 3000)

**In our project:**
```
Marquez at http://localhost:5000  ← receives lineage events from Airflow
Marquez at http://localhost:3000  ← beautiful web UI to explore lineage
```

**Marquez API (used in our backend):**
```python
# backend/app/lineage_client.py

list_namespaces()           # GET /api/v1/namespaces
list_jobs("bigdata-platform")   # GET /api/v1/namespaces/bigdata-platform/jobs
get_job_runs(ns, "clean_data")  # GET /api/v1/namespaces/.../jobs/clean_data/runs
get_lineage("job", ns, "clean_data", depth=5)  # GET /api/v1/lineage?nodeId=...
```

**ChromaDB + Lineage:**
Our `sync_lineage_to_vectordb()` function:
1. Fetches all jobs from Marquez
2. Gets the last 5 runs for each job
3. Stores each run in ChromaDB as text

So when you ask the chatbot "what datasets does the ml_pipeline read?", it can answer using lineage data from ChromaDB!

---

## 10. The Frontend — Streamlit

### What is Streamlit?

Streamlit is a **Python library that creates web applications** without writing HTML/CSS/JavaScript.

**Real-world analogy:**
Normal web development: You need to learn HTML (structure), CSS (design), JavaScript (behavior) — 3 different languages.

Streamlit: Write Python → get a web app automatically.

```python
# This Python code creates a complete web form + button:
question = st.chat_input("Ask about your data pipelines...")
if question:
    response = requests.post("/chat", json={"question": question})
    st.markdown(response.json()["answer"])
```

### Our Streamlit App Features (`frontend/streamlit_app.py`):

**Main chat interface:**
```
┌─────────────────────────────────────────────────┐
│  BigData Platform — Observability Agent          │
├──────────┬──────────────────────────────────────┤
│ SIDEBAR  │  CHAT AREA                           │
│          │                                      │
│ Settings │  User: "Why did my DAG fail?"        │
│  Mode    │                                      │
│  Backend │  AI: "Based on the logs I analyzed, │
│  URL     │  the clean_data task failed because  │
│          │  the staging directory didn't exist..."│
│ RAG Index│                                      │
│  [Index] │  Sources:                            │
│  [Stats] │  - data_transformation_dag.py:43     │
│          │  - log_embeddings (error from 10:35) │
│ Lineage  │                                      │
│  [Sync]  │  [Ask another question...]           │
│          │                                      │
│ Paste    │                                      │
│  Logs    │                                      │
│          │                                      │
│ K8s pod  │                                      │
│ Airflow  │                                      │
│  task    │                                      │
└──────────┴──────────────────────────────────────┘
```

**The sidebar lets you:**
1. Set analysis mode (auto/heuristic/llm)
2. Index codebase → stores all code in ChromaDB
3. View stats → how many items are in ChromaDB
4. Sync lineage → pulls Marquez data into ChromaDB
5. Paste logs → adds log context to your chat question
6. Fetch K8s pod logs → automatically fetches Kubernetes container logs
7. Fetch Airflow task logs → automatically fetches Airflow task logs

---

## 11. The Databases — PostgreSQL + Redis

### PostgreSQL

PostgreSQL is the **relational database** (like Excel, but much more powerful).

**What it stores in our project:**
```
Database: airflow
  Tables: dag, dag_run, task_instance, xcom, user, connection, ...
  Purpose: Airflow stores all its metadata here
           (which DAGs exist, which runs happened, which tasks ran, etc.)

Database: marquez
  Tables: namespaces, jobs, datasets, runs, run_args, ...
  Purpose: Marquez stores all lineage data here
```

**Connection strings:**
```
Airflow → postgres: postgresql+psycopg2://airflow:airflow@postgres:5432/airflow
Marquez → postgres: POSTGRES_HOST=postgres, POSTGRES_DB=marquez, USER=airflow
```

**The init script (`docker/init-multiple-dbs.sh`):**
When PostgreSQL starts for the FIRST time, it runs this script automatically to create both databases:
```bash
SELECT 'CREATE DATABASE marquez' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'marquez')\gexec
GRANT ALL PRIVILEGES ON DATABASE marquez TO airflow;
```

### Redis

Redis is an **in-memory key-value store** — like a whiteboard that computers can write to and erase from extremely fast.

**In our project, Redis is the Airflow Celery broker:**

```
airflow-scheduler: "Task X needs to run!"
  → writes task X to Redis queue

airflow-worker-1: reads Redis queue → "I'll run task X!"
  → runs the task
  → writes result back to Redis (then stored in PostgreSQL)

airflow-worker-2: reads Redis queue → "Queue is empty, waiting..."
```

**Why Redis and not PostgreSQL for this?**
- Redis operates in memory → microsecond reads
- PostgreSQL reads from disk → millisecond reads
- For a task queue with hundreds of tasks, the speed difference matters enormously

---

## 12. How Everything Connects Together

Here is the complete data flow from start to finish:

```
┌─────────────────── STARTUP SEQUENCE ───────────────────────────────┐
│                                                                     │
│  1. postgres starts first (PostgreSQL container)                    │
│     └── init-multiple-dbs.sh runs → creates airflow + marquez DBs  │
│                                                                     │
│  2. redis starts (Redis container)                                  │
│                                                                     │
│  3. marquez-api starts → connects to postgres:marquez DB            │
│                                                                     │
│  4. airflow-init runs → "airflow db migrate" → sets up Airflow DB   │
│                         Creates admin user (admin/admin)            │
│                                                                     │
│  5. ollama starts (LLM server)                                      │
│     └── ollama-init pulls llama3.1:8b model (~4.7GB)               │
│                                                                     │
│  6. backend starts → ChromaDB ready (in-process, stored in /chromadb)│
│     └── /health endpoint returns {"status": "ok"}                  │
│                                                                     │
│  7. frontend starts (waits for backend /health to pass)             │
│                                                                     │
│  8. airflow-webserver, airflow-scheduler, airflow-worker start      │
│     (wait for airflow-init to complete first)                       │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────── USER WORKFLOW ──────────────────────────────────────┐
│                                                                     │
│  User goes to http://localhost:8501 (Streamlit)                    │
│       ↓                                                            │
│  Clicks "Index Codebase"                                           │
│  Streamlit → POST /index/codebase (FastAPI backend)               │
│  FastAPI → walks project files → chunks them → embeds with         │
│            sentence-transformers → stores in ChromaDB              │
│                                                                     │
│  User goes to http://localhost:8080 (Airflow)                      │
│       ↓                                                            │
│  Enables "data_ingestion" DAG → click Trigger                     │
│  Airflow scheduler → sends task to Redis queue                     │
│  Airflow worker → picks up task → runs Python code:               │
│    ingest_csv_files: copies landing/sales_data.csv → raw/         │
│    ingest_api_data:  creates API JSON file → raw/                  │
│    validate_raw_data: checks files are not empty                   │
│  OpenLineage → sends lineage event to Marquez                     │
│                                                                     │
│  User enables "data_transformation" DAG → runs:                   │
│    clean_data: raw/ → staging/ (normalized, cleaned)               │
│    transform_aggregate: staging/ → processed/ (grouped)            │
│    enrich_with_metadata: processed/ → curated/ (timestamped)       │
│                                                                     │
│  User enables "data_quality_checks" DAG → runs all 4 in parallel   │
│    schema conformance, null ratios, row counts, duplicates          │
│                                                                     │
│  User enables "ml_pipeline" DAG → runs:                           │
│    build_features: curated/ → features/features.csv                │
│    train_model: features.csv → RandomForest → models/model.pkl     │
│    evaluate_model: checks accuracy ≥ 0.5                           │
│                                                                     │
│  Back in Streamlit chat:                                           │
│  User types: "What did the ml_pipeline produce?"                   │
│  Backend:                                                           │
│    1. Embeds question → searches ChromaDB                          │
│    2. Finds: ml_pipeline_dag.py code + lineage events              │
│    3. Builds prompt with context                                    │
│    4. Sends to Ollama LLaMA → gets answer                         │
│    5. Returns answer + sources to Streamlit                        │
│  User sees: "The ml_pipeline DAG produced model.pkl stored at      │
│             /data/models/model.pkl with accuracy 0.87..."          │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 13. File-by-File Code Explanation

### Backend Files

```
backend/app/
├── __init__.py           ← Empty file, makes 'app' a Python package
│
├── main.py               ← ENTRY POINT. Creates FastAPI app, defines all
│                           URL routes (endpoints), adds CORS middleware
│
├── models.py             ← DATA SHAPES. Pydantic models define what JSON
│                           requests/responses look like. FastAPI validates
│                           all requests automatically against these models
│
├── settings.py           ← CONFIGURATION. Reads environment variables.
│                           Other files import from here instead of reading
│                           os.getenv() everywhere (single source of truth)
│
├── chat_agent.py         ← CHAT ORCHESTRATOR. Combines:
│                           - optional log text analysis
│                           - optional K8s pod log fetching
│                           - optional Airflow task log fetching
│                           - RAG query (if Ollama available)
│                           - fallback to repo search (if Ollama down)
│
├── rag_engine.py         ← RAG PIPELINE. The core AI logic:
│                           retrieve → build context → call LLM → return
│
├── vectordb_client.py    ← CHROMADB WRAPPER. Creates/queries collections.
│                           Module-level singleton (one client, reused)
│
├── embedding_pipeline.py ← INDEXING ENGINE. Walks files, chunks them,
│                           converts to vectors, stores in ChromaDB.
│                           Also indexes logs, DAG metadata, lineage events
│
├── lineage_client.py     ← MARQUEZ CLIENT. Fetches jobs/datasets/runs
│                           from Marquez REST API. Also syncs to ChromaDB
│
├── llm_client.py         ← OLLAMA CLIENT. Two functions:
│                           call_ollama_chat() → free-form answer
│                           analyze_with_llm() → expects JSON back
│
├── log_analyzer.py       ← LOG ANALYSIS ENGINE. Two modes:
│                           heuristic: regex patterns → fast, no LLM needed
│                           llm: sends to Ollama → more detailed analysis
│
├── repo_context.py       ← FALLBACK SEARCH. When Ollama is offline,
│                           does simple keyword search through project files
│
├── k8s_logs.py           ← K8S LOG FETCHER. Uses kubernetes Python client.
│                           Works in-cluster or via KUBECONFIG on laptop
│
└── airflow_logs.py       ← AIRFLOW LOG FETCHER. Calls Airflow REST API
                            GET /api/v1/dags/{dag}/dagRuns/{run}/taskInstances/
                                 {task}/logs/{try_number}
```

### DAG Files

```
dags/
├── data_ingestion_dag.py     ← Copies CSVs + fetches API data. Runs @hourly.
├── data_transformation_dag.py← Cleans + transforms + enriches data. @daily.
├── data_quality_dag.py       ← 4 parallel quality checks. @daily.
├── ml_pipeline_dag.py        ← Feature engineering + RandomForest training. @weekly.
└── deploy_pipeline_dag.py    ← Test + build Docker images + kubectl deploy. Manual.
```

### Docker Files

```
docker/
├── docker-compose.yml        ← 12 services, all configured, health-checked,
│                               correct startup order via depends_on
├── Dockerfile.backend        ← Python 3.11 + all backend deps + embedding model baked in
├── Dockerfile.airflow        ← Airflow 2.8.1 + OpenLineage + pandas + scikit-learn
├── Dockerfile.frontend       ← Python 3.11 + Streamlit only (lean image)
└── init-multiple-dbs.sh      ← PostgreSQL init: creates 'marquez' database on first boot
```

### Kubernetes Files

```
k8s/
├── namespaces.yaml           ← Create 4 namespaces: backend, airflow, data, monitoring
├── ingress.yaml              ← External URL routing (4 subdomains → 4 services)
├── backend/
│   ├── deployment.yaml       ← ConfigMap + 2-replica backend + Service + 5GB PVC
│   ├── ollama.yaml           ← Ollama deployment + Service + 20GB PVC
│   └── frontend.yaml         ← Frontend deployment + Service
├── airflow/
│   └── deployment.yaml       ← Redis + Webserver + Scheduler + 2 Workers +
│                               ConfigMap + 50GB data-lake PVC
└── data/
    ├── postgres.yaml         ← PostgreSQL + Service + 10GB PVC + ConfigMap
    └── marquez.yaml          ← Marquez API + Marquez Web + Services
```

### Script Files

```
scripts/
├── index_codebase.py    ← CLI: python scripts/index_codebase.py [--reset]
│                          Walks project, indexes all code into ChromaDB
├── sync_lineage.py      ← CLI: python scripts/sync_lineage.py [--namespace default]
│                          Pulls Marquez lineage into ChromaDB for RAG
├── post_logs.py         ← CLI: python scripts/post_logs.py deploy.log
│                          Posts a log file to /analyze-log endpoint
├── analyze_k8s_pod.py   ← CLI: analyze a specific Kubernetes pod's logs
└── analyze_airflow_task.py ← CLI: analyze a specific Airflow task's logs
```

### Data Files

```
data/
├── landing/             ← DROP CSV FILES HERE (input zone)
│   ├── sales_data.csv   ← sample: 15 product sales records
│   └── user_events.csv  ← sample: 12 user behavior events
├── raw/                 ← Airflow copies/creates files here (data_ingestion DAG)
├── staging/             ← Cleaned files (data_transformation step 1)
├── processed/           ← Aggregated files (data_transformation step 2)
├── curated/             ← Final data with metadata (data_transformation step 3)
├── features/            ← ML features (ml_pipeline step 1)
├── models/              ← Trained model.pkl + metrics.json (ml_pipeline step 2-3)
└── chromadb/            ← ChromaDB vector database files (auto-managed)
```

---

## 14. How to Run the Project

### Prerequisites (Install These First)
1. **Docker Desktop** — download from https://docker.com/products/docker-desktop
2. **At least 8GB RAM** (LLaMA model needs ~5GB)
3. **At least 20GB free disk space** (Docker images + AI model)

### Step-by-Step Run Instructions

```bash
# ── STEP 1: Clone/Open the project ───────────────────────────────
cd path/to/bigdata-prototype

# ── STEP 2: Start all services ────────────────────────────────────
cd docker
docker compose up --build -d

# What happens:
# - Docker builds 3 custom images (takes ~5-10 minutes first time)
# - Downloads 5 images from Docker Hub (postgres, redis, ollama, marquez)
# - Starts all 12 containers
# - Databases initialize
# - ollama-init starts downloading llama3.1:8b (~4.7GB — takes time!)

# ── STEP 3: Watch the LLM model download ─────────────────────────
docker logs -f ollama-init
# Wait until you see: "Model ready."
# Press Ctrl+C to stop watching logs

# ── STEP 4: Check all services are healthy ────────────────────────
docker compose ps
# You should see all services as "running" or "Up"
# airflow-init and ollama-init will show "exited 0" (that's normal — they ran once)

# ── STEP 5: Open the Streamlit chat UI ────────────────────────────
# Open browser: http://localhost:8501
# You should see the "BigData Platform — Observability Agent" chat UI

# ── STEP 6: Index the codebase for AI search ──────────────────────
# In the Streamlit sidebar, click "Index Codebase"
# Wait ~30 seconds. You'll see "Indexed X code chunks"
# Now the AI knows about all your code, DAGs, configs

# ── STEP 7: Open Airflow and run your first pipeline ──────────────
# Open browser: http://localhost:8080
# Login: admin / admin
#
# Turn ON "data_ingestion" DAG (click the toggle)
# Click the ▶ (play) button to trigger a manual run
# Watch the tasks turn green as they succeed

# ── STEP 8: Run the full pipeline ─────────────────────────────────
# Turn on and trigger these DAGs in order:
# 1. data_ingestion     ← copies sample CSVs to raw zone
# 2. data_transformation← cleans and aggregates data
# 3. data_quality_checks← validates the data
# 4. ml_pipeline        ← trains a model on the data

# ── STEP 9: Check lineage in Marquez ──────────────────────────────
# Open browser: http://localhost:3000
# You'll see a visual graph of data flow between DAG tasks

# ── STEP 10: Sync lineage to ChromaDB for AI ──────────────────────
# In Streamlit sidebar, click "Sync Lineage to VectorDB"
# Now AI can answer questions about data lineage too

# ── STEP 11: Ask the AI questions! ────────────────────────────────
# In Streamlit chat, try these questions:
# "What does the data_transformation DAG do?"
# "Show me the data quality checks"
# "What model does the ml_pipeline train?"
# "How does the RAG engine work?"
# Paste error logs in the sidebar and ask "What went wrong?"
```

### Useful Commands

```bash
# See all running containers
docker compose ps

# See logs of a specific service
docker logs backend
docker logs airflow-scheduler
docker logs ollama

# Follow live logs
docker logs -f backend

# Stop everything (keeps your data)
docker compose down

# Stop everything AND delete all data (fresh start)
docker compose down -v

# Restart just one service
docker compose restart backend

# Open a shell inside a container
docker exec -it backend bash
docker exec -it postgres psql -U airflow

# Run tests
docker exec -it backend python -m pytest tests/ -v
# OR locally (with Python installed):
pip install -r requirements.txt
pytest tests/ -v
```

### Service URLs When Running

| Service | URL | Login |
|---------|-----|-------|
| Chat UI (Streamlit) | http://localhost:8501 | none |
| API Docs (FastAPI Swagger) | http://localhost:8000/docs | none |
| Airflow Dashboard | http://localhost:8080 | admin / admin |
| Marquez Lineage UI | http://localhost:3000 | none |
| Marquez API | http://localhost:5000 | none |
| Ollama API | http://localhost:11434 | none |
| PostgreSQL | localhost:5432 | airflow / airflow |
| Redis | localhost:6379 | none |

---

## 15. Common Questions & Answers

**Q: The AI chat isn't working / says Ollama not running**
```
A: The LLaMA model is still downloading. Check:
   docker logs -f ollama-init
   Wait until you see "Model ready."
   Then refresh the chat and try again.
```

**Q: How do I add my own CSV data?**
```
A: Drop any .csv files into the data/landing/ folder.
   Then trigger the data_ingestion DAG in Airflow.
   It automatically picks up all CSVs from that folder.
```

**Q: Why does my question not get a good AI answer?**
```
A: First index the codebase:
   Streamlit sidebar → click "Index Codebase"
   This puts all code into ChromaDB so the AI has context.
   Also click "Sync Lineage to VectorDB" for lineage context.
```

**Q: How do I add a new data pipeline?**
```
A: Create a new Python file in dags/ following the pattern:

from airflow import DAG
from airflow.operators.python import PythonOperator

def my_task(**context):
    # your logic here
    pass

with DAG(dag_id="my_new_dag", schedule_interval="@daily", ...) as dag:
    t1 = PythonOperator(task_id="my_task", python_callable=my_task)

The file is automatically picked up by Airflow (no restart needed).
```

**Q: What happens when a container crashes?**
```
Docker Compose: restart: unless-stopped — Docker automatically restarts it
Kubernetes: Deployment — Kubernetes automatically creates a new pod

Both make the system self-healing.
```

**Q: Can I run this without a GPU?**
```
Yes! Everything runs on CPU.
- Embeddings (sentence-transformers): CPU, ~1 second per query
- LLaMA 3.1:8b on CPU: slower (~30-120 seconds per response)
- GPU speeds this up to 2-5 seconds per response

To enable GPU (if you have NVIDIA GPU), uncomment the GPU section
in docker-compose.yml under the ollama service.
```

**Q: How is data kept safe between restarts?**
```
Named Docker volumes store persistent data:
- chromadb-data: your ChromaDB embeddings
- postgres-data:  all Airflow and Marquez data
- ollama-models: the downloaded LLaMA model

The data/ folder is bind-mounted, so files there persist naturally.

Only if you run "docker compose down -v" is everything deleted.
```

---

## Summary: The Complete Picture

```
┌─────────────────────────────────────────────────────────────┐
│               WHAT WE BUILT                                  │
│                                                             │
│  A company's complete data platform in a box:              │
│                                                             │
│  DATA FLOW:                                                 │
│  CSV/API → Airflow → Clean → Transform → Quality → ML      │
│                ↓                                            │
│           Marquez tracks every step (lineage)               │
│                                                             │
│  AI LAYER:                                                  │
│  All code + logs → ChromaDB (vector search)                │
│  User question → RAG → ChromaDB + Ollama → smart answer    │
│                                                             │
│  INFRASTRUCTURE:                                            │
│  Local dev: Docker Compose (12 containers, 1 machine)       │
│  Production: Kubernetes (auto-scaling, self-healing)        │
│                                                             │
│  COST: $0 — everything is open-source, runs locally        │
└─────────────────────────────────────────────────────────────┘
```
