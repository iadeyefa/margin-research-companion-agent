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
EMBEDDINGS_MODEL=sentence-transformers/all-MiniLM-L6-v2
PINECONE_API_KEY=your_key_here
PINECONE_INDEX_NAME=sports-analysis
CEREBRAS_API_KEY=your_key_here
CEREBRAS_MODEL=llama3.1-8b
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

## Ingest NBA Data Into Pinecone

1. Download the Kaggle NBA CSV dataset.
2. Put the dataset folder here:

```text
backend/data/raw/NBA box scores/
```

3. Make sure `backend/.env` has:

```bash
PINECONE_API_KEY=your_key_here
PINECONE_INDEX_NAME=sports-analysis
EMBEDDINGS_MODEL=sentence-transformers/all-MiniLM-L6-v2
```

4. Preview the generated text before uploading:

```bash
cd backend
source .venv/bin/activate
python scripts/ingest_nba_csv.py --limit 5 --dry-run
```

5. Run a small test ingest:

```bash
python scripts/ingest_nba_csv.py --limit 25
```

6. If the test looks good in Pinecone, ingest more:

```bash
python scripts/ingest_nba_csv.py --limit 1000
```

7. Full ingest:

```bash
python scripts/ingest_nba_csv.py
```
