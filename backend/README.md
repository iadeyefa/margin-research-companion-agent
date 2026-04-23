# Sports Analysis Agent Backend

Python/FastAPI backend for the sports analysis app.

## Setup

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Environment

Create `backend/.env` if you need to override defaults:

```bash
DATABASE_URL=postgresql+psycopg://postgres:password@localhost:5433/sports_agent
REDIS_URL=redis://localhost:6379
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=mistral
EMBEDDINGS_MODEL=nomic-embed-text
PINECONE_API_KEY=your_key_here
PINECONE_INDEX_NAME=sports-analysis
JWT_SECRET=dev-secret
PORT=3000
NODE_ENV=development
FRONTEND_URL=http://localhost:5173
```

## Run

By default, local development uses SQLite, so you can start the API without Docker:

```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 3000
```

If you want to use Postgres instead, install Docker Desktop, start Postgres and Redis from the repo root, and set `DATABASE_URL` in `backend/.env`:

```bash
DATABASE_URL=postgresql+psycopg://postgres:password@localhost:5433/sports_agent
```

API docs are available at `http://localhost:3000/docs`.
