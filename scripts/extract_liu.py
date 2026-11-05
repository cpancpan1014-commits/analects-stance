#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Step 1 for the sixth layer: Liu Baonan's *Zhengyi* (1866).

Same prompt, same schema, same post-processing as the five core layers, with
two adaptations that keep the comparison honest:

  1. Before the text is sent, lines that are pure canonical text (their
     normalised form is a substring of the chapter's scripture) are removed.
     Otherwise the model can quote the *Analects* as if it were a gloss.
  2. The worked example is a real rejection from the book (12-01, against Zhu
     Xi on 己), because a compilation-style sample would turn a Qing
     philologist's argument into a list of adoptions.

Control layer: it was held out of prompt construction.
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

SRC_LIU = P.CORPUS_LIU
SRC_JING = P.CORPUS
OUT = P.TERMS_LIU
LAYER = "liu"

try:
    from opencc import OpenCC
    _CC = OpenCC("t2s")
except Exception:                       # pragma: no cover
    _CC = None


def norm(s):
    """Comparison form: traditional folded to simplified, Han characters only."""
    t = _CC.convert(s) if _CC else s
    return re.sub(r"[^\u4e00-\u9fff]", "", t)


def tidy(s):
    return re.sub(r"[\s　]", "", s or "")


def build_note(text, jing_n):
    """Drop lines that are canonical text rather than commentary."""
    keep = []
    for line in (text or "").split("\n"):
        n = norm(line)
        if not n:
            continue
        if jing_n and n in jing_n:
            continue
        keep.append(line)
    return "\n".join(keep)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--model", default=os.environ.get("LLM_MODEL", "deepseek-chat"))
    ap.add_argument("--base-url", default=os.environ.get("LLM_BASE_URL", "https://api.deepseek.com"))
    args = ap.parse_args()

    liu = {r["chapter"]: r for r in (json.loads(l) for l in open(SRC_LIU, encoding="utf-8"))}
    jing = {r["chapter"]: r for r in (json.loads(l) for l in open(SRC_JING, encoding="utf-8"))}

    done = set()
    if OUT.exists():
        for l in open(OUT, encoding="utf-8"):
            try:
                d = json.loads(l)
                if d.get("ok"):
                    done.add(d["chapter"])
            except Exception:
                pass

    tasks = [ch for ch, r in sorted(liu.items())
             if len(r.get("text") or "") >= 50 and ch not in done]
    if args.limit:
        tasks = tasks[:args.limit]
    print(f"pending {len(tasks)} chapters (done {len(done)}), workers {args.workers}")

    key = os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("LLM_API_KEY")
    if args.dry_run:
        ch = tasks[0]
        note = build_note(liu[ch]["text"], norm(jing[ch].get("jing") or ""))
        print("=" * 20, ch)
        print(PS.build_user(ch, jing[ch].get("jing"), LAYER, note)[:1800])
        return 0
    if not key:
        sys.exit("set DEEPSEEK_API_KEY")

    def work(ch):
        note = build_note(liu[ch]["text"], norm(jing[ch].get("jing") or ""))
        msgs = [{"role": "system", "content": PS.SYSTEM},
                {"role": "user", "content": PS.build_user(ch, jing[ch].get("jing"), LAYER, note)}]
        try:
            raw, usage = call(key, args.base_url, args.model, msgs)
            obj = parse_json(raw)
            obj["chapter"] = ch
            obj["annotator"] = LAYER
            jt = tidy(jing[ch].get("jing") or "")
            for it in (obj.get("items") or []):
                tm = (it.get("term") or "").strip()
                it["in_text"] = bool(tm) and tm in jt
            return {"ok": True, "chapter": ch, "annotator": LAYER, "data": obj,
                    "usage": usage, "model": args.model}
        except Exception as e:
            return {"ok": False, "chapter": ch, "annotator": LAYER, "error": str(e)[:300]}

    ok = fail = 0
    t0 = time.time()
    tin = tout = 0
    with open(OUT, "a", encoding="utf-8") as f:
        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            futs = {ex.submit(work, ch): ch for ch in tasks}
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
