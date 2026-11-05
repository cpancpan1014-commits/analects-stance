#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Algorithm 1 of the paper, end to end, as a single readable file.

    Input : chapters C, layers L, schema S, thresholds tau, mu
    Output: nodes N, edges E, divergence counts D

Step 1 issues the LLM calls. Because those calls are cached in `out/`, the
default mode is to read the cache and run steps 2-11: the script then
reproduces the published counts without a key, a network, or a cent spent.
Pass `--live` to call the API instead (needs an OpenAI-compatible endpoint).

Every function below names the pseudocode lines it implements, so the code and
the listing can be read side by side.

    python3 scripts/alg1.py                 # steps 2-11 on cached calls
    python3 scripts/alg1.py --live --limit 5
"""
import argparse
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from difflib import SequenceMatcher

import paths as P

try:                                    # variant folding; optional but reported
    from opencc import OpenCC
    _T2S = OpenCC("t2s").convert
except Exception:                       # pragma: no cover
    _T2S = lambda s: s                  # noqa: E731

# ---------------------------------------------------------------- constants
MU = 4          # step 2: |term| <= mu
TAU = 0.66      # step 9: similarity threshold for one "reading"

# Step 5: the marker set that makes a rejection high-confidence.
# Read literally from the commentary, as particles rather than cue phrases.
NEG = re.compile(
    r"非也|非矣|豈|误|誤|陋|殊|不知|不曉|不識|不必|不可|不取|何以|安得|焉得|烏足|"
    r"未|失|謬|妄|不然|非是|臆説|泥矣|固矣|不得其解|必不若|過也|果其說|何所見|理學者流|堅白"
)
# Step 3: a gloss that is nothing but a fanqie spelling is a reading, not a stance.
PHON = re.compile(r"(音[^\s，。]{1,3}$)|(^[^\s，。]{1,3}反$)|(去聲|上聲|入聲|平聲|叶音)")

_EXTRA = str.maketrans({"顚": "颠", "敎": "教", "眞": "真", "卽": "即", "旣": "既",
                        "羣": "群", "峯": "峰", "牀": "床", "竝": "并", "彊": "强",
                        "隣": "邻", "飜": "翻"})

# Step 5: one authority, many spellings. Generic collectives (宋儒, 舊註) are
# kept as they stand -- they are the synecdoche the task is about.
ALIAS = {
    "朱子": "朱熹", "朱熹": "朱熹", "朱註": "朱熹", "朱注": "朱熹", "朱氏": "朱熹",
    "仁齋": "仁斋", "仁斋": "仁斋", "伊藤仁齋": "仁斋", "伊藤仁斋": "仁斋",
    "仁齋先生": "仁斋", "仁斋先生": "仁斋",
    "徂徠": "徂徕", "徂徕": "徂徕", "荻生徂徠": "徂徕", "徂徠先生": "徂徕",
    "何氏": "何晏", "何": "何晏", "邢疏": "邢昺", "邢氏": "邢昺", "邢": "邢昺",
    "马融": "馬融", "馬": "馬融", "王肃": "王肅", "王": "王肅",
    "包氏": "包咸", "包": "包咸", "郑玄": "鄭玄", "鄭": "鄭玄", "鄭註": "鄭玄",
    "程": "程子", "谢氏": "謝氏", "杨氏": "楊氏", "苏氏": "蘇氏",
    "张子": "張子", "吕氏": "呂氏",
}
GENERIC = {"宋儒", "後儒", "先儒", "舊註", "古註", "世人", "俗儒", "近世", "時人"}


# ---------------------------------------------------------------- helpers
def norm_term(s):
    """Character-level folding used only for *comparison*, never for output."""
    s = unicodedata.normalize("NFKC", s or "")
    return _T2S(s).translate(_EXTRA)


def norm_gloss(s):
    s = unicodedata.normalize("NFKC", s or "")
    s = re.sub(r"[\s　]", "", s)
    return re.sub(r"[，。、；：（）()「」『』·．\.\,\;\:\?\!—]", "", s)


def sim(a, b):
    a, b = norm_gloss(a), norm_gloss(b)
    if not a or not b:
        return 0.0
    return 1.0 if a == b else SequenceMatcher(None, a, b).ratio()


def neg(evidence):
    """Step 5's predicate. True iff the quoted span carries a negative marker."""
    return bool(NEG.search(evidence or ""))


# ---------------------------------------------------------------- step 2-3
def filter_items(calls, corpus, mu=MU):
    """Pseudocode lines 2-3.

    Keep an item only if its term is at most `mu` characters and, after variant
    folding, actually occurs in the canonical text of its chapter; drop pure
    fanqie glosses. Returns (items, stats).
    """
    by_ch = {r["chapter"]: r for r in corpus}
    jing = {ch: norm_term(re.sub(r"[\s　]", "", r.get("jing") or "")) for ch, r in by_ch.items()}
    piano = defaultdict(str)                     # the *Questions* is aligned by book
    for r in corpus:
        piano[r.get("pian_no")] += norm_term(re.sub(r"[\s　]", "", r.get("jing") or ""))
    status = {r["chapter"]: r.get("kogi_status", "ok") for r in corpus}

    items, st = [], Counter()
    for call in calls:
        ch, layer = call["chapter"], call["annotator"]
        suppressed = layer == "kogi" and status.get(ch, "ok") == "suppressed"
        scope = jing.get(ch) or piano.get(call.get("pian_no"), "")
        for it in (call["data"].get("items") or []):
            term = (it.get("term") or "").strip()
            gloss = (it.get("gloss") or "").strip()
            if not term or not gloss:
                continue
            if not 1 <= len(term) <= mu:
                st["term_too_long"] += 1
                continue
            if suppressed:
                st["suppressed"] += 1
                continue
            tn = norm_term(term)
            if tn not in scope:
                st["term_not_in_text"] += 1
                continue
            if PHON.search(gloss) and len(norm_gloss(gloss)) <= 5:
                st["phonetic"] += 1
                continue
            src = (it.get("source") or "").strip()
            src = ALIAS.get(src, src) or None
            if src in GENERIC:
                pass                              # keep the collective as written
            items.append({
                "chapter": ch, "layer": layer, "term": term, "tn": tn,
                "gloss": gloss, "type": it.get("type"),
                "stance": (it.get("stance") or "assert").lower(),
                "source": src, "evidence": it.get("evidence"),
            })
    return items, dict(st)


# ---------------------------------------------------------------- step 4-6
def gate(items):
    """Pseudocode lines 4-6: E <- E + {(critic -> source, c, term)}.

    An edge needs both a target (`source`) and a marker in `evidence`. What
    fails the test is *held*, not deleted: the paper reports both counts.
    """
    edges, held, no_target = [], [], []
    for it in items:
        if it["stance"] != "reject":
            continue
        if not it["source"]:
            no_target.append(it)
        elif neg(it["evidence"]):
            edges.append(it)
        else:
            held.append(it)
    return edges, held, no_target


# ---------------------------------------------------------------- step 7-10
def link_cluster(seq, tau=TAU, key=None):
    """Step 9's `link_cluster`: greedy single pass, first representative wins.

    Not a transitive closure -- transitivity would let a chain of pairwise
    similar glosses collapse into one reading, and the paper reports what the
    code does. Sweeping tau (see threshold_sweep.py) is how the choice is
    defended instead.

    `seq` holds gloss strings by default; pass `key` to cluster whole items on
    the gloss they carry and keep the members.
    """
    k = key or (lambda x: x)
    reps = []
    for x in seq:
        for r in reps:
            if sim(k(x), k(r[0])) >= tau:
                r.append(x)
                break
        else:
            reps.append([x])
    return reps


def build_graph(items, tau=TAU):
    """Pseudocode lines 7-10: nodes N and divergence counts D."""
    node = defaultdict(list)
    for it in items:
        if it["stance"] in ("assert", "adopt"):
            node[(it["chapter"], it["tn"])].append(it)

    D, N = {}, {}
    for key, group in node.items():
        if len({x["layer"] for x in group}) < 2:      # need two critics to compare
            continue
        clusters = link_cluster([x["gloss"] for x in group], tau)
        D[key] = len(clusters)
        if len(clusters) >= 2:
            N[key] = clusters
    return N, D


# ---------------------------------------------------------------- step 1
def load_cached(tags=("v3", "liu", "huowen")):
    """Step 1, from cache: the raw model replies, one JSON object per call."""
    files = {"v3": P.TERMS_CORE, "liu": P.TERMS_LIU, "huowen": P.TERMS_HUOWEN}
    calls = []
    for t in tags:
        for line in open(files[t], encoding="utf-8"):
            d = json.loads(line)
            if d.get("ok"):
                calls.append(d)
    return calls


def run_live(limit=0):
    """Step 1, live. Thin wrapper around extract_terms.py's client."""
    import extract_terms as ET
    print("live mode: see extract_terms.py; writes out/terms_<tag>.jsonl", file=sys.stderr)
    return ET.run(limit=limit)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="call the API instead of the cache")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--tau", type=float, default=TAU)
    ap.add_argument("--core-only", action="store_true", help="five layers only")
    a = ap.parse_args()

    if a.live:
        run_live(a.limit)
        return

    corpus = [json.loads(l) for l in open(P.CORPUS, encoding="utf-8")]
    tags = ("v3",) if a.core_only else ("v3", "liu", "huowen")
    calls = load_cached(tags)

    items, st = filter_items(calls, corpus)
    edges, held, no_target = gate(items)
    N, D = build_graph(items, a.tau)

    print(f"calls read          {len(calls):>6}")
    print(f"items kept          {len(items):>6}   dropped {st}")
    print(f"rejections          {len(edges) + len(held) + len(no_target):>6}")
    print(f"  high-confidence   {len(edges):>6}")
    print(f"  held for review   {len(held):>6}")
    print(f"  no target         {len(no_target):>6}")
    print(f"comparable nodes    {len(D):>6}")
    print(f"disputed nodes      {len(N):>6}")
    print(f"mean readings       {sum(D.values()) / max(len(D), 1):>6.2f}")


if __name__ == "__main__":
    main()
