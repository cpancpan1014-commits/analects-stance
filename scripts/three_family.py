#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三模型族对照：DeepSeek / GLM / Qwen 对同一批 37 条金标准的判读。

数据源（按 no 对齐）：
    gold/gold_40.csv                  专家 gold_stance、主模型 model_stance
    out/second_coder_gold.jsonl       GLM 判读（字段 glm_stance）
    out/second_coder_gold_qwen.jsonl  Qwen 判读（字段 glm_stance，历史命名沿用）

用法：python3 scripts/three_family.py
"""
import json
import random
import re
import sys
from collections import Counter
from pathlib import Path

import paths as P

ROOT, OUT, GOLD = P.ROOT, P.OUT, P.GOLD
CATS = ("assert", "adopt", "reject")


def load_jsonl(p):
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]


def kappa(a, b):
    n = len(a)
    po = sum(1 for x, y in zip(a, b) if x == y) / n
    pe = sum((a.count(c) / n) * (b.count(c) / n) for c in sorted(set(a) | set(b)))
    return (po - pe) / (1 - pe), po


def boot(a, b, n_boot=2000, seed=3):
    rng, n, ks = random.Random(seed), len(a), []
    for _ in range(n_boot):
        idx = [rng.randrange(n) for _ in range(n)]
        k = kappa([a[i] for i in idx], [b[i] for i in idx])[0]
        if k == k:
            ks.append(k)
    ks.sort()
    return ks[int(.025 * len(ks))], ks[int(.975 * len(ks)) - 1]


def macro_f1(gold, pred):
    out = {}
    for c in CATS:
        tp = sum(1 for g, p in zip(gold, pred) if g == c and p == c)
        fp = sum(1 for g, p in zip(gold, pred) if g != c and p == c)
        fn = sum(1 for g, p in zip(gold, pred) if g == c and p != c)
        pr = tp / (tp + fp) if tp + fp else 0.0
        rc = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * pr * rc / (pr + rc) if pr + rc else 0.0
        out[c] = (pr, rc, f1, sum(1 for g in gold if g == c))
    out["macro"] = (None, None, sum(v[2] for k, v in out.items() if k in CATS) / 3, len(gold))
    return out


def main():
    # 专家与主模型
    exp, ds, layer = {}, {}, {}
    for row in open(GOLD / "gold_40.csv", encoding="utf-8-sig"):
        f = row.rstrip("\n").split(",")
        if not f or not f[0].isdigit():
            continue
        no = int(f[0])
        exp[no] = f[5]
        ds[no] = f[4]
        layer[no] = f[2]

    glm = {r["no"]: r["glm_stance"] for r in load_jsonl(OUT / "second_coder_gold.jsonl") if r.get("ok")}
    qwn = {r["no"]: r["glm_stance"] for r in load_jsonl(OUT / "second_coder_gold_qwen.jsonl") if r.get("ok")}
    qsrc = {r["no"]: r.get("glm_source") for r in load_jsonl(OUT / "second_coder_gold_qwen.jsonl") if r.get("ok")}
    gsrc = {r["no"]: r.get("glm_source") for r in load_jsonl(OUT / "second_coder_gold.jsonl") if r.get("ok")}

    nos = sorted(set(exp) & set(glm) & set(qwn) & set(ds))
    print(f"三族 + 专家共同完成条目：{len(nos)}\n")

    pairs = [("DeepSeek", ds, "专家", exp), ("GLM", glm, "专家", exp), ("Qwen", qwn, "专家", exp),
             ("GLM", glm, "DeepSeek", ds), ("Qwen", qwn, "DeepSeek", ds), ("Qwen", qwn, "GLM", glm)]
    rows = []
    for na, a, nb, b in pairs:
        x, y = [a[n] for n in nos], [b[n] for n in nos]
        k, po = kappa(x, y)
        lo, hi = boot(x, y)
        rows.append((f"{na} × {nb}", len(x), po, k, lo, hi))
        print(f"  {na:<9} × {nb:<9} n={len(x)}  一致 {po:.1%}  κ={k:.3f}  95% CI [{lo:.2f}, {hi:.2f}]")

    print("\n对专家的分类表现（宏 F1）：")
    for name, d in (("DeepSeek", ds), ("GLM", glm), ("Qwen", qwn)):
        g = [exp[n] for n in nos]
        p = [d[n] for n in nos]
        m = macro_f1(g, p)
        detail = "  ".join(f"{c}={m[c][2]:.2f}" for c in CATS)
        print(f"  {name:<9} 宏F1={m['macro'][2]:.3f}   ({detail})")

    print("\nQwen 对专家混淆矩阵（行=专家，列=Qwen）：")
    print("        " + "".join(f"{c:>9}" for c in CATS))
    for r in CATS:
        line = f"  {r:<8}"
        for c in CATS:
            line += f"{sum(1 for n in nos if exp[n] == r and qwn[n] == c):>9}"
        print(line)

    print("\nQwen 判错条目：")
    for n in nos:
        if exp[n] != qwn[n]:
            print(f"  no.{n:<4} {layer[n]:<6} 专家={exp[n]:<7} Qwen={str(qwn[n]):<7} "
                  f"DS={ds[n]:<7} GLM={glm[n]:<7} | src Q={qsrc.get(n)} G={gsrc.get(n)}")

    # 至少在若干条上 Qwen 与专家一致而 GLM 不一致
    q_better = [n for n in nos if qwn[n] == exp[n] and glm[n] != exp[n]]
    g_better = [n for n in nos if glm[n] == exp[n] and qwn[n] != exp[n]]
    both_wrong = [n for n in nos if glm[n] != exp[n] and qwn[n] != exp[n]]
    print(f"\nQwen 对而 GLM 错：{len(q_better)} 条  {q_better}")
    print(f"GLM 对而 Qwen 错：{len(g_better)} 条  {g_better}")
    print(f"两族同错：{len(both_wrong)} 条  {both_wrong}")

    # 两族共识能否逼近专家（多数投票 vs 专家）
    print("\n多数投票（Qwen+GLM 一致时取该值，不一致时退回 DeepSeek）：")
    mv = []
    for n in nos:
        mv.append(qwn[n] if qwn[n] == glm[n] else ds[n])
    g = [exp[n] for n in nos]
    k, po = kappa(g, mv)
    print(f"  n={len(nos)}  一致 {po:.1%}  κ={k:.3f}")

    json.dump({"n": len(nos), "pairs": [{"a": r[0], "n": r[1], "po": r[2], "kappa": r[3],
                                        "ci": [r[4], r[5]]} for r in rows]},
              open(OUT / "three_family.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
