# Margin - Research Companion Agent

Margin is a full-stack research workspace for finding, saving, organizing, and synthesizing academic papers. The app combines a FastAPI backend with a React + Vite frontend and supports multi-source paper search, workspace-based organization, AI-assisted synthesis, and reading-path generation.

## What it does

- Search across `crossref`, `semantic_scholar`, `openalex`, `pubmed`, and `arxiv`
- Save papers into persistent research workspaces
- Track search history per workspace
- Write notes inside each workspace
- Generate synthesis briefs in `summary`, `compare`, or `question` mode
- Build reading paths for a selected set of papers
- Export selected papers as `bibtex` or `markdown`
- Browse a cross-workspace library of saved papers

## Project structure

```text
.
├── backend/                 FastAPI API, database models, research services
├── frontend/                React + TypeScript + Vite client
├── docker-compose.yml       Optional Postgres + Redis for local development
└── requirements.txt         Legacy root requirements file
```

## Tech stack

- Frontend: React 19, TypeScript, Vite, React Router
- Backend: FastAPI, SQLAlchemy, Pydantic
- Storage: SQLite by default, Postgres optional
- LLM routing: LangChain with Google Gemini (`GOOGLE_*`) or local/cloud Ollama (`OLLAMA_*`, optional bearer key for hosted Ollama)
- Integrations: Crossref, Semantic Scholar, OpenAlex, PubMed, arXiv

## Local development

### One-command dev

```bash
chmod +x scripts/dev.sh
./scripts/dev.sh
```

This starts the API on [http://127.0.0.1:3000](http://127.0.0.1:3000) and the frontend on [http://127.0.0.1:5173](http://127.0.0.1:5173).

### 1. Start the backend

```bash
cd /Users/Ife/Documents/margin-research-companion-agent/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 3000
```

The backend defaults to SQLite and will create `backend/research_companion.db` (path is fixed relative to the backend package, not your shell’s current directory).

### 2. Start the frontend

```bash
cd /Users/Ife/Documents/margin-research-companion-agent/frontend
npm install
npm run dev
```

The frontend runs on [http://localhost:5173](http://localhost:5173) by default and talks to `http://localhost:3000` unless `VITE_API_URL` is set.

### 3. Optional: run Postgres and Redis with Docker

If you want to use Postgres instead of SQLite:

```bash
cd /Users/Ife/Documents/margin-research-companion-agent
docker compose up -d postgres redis
```

Then set `DATABASE_URL` in `backend/.env`:

```bash
DATABASE_URL=postgresql+psycopg://postgres:password@localhost:5433/research_companion
```

## Environment variables

Copy the template and edit secrets locally (`backend/.env` is ignored by git):

```bash
cp backend/.env.example backend/.env
```

Important pieces for **AI-assisted** flows (guided search Companion, synthesis, reading path):

| Variable | Role |
| --- | --- |
| `LLM_PROVIDER` | `auto` (default): Google then Ollama. Or `google` / `ollama` only. |
| `GOOGLE_API_KEY`, `GOOGLE_MODEL` | Gemini via LangChain. |
| `OLLAMA_BASE_URL`, `OLLAMA_MODEL` | Local default `http://localhost:11434` and `llama3.2:latest`. Run `ollama pull llama3.2` so the tag exists. |
| `OLLAMA_API_KEY` | Only for **hosted** Ollama (`https://ollama.com`-style); local Ollama does not need it. |

The app loads **`backend/.env` with precedence over stray shell exports** for keys defined there, so your file wins over leftover `export OLLAMA_MODEL=…` from an old shell profile.

Other useful keys:

- **`DATABASE_URL`** — omit for default SQLite at `backend/research_companion.db`
- **`RESEARCH_CONTACT_EMAIL`** — polite pool access for Crossref / OpenAlex
- **`SEMANTIC_SCHOLAR_API_KEY`**, **`OPENALEX_API_KEY`**, **`CORE_API_KEY`** — higher rate limits or richer abstracts when available
- **`JWT_SECRET`**, **`PORT`**, **`FRONTEND_URL`**, **`NODE_ENV`**

Legacy optional: **`CEREBRAS_*`** appears in `.env.example` for older setups; synthesis and routing **use Gemini/Ollama** through `research_model.py`.

**Sanity check:** `GET /api/health/` — `research_llm: "configured"` means at least minimal LLM env is present (not a live connectivity probe).

## Demo data

```bash
cd backend
python3 scripts/seed_demo.py
```

This creates a demo workspace with saved papers and a persisted summary brief.

## Frontend experience

The client currently includes:

- Dashboard for recent workspaces, saved papers, searches, and briefs
- Workspace tabs for `Overview`, `Search`, `Saved`, `Synthesis`, `Reading path`, `Notes`, and `History`
- Global library view for saved papers across workspaces
- Paper detail pages
- Theme support and command-palette style UI plumbing

## API overview

Base URL: `http://localhost:3000/api`

### Health

- `GET /api/health/`

### Research

- `POST /research/search`
- `POST /research/search/collaborate`
- `POST /research/synthesize`
- `POST /research/reading-path`
- `POST /research/export`

### Workspaces

- `GET /workspaces/`
- `POST /workspaces/`
- `GET /workspaces/{workspace_id}`
- `PATCH /workspaces/{workspace_id}`
- `DELETE /workspaces/{workspace_id}`
- `POST /workspaces/{workspace_id}/papers`
- `DELETE /workspaces/{workspace_id}/papers/{source}/{external_id}`

### Library

- `GET /library/papers`

Interactive API docs are available at [http://localhost:3000/docs](http://localhost:3000/docs).

## Example requests

Search for papers:

```bash
curl -X POST http://localhost:3000/api/research/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "retrieval augmented generation",
    "limit_per_source": 3,
    "sources": ["semantic_scholar", "openalex", "arxiv"],
    "workspace_id": null,
    "year_from": null,
    "year_to": null,
    "open_access_only": false,
    "sort_by": "relevance"
  }'
```

Create a workspace:

```bash
curl -X POST http://localhost:3000/api/workspaces/ \
  -H "Content-Type: application/json" \
  -d '{
    "title": "RAG survey"
  }'
```

Generate a synthesis:

```bash
curl -X POST http://localhost:3000/api/research/synthesize \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "summary",
    "question": null,
    "papers": []
  }'
```

## Current status

This repo has already been refocused from an older sports-oriented project into a research workflow product. Some low-level filenames or Docker container names still reflect that earlier history, but the active backend and frontend code paths are centered on research search, workspace management, and paper synthesis.
