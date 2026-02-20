# Deploy Log Observability Agent (MVP)

This is a minimal MVP for your project goal: **a chatbot/agent that reads deployment/job logs and explains what went wrong**.

## What you get
- FastAPI backend endpoint: `POST /analyze-log`
- FastAPI chatbot endpoint: `POST /chat` (multi-turn questions)
- Streamlit UI to paste logs and get explanations
- A script for CI to post a failing log file: `scripts/post_logs.py`
- A script to make it automatic in deployments: `scripts/analyze_command.py`

## Quickstart (Windows)

1) Create a virtualenv and install deps:

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

2) Configure env:
- Copy `.env.example` to `.env`
- Recommended (free): use Ollama local model (otherwise it uses heuristics)

3) Run the backend:

```bat
python -m uvicorn backend.app.main:app --reload --port 8000
```

4) Run the UI (new terminal):

```bat
streamlit run frontend\streamlit_app.py
```

Open the UI, paste logs, click **Analyze**.

## Chatbot mode (ask anything about your project)

The Streamlit UI is now a multi-turn chat.
- Ask questions like: "What does this service do?", "How do I run it?", "Why did this deploy fail?"
- Optionally attach context in the sidebar:
  - Paste logs, OR
  - Fetch K8s pod logs, OR
  - Fetch Airflow task logs

### Use a free open-source model (Ollama)

1) Install Ollama: https://ollama.com

2) Pull a model (example):
```bash
ollama pull llama3.1:8b
```

3) In your `.env`, set:
- `LLM_PROVIDER=ollama`
- `OLLAMA_BASE_URL=http://localhost:11434`
- `OLLAMA_MODEL=llama3.1:8b`

Then set Streamlit Mode to `auto` or `llm`.

If Ollama is not running (or no model is configured), it will still return grounded repo snippets + tool summaries.

## Quick checks

### 1) Check the API is up
Open `http://localhost:8000/health` in your browser. You should see `{"status":"ok"}`.

### 2) Check analysis works (manual paste)
Use the Streamlit UI and paste any failing logs.

### 3) Check Kubernetes auto-fetch
If your machine has `kubectl` access to the cluster (dev), pick a crashing pod:
- `kubectl get pods -n <ns>`

Then run:
```bat
set BACKEND_URL=http://localhost:8000
python scripts\analyze_k8s_pod.py --namespace <ns> --pod <pod-name> --container <container-name>
```

### 4) Check Airflow auto-fetch
Set these env vars (or put them in `.env`):
- `AIRFLOW_BASE_URL=https://<your-airflow>`
- `AIRFLOW_USERNAME=...`
- `AIRFLOW_PASSWORD=...`

Then run:
```bat
set BACKEND_URL=http://localhost:8000
python scripts\analyze_airflow_task.py --dag-id <dag_id> --dag-run-id <dag_run_id> --task-id <task_id>
```

## Make it automatic in deployment

Wrap your deploy command with `scripts/analyze_command.py`. It will:
1) run the command
2) capture stdout/stderr to a log file
3) if it fails, send logs to `POST /analyze-log` and print the explanation

Example (Windows):

```bat
set BACKEND_URL=http://localhost:8000
python scripts\analyze_command.py --mode auto --service myapp --env dev -- python -c "import sys; print('deploy start'); raise SystemExit(1)"
```

In CI/CD, use the same pattern to get an explanation only when the deploy step fails.

## API

### POST /analyze-log
Request body:
```json
{
  "log_text": "...",
  "mode": "auto",
  "max_lines": 250,
  "source": "ci",
  "service": "myservice",
  "environment": "prod"
}
```

- `mode=auto`: uses LLM if `OPENAI_API_KEY` is set, otherwise heuristic.

### POST /chat
Multi-turn Q&A endpoint.

Minimal request:
```json
{
  "question": "What does this project do?",
  "history": [],
  "mode": "auto",
  "include_repo_context": true
}
```

Attach pasted logs:
```json
{
  "question": "Why did the deploy fail?",
  "history": [],
  "log_text": "...",
  "mode": "auto"
}
```

### POST /analyze-k8s-pod
Fetches pod logs automatically (Kubernetes API) and analyzes them.

Request body:
```json
{
  "namespace": "default",
  "pod": "my-pod-abc",
  "container": "app",
  "tail_lines": 500,
  "timestamps": true,
  "mode": "auto",
  "max_lines": 250
}
```

Kubernetes requirements:
- If running the backend **inside the cluster**: give it a ServiceAccount with permission `get` on `pods/log`.
- If running **outside the cluster**: provide access via `KUBECONFIG` (dev only).

### POST /analyze-airflow-task
Fetches task logs automatically (Airflow REST API) and analyzes them.

Request body:
```json
{
  "airflow_base_url": "https://<your-airflow>",
  "dag_id": "sales_ingest",
  "dag_run_id": "scheduled__2026-02-19T03:00:00+00:00",
  "task_id": "load_csv",
  "try_number": 1,
  "mode": "auto",
  "max_lines": 250
}
```

Airflow requirements:
- Set `AIRFLOW_BASE_URL` (or pass it in the request).
- If your Airflow uses basic auth, set `AIRFLOW_USERNAME` and `AIRFLOW_PASSWORD`.
- Some managed Airflow products store logs in cloud logging (CloudWatch/GCS). If the API endpoint is restricted/unavailable, fetch logs from your logging backend instead and call `POST /analyze-log`.

## Next step (to connect Airflow + lineage later)
Once this MVP is working, we can add:
- Airflow log fetch tool (Airflow REST API)
- OpenLineage/Marquez lineage graph + blast radius
- RAG (Chroma) over your DAG/SQL repo
