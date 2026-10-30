"""Ward-wide recurring patterns: cluster ALL complaints by meaning, across assets.

Per-asset grouping (logic.incidents_for) answers "how often has this asset failed?".
This answers "which kinds of problem keep coming back, and where?", e.g. drain-overflow
complaints spread across a road, its drain and a footpath next to each other.
"""
import os
from collections import Counter
from datetime import timedelta

import numpy as np
from sklearn.cluster import AgglomerativeClustering
from sklearn.feature_extraction.text import TfidfVectorizer

import ai
import logic
from db import now, rows
from textsim import SIM

# cosine distance below which complaints join the same pattern (lower = tighter groups)
DISTANCE = {"sbert": 0.45, "hash": 0.62, "tfidf": 0.8}
MIN_SIZE = int(os.environ.get("PATTERN_MIN_SIZE", "4"))
_STOP = ["the", "and", "near", "after", "again", "very", "is", "of", "on", "at", "to", "for", "a", "in", "from",
         "with", "this", "same", "spot", "not", "has", "have", "are", "two", "every", "yesterday", "week"]


def _matrix(conn):
    if SIM.is_vector:
        logic.ensure_embeddings(conn)
        rs, mat = logic.stored_vectors(conn)
        return rs, mat
    rs = rows(conn, "SELECT id, asset_id, text, clean_text, category, created_at FROM cv")
    if not rs:
        return [], None
    vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True)
    m = vec.fit_transform([r["clean_text"] or "" for r in rs]).toarray().astype(np.float32)
    return rs, m


def _keywords(texts, k=3):
    try:
        v = TfidfVectorizer(stop_words=_STOP, ngram_range=(1, 1), token_pattern=r"(?u)\b[^\W\d_]{3,}\b")
        m = v.fit_transform(texts)
        scores = np.asarray(m.sum(axis=0)).ravel()
        terms = v.get_feature_names_out()
        return [terms[i] for i in scores.argsort()[::-1][:k]]
    except ValueError:
        return []


def find_patterns(conn, use_llm=True):
    rs, mat = _matrix(conn)
    if mat is None or len(rs) < MIN_SIZE:
        return {"patterns": [], "method": SIM.backend}
    model = AgglomerativeClustering(n_clusters=None, metric="cosine", linkage="average",
                                    distance_threshold=DISTANCE[SIM.backend])
    labels = model.fit_predict(mat)
    assets = {a["asset_id"]: a for a in rows(conn, "SELECT * FROM assets")}
    t = now()
    out = []
    for lab in set(labels):
        idx = np.where(labels == lab)[0]
        if len(idx) < MIN_SIZE:
            continue
        members = [rs[i] for i in idx]
        centroid = mat[idx].mean(axis=0)
        order = idx[np.argsort(-(mat[idx] @ centroid))]
        examples = []
        for i in order:  # distinct, most typical texts first
            if rs[i]["text"] not in examples:
                examples.append(rs[i]["text"])
            if len(examples) == 4:
                break
        per_asset = Counter(m["asset_id"] for m in members)
        locs = [(assets[a]["lat"], assets[a]["lng"]) for a in per_asset if a in assets]
        spread = max((logic.haversine_m(*p, *q) for p in locs for q in locs), default=0)
        dates = sorted(m["created_at"] for m in members)
        recent = sum(1 for m in members if logic.parse(m["created_at"]) >= t - timedelta(days=90))
        before = sum(1 for m in members if t - timedelta(days=180) <= logic.parse(m["created_at"]) < t - timedelta(days=90))
        kw = _keywords([m["clean_text"] or "" for m in members])
        fallback = (", ".join(kw).capitalize()) if kw else "Similar complaints"
        if use_llm:
            label, desc, label_source = ai.pattern_label(conn, examples, fallback)
        else:
            label, desc, label_source = fallback, "", "keywords"
        cats = Counter(m["category"] for m in members)
        out.append({
            "id": int(lab),
            "label": label,
            "description": desc,
            "label_source": label_source,
            "size": len(members),
            "categories": dict(cats),
            "cross_type": len(cats) > 1,
            "assets": [{"asset_id": a, "name": assets[a]["name"] if a in assets else a, "complaints": n,
                        "lat": assets[a]["lat"] if a in assets else None, "lng": assets[a]["lng"] if a in assets else None}
                       for a, n in per_asset.most_common()],
            "spread_m": round(spread),
            "first": dates[0], "last": dates[-1],
            "last_90_days": recent, "previous_90_days": before,
            "trend": "rising" if recent > before else "falling" if recent < before else "steady",
            "examples": examples,
            "keywords": kw,
        })
    out.sort(key=lambda p: (len(p["assets"]) > 1, p["last_90_days"], p["size"]), reverse=True)
    return {"patterns": out, "method": SIM.backend, "distance_threshold": DISTANCE[SIM.backend], "min_size": MIN_SIZE}
