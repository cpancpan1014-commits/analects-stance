#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""重算 TABLE II「最常被驳斥的对象」——基于七层图（network7.json）。

与旧版（edges_folded.json，421 边）的差别：旧版是五层语料时代的产物，未含
刘宝楠《正义》与朱熹《或问》。本脚本按当前 867 条高置信边重算，口径：
  · 合称（如「范吕謝尹氏」）按分隔符拆开、权重均分，保证合计仍为 867；
  · 真别名归并（朱子/朱註→朱熹，邢疏→邢昺 …）；
  · 泛称（宋儒/後儒/舊註/或曰 …）与典籍（皇疏/家語/釋文 …）不并入个人。
输出 out/table2.json 并打印可直接抄入正文的数字。
"""
import json
import re
from collections import Counter
from pathlib import Path

import paths as P

OUT = P.OUT

# 真别名 → 规范名（只并同一人/同一书的异写，不并泛称）
ALIAS = {
    "朱子": "朱熹", "朱註": "朱熹", "朱注": "朱熹", "朱氏": "朱熹",
    "程氏": "程子", "程": "程子",
    "顔師古": "顏師古", "颜师古": "顏師古", "颜注": "顏師古", "顏注": "顏師古",
    "韩愈": "韓愈", "旧注": "舊註", "舊注": "舊註",
    "何註": "何晏", "何本": "何晏", "集解": "何晏", "何晏集解": "何晏",
    "邢疏": "邢昺", "邢本": "邢昺",
    "包氏慎言": "包慎言", "王念孙": "王念孫", "王念孫": "王念孫",
    "升庵": "楊慎", "楊升庵": "楊慎",
    "太史公": "司馬遷", "史遷": "司馬遷",
    "孔安國、朱熹": "孔安國",
}

# 泛称（不指向具体个人）
COLLECTIVE = {
    "後儒", "宋儒", "先儒", "漢儒", "世儒", "世人", "世", "後人", "後世",
    "後世學", "後世心學", "舊註", "古註", "舊說", "舊解", "俗本", "俗解",
    "諸說", "諸家", "衆說", "說者", "解者", "傳者", "或曰", "或說", "或",
    "或者", "或謂", "道學先生", "諸老先生", "程朱諸先生", "宋諸老先生",
    "漢以來諸家", "舊時說者", "說尚書者", "釋氏", "禮家", "諸家說",
}

# 典籍/字书/史书（作为靶标被引而非被驳的具体人）
WORKS = {
    "皇疏", "皇本", "孔疏", "正義", "儀註", "集註", "家語", "周禮", "世本",
    "玉篇", "廣韻", "釋文", "白虎通", "史記·世家", "舊唐書", "魏書高閭傳",
    "後漢書佞幸傳贊", "公羊疏", "公羊定四年疏", "禮記疏", "曲禮", "路史",
    "明一統志", "于欽齊乘", "學齋佔堡", "路史國名紀、氏族大全", "唐石經",
    "蜀石经", "衛氏古文尚書", "东晋古文", "儀禮", "論語", "邢本、集注本",
    "皇本邢疏", "邢疏、皇疏",
}

SPLIT = re.compile(r"[、，,/及]\s*")


def fold(label: str):
    """返回 [(规范名, 权重份额)]"""
    parts = [p.strip() for p in SPLIT.split(label) if p.strip()]
    if not parts:
        return []
    w = 1.0 / len(parts)
    return [(ALIAS.get(p, p), w) for p in parts]


def kind(name: str) -> str:
    if name in COLLECTIVE:
        return "collectivity"
    if name in WORKS:
        return "work"
    if name in {"宰我", "孟子", "子貢", "子路"}:
        return "interlocutor"
    if "、" in name:
        return "compound"
    return "individual"


def main():
    d = json.loads((OUT / "network7.json").read_text(encoding="utf-8"))
    tgt = Counter()
    for k, v in d["edges"].items():
        name = k.split("->")[1]
        for n, share in fold(name):
            tgt[n] += v * share

    total = sum(tgt.values())
    ranked = tgt.most_common()
    kinds = Counter()
    for n, v in ranked:
        kinds[kind(n)] += v

    print(f"高置信边合计 {total:.0f}（应为 867）")
    print(f"靶标标签 {len(ranked)} 个")
    print("\n类型构成：")
    for k, v in kinds.most_common():
        print(f"  {k:14} {v:7.1f}  {v/total*100:5.1f}%")

    print("\n前 12 名：")
    top = ranked[:12]
    for i, (n, v) in enumerate(top, 1):
        print(f"  {i:2d}. {n:12} {v:7.1f}  {v/total*100:5.1f}%  [{kind(n)}]")
    rest = total - sum(v for _, v in top)
    print(f"  其余 {len(ranked)-len(top)} 个靶标：{rest:.1f}（{rest/total*100:.1f}%）")

    json.dump({"total": round(total), "ranked": [(n, round(v, 1)) for n, v in ranked],
               "kinds": {k: round(v, 1) for k, v in kinds.items()}},
              open(OUT / "table2.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("\n已写入 out/table2.json")


if __name__ == "__main__":
    main()
