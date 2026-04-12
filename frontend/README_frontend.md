# Frontend — Vite + React + TailwindCSS

This directory contains the web UI for the BigData Prototype platform.
It replaces the previous Streamlit-based frontend (`streamlit_app.py`, now deleted).

---

## Tech Stack

| Layer        | Choice                  | Why                                                       |
|--------------|-------------------------|-----------------------------------------------------------|
| Bundler      | **Vite 8**              | Near-instant HMR, native ESM, fast production builds      |
| Framework    | **React 19**            | Component model, huge ecosystem, hooks for state          |
| Styling      | **TailwindCSS v4**      | Utility-first CSS, no separate stylesheet files needed    |
| Routing      | **React Router v7**     | Client-side SPA routing between the 5 pages               |
| HTTP         | **fetch API** (native)  | No extra library needed for simple JSON POST/GET calls     |

---

## Directory Structure

```
frontend/
├── index.html                 # HTML shell — Vite injects the JS bundle here
├── package.json               # Dependencies and npm scripts
├── vite.config.js             # Vite config: React plugin, TailwindCSS plugin, API proxy
├── src/
│   ├── main.jsx               # Entry point — mounts React into #root with BrowserRouter
│   ├── App.jsx                # Layout shell: Navbar (top) + Sidebar (left) + <Routes>
│   ├── index.css              # Single line: @import "tailwindcss" (Tailwind v4 style)
│   ├── components/
│   │   ├── Navbar.jsx         # Top navigation bar with links to all 5 pages
│   │   ├── Sidebar.jsx        # Left panel: Index Codebase, Sync Lineage, ChromaDB stats
│   │   ├── ModeSelector.jsx   # Dropdown: auto / heuristic / llm — reused on every page
│   │   └── LogResultDisplay.jsx  # Shared result card for log analysis responses
│   └── pages/
│       ├── ChatPage.jsx       # Route /       — conversational Q&A with source citations
│       ├── LogAnalysisPage.jsx# Route /logs   — paste raw logs, get structured analysis
│       ├── AirflowPage.jsx    # Route /airflow— analyse Airflow task logs by DAG/task ID
│       ├── K8sPage.jsx        # Route /k8s    — analyse Kubernetes pod logs
│       └── LineagePage.jsx    # Route /lineage— browse OpenLineage namespaces/jobs/datasets
```

---

## How It Works

### Rendering Flow

1. **`index.html`** loads `src/main.jsx` as an ES module.
2. **`main.jsx`** wraps `<App />` in `<BrowserRouter>` and renders into `#root`.
3. **`App.jsx`** renders a flex layout:
   - `<Navbar />` across the top (full width)
   - `<Sidebar />` on the left (fixed 256px)
   - `<Routes>` in the remaining space — switches between the 5 page components
4. Every page component manages its own local state with `useState` and calls
   the FastAPI backend via `fetch()`.

### API Communication

In **development**, Vite's dev server proxies API paths to `http://localhost:8000`:

```js
// vite.config.js
server: {
  proxy: {
    '/chat': 'http://localhost:8000',
    '/analyze-log': 'http://localhost:8000',
    // ... etc
  }
}
```

In **production** (Docker), nginx does the same thing via reverse proxy rules
defined in `docker/nginx-frontend.conf`. The React code uses relative URLs
(e.g. `fetch('/chat')`) so it works identically in both environments.

### API Endpoints Used

| Page / Component | Method | Endpoint                        | Purpose                        |
|------------------|--------|---------------------------------|--------------------------------|
| ChatPage         | POST   | `/chat`                         | Ask a question, get answer + sources |
| LogAnalysisPage  | POST   | `/analyze-log`                  | Analyse pasted raw log text    |
| AirflowPage      | POST   | `/analyze-airflow-task`         | Analyse Airflow task log       |
| K8sPage          | POST   | `/analyze-k8s-pod`              | Analyse Kubernetes pod log     |
| LineagePage       | GET    | `/lineage/namespaces`           | List OpenLineage namespaces    |
| LineagePage       | GET    | `/lineage/jobs/{ns}`            | List jobs in a namespace       |
| LineagePage       | GET    | `/lineage/datasets/{ns}`        | List datasets in a namespace   |
| Sidebar          | POST   | `/index/codebase`               | Trigger codebase indexing      |
| Sidebar          | POST   | `/lineage/sync`                 | Sync lineage events to VectorDB|
| Sidebar          | GET    | `/index/stats`                  | Fetch ChromaDB collection stats|

### Styling Approach

- **Dark theme**: `bg-gray-900` on `<body>`, `bg-gray-950` on navbar/sidebar,
  `bg-gray-800` on cards and inputs.
- **All styling is Tailwind utility classes** — no custom CSS, no CSS-in-JS.
- TailwindCSS v4 uses the `@tailwindcss/vite` plugin (configured in
  `vite.config.js`) and a single `@import "tailwindcss"` in `index.css`.
  There is no `tailwind.config.js` — v4 uses CSS-based configuration by default.

### State Management

There is no global state library. Each page manages its own state with
React's `useState` and `useEffect` hooks. This keeps things simple — the
pages are independent and don't share data.

The Chat page maintains conversation `history` as an array of messages that
gets sent to the backend on every turn, enabling multi-turn conversations.

### Shared Components

- **`ModeSelector`** — a `<select>` dropdown for `auto / heuristic / llm`.
  Used on Chat, Logs, Airflow, and K8s pages. Takes `value` and `onChange` props.
- **`LogResultDisplay`** — renders the structured analysis result (category badge,
  error signature, root cause, next actions, confidence). Used on Logs, Airflow,
  and K8s pages.

---

## Running Locally (Development)

```bash
cd frontend
npm install        # Install dependencies (one-time)
npm run dev        # Start Vite dev server → http://localhost:5173
```

The dev server hot-reloads on file changes. API calls are proxied to
`http://localhost:8000` (the FastAPI backend must be running separately).

## Building for Production

```bash
cd frontend
npm run build      # Outputs optimised bundle to frontend/dist/
npm run preview    # Preview the production build locally
```

## Running in Docker

The `docker/Dockerfile.frontend` uses a two-stage build:

1. **Stage 1 (`node:20-alpine`)**: Installs deps, runs `npm run build`
2. **Stage 2 (`nginx:alpine`)**: Copies `dist/` into nginx, serves on port 80

```bash
cd docker
docker compose up frontend    # Builds and starts on http://localhost:3001
```

Nginx serves static files and reverse-proxies API routes to the `backend`
container. See `docker/nginx-frontend.conf` for the proxy rules.

---

## What Changed From Streamlit

| Before (Streamlit)                     | After (Vite + React)                       |
|----------------------------------------|--------------------------------------------|
| `streamlit_app.py` (single Python file)| Multi-file React SPA in `src/`             |
| Server-rendered, full page reloads     | Client-side SPA, instant navigation        |
| Streamlit widgets for UI               | Custom components with Tailwind utility CSS |
| Port 8501                              | Port 5173 (dev) / 80 (Docker/nginx)        |
| `pip install streamlit`                | `npm install` (Node.js ecosystem)          |
| `BACKEND_URL` env var for API calls    | Vite proxy (dev) / nginx proxy (prod)      |
| Python runtime required in container   | Static files only in prod container (nginx) |

---

## Key Design Decisions

1. **No state management library** — `useState` is sufficient for independent
   pages that don't share data. Adding Redux/Zustand would be premature.

2. **Relative API URLs** (`/chat` not `http://localhost:8000/chat`) — the proxy
   layer (Vite in dev, nginx in prod) handles routing to the backend. This
   avoids CORS issues and environment-specific config.

3. **TailwindCSS v4 with Vite plugin** — no PostCSS config, no `tailwind.config.js`.
   The `@tailwindcss/vite` plugin handles everything at build time.

4. **Two-stage Docker build** — the final image is ~25MB (nginx:alpine + static
   files) instead of ~200MB+ if we shipped Node.js.

5. **Nginx reverse proxy in Docker** — keeps the frontend and backend on the
   same origin, avoiding CORS complexity. The browser talks to nginx on port 80;
   nginx forwards API paths to the backend container.
