# edcm_metrics.py
# Canonical-ish EDCM metrics (behavioral proxies; no intent inference)
# Implements: DA, RPI, CE, GL, RM
#
# Design constraints:
# - observable outputs only
# - falsifiable proxies
# - degradation allowed; polarity must not invert
#
# 📌 hmm: If a metric can't be computed without "story", disable it.

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

WORD_RE = re.compile(r"\b[\w']+\b", re.UNICODE)


# -------------------------
# Data model
# -------------------------
@dataclass(frozen=True)
class Turn:
    idx: int
    role: str
    content: str
    ts: Optional[str] = None


@dataclass(frozen=True)
class TurnFeatures:
    idx: int
    role: str
    tokens: int
    entropy: float
    novelty: float
    repetition: float
    gl_raw: float
    rm_raw: float


@dataclass(frozen=True)
class PairFeatures:
    idx: int
    sim_to_prev: float
    novelty_delta: float
    entropy_delta: float
    rpi: Optional[float]


# -------------------------
# Tokenization + math primitives
# -------------------------
def tokenize(text: str) -> List[str]:
    if not isinstance(text, str) or not text:
        return []
    return WORD_RE.findall(text.lower())


def _freq(tokens: Sequence[str]) -> Dict[str, int]:
    d: Dict[str, int] = {}
    for t in tokens:
        d[t] = d.get(t, 0) + 1
    return d


def shannon_entropy(tokens: Sequence[str]) -> float:
    if not tokens:
        return 0.0
    f = _freq(tokens)
    n = len(tokens)
    ent = 0.0
    for c in f.values():
        p = c / n
        ent -= p * math.log(p, 2)
    return ent


def novelty_ratio(tokens: Sequence[str]) -> float:
    if not tokens:
        return 0.0
    return len(set(tokens)) / float(len(tokens))


def cosine_sim_frequencies(a: Dict[str, int], b: Dict[str, int]) -> float:
    if not a or not b:
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for k, va in a.items():
        na += va * va
        vb = b.get(k, 0)
        dot += va * vb
    for vb in b.values():
        nb += vb * vb
    if na == 0 or nb == 0:
        return 0.0
    return dot / math.sqrt(na * nb)


def _clip01(x: float) -> float:
    return 0.0 if x < 0.0 else 1.0 if x > 1.0 else x


def _squash_pos(x: float, k: float = 1.0) -> float:
    """Monotone squash for x>=0 into [0,1). Preserves polarity."""
    if x <= 0:
        return 0.0
    return 1.0 - math.exp(-k * x)


# -------------------------
# GL / RM heuristics (replaceable)
# -------------------------
_DEFAULT_GL_MARKERS = (
    "policy", "policies", "guidelines", "rules", "safety",
    "i can't", "i cannot", "i won’t", "i won't",
    "not allowed", "unable to", "as an ai",
    "i don't have", "i do not have",
    "refuse", "refusal",
)

_DEFAULT_RM_MARKERS = (
    "you decide", "up to you",
    "tell me what", "tell me exactly",
    "i can't determine", "i cannot determine",
    "clarify your intent", "what do you mean exactly",
    "you must", "you need to",
)


def grounding_load_raw(text: str, markers: Sequence[str] = _DEFAULT_GL_MARKERS) -> float:
    """
    GL raw proxy: marker hits per token.
    Monotone with "grounding/policy overhead" language.
    """
    if not isinstance(text, str) or not text:
        return 0.0
    low = text.lower()
    hits = sum(1 for m in markers if m in low)
    denom = max(1, len(tokenize(text)))
    return hits / float(denom)


def role_misassignment_raw(text: str, markers: Sequence[str] = _DEFAULT_RM_MARKERS) -> float:
    """
    RM raw proxy: marker hits per token.
    Monotone with offloading regulation/interpretation to user.
    """
    if not isinstance(text, str) or not text:
        return 0.0
    low = text.lower()
    hits = sum(1 for m in markers if m in low)
    denom = max(1, len(tokenize(text)))
    return hits / float(denom)


# -------------------------
# Correction detection for RPI
# -------------------------
_CORRECTION_TRIGGERS = (
    "actually", "correction", "that's wrong", "that is wrong",
    "not correct", "incorrect", "fix:", "edit:", "i meant", "i mean",
    "retract",
)


def is_correction_turn(content: str) -> bool:
    if not isinstance(content, str) or not content:
        return False
    low = content.lower()
    return any(t in low for t in _CORRECTION_TRIGGERS)


# -------------------------
# Feature extraction
# -------------------------
def normalize_turns(raw_turns: Iterable[Dict[str, Any]]) -> List[Turn]:
    """
    Expects dicts with keys: role, content, optional ts.
    Adds idx if missing.
    """
    out: List[Turn] = []
    for i, r in enumerate(raw_turns):
        role = str(r.get("role", "unknown"))
        content = str(r.get("content", "") or "")
        ts = r.get("ts", None)
        out.append(Turn(idx=i, role=role, content=content, ts=str(ts) if ts is not None else None))
    return out


def compute_turn_features(turns: Sequence[Turn]) -> List[TurnFeatures]:
    feats: List[TurnFeatures] = []
    for t in turns:
        toks = tokenize(t.content)
        ent = shannon_entropy(toks)
        nov = novelty_ratio(toks)
        rep = 1.0 - nov
        gl = grounding_load_raw(t.content)
        rm = role_misassignment_raw(t.content)
        feats.append(
            TurnFeatures(
                idx=t.idx,
                role=t.role,
                tokens=len(toks),
                entropy=ent,
                novelty=nov,
                repetition=rep,
                gl_raw=gl,
                rm_raw=rm,
            )
        )
    return feats


def compute_pair_features(turns: Sequence[Turn], tf: Sequence[TurnFeatures]) -> List[PairFeatures]:
    """
    Pairwise metrics:
    - sim_to_prev: cosine similarity between adjacent turns (frequency vectors)
    - novelty_delta, entropy_delta
    - rpi: only when a correction occurred and the next assistant turn arrives
    """
    out: List[PairFeatures] = []
    prev_f: Optional[Dict[str, int]] = None
    prev_ent: Optional[float] = None
    prev_nov: Optional[float] = None

    pending_correction: Optional[int] = None

    for i, t in enumerate(turns):
        toks = tokenize(t.content)
        f = _freq(toks)

        if prev_f is None:
            sim = 0.0
            nd = 0.0
            ed = 0.0
        else:
            sim = cosine_sim_frequencies(f, prev_f)
            nd = tf[i].novelty - (prev_nov if prev_nov is not None else tf[i].novelty)
            ed = tf[i].entropy - (prev_ent if prev_ent is not None else tf[i].entropy)

        rpi_val: Optional[float] = None

        if is_correction_turn(t.content):
            pending_correction = i

        if pending_correction is not None and t.role == "assistant":
            # proxy: "changed appropriately" after correction
            # Encourage dissimilarity + non-negative novelty gain.
            rpi_raw = (1.0 - sim) + max(0.0, nd)
            rpi_val = _clip01(rpi_raw)
            pending_correction = None

        out.append(
            PairFeatures(
                idx=t.idx,
                sim_to_prev=sim,
                novelty_delta=nd,
                entropy_delta=ed,
                rpi=rpi_val,
            )
        )

        prev_f = f
        prev_ent = tf[i].entropy
        prev_nov = tf[i].novelty

    return out


# -------------------------
# Windowed core signals (0..1)
# -------------------------
def signal_DA(tf: Sequence[TurnFeatures], window: int = 12) -> List[float]:
    """
    DA proxy: repetition mean + novelty decay + entropy volatility
    Polarity: higher => more accumulation/instability.
    """
    out: List[float] = []
    n = len(tf)
    w = max(1, window)
    for i in range(n):
        lo = max(0, i - w + 1)
        chunk = tf[lo : i + 1]

        rep_mean = sum(c.repetition for c in chunk) / len(chunk)

        novs = [c.novelty for c in chunk]
        nov_trend = (novs[-1] - novs[0]) if len(novs) > 1 else 0.0  # negative => decay

        ents = [c.entropy for c in chunk]
        e_mean = sum(ents) / len(ents)
        e_var = sum((e - e_mean) ** 2 for e in ents) / len(ents)
        e_vol = _squash_pos(e_var, k=1.0)  # monotone

        score = rep_mean + max(0.0, -nov_trend) + 0.5 * e_vol
        out.append(_clip01(score))
    return out


def signal_CE(tf: Sequence[TurnFeatures], window: int = 12) -> List[float]:
    """
    CE proxy: novelty adjusted by verbosity penalty.
    Polarity: higher => more 'conversion' vs repetition.
    """
    out: List[float] = []
    n = len(tf)
    w = max(1, window)
    for i in range(n):
        lo = max(0, i - w + 1)
        chunk = tf[lo : i + 1]

        nov = sum(c.novelty for c in chunk) / len(chunk)

        lens = [c.tokens for c in chunk if c.tokens > 0]
        avg_len = (sum(lens) / len(lens)) if lens else 0.0
        # penalty grows with output length but cannot invert polarity
        penalty = _squash_pos(avg_len / 120.0, k=1.0)  # 0..1
        score = nov * (1.0 - 0.35 * penalty)

        out.append(_clip01(score))
    return out


def signal_GL(tf: Sequence[TurnFeatures], window: int = 12, scale: float = 30.0) -> List[float]:
    """
    GL proxy: mean grounding marker density (scaled into 0..1).
    Polarity: higher => more overhead.
    """
    out: List[float] = []
    n = len(tf)
    w = max(1, window)
    for i in range(n):
        lo = max(0, i - w + 1)
        chunk = tf[lo : i + 1]
        raw = sum(c.gl_raw for c in chunk) / len(chunk)
        out.append(_clip01(raw * scale))
    return out


def signal_RM(tf: Sequence[TurnFeatures], window: int = 12, scale: float = 30.0) -> List[float]:
    """
    RM proxy: mean offload marker density (scaled into 0..1).
    Polarity: higher => more misassignment.
    """
    out: List[float] = []
    n = len(tf)
    w = max(1, window)
    for i in range(n):
        lo = max(0, i - w + 1)
        chunk = tf[lo : i + 1]
        raw = sum(c.rm_raw for c in chunk) / len(chunk)
        out.append(_clip01(raw * scale))
    return out


def rpi_events(pf: Sequence[PairFeatures]) -> List[Tuple[int, float]]:
    """
    Returns sparse (idx, rpi) points where RPI was computable.
    """
    return [(p.idx, float(p.rpi)) for p in pf if p.rpi is not None]


# -------------------------
# One-call convenience
# -------------------------
def compute_edcm_metrics(
    raw_turns: Iterable[Dict[str, Any]],
    *,
    window: int = 12,
    roles: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """
    Returns:
      - turns (normalized)
      - turn_features
      - pair_features
      - signals: DA, CE, GL, RM (lists aligned to filtered turns)
      - rpi_points: sparse list of (idx, rpi)
    """
    turns = normalize_turns(raw_turns)
    if roles is not None:
        role_set = set(roles)
        turns = [t for t in turns if t.role in role_set]
        # reindex for alignment
        turns = [Turn(idx=i, role=t.role, content=t.content, ts=t.ts) for i, t in enumerate(turns)]

    tf = compute_turn_features(turns)
    pf = compute_pair_features(turns, tf)

    DA = signal_DA(tf, window=window)
    CE = signal_CE(tf, window=window)
    GL = signal_GL(tf, window=window)
    RM = signal_RM(tf, window=window)
    RPI = rpi_events(pf)

    return {
        "turns": turns,
        "turn_features": tf,
        "pair_features": pf,
        "signals": {"DA": DA, "CE": CE, "GL": GL, "RM": RM},
        "rpi_points": RPI,
        "hmm": "EDCM diagnostic-only; measurable; constraint-resilient; never narrative-first.",
    }
    
    import matplotlib.pyplot as plt
import os

class EDCMAnalyzer:
    def __init__(self):
        # Placeholder weights for your specific model
        self.dissonance_weight = 1.5
        self.energy_weight = 1.0

    def run_full_audit(self, prompt, resp_a, correction, resp_b):
        """
        Main entry point. Takes the 4 text blocks and returns a results dict.
        """
        # 1. Calculate Raw Metrics (The Math)
        metrics = {
            "p_len": len(prompt.split()),
            "a_len": len(resp_a.split()),
            "c_len": len(correction.split()),
            "b_len": len(resp_b.split()),
            # Placeholder: Simple ratio of Correction vs Response A
            "dissonance_score": self._calculate_dissonance(resp_a, correction),
            "convergence_score": self._calculate_convergence(resp_a, resp_b)
        }
        
        return metrics

    def _calculate_dissonance(self, text_a, text_c):
        """
        Your custom logic goes here.
        Example: How much 'friction' (correction) was applied to the energy (text_a)?
        """
        if not text_a: return 0
        return round((len(text_c) / len(text_a)) * 100, 2)

    def _calculate_convergence(self, text_a, text_b):
        """Did Response B improve? (Placeholder logic)"""
        # In a real model, you'd compare semantic distance here
        return abs(len(text_a) - len(text_b))

    def generate_visuals(self, metrics, output_dir="."):
        """
        Generates the PDF/PNG charts using Matplotlib.
        Adapted from your 'stars.py'.
        """
        try:
            # Data preparation
            labels = ['Prompt', 'Resp A', 'Correction', 'Resp B']
            values = [metrics['p_len'], metrics['a_len'], metrics['c_len'], metrics['b_len']]

            # Setup Figure
            fig, ax = plt.subplots(figsize=(6, 4))
            bars = ax.bar(labels, values, color=['#404040', '#808080', '#D04040', '#40D040'])
            
            # Styling
            ax.set_title("EDCM Metric Visualization (N=7 Audit Lens)")
            ax.set_ylabel("Token Energy (Volume)")
            ax.set_facecolor('#f0f0f0')
            
            # Save Files
            pdf_path = os.path.join(output_dir, "FIG3_Audit.pdf")
            png_path = os.path.join(output_dir, "FIG3_Audit.png")
            
            plt.savefig(pdf_path, bbox_inches="tight")
            plt.savefig(png_path, dpi=200, bbox_inches="tight")
            plt.close(fig)
            
            return f"Graphs saved to:\n{png_path}"
        except Exception as e:
            return f"Graph Error: {str(e)}"
