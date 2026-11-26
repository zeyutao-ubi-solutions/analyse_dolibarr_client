"""Activity scorer: from a company's LinkedIn description, how well its activity fits our target segments.

Reframed 2026-11-23: score any company on *what it does*, never on country. Two separate outputs
(decided 2026-11-24):

- ``fit``: a ranking score for "the company is an end user in one of the target segments", plus
  the segment. ``label`` is ``prospect`` when ``fit >= 0.65``, else the likeliest non-prospect label;
- ``priority``: a sales ordering. ``low`` for prospects under 51 employees or in a low-priority
  segment (research labs). Low priority is never an exclusion.

Model: multilingual-e5-large vector of the description + a one-hot of the LinkedIn industry -> one
multinomial logistic regression over
44 classes: 37 segments of ``docs/segments/segments_v2.csv`` plus 7 non-prospect labels. ``fit`` is
the summed probability of the segment classes. Labels come from a 3-model vote (gpt-6.2-sol,
Sonnet, Haiku) on name, industry, size and description; only rows where all three agree are used.

Country must not reach the score (decision 2026-11-20/23). Two safeguards, both from the review of
2026-11-24:

- LinkedIn's template description ("X is a ... company based out of <address>, <city>, <country>")
  is cut before "based out of", and such pages are flagged ``thin_text``;
- training rows are weighted so the prospect share is the same in every description language,
  otherwise the model learns "French text -> prospect" (our prospect lists are mostly French).
  Language only sets these weights; it is never a feature.

Each score carries the three most similar labelled training companies of its segment (an exact
copy of the scored text is skipped), so sales can see why a company was put there. Model files are
plain arrays (no pickle); vectors are cached by sha256(model + text).

    python -m analyse_dolibarr_client.activity train --labels .../labels.csv --out data/models/activity/<v>
    python -m analyse_dolibarr_client.activity score --model data/models/activity/<v> --input companies.csv --output scores.csv
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
PROSPECT_THRESHOLD = 0.65  # keeps OOF prospect recall ~0.95 (0.5 let 43% of "other" through; 0.7 once "other" was split)
INDUSTRY_WEIGHT = 0.3  # value of the LinkedIn-industry one-hot next to the unit-length text vector
INDUSTRY_MIN_ROWS = 5  # industries seen fewer times in training get no feature
INDUSTRY_DROPOUT_WEIGHT = 0.5  # weight of the industry-blanked copy of each training row
DEFAULT_C = 30.0
N_EXAMPLES = 3
SAME_TEXT_SIMILARITY = 0.999
MIN_LANGUAGE_ROWS = 30
# "other" split by a second 3-model vote (2026-11-25): companies of a target industry that do not run it are
# the commonest false prospects, so the model gets them as explicit classes.
OTHER_SUBTYPES = ("sector_body", "investor_owner", "sector_vendor", "single_small_site", "unrelated")
NON_PROSPECT = ("other", "consulting", "supplier", "competitor", "school", "media", "insufficient_info") + tuple(
    f"other_{t}" for t in OTHER_SUBTYPES)
DEFAULT_SEGMENTS = Path("docs/segments/segments_v2.csv")
DEFAULT_WEIGHTS_DIR = Path("data/models/fastembed")
DEFAULT_CACHE = Path("data/models/embedding_cache/activity_e5large.npz")
PROBE_TEXT = TEXT_PREFIX + "Industrial laundry washing hospital linen and workwear for hotels."

_TEMPLATE_ADDRESS = re.compile(  # "<name> is a <industry> company based out of <address>"
    r"^\s*(?P<name>[^\n]{1,150}?)\s+is an?\s+(?P<industry>[^.\n]{0,80}?)\s*company\s+based out of\b.*$",
    re.IGNORECASE | re.DOTALL,
)
_TEMPLATE_SHORT = re.compile(  # "<name> is a <industry> company." alone, the name without a sentence break
    r"^\s*(?P<name>(?:(?!\.\s)[^\n]){1,150}?)\s+is an?\s+(?P<industry>[^.\n]{0,80}?)\s*company[.\s]*$",
    re.IGNORECASE,
)


def _template_match(d: str):
    return _TEMPLATE_ADDRESS.match(d) or (len(d.split()) < THIN_TEXT_WORDS and _TEMPLATE_SHORT.match(d)) or None
_STOPWORDS = {
    "en": {"the", "and", "of", "to", "we", "our", "for", "with", "is", "in", "a"},
    "fr": {"de", "la", "le", "et", "les", "des", "du", "pour", "nous", "une", "est", "en"},
    "es": {"de", "la", "el", "y", "los", "las", "para", "con", "una", "somos", "en"},
    "de": {"und", "der", "die", "das", "für", "mit", "wir", "ist", "von", "ein", "eine"},
    "it": {"di", "il", "e", "la", "per", "con", "una", "che", "della", "siamo"},
    "nl": {"de", "het", "en", "van", "een", "voor", "met", "wij", "zijn", "onze"},
    "pl": {"i", "w", "na", "z", "do", "się", "jest", "oraz", "dla", "firma"},
    "pt": {"de", "e", "o", "a", "para", "com", "uma", "os", "das", "somos"},
}


# ------------------------------------------------------------------------------ text


def _clean(v) -> str:
    if v is None or v is pd.NA or (isinstance(v, float) and math.isnan(v)):
        return ""
    return str(v)


def is_template(description) -> bool:
    """LinkedIn's auto-generated page text and nothing else: "<name> is a <industry> company
    [based out of <address>, <city>, <country>]"."""
    return _template_match(_clean(description)) is not None


def clean_description(description) -> str:
    """The description, except that a template page becomes a neutral sentence with its LinkedIn
    industry only: the name, address and country are all country proxies (review 2026-11-25)."""
    d = _clean(description)
    if not is_template(d):
        return d
    industry = re.sub(r"\s+", " ", _template_match(d).group("industry")).strip()
    return f"This organisation is a {industry} company." if industry else "This organisation is a company."


def template_industry(description) -> str:
    """LinkedIn industry named in a template page ("" if none or not a template)."""
    m = _template_match(_clean(description))
    return re.sub(r"\s+", " ", m.group("industry")).strip().lower() if m else ""


# Older LinkedIn industry names still used on template pages -> current names in segments_v2.csv.
INDUSTRY_ALIASES = {
    "textiles": "textile manufacturing",
    "transportation/trucking/railroad": "truck transportation",
    "package/freight delivery": "freight and package transportation",
    "machinery": "machinery manufacturing",
    "electrical/electronic manufacturing": "appliances, electrical, and electronics manufacturing",
    "individual & family services": "individual and family services",
    "hospital & health care": "hospitals and health care",
    "food & beverages": "food & beverages",
    "logistics and supply chain": "transportation, logistics, supply chain and storage",
    "warehousing": "warehousing and storage",
    "automotive": "motor vehicle manufacturing",
    "aviation & aerospace": "aviation & aerospace",
    "airlines/aviation": "airlines and aviation",
    "events services": "events services",
    "leisure, travel & tourism": "hospitality",
    "environmental services": "environmental services",
    "public safety": "public safety",
    "museums and institutions": "museums, historical sites, and zoos",
    "mechanical or industrial engineering": "industrial machinery manufacturing",
    "building materials": "building materials",
    "chemicals": "chemical manufacturing",
    "plastics": "plastics manufacturing",
    "pharmaceuticals": "pharmaceutical manufacturing",
    "medical devices": "medical equipment manufacturing",
    "packaging and containers": "packaging and containers manufacturing",
    "furniture": "furniture and home furnishings manufacturing",
    "printing": "printing services",
    "telecommunications": "telecommunications",
    "farming": "farming",
    "dairy": "food production",
    "libraries": "museums, historical sites, and zoos",
    "wine and spirits": "beverage manufacturing",
    "railroad manufacture": "manufacturing",
    "medical practice": "medical practices",
    "civic & social organization": "civic and social organizations",
    "renewables & environment": "renewable energy power generation",
    "cosmetics": "personal care product manufacturing",
    "matériaux de construction": "building materials",
}


def industry_candidates(segments: pd.DataFrame) -> dict[str, list[str]]:
    """LinkedIn industry (lower case) -> segments listing it in ``linkedin_industries``, in file order."""
    out: dict[str, list[str]] = {}
    for sid, inds in zip(segments["segment_id"], segments.get("linkedin_industries", pd.Series(dtype=str)).fillna("")):
        for ind in inds.split(";"):
            if ind.strip():
                out.setdefault(ind.strip().lower(), []).append(sid)
    for old, new in INDUSTRY_ALIASES.items():
        if new in out:
            out.setdefault(old, list(out[new]))
    return out


def normalize_industry(industry) -> str:
    """LinkedIn industry, lower case, older names mapped to the current taxonomy."""
    v = re.sub(r"\s+", " ", _clean(industry)).strip().lower()
    return INDUSTRY_ALIASES.get(v, v)


def industry_features(industries: Sequence, vocab: Sequence[str], weight: float = INDUSTRY_WEIGHT) -> np.ndarray:
    """One-hot of the LinkedIn industry over ``vocab`` (all zeros when missing or unseen)."""
    idx = {v: i for i, v in enumerate(vocab)}
    M = np.zeros((len(industries), len(vocab)), dtype=np.float32)
    for r, v in enumerate(industries):
        j = idx.get(normalize_industry(v))
        if j is not None:
            M[r, j] = weight
    return M


def company_text(description) -> str:
    """The exact passage the model embeds, in training and in scoring."""
    return TEXT_PREFIX + clean_description(description)[:MAX_DESCRIPTION_CHARS]


def thin_text(description) -> bool:
    """Too little text to trust the score: a template page or fewer than 20 words."""
    return is_template(description) or len(clean_description(description).split()) < THIN_TEXT_WORDS


def description_language(description) -> str:
    """Rough language by stopwords; only used to balance training weights, never as a feature."""
    words = re.findall(r"[^\W\d_]+", clean_description(description).lower())
    scores = {lang: sum(w in sw for w in words) for lang, sw in _STOPWORDS.items()}
    best = max(scores, key=scores.get)
    ranked = sorted(scores.values(), reverse=True)
    return best if ranked[0] >= 3 and ranked[0] > 1.2 * ranked[1] else "unknown"


# ------------------------------------------------------------------------------ embeddings


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
        if not texts:
            return np.zeros((0, 0), dtype=np.float32)
        order = np.argsort([len(t) for t in texts])  # similar lengths per batch: much faster
        vecs = np.asarray(list(self._model.embed([texts[i] for i in order], batch_size=self._batch)), dtype=np.float32)
        out = np.zeros_like(vecs)
        out[order] = vecs
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


class EmbeddingCache:
    """Vectors keyed by sha256(model name + text); one npz per model. Missing texts are embedded."""

    def __init__(self, path: Path | None, model_name: str):
        self.path, self.model_name = path, model_name
        self.vecs: dict[str, np.ndarray] = {}
        if path and path.exists():
            with np.load(path, allow_pickle=False) as z:
                if str(z["model_name"]) != model_name:
                    raise ValueError(f"{path} holds vectors of {z['model_name']}, not {model_name}")
                self.vecs = dict(zip(z["keys"].tolist(), z["vectors"]))

    def key(self, text: str) -> str:
        return hashlib.sha256(f"{self.model_name}\n{text}".encode()).hexdigest()

    def get(self, texts: Sequence[str], embedder: Embedder | None) -> np.ndarray:
        keys = [self.key(t) for t in texts]
        missing = sorted({k: t for k, t in zip(keys, texts) if k not in self.vecs}.items())
        if missing:
            if embedder is None:
                raise KeyError(f"{len(missing)} texts are not in the cache and no embedder was given")
            if embedder.name != self.model_name:
                raise ValueError(f"embedder {embedder.name} does not match cache model {self.model_name}")
            new = embedder.embed([t for _, t in missing])
            self.vecs.update({k: v.astype(np.float32) for (k, _), v in zip(missing, new)})
            self.save()
        return np.stack([self.vecs[k] for k in keys]) if keys else np.zeros((0, 0), dtype=np.float32)

    def save(self) -> None:
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        keys = list(self.vecs)
        np.savez(self.path, model_name=np.array(self.model_name), keys=np.array(keys),
                 vectors=np.stack([self.vecs[k] for k in keys]).astype(np.float32))


# ------------------------------------------------------------------------------ size and priority


def _int(s: str) -> int | None:
    s = re.sub(r"(?<=\d)[,.\s ](?=\d{3}\b)", "", s.strip())  # 1,001 / 1.001 / 1 001 -> 1001
    m = re.fullmatch(r"(\d+)(?:\.\d+)?", s)
    return int(m.group(1)) if m else None


def employee_lower_bound(count=None, count_range=None) -> tuple[int | None, str]:
    """Lower bound of headcount and where it came from: ``range``, ``count`` or ``unknown``.

    The declared LinkedIn range is the real size. ``employee_count`` counts members linked to the
    page, so it only proves "at least n". Accepts ``51-200``, ``1,001-5,000``, ``51_200``,
    ``10,001+``, ``201_plus``, ``{'start': 51, 'end': 200}`` or a number.
    """
    r = re.sub(r"(?<=\d)[,.\s ](?=\d{3}\b)", "", _clean(count_range))
    m = re.search(r"\d+", r)
    if m:
        return int(m.group()), "range"
    c = _clean(count).strip()
    if c:
        band = re.match(r"([\d,. ]+?)\s*(?:[-_]\s*[\d,. ]+|[-_]?plus|\+)$", c)  # server exports put the band here
        if band and _int(band.group(1)) is not None:
            return _int(band.group(1)), "range"
        n = _int(c)
        if n is not None:
            return n, "count"
    return None, "unknown"


def size_evidence(count=None, count_range=None) -> tuple[int | None, int | None]:
    """(lower bound of the declared range, LinkedIn member count); either may be None.

    A band written into the count column (server exports: ``51_200``) counts as a declared range.
    """
    n, src = employee_lower_bound(count, count_range)
    if src == "range" and _clean(count_range).strip():
        m = employee_lower_bound(count, None)
        return n, (m[0] if m[1] == "count" else None)
    if src == "range":
        return n, None
    return None, (n if src == "count" else None)


def priority(label: str, segment: str, segment_priority: dict[str, str], declared: int | None,
             members: int | None) -> tuple[str, str]:
    """``low`` / ``normal`` / ``unknown_size`` plus a reason in Chinese / French. Never an exclusion.

    - segment priority applies to prospects only (research labs);
    - the declared LinkedIn range decides, except that 51+ linked members prove the range is stale;
    - members are a lower bound: under 51 without a range says nothing (``unknown_size``).
    """
    big = SMALL_COMPANY_EMPLOYEES
    if label == "prospect" and segment_priority.get(segment) == "low":
        return "low", f"low-priority segment ({segment}) / segment à priorité basse"
    if declared is not None and declared < big:
        if members is not None and members >= big:
            return "normal", f"declared employee range <{big}, but LinkedIn already has {members} members / tranche < {big} mais {members} membres LinkedIn"
        return "low", f"declared employee range <{big} employees / moins de {big} salariés (tranche déclarée)"
    if declared is not None:
        return "normal", f"declared employee range ≥{big} employees / au moins {big} salariés (tranche déclarée)"
    if members is not None and members >= big:
        return "normal", f"no declared employee range, LinkedIn members ≥{members} / pas de tranche, au moins {members} membres"
    if members is not None:
        return "unknown_size", f"no declared employee range, only {members} LinkedIn members / pas de tranche, seulement {members} membres"
    return "unknown_size", "no size information / taille inconnue"


# ------------------------------------------------------------------------------ training data


def linkedin_slug(url) -> str | None:
    m = re.search(r"linkedin\.com/company/([^/?#]+)", _clean(url), re.IGNORECASE)
    return m.group(1).lower() if m else None


def training_rows(labels: pd.DataFrame) -> pd.DataFrame:
    """Clean training rows with the flat target ``y`` (segment for prospects, else the label).

    Drops rows whose LinkedIn page or description also appears in the evaluation split
    (customers stay evaluation-only), keeps one row per identical description, and drops template
    pages (their vote leaned on the company name, which the model must not see).
    """
    clean = labels["clean"].astype(str).str.lower().eq("true")
    df = labels[labels["split"].eq("train") & clean].copy()
    prospect = df["cons_label"].eq("prospect")
    if (prospect & df["cons_segment"].fillna("").eq("")).any():
        raise ValueError("clean prospect rows without a segment")
    # insufficient_info had 6 clean rows: too few to learn; thin and template pages are flagged separately
    df["y"] = np.where(prospect, df["cons_segment"], df["cons_label"].replace({"insufficient_info": "other"}))
    if "other_subtype" in df.columns:  # majority of the 3-model sub-label vote, see OTHER_SUBTYPES
        sub = df["other_subtype"].where(df["other_subtype"].isin(OTHER_SUBTYPES))
        df["y"] = np.where(df["y"].eq("other") & sub.notna(), "other_" + sub.fillna(""), df["y"])
    ev = labels[~labels["split"].eq("train")]
    if "linkedin_company_url" in labels.columns:
        ev_slugs = set(ev["linkedin_company_url"].map(linkedin_slug)) - {None}
        df = df[~df["linkedin_company_url"].map(linkedin_slug).isin(ev_slugs)]
    ev_text = set(ev["description"].map(clean_description)) - {""}
    text = df["description"].map(clean_description)
    df = df[~text.isin(ev_text)]
    df = df[~df["description"].map(clean_description).duplicated()]
    df = df[~df["description"].map(is_template)]  # labels there leaned on the name; the model never sees it
    return df.reset_index(drop=True)


def training_weights(y: Sequence[str], languages: Sequence[str]) -> np.ndarray:
    """Balanced class weights x a language factor that gives every language the global prospect share."""
    y = np.asarray(y, dtype=str)
    lang = np.asarray(languages, dtype=str)
    classes, counts = np.unique(y, return_counts=True)
    w = (len(y) / (len(classes) * counts))[np.searchsorted(classes, y)]
    isp = ~np.isin(y, NON_PROSPECT)
    p = isp.mean()
    for lg in np.unique(lang):
        m = lang == lg
        share = isp[m].mean()
        if m.sum() < MIN_LANGUAGE_ROWS or share in (0.0, 1.0):
            continue
        w[m & isp] *= p / share
        w[m & ~isp] *= (1 - p) / (1 - share)
    return w * len(y) / w.sum()


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
    probe_vector: np.ndarray  # vector of PROBE_TEXT, to check the scoring embedder
    industry_vocab: np.ndarray = field(default_factory=lambda: np.array([], dtype=str))
    meta: dict = field(default_factory=dict)

    @property
    def threshold(self) -> float:
        return float(self.meta.get("prospect_threshold", PROSPECT_THRESHOLD))

    def features(self, X: np.ndarray, industries: Sequence | None = None) -> np.ndarray:
        """Text vectors plus the LinkedIn-industry one-hot (zeros when no industry is given)."""
        if not len(self.industry_vocab):
            return X
        ind = industries if industries is not None else [None] * len(X)
        return np.hstack([X, industry_features(ind, self.industry_vocab, self.meta.get("industry_weight", INDUSTRY_WEIGHT))])

    def predict_proba(self, X: np.ndarray, industries: Sequence | None = None) -> np.ndarray:
        """``X``: text vectors (the industry columns are added here)."""
        return _softmax(self.features(X, industries) @ self.coef.T + self.intercept)

    def save(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            directory / "model.npz", classes=self.classes.astype(str), coef=self.coef, intercept=self.intercept,
            ref_vectors=self.ref_vectors.astype(np.float16), ref_names=self.ref_names.astype(str),
            ref_segments=self.ref_segments.astype(str), probe_vector=self.probe_vector.astype(np.float32),
            industry_vocab=self.industry_vocab.astype(str),
        )
        (directory / "meta.json").write_text(json.dumps(self.meta, indent=2, ensure_ascii=False) + "\n")

    @classmethod
    def load(cls, directory: Path) -> "ActivityModel":
        z = np.load(directory / "model.npz", allow_pickle=False)
        meta = json.loads((directory / "meta.json").read_text())
        vocab = z["industry_vocab"] if "industry_vocab" in z.files else np.array([], dtype=str)
        return cls(z["classes"], z["coef"], z["intercept"], z["ref_vectors"].astype(np.float32),
                   z["ref_names"], z["ref_segments"], z["probe_vector"], vocab, meta)

    def check_embedder(self, embedder: Embedder) -> None:
        if embedder.name != self.meta.get("embedding_model"):
            raise ValueError(f"model was trained on {self.meta.get('embedding_model')} vectors, not {embedder.name}")
        cos = float(embedder.embed([PROBE_TEXT])[0] @ self.probe_vector)
        if cos < 0.99:
            raise ValueError(f"embedder output differs from training (probe cosine {cos:.3f})")


def fit(X: np.ndarray, y: Sequence[str], names: Sequence[str], probe_vector: np.ndarray, C: float = DEFAULT_C,
        sample_weight: np.ndarray | None = None, meta: dict | None = None,
        industries: Sequence | None = None) -> ActivityModel:
    """Multinomial logistic regression on text vectors (+ LinkedIn-industry one-hot when ``industries``).

    With industries, every training row that has one is added a second time with the industry blanked
    (weight ``INDUSTRY_DROPOUT_WEIGHT``), so pages without an industry are scored sensibly too.
    """
    from sklearn.linear_model import LogisticRegression

    y = np.asarray(y, dtype=str)
    if len(np.unique(y)) < 3:
        raise ValueError("need at least 3 classes (binary coef_ has one row and breaks the softmax)")
    w = np.asarray(sample_weight, dtype=float) if sample_weight is not None else training_weights(y, ["all"] * len(y))
    vocab = np.array([], dtype=str)
    Xf, yf, wf = X, y, w
    if industries is not None:
        norm = pd.Series([normalize_industry(v) for v in industries])
        counts = norm[norm.ne("")].value_counts()
        vocab = np.array(sorted(counts[counts >= INDUSTRY_MIN_ROWS].index), dtype=str)
        F = industry_features(list(industries), vocab)
        has = F.any(axis=1)
        Xf = np.vstack([np.hstack([X, F]), np.hstack([X[has], np.zeros_like(F[has])])])
        yf = np.concatenate([y, y[has]])
        wf = np.concatenate([w, w[has] * INDUSTRY_DROPOUT_WEIGHT])
    lr = LogisticRegression(C=C, max_iter=4000).fit(Xf, yf, sample_weight=wf)
    ref = ~np.isin(y, NON_PROSPECT)
    return ActivityModel(
        classes=lr.classes_.astype(str), coef=lr.coef_.astype(np.float32), intercept=lr.intercept_.astype(np.float32),
        ref_vectors=X[ref], ref_names=np.asarray(names, dtype=str)[ref], ref_segments=y[ref],
        probe_vector=np.asarray(probe_vector, dtype=np.float32), industry_vocab=vocab,
        meta=dict(meta or {}, C=C, prospect_threshold=PROSPECT_THRESHOLD, industry_weight=INDUSTRY_WEIGHT,
                  industry_dropout_weight=INDUSTRY_DROPOUT_WEIGHT, n_industries=int(len(vocab))),
    )


def decide(P: np.ndarray, classes: np.ndarray, threshold: float = PROSPECT_THRESHOLD) -> dict[str, np.ndarray]:
    """From class probabilities: fit, label, top-2 segments with their probability given prospect."""
    seg_mask = ~np.isin(classes, NON_PROSPECT)
    seg_classes, Ps, Pn = classes[seg_mask], P[:, seg_mask], P[:, ~seg_mask]
    fit_ = Ps.sum(axis=1)
    cond = Ps / np.where(fit_ > 0, fit_, 1)[:, None]
    top = np.argsort(-cond, axis=1)[:, :2]
    rows = np.arange(len(P))
    non = classes[~seg_mask]
    best_non = non[Pn.argmax(axis=1)] if Pn.shape[1] else np.full(len(P), "other")
    return {
        "fit": fit_,
        "label": np.where(fit_ >= threshold, "prospect", best_non),
        "segment": seg_classes[top[:, 0]],
        "segment_prob": cond[rows, top[:, 0]],
        "segment_2": seg_classes[top[:, 1]],
        "segment_2_prob": cond[rows, top[:, 1]],
        "top_non_prospect": best_non,
        "top_non_prospect_prob": Pn.max(axis=1) if Pn.shape[1] else np.zeros(len(P)),
    }


def score_vectors(model: ActivityModel, X: np.ndarray, industries: Sequence | None = None) -> pd.DataFrame:
    d = decide(model.predict_proba(X, industries), model.classes, model.threshold)
    examples = []
    for i in range(len(X)):
        in_seg = np.flatnonzero(model.ref_segments == d["segment"][i])
        sims = model.ref_vectors[in_seg] @ X[i]
        keep = [j for j in np.argsort(-sims) if sims[j] < SAME_TEXT_SIMILARITY][:N_EXAMPLES]
        examples.append("; ".join(f"{model.ref_names[in_seg[j]]} ({sims[j]:.2f})" for j in keep))
    out = pd.DataFrame({k: v for k, v in d.items()})
    for k in ("fit", "segment_prob", "segment_2_prob", "top_non_prospect_prob"):
        out[k] = out[k].astype(float).round(4)
    out["similar_training_companies"] = examples
    return out


def _first(df: pd.DataFrame, *cols: str) -> pd.Series:
    out = pd.Series([None] * len(df), index=df.index, dtype=object)
    for c in cols:
        if c in df.columns:
            out = out.where(out.notna() & out.astype(str).ne(""), df[c])
    return out


def score_companies(model: ActivityModel, companies: pd.DataFrame, embedder: Embedder, segments: pd.DataFrame,
                    cache: EmbeddingCache | None = None) -> pd.DataFrame:
    """Score a LinkedIn company table. Needs ``description``; uses ``employee_count_range`` then
    ``employee_count`` / ``employees`` for priority. Country columns are never read."""
    model.check_embedder(embedder)
    desc = companies["description"] if "description" in companies.columns else pd.Series("", index=companies.index)
    texts = [company_text(d) for d in desc]
    X = (cache or EmbeddingCache(None, embedder.name)).get(texts, embedder)
    s = score_vectors(model, X, list(_first(companies, "industry")))
    s.index = companies.index
    seg_prio = dict(zip(segments["segment_id"], segments["segment_priority"].fillna("normal")))
    names = dict(zip(segments["segment_id"], segments["name_en"]))
    template = desc.map(is_template).values
    # Template pages: the model only sees "This organisation is a <industry> company", too little to pick a
    # segment. Candidates come from the LinkedIn industry -> segment table instead; fit stays as a rough hint.
    cand = industry_candidates(segments)
    for i in np.flatnonzero(template):
        ind = template_industry(desc.iloc[i])
        c = cand.get(ind, [])
        s.iat[i, s.columns.get_loc("label")] = "template_only"
        s.iat[i, s.columns.get_loc("segment")] = c[0] if c else ""
        s.iat[i, s.columns.get_loc("segment_2")] = c[1] if len(c) > 1 else ""
        for col in ("segment_prob", "segment_2_prob"):
            s.iat[i, s.columns.get_loc(col)] = np.nan
        if not ind:
            s.iat[i, s.columns.get_loc("fit")] = np.nan
    s.loc[~s["label"].eq("prospect"), "similar_training_companies"] = ""
    s.insert(3, "segment_name_en", s["segment"].map(names))
    ranges = _first(companies, "employee_count_range")
    sizes = [size_evidence(c, r) for c, r in zip(_first(companies, "employee_count", "employees"), ranges)]
    pr = [priority(lab, seg, seg_prio, d, m) for lab, seg, (d, m) in zip(s["label"], s["segment"], sizes)]
    s["declared_range_lower"] = [d for d, _ in sizes]
    s["linkedin_members"] = [m for _, m in sizes]
    s["priority"] = [p for p, _ in pr]
    s["priority_reason"] = [r for _, r in pr]
    s["template_text"] = template
    s["thin_text"] = desc.map(thin_text).values
    return add_sales_columns(s, segments)


SALES_LABELS = {"prospect": "prospect", "competitor": "competitor", "template_only": "template_only"}


def add_sales_columns(s: pd.DataFrame, segments: pd.DataFrame) -> pd.DataFrame:
    """``sales_label``: prospect / competitor / template_only / not_target (the fine label stays in
    ``label``), and ``category``: the segment's group in segments_v2.csv (prospects and template pages)."""
    s = s.copy()
    s["sales_label"] = s["label"].map(SALES_LABELS).fillna("not_target")
    cat = dict(zip(segments["segment_id"], segments["category"])) if "category" in segments.columns else {}
    has_seg = s["label"].isin(["prospect", "template_only"])
    s["category"] = s["segment"].map(cat).astype(object).where(has_seg, None)
    return s


# ------------------------------------------------------------------------------ CLI


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def train_from_labels(labels: pd.DataFrame, embedder: Embedder, cache: EmbeddingCache, C: float = DEFAULT_C,
                      meta: dict | None = None) -> ActivityModel:
    rows = training_rows(labels)
    X = cache.get([company_text(d) for d in rows["description"]], embedder)
    langs = rows["description"].map(description_language)
    w = training_weights(rows["y"], langs)
    probe = embedder.embed([PROBE_TEXT])[0]
    industries = list(rows["industry"]) if "industry" in rows.columns else None
    meta = dict(meta or {}, embedding_model=embedder.name, n_train=int(len(rows)),
                n_prospect=int((~rows["y"].isin(NON_PROSPECT)).sum()),
                class_counts=rows["y"].value_counts().to_dict(), language_counts=langs.value_counts().to_dict(),
                text=f"'{TEXT_PREFIX}' + description without template address, first {MAX_DESCRIPTION_CHARS} chars",
                weights="balanced classes x language factor (equal prospect share per language)",
                features="text vector + LinkedIn industry one-hot (industry-blanked copies at half weight)")
    return fit(X, rows["y"], rows["company_name"].fillna(rows["item_id"]), probe, C=C, sample_weight=w, meta=meta,
               industries=industries)


OOF_COLUMNS = ("fit", "label", "segment", "segment_prob", "segment_2", "segment_2_prob", "top_non_prospect", "top_non_prospect_prob")


def text_key(description) -> str:
    return hashlib.sha256(company_text(description).encode()).hexdigest()


def out_of_fold(labels: pd.DataFrame, embedder: Embedder, cache: EmbeddingCache, C: float = DEFAULT_C,
                folds: int = 5, seed: int = 0) -> pd.DataFrame:
    """Scores of each training row from a model fitted without it (k-fold), keyed by text.

    Training companies scored by the final model mostly repeat their own label; sales should see
    these honest scores instead.
    """
    from sklearn.model_selection import StratifiedKFold

    rows = training_rows(labels)
    X = cache.get([company_text(d) for d in rows["description"]], embedder)
    y = rows["y"].to_numpy(dtype=str)
    langs = rows["description"].map(description_language).to_numpy(dtype=str)
    classes = np.unique(y)
    strat = np.where(rows["y"].map(rows["y"].value_counts()) >= folds, y, "rare")
    P = np.zeros((len(y), len(classes)))
    probe = np.zeros(X.shape[1], dtype=np.float32)
    ind = np.asarray(rows["industry"] if "industry" in rows.columns else [None] * len(rows), dtype=object)
    for a, b in StratifiedKFold(folds, shuffle=True, random_state=seed).split(X, strat):
        m = fit(X[a], y[a], y[a], probe, C=C, sample_weight=training_weights(y[a], langs[a]), industries=list(ind[a]))
        P[np.ix_(b, np.searchsorted(classes, m.classes))] = m.predict_proba(X[b], list(ind[b]))
    d = decide(P, classes)
    out = pd.DataFrame({k: d[k] for k in OOF_COLUMNS})
    out.insert(0, "item_id", rows["item_id"].values)
    out.insert(0, "text_key", rows["description"].map(text_key).values)
    return out


def apply_out_of_fold(companies: pd.DataFrame, scores: pd.DataFrame, oof: pd.DataFrame, segments: pd.DataFrame) -> pd.DataFrame:
    """Replace the model's scores by out-of-fold ones for companies whose text was trained on."""
    s = scores.copy()
    desc = companies["description"] if "description" in companies.columns else pd.Series("", index=companies.index)
    o = oof.drop_duplicates("text_key").set_index("text_key")
    keys = desc.map(text_key)
    hit = keys.isin(o.index).values
    s["score_source"] = np.where(hit, "out_of_fold", "model")
    for c in OOF_COLUMNS:
        s.loc[hit, c] = o.loc[keys[hit], c].values
    s.loc[hit, "segment_name_en"] = s.loc[hit, "segment"].map(dict(zip(segments["segment_id"], segments["name_en"])))
    seg_prio = dict(zip(segments["segment_id"], segments["segment_priority"].fillna("normal")))
    for i in np.flatnonzero(hit):
        if s.iloc[i]["label"] not in ("prospect",):
            s.iat[i, s.columns.get_loc("similar_training_companies")] = ""
        p, r = priority(s.iloc[i]["label"], s.iloc[i]["segment"], seg_prio,
                        None if pd.isna(s.iloc[i]["declared_range_lower"]) else int(s.iloc[i]["declared_range_lower"]),
                        None if pd.isna(s.iloc[i]["linkedin_members"]) else int(s.iloc[i]["linkedin_members"]))
        s.iat[i, s.columns.get_loc("priority")], s.iat[i, s.columns.get_loc("priority_reason")] = p, r
    return add_sales_columns(s, segments)


def cmd_train(a) -> int:
    labels = pd.read_csv(a.labels, dtype=str)
    segments = pd.read_csv(a.segments, dtype=str)
    unknown = sorted(set(training_rows(labels)["y"]) - set(segments["segment_id"]) - set(NON_PROSPECT))
    if unknown:
        raise ValueError(f"labels use classes missing from {a.segments}: {unknown}")
    meta = {"created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "labels": str(a.labels), "labels_sha256": _sha256(a.labels),
            "segments": str(a.segments), "segments_sha256": _sha256(a.segments)}
    if a.eval_results and a.eval_results.exists():
        meta["eval"] = pd.read_csv(a.eval_results).to_dict("records")
    embedder = FastEmbedEmbedder(a.embedding_model, weights_dir=a.weights_dir)
    model = train_from_labels(labels, embedder, EmbeddingCache(a.cache, a.embedding_model), C=a.C, meta=meta)
    model.save(a.out)
    if a.oof_out:
        out_of_fold(labels, embedder, EmbeddingCache(a.cache, a.embedding_model), C=a.C).to_csv(a.oof_out, index=False)
        print(f"out-of-fold scores of the training rows -> {a.oof_out}")
    print(f"trained on {model.meta['n_train']} rows ({model.meta['n_prospect']} prospects, {len(model.classes)} classes) -> {a.out}")
    return 0


def cmd_score(a) -> int:
    model = ActivityModel.load(a.model)
    companies = pd.read_csv(a.input, dtype=str)
    embedder = FastEmbedEmbedder(model.meta["embedding_model"], weights_dir=a.weights_dir)
    cache = EmbeddingCache(a.cache, model.meta["embedding_model"])
    segments = pd.read_csv(a.segments, dtype=str)
    scores = score_companies(model, companies, embedder, segments, cache)
    if a.oof:
        scores = apply_out_of_fold(companies, scores, pd.read_csv(a.oof, dtype={"text_key": str}), segments)
        print(f"{(scores['score_source'] == 'out_of_fold').sum()} companies took their out-of-fold score")
    keep = [c for c in a.keep.split(",") if c in companies.columns]
    out = pd.concat([companies[keep], scores], axis=1)
    out.to_csv(a.output, index=False)
    print(f"scored {len(out)} companies -> {a.output}")
    print(out["label"].value_counts().to_string())
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--segments", type=Path, default=DEFAULT_SEGMENTS)
    common.add_argument("--weights-dir", type=Path, default=DEFAULT_WEIGHTS_DIR)
    common.add_argument("--cache", type=Path, default=DEFAULT_CACHE, help="vector cache keyed by text")
    t = sub.add_parser("train", parents=[common], help="fit the classifier on clean vote labels")
    t.add_argument("--labels", type=Path, required=True, help="labels.csv from the 3-model vote")
    t.add_argument("--embedding-model", default=EMBEDDING_MODEL)
    t.add_argument("--eval-results", type=Path, help="optional evaluation table copied into meta.json")
    t.add_argument("--C", type=float, default=DEFAULT_C)
    t.add_argument("--out", type=Path, required=True)
    t.add_argument("--oof-out", type=Path, help="also write out-of-fold scores of the training rows (CSV)")
    t.set_defaults(func=cmd_train)
    s = sub.add_parser("score", parents=[common], help="score a CSV of LinkedIn company pages")
    s.add_argument("--model", type=Path, required=True)
    s.add_argument("--input", type=Path, required=True)
    s.add_argument("--output", type=Path, required=True)
    s.add_argument("--oof", type=Path, help="out-of-fold CSV from train --oof-out: used for companies trained on")
    s.add_argument("--keep", default="unit_id,item_id,name,company_name,linkedin_url,linkedin_company_url,industry",
                   help="input columns copied to the output, comma-separated")
    s.set_defaults(func=cmd_score)
    a = p.parse_args(argv)
    return a.func(a)


if __name__ == "__main__":
    raise SystemExit(main())
