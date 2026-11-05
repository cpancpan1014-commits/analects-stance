#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Step 1 of Algorithm 1: one call per (chapter, layer) pair.

Pure standard library, any OpenAI-compatible endpoint. The prompt is not in
this file -- it is in data/prompts/ (see promptset.py), so the code and
Appendix A cannot drift apart.

Usage
    export DEEPSEEK_API_KEY=sk-xxxx
    python3 scripts/extract_terms.py --dry-run          # show the first message
    python3 scripts/extract_terms.py --limit 10         # ten calls
    python3 scripts/extract_terms.py                    # all 1,695

Output
    out/terms_<tag>.jsonl, one record per call, including the raw reply, so a
    reviewer can audit any item without re-running the model. Re-running skips
    pairs already present. The five core layers are tag v3.
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

import paths as P
import promptset as PS

SRC = P.CORPUS
LOG = P.OUT / "extract_log.txt"

LAYERS = P.CORE_LAYERS


def call(api_key, base_url, model, messages, temperature=0.0, retries=3):
    """POST one chat completion; retry only on transport and 5xx/429."""
    body = json.dumps({
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "response_format": {"type": "json_object"},
        "max_tokens": 4000,
    }).encode("utf-8")
    for att in range(retries):
        req = urllib.request.Request(
            base_url.rstrip("/") + "/chat/completions", data=body,
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {api_key}"})
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                d = json.loads(r.read().decode("utf-8"))
            return d["choices"][0]["message"]["content"], d.get("usage", {})
        except urllib.error.HTTPError as e:
            msg = e.read().decode("utf-8", "ignore")[:300]
            if e.code in (429, 500, 502, 503, 504) and att < retries - 1:
                time.sleep(2 ** att * 3)
                continue
            raise RuntimeError(f"HTTP {e.code}: {msg}")
        except Exception:
            if att < retries - 1:
                time.sleep(2 ** att * 2)
                continue
            raise


def parse_json(s):
    """Tolerate a stray code fence; JSON mode usually makes this unnecessary."""
    s = s.strip()
    s = re.sub(r"^```(?:json)?\s*", "", s)
    s = re.sub(r"\s*```$", "", s)
    i, j = s.find("{"), s.rfind("}")
    if i < 0 or j < 0:
        raise ValueError("no json object")
    return json.loads(s[i:j + 1])


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--chapter", default="")
    ap.add_argument("--layer", default="")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--tag", default="v3", help="results go to out/terms_<tag>.jsonl")
    ap.add_argument("--model", default=os.environ.get("LLM_MODEL", "deepseek-chat"))
    ap.add_argument("--base-url", default=os.environ.get("LLM_BASE_URL", "https://api.deepseek.com"))
    args = ap.parse_args(argv)

    out = P.OUT / f"terms_{args.tag}.jsonl"
    rows = [json.loads(l) for l in open(SRC, encoding="utf-8")]
    full = [r for r in rows if all((r.get(L) or "").strip() for L in LAYERS)]
    by_ch = {r["chapter"]: r for r in full}
    tasks = [(r["chapter"], L) for r in full for L in LAYERS]
    if args.chapter:
        tasks = [t for t in tasks if t[0] == args.chapter]
    if args.layer:
        tasks = [t for t in tasks if t[1] == args.layer]

    done = set()
    if out.exists():
        for l in open(out, encoding="utf-8"):
            try:
                d = json.loads(l)
                if d.get("ok"):
                    done.add((d["chapter"], d["annotator"]))
            except Exception:
                pass
    tasks = [t for t in tasks if t not in done]
    if args.limit:
        tasks = tasks[:args.limit]

    # A dry run reads the prompt, not the cache: show a call even when all of
    # them are already on disk.
    if args.dry_run and not tasks:
        tasks = [(r["chapter"], L) for r in full for L in LAYERS][:1]
        args.limit = 1

    print(f"pending {len(tasks)} (done {len(done)})")

    if args.dry_run:
        if not tasks:
            print("nothing to do")
            return 0
        ch, L = tasks[0]
        r = by_ch[ch]
        print("=" * 60)
        print("SYSTEM:\n" + PS.SYSTEM)
        print("=" * 60)
        print("USER:\n" + PS.build_user(ch, r.get("jing"), L, r.get(L)))
        print("=" * 60)
        est_in = (len(PS.SYSTEM) + 1200) * 1.6
        print(f"~{est_in:.0f} input tokens per call; {len(tasks)} calls "
              f"~ {est_in * len(tasks) / 1e6:.2f}M tokens")
        return 0

    api_key = os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("LLM_API_KEY")
    if not api_key:
        sys.exit("set DEEPSEEK_API_KEY (or LLM_API_KEY)")

    ok = fail = 0
    tot_in = tot_out = 0
    with open(out, "a", encoding="utf-8") as f, open(LOG, "a", encoding="utf-8") as lg:
        for i, (ch, L) in enumerate(tasks, 1):
            r = by_ch[ch]
            msgs = [{"role": "system", "content": PS.SYSTEM},
                    {"role": "user", "content": PS.build_user(ch, r.get("jing"), L, r.get(L))}]
            try:
                raw, usage = call(api_key, args.base_url, args.model, msgs)
                obj = parse_json(raw)
                obj["chapter"] = ch
                obj["annotator"] = L
                jing = re.sub(r"[\s　]", "", r.get("jing") or "")
                for it in (obj.get("items") or []):
                    t = (it.get("term") or "").strip()
                    it["in_text"] = bool(t) and t in jing
                rec = {"ok": True, "chapter": ch, "annotator": L, "data": obj,
                       "usage": usage, "model": args.model}
                ok += 1
                tot_in += usage.get("prompt_tokens", 0)
                tot_out += usage.get("completion_tokens", 0)
            except Exception as e:
                rec = {"ok": False, "chapter": ch, "annotator": L, "error": str(e)[:300]}
                fail += 1
                lg.write(f"{ch}\t{L}\t{str(e)[:200]}\n")
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
            if i % 20 == 0:
                print(f"  {i}/{len(tasks)}  ok={ok} fail={fail}  in={tot_in} out={tot_out}")

    print(f"done ok={ok} fail={fail}  input {tot_in} tokens, output {tot_out}")
    print(f"result: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
