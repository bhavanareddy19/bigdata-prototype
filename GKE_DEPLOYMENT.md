# BigData Platform — GKE Deployment (Lean Variant)

Deploy the whole stack — **frontend (React+nginx), backend (FastAPI), Airflow (webserver+scheduler, LocalExecutor), Postgres** — to a cheap zonal GKE cluster on your own GCP account.

Designed to fit inside the **$50 GCP free-credit envelope**: ~$35–40/month running 24/7, or cents/hour if you only run it during demos and tear down with `teardown-gke.sh`.

---

## What gets dropped vs. the Cloud Run setup

| Original (friend's) | Lean GKE (yours) |
|---|---|
| Cloud Run (backend + frontend) | GKE Deployments behind a LoadBalancer Service |
| Cloud Composer (Airflow) | Airflow webserver + scheduler pods (LocalExecutor) |
| Cloud SQL / none | Postgres StatefulSet + 5 Gi PVC |
| Ollama (local LLM) | **dropped** — Gemini API only |
| Marquez / OpenLineage | **dropped** — not needed for the demo |
| Redis + Celery worker | **dropped** — LocalExecutor instead |

---

## Prerequisites

1. `gcloud` CLI logged in: `gcloud auth login`
2. `kubectl` installed
3. `docker` running locally (Docker Desktop on Windows is fine)
4. Billing enabled on project `big-data-project-493204`
5. `.env` at the repo root contains `GOOGLE_API_KEY=...` (already populated)

---

## One-shot deploy

```bash
cd bigdata-prototype
bash scripts/deploy-gke.sh
```

The script is idempotent — re-running it builds new image tags and rolls out a fresh version without recreating the cluster.

It will:
1. Enable GKE, Artifact Registry, Cloud Build APIs
2. Create Artifact Registry repo `bigdata` in `us-central1`
3. Create GKE zonal cluster `bigdata-lean` (1× `e2-standard-2` spot node) in `us-central1-a`
4. Build + push `backend`, `frontend`, `airflow` images with a timestamp tag
5. Apply manifests in order: namespaces → RBAC → postgres → backend → airflow → frontend
6. Create `backend-secrets` with your Gemini API key (from `.env`)
7. Wait for rollouts and print the LoadBalancer IP

Expected runtime: **~8–12 min** first time (cluster creation dominates). ~2–3 min on re-runs.

---

## Access after deploy

The script prints something like:

```
Frontend:   http://34.123.45.67/
Backend:    http://34.123.45.67/health
Airflow UI: http://34.123.45.67/airflow/   (admin / admin)
```

All three go through the single LoadBalancer via nginx path routing (cheapest option).

---

## Using the K8s log analyzer chatbot

After deploy, open the frontend IP in the browser. The **Kubernetes** tab now has two modes:

- **Diagnose** — pick a namespace, click *Scan Namespace*. The backend uses its ServiceAccount (mounted in-cluster, see `k8s/backend/rbac.yaml`) to list pods, detect `CrashLoopBackOff` / `ImagePullBackOff` / `OOMKilled` / `Pending` / `FailedScheduling` / `FailedMount` / restart storms, and pull warning events. Click **Ask AI to Fix** and Gemini receives the full diagnosis as context and returns remediation steps (kubectl commands, manifest edits).
- **Pod Logs** — picks a pod from a dropdown (populated from the cluster), fetches tail logs, runs log analysis.

The chatbot on the **Chat** tab also auto-diagnoses whenever your question contains K8s trigger words (`crashloop`, `imagepull`, `pod`, `pending`, `oomkill`, etc.) — it scans up to 5 namespaces and feeds the results to the LLM.

### Test it end-to-end (deliberately break something)

```bash
# 1. Bad image tag → ImagePullBackOff
kubectl -n backend set image deploy/backend backend=does-not-exist:bad
# open the frontend → Kubernetes tab → namespace=backend → Scan → Ask AI to Fix

# 2. Tiny memory limit → OOMKilled on next load
kubectl -n backend set resources deploy/backend --limits=memory=40Mi

# roll back after the demo
kubectl -n backend rollout undo deploy/backend
```

---

## Teardown (stop all charges)

```bash
bash scripts/teardown-gke.sh
```

Deletes: LoadBalancer → cluster → Artifact Registry repo. Takes ~5 min. Persistent disks attached to the cluster are deleted with it.

---

## Cost breakdown (lean, 24/7)

| Resource | ~$/month |
|---|---|
| GKE control plane (1 zonal cluster in free tier) | **$0** |
| 1× `e2-standard-2` spot node | ~$15 |
| Regional HTTP LoadBalancer | ~$18 |
| 15 Gi persistent disks | ~$2 |
| Artifact Registry storage | <$1 |
| **Total** | **~$35** |

If you only run the cluster during demos (e.g. 2 hrs/day), divide the node cost by 12 → ~$5–8/month total. To auto-stop: `gcloud container clusters resize bigdata-lean --num-nodes=0 --zone=us-central1-a` shrinks the nodepool to zero (LB stays, disks stay). Resize back to 1 when you need it.

### Even cheaper: skip the LoadBalancer ($18/mo saved)

Change `Service.type` in `k8s/backend/frontend.yaml` from `LoadBalancer` to `NodePort`, re-apply, then:

```bash
kubectl port-forward -n backend svc/frontend 8080:80
```

Browse `http://localhost:8080`. Free — but only accessible from your machine.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `deploy-gke.sh` fails on `gcloud services enable` | Run `gcloud auth login` and `gcloud config set project big-data-project-493204` |
| `docker push` fails with 403 | Re-run `gcloud auth configure-docker us-central1-docker.pkg.dev` |
| Cluster creation fails with quota | Request quota increase or switch region; spot nodes have separate quota |
| LB IP never appears | Check `kubectl -n backend describe svc frontend` — look for events about forwarding rules |
| Airflow scheduler CrashLoopBackOff | Usually DB not ready; `kubectl -n airflow logs deploy/airflow-scheduler` — if DB connection refused, restart after postgres is ready |
| Backend can't read pod logs (403) | RBAC not applied — `kubectl apply -f k8s/backend/rbac.yaml` |

---

## File map

```
k8s/
├── namespaces.yaml               # backend / airflow / data
├── backend/
│   ├── deployment.yaml           # FastAPI + ConfigMap + Secret + PVC + ClusterIP
│   ├── frontend.yaml             # React+nginx + ConfigMap (nginx proxy config) + LoadBalancer
│   └── rbac.yaml                 # ServiceAccount + ClusterRole for K8s log access
├── airflow/
│   └── deployment.yaml           # webserver + scheduler (LocalExecutor) + shared PVC
└── data/
    └── postgres.yaml             # StatefulSet + 5 Gi PVC + Secret

scripts/
├── deploy-gke.sh                 # one-shot deploy
└── teardown-gke.sh               # one-shot teardown

backend/app/
├── k8s_logs.py                   # list/describe/diagnose + format for LLM
├── chat_agent.py                 # auto-invokes diagnose on K8s questions
└── main.py                       # /k8s/namespaces /k8s/pods/{ns} /k8s/diagnose/{ns} /k8s/describe/{ns}/{pod}
```
