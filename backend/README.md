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

From the repo root, start Postgres and Redis:

```bash
docker compose up -d postgres redis
```

Then run the API:

```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 3000
```

API docs are available at `http://localhost:3000/docs`.
