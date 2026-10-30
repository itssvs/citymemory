"""Text normalisation, embeddings and similarity.

Backends (CITYMEMORY_EMBEDDER):
  auto  (default) use sentence-transformers if installed and the model is available, else TF-IDF
  sbert           paraphrase-multilingual-MiniLM-L12-v2 (multilingual sentence embeddings)
  hash            a small hashing embedder; no download, used in tests
  tfidf           TF-IDF over character n-grams; no vectors stored

Vector backends store one embedding per complaint, so matching a new complaint only needs
one encode plus a dot product against nearby assets' stored vectors.
"""
import os
import re

import numpy as np

SBERT_MODEL = os.environ.get("CITYMEMORY_SBERT_MODEL", "paraphrase-multilingual-MiniLM-L12-v2")

_RULES = [
    (r"\bbig holes?\b|\bpot ?holes?\b|\bcraters?\b|\bpits?\b|\bholes?\b", "pothole"),
    (r"\bstreet ?(?:lights?|lamps?)\b|\blamp ?posts?\b|\blamps?\b|\bbulbs?\b|\blights?\b", "streetlight"),
    (r"\bclogg?ed\b|\bchoked\b|\bblocked\b|\bjammed\b", "blocked"),
    (r"\bover ?flow(?:ing|s|ed)?\b|\bspilling\b|\bgushing\b", "overflow"),
    (r"\bsewage\b|\bsewer\b|\bdirty water\b|\bstagnant water\b|\bwater ?logg?(?:ing|ed)\b", "waterlogging"),
    (r"\bnot working\b|\bswitched off\b|\bnot glowing\b|\bfused\b|\bgoes off\b", "notworking"),
    (r"\bflicker(?:ing|s)?\b|\bblinking\b", "flicker"),
    (r"\bcracked\b|\bcracks\b", "crack"),
]
_COMPILED = [(re.compile(p), r) for p, r in _RULES]


def normalise(text: str) -> str:
    t = (text or "").lower()
    t = re.sub(r"[^\w\s]", " ", t)
    for rx, rep in _COMPILED:
        t = rx.sub(rep, t)
    return re.sub(r"\s+", " ", t).strip()


class TextSim:
    def __init__(self, mode=None):
        mode = (mode or os.environ.get("CITYMEMORY_EMBEDDER", "auto")).lower()
        self.backend, self.model_name, self._model, self.error = "tfidf", "tfidf-char", None, None
        if mode in ("auto", "sbert"):
            try:
                from sentence_transformers import SentenceTransformer

                self._model = SentenceTransformer(SBERT_MODEL)
                self.backend, self.model_name = "sbert", SBERT_MODEL
            except Exception as exc:
                self.error = f"{type(exc).__name__}: {exc}"[:200]
                print(f"[textsim] sentence-transformers unavailable, using TF-IDF ({self.error})")
        elif mode == "hash":
            from sklearn.feature_extraction.text import HashingVectorizer

            self._model = HashingVectorizer(analyzer="char_wb", ngram_range=(3, 5), n_features=1024,
                                            alternate_sign=False, norm="l2")
            self.backend, self.model_name = "hash", "hashing-1024"

    @property
    def is_vector(self) -> bool:
        return self.backend in ("sbert", "hash")

    def encode(self, texts) -> np.ndarray:
        """L2-normalised float32 vectors, one row per text. Vector backends only."""
        texts = [t or "" for t in texts]
        if self.backend == "sbert":
            v = self._model.encode(texts, normalize_embeddings=True, batch_size=32, show_progress_bar=False)
            return np.asarray(v, dtype=np.float32)
        if self.backend == "hash":
            return self._model.transform([normalise(t) for t in texts]).toarray().astype(np.float32)
        raise RuntimeError("encode() needs a vector backend")

    @staticmethod
    def cosine(query_vec, mat) -> list:
        if mat is None or len(mat) == 0:
            return []
        sims = np.asarray(mat, dtype=np.float32) @ np.asarray(query_vec, dtype=np.float32)
        return [float(max(0.0, min(1.0, s))) for s in sims]

    def tfidf_scores(self, query_clean: str, docs_clean: list, corpus: list = None) -> list:
        if not docs_clean:
            return []
        from sklearn.feature_extraction.text import TfidfVectorizer

        vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True)
        vec.fit(list(corpus or []) + list(docs_clean) + [query_clean])
        sims = (vec.transform(list(docs_clean)) @ vec.transform([query_clean]).T).toarray().ravel()
        return [float(max(0.0, min(1.0, s))) for s in sims]

    def pair(self, a_raw: str, b_raw: str) -> float:
        """Similarity of two texts, whatever the backend."""
        if self.is_vector:
            v = self.encode([a_raw, b_raw])
            return float(max(0.0, min(1.0, v[0] @ v[1])))
        return self.tfidf_scores(normalise(a_raw), [normalise(b_raw)])[0]

    def info(self) -> dict:
        return {"backend": self.backend, "model": self.model_name, "error": self.error}


SIM = TextSim()


def to_blob(vec) -> bytes:
    return np.asarray(vec, dtype=np.float32).tobytes()


def from_blob(blob) -> np.ndarray:
    return np.frombuffer(blob, dtype=np.float32)
