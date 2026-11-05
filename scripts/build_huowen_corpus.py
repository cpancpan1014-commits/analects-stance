#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""《四書或問·論語或問》语料构建。

底本：ctext.org《四書或問》三十九卷（《欽定四庫全書》本），
      卷06–25 为《論語或問》二十篇，卷26 起转入《孟子或問》，故舍。
源：raw/huowen/NN.html（NN = 卷次 06..25）

与《論語正義》不同，本卷天然近似「一章一段」：
每卷首 2 行是「欽定四庫全書」「宋朱子撰」，第 3 行是篇名（如「學而第一凡十六章」），
其后每行一段，段首多为「或問」。

但段数与章数并非严格相等（公冶長少 1、雍也多 1），因此**不按序号硬对齐**：
以篇为容器、以段为抽取单元，另用经文重叠度为每段推测所对应的章，仅作参考字段，
不参与任何统计。这样既不伪造对齐，也保留后续章级分析的余地。

输出 out/huowen_corpus.jsonl，每行：
  {chapter, pian_no, pian, vol, seg_no, text, n_chars, guess_chapter, guess_sim}
"""
import json
import re
import unicodedata
from html import unescape
from pathlib import Path

import paths as P

BASE = P.ROOT
RAW = P.RAW / "huowen"
OUT = P.CORPUS_HUOWEN
CORPUS = P.CORPUS

# 卷次 -> 篇序（卷06 起为学而）
VOL2PIAN = {v: v - 5 for v in range(6, 26)}

PIAN_RE = re.compile(r"^(.{2,4})第([一二三四五六七八九十]+)凡(.+?)章$")
# 四库本缺字标记，如「●缺字：2962」，整段剔除该记号但保留前后文
MISSING = re.compile(r"[●○]缺字[：:]\s*\d+")


def rows_of(html_text):
    """正文在 <tr class="result"> 的最后一个 td.ctext 里。"""
    out = []
    for m in re.finditer(r'<tr class="result"[^>]*>(.*?)</tr>', html_text, re.S):
        tds = re.findall(r'<td class="ctext"[^>]*>(.*?)</td>', m.group(1), re.S)
        if not tds:
            continue
        s = unescape(re.sub(r"<[^>]+>", "", tds[-1]))
        s = s.replace("\u3000", "").strip()
        if s:
            out.append(s)
    return out


def clean_seg(s):
    s = MISSING.sub("", s)
    s = re.sub(r"[\s\u3000]+", "", s)
    return s.strip()


def keystream(s):
    """比对用：只留汉字。"""
    return "".join(ch for ch in s if "\u4e00" <= ch <= "\u9fff")


CN_NUM = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8,
          "九": 9, "十": 10, "百": 100}
# 朱子原文常在段首自标章次：「或問十六章之說曰…」「或問九章之說曰…」
SELF_NUM = re.compile(r"^或問([一二三四五六七八九十百]+)章")


def cn2int(s):
    """中文数字转整数，覆盖 1–99（本书章次不超过 47）。"""
    if not s:
        return None
    if "百" in s:
        return None
    if "十" not in s:
        return CN_NUM.get(s) if len(s) == 1 else None
    a, _, b = s.partition("十")
    tens = CN_NUM.get(a, 0) if a else 1
    ones = CN_NUM.get(b, 0) if b else 0
    if (a and a not in CN_NUM) or (b and b not in CN_NUM):
        return None
    return tens * 10 + ones


def declare(seg, pian_no, pool):
    """（一）段首自标章次 → 直接采用；（二）否则按经文重叠度取最相近的一章。
    返回 (chapter_id, 依据)，依据 ∈ {'self-num','overlap',None}。"""
    m = SELF_NUM.match(seg)
    if m:
        n = cn2int(m.group(1))
        if n:
            return f"{pian_no:02d}-{n:02d}", "self-num"
    if not pool:
        return None, None
    head = set(keystream(seg)[:100])
    best, bs = None, 0.0
    for ch_id, jing in pool:
        js = set(keystream(jing))
        if not js:
            continue
        r = len(head & js) / len(js)
        if r > bs:
            best, bs = ch_id, r
    if bs >= 0.5:
        return best, "overlap"
    return None, None


def main():
    books = {}
    for vol in sorted(VOL2PIAN):
        f = RAW / f"{vol:02d}.html"
        if not f.exists():
            print(f"缺 卷{vol:02d}")
            continue
        rs = [clean_seg(x) for x in rows_of(f.read_text(encoding="utf-8", errors="replace"))]
        rs = [x for x in rs if x]
        # 去掉卷首 "欽定四庫全書" / "宋朱子撰"
        rs = [x for x in rs if not x.startswith("欽定四庫") and not re.match(r"^宋.{0,3}朱子", x)]
        if not rs:
            print(f"卷{vol:02d} 空")
            continue
        m = PIAN_RE.match(rs[0])
        if not m:
            print(f"卷{vol:02d} 篇名未识别：{rs[0][:30]}")
            pian = f"卷{vol:02d}"
        else:
            pian = m.group(1)
        segs = rs[1:]
        # 段末会混入「四書或問卷八」这类卷尾标记，非正文，剔除
        segs = [x for x in segs if not re.fullmatch(r"四書或問卷[一二三四五六七八九十]+", x)]
        books[VOL2PIAN[vol]] = {"vol": vol, "pian": pian, "segs": segs}
        print(f"卷{vol:02d} → 篇{VOL2PIAN[vol]:02d} {pian:6} 段 {len(segs):3}")

    # 经文池：按篇
    jing = {}
    for line in open(CORPUS, encoding="utf-8"):
        r = json.loads(line)
        jing.setdefault(r["pian_no"], []).append((r["chapter"], r.get("jing") or ""))

    out = []
    for pian_no in sorted(books):
        b = books[pian_no]
        pool = jing.get(pian_no, [])
        for k, seg in enumerate(b["segs"], 1):
            gc, how = declare(seg, pian_no, pool)
            out.append({
                "chapter": f"{pian_no:02d}-{k:02d}",
                "pian_no": pian_no,
                "pian": b["pian"],
                "vol": b["vol"],
                "seg_no": k,
                "text": seg,
                "n_chars": len(keystream(seg)),
                "declared_chapter": gc,
                "align_by": how,
            })

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        for r in out:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    tot = sum(r["n_chars"] for r in out)
    print(f"\n{len(out)} 段，{tot:,} 汉字 → {OUT.relative_to(BASE)}")
    import statistics
    L = [r["n_chars"] for r in out]
    print(f"段长 中位 {statistics.median(L):.0f} 最长 {max(L)} 最短 {min(L)}")
    n_self = sum(1 for r in out if r["align_by"] == "self-num")
    n_ov = sum(1 for r in out if r["align_by"] == "overlap")
    print(f"章归属：自标章次 {n_self} / 经文重叠 {n_ov} / 未定 {len(out)-n_self-n_ov}")


if __name__ == "__main__":
    main()
