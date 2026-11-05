#!/usr/bin/env python3
"""把「中华典藏」站的《论语正义》全文，对齐到既有五层语料的 501 章结构。

对齐难点与对策：
  1. 站点把何晏《集解》以 `【〔注〕…】` 形式插在经文中间，经文因此被切断。
     对策：只取 `【】` 之外的部分拼成「经文流」，该流即全书经文的连续序列。
  2. 站点文本简繁混杂，且有异体字（愼/慎、囘/回、褅/禘、吿/告、漆彤/漆雕）。
     对策：OpenCC t2s + 手工异体表，再逐章用经文前缀在流中单调定位。
  3. 少数章经文起句与站点不同（如 03-21 站点从「宰我对曰」起），前缀必失败。
     对策：降级到 difflib 最长公共块，阈值 6 字。

输出 out/liu_corpus.jsonl：{"chapter", "pian_no", "text", "n_paras", "offset"}
其中 text 已剥去 `【】` 内的集解注——那是何晏层的文字，留在里面会被误判为刘宝楠的主张。
"""
import html
import json
import re
import sys
from bisect import bisect_right
from difflib import SequenceMatcher
from pathlib import Path

from opencc import OpenCC

import paths as P

ROOT = P.ROOT
RAW = P.RAW / "liu_zhengyi"
CORPUS = P.CORPUS
OUT = P.CORPUS_LIU

JUAN2PIAN = {
    1: 1, 2: 2, 3: 3, 4: 3, 5: 4, 6: 5, 7: 6, 8: 7, 9: 8, 10: 9,
    11: 10, 12: 10, 13: 10, 14: 11, 15: 12, 16: 13, 17: 14, 18: 15,
    19: 16, 20: 17, 21: 18, 22: 19, 23: 20,
}

CC = OpenCC("t2s")
KEEP = re.compile(r"[^\u4e00-\u9fff]")
NOTE = re.compile(r"【[^】]*】")
PINYIN = re.compile(r"\[\s*[\wāáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜ]+\s*\]")

# 语料自身的经文残缺，对齐前先补：01-12 的 jing 字段为空（原文仅「有子曰：「」」）
JING_FIX = {
    "01-12": "有子曰：「禮之用，和爲貴。先王之道，斯爲美，小大由之。有所不行，"
             "知和而和，不以禮節之，亦不可行也。」",
}

# 对齐专用异体归并（不改动正文，只用于定位）
VARIANT = str.maketrans({
    "愼": "慎", "囘": "回", "褅": "禘", "吿": "告", "彫": "雕", "汎": "泛",
    "惟": "唯", "於": "于", "彊": "强", "脩": "修", "徧": "遍", "敍": "叙",
    "覈": "核", "譌": "讹", "竝": "并", "羣": "群", "峯": "峰", "牀": "床",
    "畧": "略", "歎": "叹", "塚": "冢", "衹": "只", "廼": "乃", "邨": "村",
})


def norm(s: str) -> str:
    """定位用的归一化：简繁归一 + 异体归并 + 只留汉字。"""
    return KEEP.sub("", CC.convert(s).translate(VARIANT))


def page_paras(path: Path):
    h = path.read_text(encoding="utf-8", errors="replace")
    m = re.search(r'<div[^>]*id="content"[^>]*>(.*?)</div>\s*<', h, re.S)
    body = m.group(1) if m else h
    out = []
    for p in re.findall(r"<p[^>]*>(.*?)</p>", body, re.S):
        t = html.unescape(re.sub(r"<[^>]+>", "", p)).strip()
        t = PINYIN.sub("", t)
        if t:
            out.append(t)
    return out


def locate(key: str, stream: str, ptr: int):
    """在 stream 中从 ptr 起定位本章起点；返回偏移或 None。"""
    for k in (16, 12, 10, 8, 6):
        if len(key) >= k:
            i = stream.find(key[:k], ptr)
            if i >= 0:
                return i
    win = stream[ptr:ptr + 800]
    if not win:
        return None
    m = SequenceMatcher(None, key[:40], win, autojunk=False).find_longest_match(
        0, min(40, len(key)), 0, len(win))
    if m.size >= 6:
        return max(ptr, ptr + m.b - m.a)
    return None


def main():
    books = {}
    for juan, pian in JUAN2PIAN.items():
        books.setdefault(pian, []).extend(page_paras(RAW / f"{juan:02d}.html"))

    rows = [json.loads(l) for l in CORPUS.open(encoding="utf-8")]
    by_pian = {}
    for r in rows:
        by_pian.setdefault(r["pian_no"], []).append(r)

    out, misses, fuzzy = [], [], []
    for pian in sorted(by_pian):
        chapters = sorted(by_pian[pian], key=lambda r: r["no"])
        paras = books.get(pian, [])

        # 经文流：只取【】之外的部分，并记下每个字符位置落在哪一段
        parts, cum = [], []
        c = 0
        for pi, para in enumerate(paras):
            for seg in re.split(r"(【[^】]*】)", para):
                if not seg or seg.startswith("【"):
                    continue
                n = norm(seg)
                if not n:
                    continue
                parts.append(n)
                cum.append((c, pi))
                c += len(n)
        stream = "".join(parts)
        starts = [x[0] for x in cum]

        def para_at(off):
            i = bisect_right(starts, off) - 1
            return cum[max(0, i)][1]

        ptr, bounds = 0, []
        for r in chapters:
            key = norm(JING_FIX.get(r["chapter"], r["jing"]))
            pos = locate(key, stream, ptr)
            if pos is None:
                misses.append(r["chapter"])
                bounds.append(None)
                continue
            if pos > ptr + 3:
                fuzzy.append(r["chapter"])
            bounds.append(pos)
            ptr = max(ptr, pos)

        # 二次补偿：在前后已知位置的留白区间内，用更短前缀 / 差分重搜
        for i, b in enumerate(bounds):
            if b is not None:
                continue
            key = norm(JING_FIX.get(chapters[i]["chapter"], chapters[i]["jing"]))
            lo = next((bounds[j] for j in range(i - 1, -1, -1) if bounds[j] is not None), 0)
            hi = next((bounds[j] for j in range(i + 1, len(bounds))
                       if bounds[j] is not None), len(stream))
            if hi <= lo:
                continue
            gap = stream[lo:hi]
            hit = -1
            for k in (10, 8, 6, 5, 4):
                if len(key) >= k:
                    hit = gap.find(key[:k])
                    if hit >= 0:
                        break
            if hit < 0 and len(key) >= 4:
                m = SequenceMatcher(None, key, gap, autojunk=False).find_longest_match(
                    0, len(key), 0, len(gap))
                if m.size >= 5:
                    hit = max(0, m.b - m.a)
            if hit >= 0:
                bounds[i] = lo + hit
                if chapters[i]["chapter"] in misses:
                    misses.remove(chapters[i]["chapter"])

        pidx = [None if b is None else para_at(b) for b in bounds]
        for i, r in enumerate(chapters):
            if pidx[i] is None:
                out.append({"chapter": r["chapter"], "pian_no": pian,
                            "text": "", "n_paras": 0, "offset": -1})
                continue
            nxt = next((p for p in pidx[i + 1:] if p is not None), len(paras))
            seg = paras[pidx[i]:max(nxt, pidx[i] + 1)]
            text = "\n".join(NOTE.sub("", s).strip() for s in seg)
            # 卷题（如「乡党第十（中）」）会落到上一章末尾，剔掉
            text = re.sub(r"(?m)^\s*.{1,4}第[一二三四五六七八九十]+[（(]?[上中下]?[）)]?\s*$",
                          "", text)
            text = re.sub(r"\n{2,}", "\n", text).strip()
            out.append({"chapter": r["chapter"], "pian_no": pian,
                        "text": text, "n_paras": len(seg),
                        "offset": bounds[i]})

    out.sort(key=lambda x: x["chapter"])
    with OUT.open("w", encoding="utf-8") as f:
        for r in out:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    tot = sum(len(r["text"]) for r in out)
    empty = [r["chapter"] for r in out if len(r["text"]) < 30]
    print(f"章数 {len(out)}  总字数 {tot:,}  平均 {tot/len(out):.0f} 字/章")
    print(f"未定位 {len(misses)} 章: {misses[:15]}")
    print(f"走差分兜底 {len(fuzzy)} 章")
    print(f"近空 {len(empty)} 章: {empty[:15]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
