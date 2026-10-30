# CityMemory

**Intelligent civic infrastructure history and failure prediction** (Hackathon Problem Statement 9).

CityMemory links complaints, photos, dates, locations, asset identifiers and maintenance actions into a
searchable timeline for every road, drain, streetlight, footpath and public toilet. It finds similar
complaints, groups recurring failures, ranks which assets need attention first, and tells engineers when
to stop patching and plan a permanent fix.

> All data in this prototype is **simulated**. The AI suggests; engineers decide.

## What it does

| Brief asks for | Where it is |
| --- | --- |
| Searchable timeline of complaints, photos, dates, locations, asset IDs, repairs | Asset panel timeline, header search |
| AI identifies semantically similar complaints | Complaint matching: location + text similarity |
| Cluster recurring incidents | Complaints grouped into failure incidents per asset; "recurring" flag; cause tags |
| Estimate which assets deserve higher priority | Explainable 0-100 priority score with reasons |
| Practical dashboard for municipal teams | Map, priority queue, stop-patching alerts, review queue, contractor durability |

Extra: a **prediction check** that hides each asset's latest failure and tests whether the estimated
window caught it.

## How a complaint flows

`receive → clean → duplicate check → find nearby assets of the same type → compare text with their history → link (auto / engineer review / new asset) → store → cause tag + rescore in the background`

- Combined match score = 0.6 × location closeness + 0.4 × text similarity.
- ≥ 0.62 links automatically, 0.38–0.62 goes to engineer review, below that creates an unregistered asset.
- Settings live at the top of `backend/logic.py`.

## Run it locally

You need Python 3.10+ and Node 18+.

**Backend** (terminal 1):

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python seed.py                 # creates citymemory.db with simulated data
uvicorn main:app --reload --port 8000
```

API docs: http://localhost:8000/docs

**Frontend** (terminal 2):

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. In dev, `/api` is proxied to port 8000.

**Single server (for a demo):** run `npm run build` in `frontend`, then start only the backend.
FastAPI serves the built app at http://localhost:8000.

**Tests:** `cd backend && pip install pytest && python -m pytest -q` (the LLM is mocked in tests)

## Project layout

```
backend/
  main.py       FastAPI endpoints
  logic.py      cleaning, matching, incidents, priority, cost comparison, failure window, back-test
  textsim.py    text normalisation, sentence embeddings, TF-IDF fallback
  patterns.py   ward-wide clustering of complaints by meaning
  llm.py        OpenAI-compatible LLM client (Ollama by default)
  ai.py         LLM cause tagging, asset briefings, pattern labels, with caches and checks
  ai_warmup.py  precompute all AI outputs before a demo
  causes.py     keyword cause tagger (fallback)
  db.py         SQLite schema: assets, complaints, repairs
  seed.py       simulated demo data
  test_api.py   tests
frontend/
  src/App.jsx              layout, dashboard, priority queue
  src/components/          map, asset panel, report form, review/contractor/insight views
```

## Key API endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/api/complaints` | Submit a complaint (form data: text, category, lat, lng, reporter?, photo?) |
| GET | `/api/priority` | Ranked assets |
| GET | `/api/assets/{id}` | Timeline, priority breakdown, cause, cost comparison, failure window |
| GET | `/api/patterns` | Recurring complaint patterns across the ward |
| GET | `/api/assets/{id}/ai-summary` | AI briefing for one asset |
| POST | `/api/ai/retag` | Re-tag all causes with the LLM |
| GET | `/api/search?q=` | Search across assets, complaints and repairs |
| GET | `/api/review` | Uncertain matches for engineer review |
| POST | `/api/complaints/{id}/review` | Confirm, reassign or create a new asset |
| POST | `/api/repairs` | Log a repair |
| GET | `/api/contractors` | Repair durability by contractor |
| GET | `/api/backtest` | Prediction check |
| POST | `/api/reset` | Restore demo data |

## AI models

| Brief's AI job | Model | Fallback if unavailable |
| --- | --- | --- |
| Find semantically similar complaints | `paraphrase-multilingual-MiniLM-L12-v2` (sentence-transformers), vectors stored per complaint | TF-IDF text similarity |
| Cluster recurring incidents | Agglomerative clustering (scikit-learn) over those embeddings, across all assets (`/api/patterns`) | Same clustering over TF-IDF vectors |
| Explain likely cause | LLM picks one cause from a fixed list, with a short reason | Keyword rules |
| Asset briefing + pattern names | LLM, written only from the asset's records; rejected if it states a number not in them | Template text / keywords |

The priority score and failure window stay as transparent formulas on purpose, so engineers can see why.

### Set up (once, needs internet)

```bash
cd backend
pip install -r requirements.txt          # includes sentence-transformers
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')"
ollama pull llama3.2:3b                  # install Ollama from ollama.com first
```

### Before every demo

```bash
python ai_warmup.py --check   # shows which AI parts are working
python ai_warmup.py           # precomputes embeddings, AI cause tags, pattern names, briefings (cached)
uvicorn main:app --port 8000
```

The header badge shows what is live: `AI: embeddings on · LLM on (llama3.2:3b)`.
The Reset button rebuilds demo data but keeps the cached AI answers.

### Use a cloud LLM instead of Ollama

Any OpenAI-compatible API works. Set these before starting the server (PowerShell: `$env:NAME="value"`):

```
LLM_BASE_URL=<provider's OpenAI-compatible base URL>
LLM_MODEL=<model name>
LLM_API_KEY=<your key>
```

Other switches: `LLM_ENABLED=off`, `CITYMEMORY_EMBEDDER=tfidf` (skip the embedding model).

## Deploy

- Backend: Render or Railway, start command `uvicorn main:app --host 0.0.0.0 --port $PORT` (root: `backend`).
- Frontend: Vercel (root: `frontend`), set `VITE_API_URL` to the backend URL.
- Or build the frontend and deploy only the backend, which serves both.
