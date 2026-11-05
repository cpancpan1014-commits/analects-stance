#!/usr/bin/env python3
"""把 gold/sample_40.json 转成 second_coder 可用的条目格式（补经文与上下文）。

用途：让第二个模型族也判这 40 条，从而得到
  κ(DeepSeek, 专家) / κ(GLM, 专家) / κ(DeepSeek, GLM) 三方对照。
注意：金标准只覆盖五层核心语料，因此这些条目均有经文。
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import second_coder as SC  # noqa: E402
import paths as P  # noqa: E402

OUT = SC.OUT
ROOT = SC.ROOT


def main():
    import csv
    # 注意：sample_40.json 的 stance 是**模型原判**，专家纠正只记在 gold_40.csv 的
    # gold_stance / model_stance 两列，必须从 CSV 取，否则 κ(模型,专家) 会被构造成 1.0。
    gold = json.loads((P.GOLD / "sample_40.json").read_text(encoding="utf-8"))
    lab = {int(r["\ufeffno"]): r for r in
           csv.DictReader(open(P.GOLD_CSV, encoding="utf-8"))}
    for g in gold:
        lr = lab.get(g["no"])
        if lr:
            g["model_stance"] = lr["model_stance"]
            g["gold_stance"] = lr["gold_stance"]
    pool = SC.build_pool()
    # 以 (章, 层, 术语, 立场) 为键建索引
    idx = {}
    for x in pool:
        idx.setdefault((x["ch"], x["L"], x["term"], x["ds_stance"]), []).append(x)

    items, miss = [], []
    for g in gold:
        key = (g["ch"], g["L"], g["term"], g["model_stance"])
        cand = idx.get(key)
        if not cand:                       # 立场键不匹配时退到 (章, 层, 术语)
            cand = [x for x in pool
                    if x["ch"] == g["ch"] and x["L"] == g["L"] and x["term"] == g["term"]]
        if not cand:
            miss.append(g)
            continue
        x = dict(cand[0])
        # 用金标准的术语/释义覆盖，确保模型判的就是被标注的那一条
        x["term"], x["gloss"] = g["term"], g["gloss"]
        x["no"] = g["no"]
        x["bucket"] = g["bucket"]
        x["gold_stance"] = g["gold_stance"]        # 专家判定
        x["ds_stance"] = g["model_stance"]         # DeepSeek 原判
        items.append(x)

    (OUT / "gold40_items.json").write_text(
        json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"装配 {len(items)} 条，未匹配 {len(miss)} 条")
    for g in miss:
        print("  缺:", g["ch"], g["L"], g["term"], g["stance"])
    nog = [x for x in items if not x.get("jing")]
    print("无经文的条目:", len(nog))


if __name__ == "__main__":
    main()
