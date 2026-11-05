#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""四个模型族在 37 条金标准上的对照，外加「汉注／日注」分组。

返修后论文的重心从「度量注本分歧」移到「中国大模型能否判读日人汉文注本」，
因此需要两个口径的数字：

  1. 对专家的一致性：DeepSeek / GLM / Qwen-max / Qwen-plus
  2. 按注本语言分组：汉注（何晏、邢昺、朱熹）与日注（仁斋、徂徕）
     ——两者同为汉字文本，但后者出自日本人之手，属文体迁移。

数据源（按 no 对齐）：
    gold/gold_40.csv                   专家 gold_stance、主模型 model_stance
    out/second_coder_gold.jsonl        GLM（字段 glm_stance）
    out/second_coder_gold_qwen.jsonl   Qwen-plus（字段名沿用 glm_stance）
    out/second_coder_gold_qwenmax.jsonl Qwen-max

用法：python3 scripts/cross_family.py
"""
import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from three_family import kappa, boot, macro_f1, load_jsonl  # noqa: E402

import paths as P

ROOT = P.ROOT
GOLD = P.GOLD_CSV

CN_LAYERS = {"heyan", "shu", "zhuxi"}
JP_LAYERS = {"kogi", "cho"}

FAMILIES = [
    (f["name"], f["field"], (ROOT / f["file"]) if f["file"] else None)
    for f in json.loads((P.DATA / "families.json").read_text(encoding="utf-8"))["families"]
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--extra", action="append", default=[],
                    metavar="name=out/second_coder_gold_xxx.jsonl",
                    help="add a family that is not in data/families.json")
    a = ap.parse_args()
    fams = list(FAMILIES)
    for spec in a.extra:
        name, _, path = spec.partition("=")
        fams.append((name, "glm_stance", ROOT / path))

    rows = list(csv.DictReader(open(GOLD, encoding="utf-8-sig")))
    rows = [r for r in rows if r["gold_stance"]]
    gidx = {int(r["no"]): r for r in rows}

    # 先取所有族的公共子集：主模型覆盖 40 条 gold，外部族只跑了有 prompt 的 37 条，
    # 若各算各的 n（40 vs 37）表内不可比，故统一到交集。
    per = {}
    for name, key, path in fams:
        if path is None:
            per[name] = {n: gidx[n][key] for n in gidx}
        else:
            per[name] = {d["no"]: d[key] for d in load_jsonl(path) if d.get("ok")}
    common = set(gidx)
    for d in per.values():
        common &= set(d)
    common = sorted(common)

    res = []
    for name, key, path in fams:
        nos = common
        pred = per[name]
        layer = {n: gidx[n]["layer"] for n in nos}
        gold = [gidx[n]["gold_stance"] for n in nos]
        p = [pred[n] for n in nos]
        k, po = kappa(gold, p)
        lo, hi = boot(gold, p)
        f1 = macro_f1(gold, p)["macro"][2]
        row = {"family": name, "n": len(nos), "agree": round(po * 100, 1),
               "kappa": round(k, 3), "ci": [round(lo, 2), round(hi, 2)],
               "macro_f1": round(f1, 3)}
        for tag, keep in (("cn", CN_LAYERS), ("jp", JP_LAYERS)):
            ii = [i for i, n in enumerate(nos) if layer[n] in keep]
            g2 = [gold[i] for i in ii]
            p2 = [p[i] for i in ii]
            k2, po2 = kappa(g2, p2)
            row[tag] = {"n": len(ii), "agree": round(po2 * 100, 1),
                        "kappa": round(k2, 3)}
        res.append(row)

    hdr = f'{"族":<18}{"n":>4}{"一致%":>8}{"kappa":>8}{"95%CI":>14}{"宏F1":>8}' \
          f'{"汉注k":>8}{"日注k":>8}{"差":>7}'
    print(hdr)
    print("-" * len(hdr))
    for r in res:
        print(f'{r["family"]:<18}{r["n"]:>4}{r["agree"]:>8.1f}{r["kappa"]:>8.3f}'
              f'{str(r["ci"]):>14}{r["macro_f1"]:>8.3f}'
              f'{r["cn"]["kappa"]:>8.3f}{r["jp"]["kappa"]:>8.3f}'
              f'{r["jp"]["kappa"] - r["cn"]["kappa"]:>+7.3f}')
    print(f'\n分组条目数：汉注 {res[0]["cn"]["n"]}　日注 {res[0]["jp"]["n"]}')

    json.dump(res, open(ROOT / "out" / "cross_family.json", "w"),
              ensure_ascii=False, indent=1)
    print("写出 out/cross_family.json")


if __name__ == "__main__":
    main()
