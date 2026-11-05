#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Step 1 for the seventh layer: Zhu Xi's *Questions* (*Huowen*).

Same prompt and schema as the other six. Three adaptations, none of which
changes the extraction rule:

  1. The unit is a *paragraph*, not a chapter. The book is written as a series
     of question-and-answer groups Zhu Xi set himself, not one entry per verse;
     a second 或問 inside a paragraph usually quotes someone else, so paragraphs
     are not split further.
  2. Unit ids are `hw-<book>-<segment>`; the chapter label shown to the model is
     the chapter Zhu Xi declares, or the one recovered from text overlap, or the
     book, in that order. Chapter boundaries are not the unit of this book.
  3. The worked example is drawn from the book itself (01-01 for an assertion,
     01-16 for judging two predecessors), otherwise the model treats a
     question-and-answer text as all assertion.

Control layer: held out of prompt construction. Its terms are validated against
the book-level scripture, which the paper discloses as the one relaxation.
"""
import argparse
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import paths as P
import promptset as PS
from extract_terms import call, parse_json

SRC = P.CORPUS_HUOWEN
SRC_JING = P.CORPUS
OUT = P.TERMS_HUOWEN
LAYER = "huowen"


def tidy(s):
    return re.sub(r"[\s　]", "", s or "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--model", default=os.environ.get("LLM_MODEL", "deepseek-chat"))
    ap.add_argument("--base-url", default=os.environ.get("LLM_BASE_URL", "https://api.deepseek.com"))
    args = ap.parse_args()

    segs = [json.loads(l) for l in open(SRC, encoding="utf-8")]
    jing, by_pian = {}, {}
    for line in open(SRC_JING, encoding="utf-8"):
        r = json.loads(line)
        jing[r["chapter"]] = r.get("jing") or ""
        by_pian.setdefault(r["pian_no"], []).append(r.get("jing") or "")

    done = set()
    if OUT.exists():
        for l in open(OUT, encoding="utf-8"):
            try:
                d = json.loads(l)
                if d.get("ok"):
                    done.add(d["chapter"])
            except Exception:
                pass

    tasks = [r for r in segs if r["n_chars"] >= 40 and r["chapter"] not in done]
    if args.limit:
        tasks = tasks[:args.limit]
    print(f"pending {len(tasks)} segments (done {len(done)}), workers {args.workers}")

    def payload(r):
        """(chapter label, scripture context) for one paragraph."""
        dc = r.get("declared_chapter")
        if dc and len(re.sub(r"[^\u4e00-\u9fff]", "", jing.get(dc) or "")) >= 8:
            return dc, jing[dc]
        # Book-level fallback: skip fragmentary scripture (01-12 holds only
        # 有子曰：「」 in this corpus) so an empty line is not offered as context.
        parts = [j for j in by_pian.get(r["pian_no"], [])
                 if len(re.sub(r"[^\u4e00-\u9fff]", "", j or "")) >= 8]
        return (dc or f"{r['pian_no']:02d}篇"), "".join(parts)[:1200]

    key = os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("LLM_API_KEY")
    if args.dry_run:
        r = tasks[0]
        ch, tx = payload(r)
        print("=" * 20, r["chapter"], "-> model sees chapter:", ch)
        print(PS.build_user(ch, tx, LAYER, r["text"])[:2200])
        return 0
    if not key:
        sys.exit("set DEEPSEEK_API_KEY")

    def work(r):
        ch, tx = payload(r)
        msgs = [{"role": "system", "content": PS.SYSTEM},
                {"role": "user", "content": PS.build_user(ch, tx, LAYER, r["text"])}]
        try:
            raw, usage = call(key, args.base_url, args.model, msgs)
            obj = parse_json(raw)
            obj["chapter"] = ch
            obj["annotator"] = LAYER
            jt = tidy(tx)
            for it in (obj.get("items") or []):
                tm = (it.get("term") or "").strip()
                it["in_text"] = bool(tm) and tm in jt
            return {"ok": True, "chapter": r["chapter"], "unit": r["chapter"],
                    "pian_no": r["pian_no"], "seg_no": r["seg_no"],
                    "shown_chapter": ch, "annotator": LAYER,
                    "data": obj, "usage": usage, "model": args.model}
        except Exception as e:
            return {"ok": False, "chapter": r["chapter"], "annotator": LAYER,
                    "error": str(e)[:300]}

    ok = fail = 0
    t0 = time.time()
    tin = tout = 0
    with open(OUT, "a", encoding="utf-8") as f:
        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            futs = {ex.submit(work, r): r for r in tasks}
            for i, fu in enumerate(as_completed(futs), 1):
                rec = fu.result()
                if rec["ok"]:
                    ok += 1
                    tin += rec["usage"].get("prompt_tokens", 0)
                    tout += rec["usage"].get("completion_tokens", 0)
                else:
                    fail += 1
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                f.flush()
                if i % 50 == 0 or i == len(tasks):
                    el = time.time() - t0
                    print(f"  {i}/{len(tasks)} ok={ok} fail={fail} "
                          f"{el/60:.1f}min in={tin} out={tout}", flush=True)
    print(f"done ok={ok} fail={fail} in={tin} out={tout}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
