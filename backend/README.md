# Research Companion Agent Backend

Python/FastAPI backend for the research companion agent.

This backend now focuses on a research companion workflow, including multi-source publication search across major scholarly metadata providers.

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
DATABASE_URL=postgresql+psycopg://postgres:password@localhost:5433/research_companion
REDIS_URL=redis://localhost:6379
CEREBRAS_API_KEY=your_key_here
CEREBRAS_MODEL=llama3.1-8b
JWT_SECRET=dev-secret
PORT=3000
NODE_ENV=development
FRONTEND_URL=http://localhost:5173
RESEARCH_CONTACT_EMAIL=your_email@example.com
SEMANTIC_SCHOLAR_API_KEY=optional_key_here
OPENALEX_API_KEY=optional_key_here
```

## Run

By default, local development uses SQLite, so you can start the API without Docker:

```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 3000
```

If you want to use Postgres instead, install Docker Desktop, start Postgres and Redis from the repo root, and set `DATABASE_URL` in `backend/.env`:

```bash
DATABASE_URL=postgresql+psycopg://postgres:password@localhost:5433/research_companion
```

API docs are available at `http://localhost:3000/docs`.

There is no Pinecone or sports-ingestion dependency in the active research companion app anymore.

## Research Companion Search

The backend can search across multiple publication APIs and normalize the results into one response shape.

Current sources:

- `crossref`
- `semantic_scholar`
- `openalex`
- `pubmed`
- `arxiv`

Example request:

```bash
curl -X POST http://localhost:3000/api/research/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "retrieval augmented generation",
    "limit_per_source": 3
  }'
```

Example request with chosen sources:

```bash
curl -X POST http://localhost:3000/api/research/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "transformers interpretability",
    "limit_per_source": 3,
    "sources": ["semantic_scholar", "openalex", "arxiv"]
  }'
```

## Workspaces

Persistent workspaces let you keep saved papers, search history, and notes together.

Example:

```bash
curl -X POST http://localhost:3000/api/workspaces/ \
  -H "Content-Type: application/json" \
  -d '{
    "title": "RAG survey"
  }'
```

## Synthesis

Use the synthesis endpoint to summarize or compare selected papers.

Example:

```bash
curl -X POST http://localhost:3000/api/research/synthesize \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "summary",
    "papers": [
      {
        "source": "arxiv",
        "external_id": "1234.5678",
        "title": "Example Paper",
        "abstract": "Example abstract",
        "authors": ["A. Author"],
        "venue": "arXiv",
        "year": 2025,
        "publication_date": "2025-02-01",
        "doi": null,
        "url": "https://arxiv.org/abs/1234.5678",
        "pdf_url": "https://arxiv.org/pdf/1234.5678",
        "citation_count": null,
        "open_access": true
      }
    ]
  }'
```
