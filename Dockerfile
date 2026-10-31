# CityMemory: one container that serves the website and the API.
# Works on Hugging Face Spaces (Docker SDK, port 7860) and on any Docker host.

# ---- 1. build the website ----
FROM node:22-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- 2. run the API, which also serves the built website ----
FROM python:3.12-slim
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/home/user/.cache/huggingface \
    CITYMEMORY_EMBEDDER=sbert \
    CITYMEMORY_DEMO=1 \
    LLM_ENABLED=off
WORKDIR /home/user/app

# CPU-only PyTorch keeps the image small (no GPU libraries), then the rest
COPY --chown=user backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir --user torch --index-url https://download.pytorch.org/whl/cpu \
 && pip install --no-cache-dir --user -r backend/requirements.txt

# download the multilingual matching model once, at build time
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')"

COPY --chown=user backend/ backend/
COPY --chown=user --from=web /web/dist frontend/dist

WORKDIR /home/user/app/backend
EXPOSE 7860
# the demo database is created and seeded on first start
CMD ["sh", "-c", "python -m uvicorn main:app --host 0.0.0.0 --port ${PORT:-7860}"]
