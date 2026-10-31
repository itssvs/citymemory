---
title: CityMemory
emoji: 🏙️
colorFrom: yellow
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
short_description: Civic infrastructure history and failure prediction
---

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
| Searchable timeline of complaints, photos, dates, locations, asset IDs, repairs | **Timeline** page (engineer and commissioner): every complaint, repair and repair job in the ward, newest first, with photos; filter by date range, asset type, event kind or one asset; search by meaning, street or asset ID. Each complaint says which failure of its asset it started or repeated; each repair says how long it held. Also per asset in the asset panel |
| AI identifies semantically similar complaints | Complaint matching: location + text similarity |
| Cluster recurring incidents | Complaints grouped into failure incidents per asset; "recurring" flag; cause tags |
| Estimate which assets deserve higher priority | Explainable 0-100 priority score with reasons |
| Practical dashboard for municipal teams | Map, priority queue, stop-patching alerts, review queue, contractor durability |

Extra: a **prediction check** that hides each asset's latest failure and tests whether the estimated
window caught it.

## Roles and login

Three dashboards, each behind a login. The API checks the role on every request, so hiding a screen is
not the only protection.

| Role | Sees and does | Demo login |
| --- | --- | --- |
| Citizen | Report an issue (photo, text, map pin); **My complaints** with progress and whether the spot has failed before. Cannot see priorities, costs or other people's complaints. | `citizen001` / `citizen@123` |
| Ward engineer | **Work queue** (map, ranked assets, full asset history, AI briefing, patch-or-replace), **Review queue** for uncertain matches, **Patterns**, search | `engineer` / `engineer@123` |
| Commissioner | **Overview** (spend, stop-patching decision with pay-back, complaints per month, contractor accountability), read-only assets, patterns, contractors, prediction check | `commissioner` / `commissioner@123` |

- Citizens can create their own accounts; engineer and commissioner accounts are created by the city (seeded here).
- Passwords are hashed (PBKDF2-SHA256). Login returns a session token (12 hours), sent as `Authorization: Bearer <token>`.
- Demo passwords are for the prototype only.



`receive → clean → duplicate check → find nearby assets of the same type → compare text with their history → link (auto / engineer review / new asset) → store → cause tag + rescore in the background`

- Combined match score = 0.6 × location closeness + 0.4 × text similarity.
- ≥ 0.62 links automatically, 0.38–0.62 goes to engineer review, below that creates an unregistered asset.
- Settings live at the top of `backend/logic.py`.

## Design

Warm beige canvas, white / taupe / charcoal cards, yellow and coral accents, Manrope (bundled, works offline).
Each role's home has one taupe "bubble" card for its headline numbers (bubble area follows the value; zero is a
dashed outline), a dark calendar of complaints and repairs, a gauge, a pill progress bar and a ranked list.
Asset history opens in a slide-over panel. Demo users: Priya Sharma (citizen), Arjun Rao (engineer),
Meena Iyer (commissioner).

## Run it locally

You need Python 3.10+ and Node 18+.

**Backend** (terminal 1):

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python seed.py                 # creates citymemory.db with simulated data and demo accounts
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
  main.py       FastAPI endpoints (each one checks the caller's role)
  auth.py       users, password hashing, sessions, role checks
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
  src/App.jsx              login gate; picks the dashboard for the user's role
  src/ui.jsx               design-system pieces: shell + sidebar, bubble card, calendar, gauge, progress, drawer
  src/index.css            design tokens and all styles
  src/pages/               Login, CitizenApp, EngineerApp, CommissionerApp, staff.jsx (shared lists, map, drawer)
  src/components/          map, asset detail, report form, patterns, review/contractor/prediction views
```

## Key API endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/api/auth/login` · `/api/auth/register` · `/api/auth/logout` | Login, citizen sign-up, logout |
| GET | `/api/me/complaints` | Citizen: own complaints with status |
| GET | `/api/overview` | Commissioner: ward spend and decisions |
| POST | `/api/assets/{id}/work-orders` | Engineer: assign a repair (contractor, type, target date) |
| POST | `/api/work-orders/{id}/start` · `/complete` | Engineer: mark work started; mark fixed with cost and after photo |
| GET | `/api/work-orders?status=open` | Repair jobs, overdue first |
| POST | `/api/complaints` | Submit a complaint (form data: text, category, lat, lng, reporter?, photo?) |
| GET | `/api/priority` | Ranked assets |
| GET | `/api/assets/{id}` | Timeline, priority breakdown, cause, cost comparison, failure window |
| GET | `/api/patterns` | Recurring complaint patterns across the ward |
| GET | `/api/assets/{id}/ai-summary` | AI briefing for one asset |
| POST | `/api/ai/retag` | Re-tag all causes with the LLM |
| GET | `/api/timeline?start=&end=&types=&kinds=&asset_id=&q=&sort=` | Ward timeline: filtered, searchable history of complaints, repairs and repair jobs |
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
`python seed.py` rebuilds the demo data but keeps cached AI answers and user accounts.

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
