"""Activity scorer: from a company's LinkedIn description, how well its activity fits our target segments.

Reframed 2026-11-23: score any company on *what it does*, never on country. Two separate outputs
(decided 2026-11-24):

- ``fit``: P(the company is an end user in one of the target segments), plus the segment;
- ``priority``: a sales ordering, ``low`` for companies under 51 employees or in a
  low-priority segment (research labs). Low priority is never an exclusion.

Model: multilingual-e5-large vector of the description (``passage: `` + first 1,500 characters,
exactly the text the labelling LLMs saw) -> one multinomial logistic regression over 44 classes:
37 segments of ``docs/segments/segments_v2.csv`` plus 7 non-prospect labels. ``fit`` is the summed
probability of the segment classes. Labels come from a 3-model vote (gpt-6.2-sol, Sonnet, Haiku),
keeping only rows where all three agree; see the README next to the labels.

Each score carries the three most similar labelled training companies of its segment, so sales
can see why a company was put there. The model file holds plain arrays (no pickle).

    python -m analyse_dolibarr_client.activity train --labels .../labels.csv \\
        --embeddings .../embeddings_e5large.npz --out data/models/activity/2026-11-24
    python -m analyse_dolibarr_client.activity score --model data/models/activity/2026-11-24 \\
        --input companies.csv --output scores.csv
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol, Sequence

import numpy as np
import pandas as pd

EMBEDDING_MODEL = "intfloat/multilingual-e5-large"
TEXT_PREFIX = "passage: "
MAX_DESCRIPTION_CHARS = 1500
THIN_TEXT_WORDS = 20
SMALL_COMPANY_EMPLOYEES = 51
DEFAULT_C = 30.0
N_EXAMPLES = 3
NON_PROSPECT = ("other", "consulting", "supplier", "competitor", "school", "media", "insufficient_info")
DEFAULT_SEGMENTS = Path("docs/segments/segments_v2.csv")
DEFAULT_WEIGHTS_DIR = Path("data/models/fastembed")


# ------------------------------------------------------------------------------ text and embeddings


def _clean(v) -> str:
    if v is None or v is pd.NA or (isinstance(v, float) and math.isnan(v)):
        return ""
    return str(v)


def company_text(description) -> str:
    """The exact passage the model embeds: prefix + first 1,500 characters of the description."""
    return TEXT_PREFIX + _clean(description)[:MAX_DESCRIPTION_CHARS]


def thin_text(description) -> bool:
    return len(_clean(description).split()) < THIN_TEXT_WORDS


class Embedder(Protocol):
    name: str

    def embed(self, texts: Sequence[str]) -> np.ndarray: ...


def l2_normalize(m: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(m, axis=1, keepdims=True)
    return np.divide(m, n, out=np.zeros_like(m), where=n > 0)


class FastEmbedEmbedder:
    """Local ONNX e5 via fastembed; weights are downloaded once into ``weights_dir``."""

    def __init__(self, model_name: str = EMBEDDING_MODEL, weights_dir: Path | None = DEFAULT_WEIGHTS_DIR, batch_size: int = 16):
        from fastembed import TextEmbedding

        self.name = model_name
        self._model = TextEmbedding(model_name, cache_dir=str(weights_dir) if weights_dir else None)
        self._batch = batch_size

    def embed(self, texts: Sequence[str]) -> np.ndarray:
        order = np.argsort([len(t) for t in texts])  # similar lengths per batch: much faster
        out = np.zeros((len(texts), 0), dtype=np.float32)
        vecs = list(self._model.embed([texts[i] for i in order], batch_size=self._batch))
        if vecs:
            out = np.zeros((len(texts), len(vecs[0])), dtype=np.float32)
            out[order] = np.asarray(vecs, dtype=np.float32)
        return l2_normalize(out)


class HashEmbedder:
    """Deterministic stand-in for tests: hashed bag of words, no download."""

    def __init__(self, dim: int = 64):
        self.dim, self.name = dim, f"fake-hash-{dim}"

    def embed(self, texts: Sequence[str]) -> np.ndarray:
        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        for i, t in enumerate(texts):
            for tok in re.findall(r"\w+", t.lower()):
                h = int.from_bytes(hashlib.sha1(tok.encode()).digest()[:8], "little")
                out[i, h % self.dim] += 1.0 if (h >> 32) & 1 else -1.0
        return l2_normalize(out)


# ------------------------------------------------------------------------------ size and priority


def employee_lower_bound(count=None, count_range=None) -> tuple[int | None, str]:
    """Lower bound of headcount and where it came from.

    The declared LinkedIn range wins over ``employee_count`` (the count of members linked to the
    page, which undercounts: 34% of customers under 51 against 19% by range). Accepts
    ``51-200``, ``51_200``, ``10001+``, ``201_plus``, ``{'start': 51, 'end': 200}`` or a number.
    """
    r = _clean(count_range).strip()
    if r:
        m = re.search(r"\d+", r)
        if m:
            return int(m.group()), "range"
    c = _clean(count).strip()
    if c:
        m = re.fullmatch(r"\d+(?:\.0*)?", c)
        if m:
            return int(float(c)), "count"
        m = re.match(r"(\d+)(?:[-_]\d+|[-_]?plus|\+)$", c)  # server exports put the band in this column
        if m:
            return int(m.group(1)), "range"
    return None, "unknown"


def priority(segment: str, segment_priority: dict[str, str], n_employees: int | None, size_source: str) -> tuple[str, str]:
    """``low`` / ``normal`` / ``unknown_size`` plus a short reason. Never an exclusion."""
    if segment_priority.get(segment) == "low":
        return "low", f"segment {segment} is low priority"
    if n_employees is not None and n_employees < SMALL_COMPANY_EMPLOYEES:
        return "low", f"fewer than {SMALL_COMPANY_EMPLOYEES} employees ({size_source})"
    if n_employees is None:
        return "unknown_size", "no employee count or range"
    return "normal", ""


# ------------------------------------------------------------------------------ training data


def training_rows(labels: pd.DataFrame) -> pd.DataFrame:
    """Clean training rows with the flat target ``y``: the segment for prospects, else the label."""
    clean = labels["clean"].astype(str).str.lower().eq("true")
    df = labels[labels["split"].eq("train") & clean].copy()
    prospect = df["cons_label"].eq("prospect")
    if (prospect & df["cons_segment"].fillna("").eq("")).any():
        raise ValueError("clean prospect rows without a segment")
    df["y"] = np.where(prospect, df["cons_segment"], df["cons_label"])
    return df.reset_index(drop=True)


def load_vectors(path: Path, ids: Sequence[str]) -> np.ndarray:
    z = np.load(path, allow_pickle=True)
    index = {str(k): i for i, k in enumerate(z["ids"].tolist())}
    missing = [i for i in ids if i not in index]
    if missing:
        raise KeyError(f"{len(missing)} ids have no vector in {path}, e.g. {missing[:3]}")
    return np.asarray(z["V"], dtype=np.float32)[[index[i] for i in ids]]


# ------------------------------------------------------------------------------ model


def _softmax(z: np.ndarray) -> np.ndarray:
    z = z - z.max(axis=1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=1, keepdims=True)


@dataclass
class ActivityModel:
    classes: np.ndarray
    coef: np.ndarray
    intercept: np.ndarray
    ref_vectors: np.ndarray  # training prospects, for the "similar companies" explanation
    ref_names: np.ndarray
    ref_segments: np.ndarray
    meta: dict = field(default_factory=dict)

    @property
    def segment_mask(self) -> np.ndarray:
        return ~np.isin(self.classes, NON_PROSPECT)

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        return _softmax(X @ self.coef.T + self.intercept)

    def save(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            directory / "model.npz", classes=self.classes.astype(str), coef=self.coef, intercept=self.intercept,
            ref_vectors=self.ref_vectors.astype(np.float16), ref_names=self.ref_names.astype(str),
            ref_segments=self.ref_segments.astype(str),
        )
        (directory / "meta.json").write_text(json.dumps(self.meta, indent=2, ensure_ascii=False) + "\n")

    @classmethod
    def load(cls, directory: Path) -> "ActivityModel":
        z = np.load(directory / "model.npz", allow_pickle=False)
        meta = json.loads((directory / "meta.json").read_text())
        return cls(z["classes"], z["coef"], z["intercept"], z["ref_vectors"].astype(np.float32),
                   z["ref_names"], z["ref_segments"], meta)


def fit(X: np.ndarray, y: Sequence[str], names: Sequence[str], C: float = DEFAULT_C, meta: dict | None = None) -> ActivityModel:
    from sklearn.linear_model import LogisticRegression

    y = np.asarray(y, dtype=str)
    lr = LogisticRegression(C=C, max_iter=4000, class_weight="balanced").fit(X, y)
    ref = ~np.isin(y, NON_PROSPECT)
    return ActivityModel(
        classes=lr.classes_.astype(str), coef=lr.coef_.astype(np.float32), intercept=lr.intercept_.astype(np.float32),
        ref_vectors=X[ref], ref_names=np.asarray(names, dtype=str)[ref], ref_segments=y[ref], meta=dict(meta or {}, C=C),
    )


def score_vectors(model: ActivityModel, X: np.ndarray) -> pd.DataFrame:
    """Per company: fit, label, top-2 segments (probability given prospect) and similar training companies."""
    P = model.predict_proba(X)
    seg_mask = model.segment_mask
    seg_classes, Ps = model.classes[seg_mask], P[:, seg_mask]
    fit_ = Ps.sum(axis=1)
    top = np.argsort(-Ps, axis=1)[:, :2]
    non = model.classes[~seg_mask]
    best_non = non[P[:, ~seg_mask].argmax(axis=1)] if len(non) else np.full(len(X), "other")
    best_non_p = P[:, ~seg_mask].max(axis=1) if len(non) else np.zeros(len(X))
    rows = []
    for i in range(len(X)):
        s1, s2 = seg_classes[top[i, 0]], seg_classes[top[i, 1]] if top.shape[1] > 1 else ""
        cond = Ps[i] / fit_[i] if fit_[i] > 0 else Ps[i]
        in_seg = model.ref_segments == s1
        examples = ""
        if in_seg.any():
            sims = model.ref_vectors[in_seg] @ X[i]
            best = np.argsort(-sims)[:N_EXAMPLES]
            examples = "; ".join(f"{model.ref_names[in_seg][j]} ({sims[j]:.2f})" for j in best)
        rows.append({
            "fit": round(float(fit_[i]), 4),
            "label": "prospect" if fit_[i] >= best_non_p[i] else str(best_non[i]),
            "segment": s1,
            "segment_prob": round(float(cond[top[i, 0]]), 3),
            "segment_2": s2,
            "segment_2_prob": round(float(cond[top[i, 1]]), 3) if s2 else None,
            "top_non_prospect": str(best_non[i]),
            "top_non_prospect_prob": round(float(best_non_p[i]), 3),
            "similar_training_companies": examples,
        })
    return pd.DataFrame(rows)


def _first(df: pd.DataFrame, *cols: str) -> pd.Series:
    out = pd.Series([None] * len(df), index=df.index, dtype=object)
    for c in cols:
        if c in df.columns:
            out = out.where(out.notna() & out.astype(str).ne(""), df[c])
    return out


def score_companies(model: ActivityModel, companies: pd.DataFrame, embedder: Embedder, segments: pd.DataFrame) -> pd.DataFrame:
    """Score a LinkedIn company table. Needs ``description``; uses ``employee_count_range`` /
    ``employee_count`` / ``employees`` for priority. Country columns are ignored on purpose."""
    if embedder.name != model.meta.get("embedding_model"):
        raise ValueError(f"model was trained on {model.meta.get('embedding_model')} vectors, not {embedder.name}")
    desc = companies["description"] if "description" in companies.columns else pd.Series("", index=companies.index)
    X = embedder.embed([company_text(d) for d in desc])
    s = score_vectors(model, X)
    s.index = companies.index
    seg_prio = dict(zip(segments["segment_id"], segments["segment_priority"].fillna("normal")))
    names = dict(zip(segments["segment_id"], segments["name_zh"]))
    s.insert(3, "segment_name_zh", s["segment"].map(names))
    sizes = [employee_lower_bound(c, r) for c, r in zip(_first(companies, "employee_count", "employees"),
                                                       _first(companies, "employee_count_range"))]
    pr = [priority(seg, seg_prio, n, src) for seg, (n, src) in zip(s["segment"], sizes)]
    s["employees_lower_bound"] = [n for n, _ in sizes]
    s["size_source"] = [src for _, src in sizes]
    s["priority"] = [p for p, _ in pr]
    s["priority_reason"] = [r for _, r in pr]
    s["thin_text"] = desc.map(thin_text).values
    return s


# ------------------------------------------------------------------------------ CLI


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def cmd_train(a) -> int:
    labels = pd.read_csv(a.labels, dtype=str)
    rows = training_rows(labels)
    segments = pd.read_csv(a.segments, dtype=str)
    unknown = sorted(set(rows["y"]) - set(segments["segment_id"]) - set(NON_PROSPECT))
    if unknown:
        raise ValueError(f"labels use classes missing from {a.segments}: {unknown}")
    X = load_vectors(a.embeddings, rows["item_id"].tolist())
    meta = {
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "embedding_model": a.embedding_model,
        "text": f"'{TEXT_PREFIX}' + description[:{MAX_DESCRIPTION_CHARS}]",
        "labels": str(a.labels), "labels_sha256": _sha256(a.labels),
        "segments": str(a.segments), "segments_sha256": _sha256(a.segments),
        "n_train": int(len(rows)), "n_prospect": int((~rows["y"].isin(NON_PROSPECT)).sum()),
        "class_counts": rows["y"].value_counts().to_dict(),
    }
    if a.eval_results and a.eval_results.exists():
        meta["eval"] = pd.read_csv(a.eval_results).to_dict("records")
    model = fit(X, rows["y"], rows["company_name"].fillna(rows["item_id"]), C=a.C, meta=meta)
    model.save(a.out)
    print(f"trained on {len(rows)} rows ({meta['n_prospect']} prospects, {len(model.classes)} classes) -> {a.out}")
    return 0


def cmd_score(a) -> int:
    model = ActivityModel.load(a.model)
    companies = pd.read_csv(a.input, dtype=str)
    embedder = FastEmbedEmbedder(model.meta["embedding_model"], weights_dir=a.weights_dir)
    scores = score_companies(model, companies, embedder, pd.read_csv(a.segments, dtype=str))
    keep = [c for c in a.keep.split(",") if c in companies.columns]
    out = pd.concat([companies[keep], scores], axis=1)
    out.to_csv(a.output, index=False)
    print(f"scored {len(out)} companies -> {a.output}")
    print(out["label"].value_counts().to_string())
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("train", help="fit the classifier on clean vote labels and precomputed vectors")
    t.add_argument("--labels", type=Path, required=True, help="labels.csv from the 3-model vote")
    t.add_argument("--embeddings", type=Path, required=True, help="npz with ids and V (normalised vectors)")
    t.add_argument("--segments", type=Path, default=DEFAULT_SEGMENTS)
    t.add_argument("--embedding-model", default=EMBEDDING_MODEL)
    t.add_argument("--eval-results", type=Path, help="optional train_eval_results.csv copied into meta.json")
    t.add_argument("--C", type=float, default=DEFAULT_C)
    t.add_argument("--out", type=Path, required=True)
    t.set_defaults(func=cmd_train)
    s = sub.add_parser("score", help="score a CSV of LinkedIn company pages")
    s.add_argument("--model", type=Path, required=True)
    s.add_argument("--input", type=Path, required=True)
    s.add_argument("--output", type=Path, required=True)
    s.add_argument("--segments", type=Path, default=DEFAULT_SEGMENTS)
    s.add_argument("--weights-dir", type=Path, default=DEFAULT_WEIGHTS_DIR)
    s.add_argument("--keep", default="unit_id,item_id,name,company_name,linkedin_url,linkedin_company_url,industry",
                   help="input columns copied to the output, comma-separated")
    s.set_defaults(func=cmd_score)
    a = p.parse_args(argv)
    return a.func(a)


if __name__ == "__main__":
    raise SystemExit(main())
