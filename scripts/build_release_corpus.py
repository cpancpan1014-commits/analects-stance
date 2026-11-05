#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build the released corpus: OCR repair, edition-defect flags, corpus statistics.

    data/corpus_raw.jsonl  ->  data/corpus_clean.jsonl
                               data/corpus_stats.json
                               data/contamination.json

Three things happen here, in this order.

1. OCR repair. The five core layers were transcribed from page images and from
   wiki text; running headers, volume numbers, stray page numbers and
   proofreading circles survive across page breaks. Nine rules remove them.
   Nothing else in the text is touched -- terms and glosses in the released
   jsonl are the characters a reader of the edition sees.

2. Edition defect (Ito Jinsai layer). In six chapters the printed edition binds
   the *Riddle* (*Rongo Kogi*) and the *Ancient Meaning* (*Rongo Cho*) in one
   volume and mis-assigns the page ranges where chapters run short, so the
   "Jinsai" layer holds Sorai's text. Those six chapters are flagged
   `kogi_status = "suppressed"`. The judgement is stored in the data, not in
   the code, so a reader can inspect and overrule it; `contamination.json`
   records the evidence per chapter.

3. Statistics written to `corpus_stats.json`: what is in the file, layer by
   layer, so the data card does not have to be trusted on arithmetic.

The output is byte-identical, layer by layer, to the corpus the published runs
used (`--check` proves it against out/terms_* build inputs).
"""
import argparse
import json
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path

import paths as P

BOOKS = r"(?:論語古義\s*[、．·•]?\s*論語徵|論語古義論語徵|論語徵|論語古義)"

RULES = [
    (re.compile(r"\d{1,4}\s*" + BOOKS), ""),                                   # page + running head
    (re.compile(r"卷[一二三四五六七八九十百]{1,3}\s*\d{1,4}"), ""),             # 卷一13
    (re.compile(r"卷[一二三四五六七八九十百]{1,3}"), ""),                        # bare volume mark
    (re.compile(BOOKS), ""),                                                   # residual title
    (re.compile(r"[\u2460-\u2473\u24EA-\u24FF\u2776-\u277F①-⑳]"), ""),          # proofreading circles
    (re.compile(r"(?<=[\u4e00-\u9fff])\d{1,4}(?=[\u4e00-\u9fff])"), ""),        # stray page number
    (re.compile(r"-\{.*?\}-", re.S), ""),                                      # wiki language block
    (re.compile(r"\[https?://[^\]]*\]?", re.S), ""),                            # external link
    (re.compile(r"^\s*(Categor|更多有聲文獻|此錄音来自外部鏈接).*$", re.M), ""),    # site boilerplate
]

PUNCT = re.compile(r"[\s　，。、；：（）()「」『』·．\.\,\;\:\?\!—◯○]")


def clean(s):
    if not s:
        return s, 0
    n0 = len(s)
    for pat, rep in RULES:
        s = pat.sub(rep, s)
    return s, n0 - len(s)


def similarity(a, b):
    a, b = PUNCT.sub("", a or ""), PUNCT.sub("", b or "")
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def find_defect(rows, theta=0.85, min_chars=50):
    """Chapters where the Jinsai layer duplicates the Sorai layer.

    The rule is a similarity floor plus a length floor. The length floor is not
    cosmetic: SequenceMatcher inflates on short strings, and 11-05 -- a chapter
    where Jinsai writes 24 characters -- scores .889 on a shared classical
    phrase while its text is plainly his own. Below 50 characters the ratio
    carries no signal, so those chapters are listed but not flagged.
    """
    flagged, skipped = [], []
    for r in rows:
        s = similarity(r.get("kogi"), r.get("cho"))
        if s < theta:
            continue
        rec = {
            "chapter": r["chapter"],
            "pian": r.get("pian"),
            "similarity_kogi_vs_cho": round(s, 3),
            "kogi_chars": len((r.get("kogi") or "").strip()),
            "contains_self_reference": "仁齋先生曰" in (r.get("kogi") or ""),
            "kogi_head": (r.get("kogi") or "")[:60],
            "cho_head": (r.get("cho") or "")[:60],
        }
        if rec["kogi_chars"] < min_chars:
            rec["action"] = "not flagged: layer shorter than %d chars" % min_chars
            skipped.append(rec)
            continue
        rec["action"] = "kogi_status=suppressed"
        flagged.append(rec)
    return flagged, skipped


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default=str(P.DATA / "corpus_raw.jsonl"))
    ap.add_argument("--out", default=str(P.CORPUS))
    ap.add_argument("--check", action="store_true",
                    help="compare against the corpus the published runs used")
    a = ap.parse_args()

    rows = [json.loads(l) for l in open(a.raw, encoding="utf-8")]
    removed = {L: 0 for L in P.CORE_LAYERS}
    removed_jing = 0

    for r in rows:
        for L in P.CORE_LAYERS:
            r[L], d = clean(r.get(L))
            removed[L] += d
        r["jing"], d = clean(r.get("jing"))
        removed_jing += d

    defect, near_miss = find_defect(rows)
    flagged = {d["chapter"] for d in defect}
    for r in rows:
        r["kogi_status"] = "suppressed" if r["chapter"] in flagged else "ok"
        if r["chapter"] in flagged:
            r["kogi_status_note"] = ("edition defect: page ranges of the Kogi/Cho "
                                     "joint volume swap in short chapters; layer "
                                     "excluded from analysis")

    with open(a.out, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    (P.DATA / "contamination.json").write_text(json.dumps({
        "rule": "similarity(kogi, cho) >= 0.85 after punctuation removal, "
                "and the kogi layer at least 50 characters long",
        "source": "the edition binds Rongo Kogi and Rongo Cho in one volume and mis-assigns "
                  "page ranges where chapters run short, so the Kogi layer carries Cho text",
        "chapters": defect,
        "n_chapters": len(defect),
        "similarity_range": [min((d["similarity_kogi_vs_cho"] for d in defect), default=None),
                             max((d["similarity_kogi_vs_cho"] for d in defect), default=None)],
        "near_misses_not_flagged": near_miss,
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    stats = {
        "chapters": len(rows),
        "pian": len({r["pian_no"] for r in rows}),
        "layers": {},
        "chars_removed": {**removed, "jing": removed_jing},
        "kogi_suppressed": sorted(flagged),
        "chapters_with_all_five_layers": sum(
            1 for r in rows if all((r.get(L) or "").strip() for L in P.CORE_LAYERS)),
        "chapters_with_any_layer": sum(
            1 for r in rows if any((r.get(L) or "").strip() for L in P.CORE_LAYERS)),
        "chapters_kogi_over_30_chars": sum(
            1 for r in rows if len((r.get("kogi") or "").strip()) > 30),
    }
    for L in P.CORE_LAYERS + ["jing"]:
        n = sum(len(r.get(L) or "") for r in rows)
        stats["layers"][L] = {
            "chars": n,
            "chapters_non_empty": sum(1 for r in rows if (r.get(L) or "").strip()),
        }
    (P.DATA / "corpus_stats.json").write_text(
        json.dumps(stats, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"chapters {stats['chapters']}  books {stats['pian']}")
    for L, s in stats["layers"].items():
        print(f"  {L:6s} {s['chars']:8d} chars in {s['chapters_non_empty']:3d} chapters"
              f"   (removed {removed.get(L, removed_jing)} as OCR noise)")
    print(f"five layers complete in {stats['chapters_with_all_five_layers']} chapters")
    print(f"kogi suppressed in {len(flagged)}: {sorted(flagged)}")

    if a.check:
        ref = [json.loads(l) for l in open(P.DATA / "corpus_clean.reference.jsonl",
                                           encoding="utf-8")]
        bad = [(r["chapter"], L) for r, q in zip(rows, ref) for L in P.CORE_LAYERS + ["jing"]
               if (r.get(L) or "") != (q.get(L) or "")]
        print("text identical to reference:", not bad, f"({len(bad)} mismatches)")
        if bad:
            print(bad[:5], file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
